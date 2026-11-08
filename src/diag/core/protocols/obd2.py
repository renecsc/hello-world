"""Codificación y decodificación de mensajes OBD2 (SAE J1979 / ISO 15031-5).

Funciones **puras**: reciben y devuelven bytes, sin E/S. Las usan tanto el cliente OBD2
(que habla con un adaptador real) como el simulador (que responde como una ECU), para que
ambos lados compartan exactamente la misma interpretación de la norma.

Formato de los mensajes, ya sin segmentar (el adaptador se ocupa de ISO-TP):

- Petición servicio 01: ``01 PID [PID ...]`` (hasta 6 PIDs sobre CAN).
- Respuesta servicio 01: ``41 PID datos [PID datos ...]``.
- Petición servicio 02: ``02 PID FRAME``. Respuesta: ``42 PID FRAME datos``.
- Respuesta servicios 03/07/0A: ``43 [N] DTC1 DTC2 ...`` (``N`` = cantidad, solo sobre CAN).
- Respuesta servicio 09/02 (VIN) sobre CAN: ``49 02 01`` + 17 caracteres ASCII.
- Respuesta negativa: ``7F SID NRC``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from diag.core.protocols.constants import (
    DTC_BYTES,
    DTC_SYSTEM_LETTERS,
    FREEZE_FRAME_DTC_PID,
    MAX_PIDS_PER_REQUEST_CAN,
    NEGATIVE_RESPONSE_SID,
    PID_SUPPORT_BYTES,
    PID_SUPPORT_RANGE,
    POSITIVE_RESPONSE_OFFSET,
    VIN_DATA_ITEMS,
    VIN_INFOTYPE,
    VIN_LENGTH,
    Obd2Service,
)

_BITS_PER_BYTE = 8
# Caracteres ASCII imprimibles sin espacio: rango válido para un VIN (ISO 3779).
_ASCII_FIRST_VISIBLE, _ASCII_LAST_VISIBLE = 0x21, 0x7E
_DTC_CODE_LENGTH = 5  # Letra + 4 dígitos hexadecimales, p. ej. "P0301" (SAE J2012)


class ProtocolError(ValueError):
    """Mensaje mal formado o inesperado para el servicio consultado."""


# --- Utilidades generales -------------------------------------------------------------------


def response_sid(service: int) -> int:
    """SID de la respuesta positiva a ``service`` (``servicio + 0x40``)."""
    return service + POSITIVE_RESPONSE_OFFSET


def negative_response_code(payload: bytes, service: int) -> int | None:
    """Si ``payload`` es una respuesta negativa a ``service``, devuelve su NRC.

    Returns:
        El código NRC (ISO 14229-1, Anexo A) o ``None`` si no es respuesta negativa.
    """
    if len(payload) >= 3 and payload[0] == NEGATIVE_RESPONSE_SID and payload[1] == service:
        return payload[2]
    return None


def _expect_sid(payload: bytes, service: int) -> None:
    """Comprueba que ``payload`` sea respuesta positiva a ``service``."""
    if not payload:
        raise ProtocolError("Respuesta vacía.")
    expected = response_sid(service)
    if payload[0] != expected:
        raise ProtocolError(
            f"Se esperaba SID {expected:02X} y llegó {payload[0]:02X} ({payload.hex(' ')})."
        )


# --- Servicio 01: datos actuales ------------------------------------------------------------


def build_current_data_request(pids: Sequence[int]) -> bytes:
    """Construye una petición del servicio 01.

    Args:
        pids: Entre 1 y 6 PIDs (SAE J1979 §6.1.2).

    Raises:
        ValueError: Si la cantidad de PIDs está fuera de rango o algún PID no cabe en 1 byte.
    """
    if not 1 <= len(pids) <= MAX_PIDS_PER_REQUEST_CAN:
        raise ValueError(f"Una petición admite de 1 a {MAX_PIDS_PER_REQUEST_CAN} PIDs.")
    return bytes([Obd2Service.CURRENT_DATA, *pids])


def parse_current_data_response(
    payload: bytes, data_lengths: Mapping[int, int]
) -> dict[int, bytes]:
    """Separa una respuesta (posiblemente multi-PID) del servicio 01.

    Args:
        payload: Respuesta completa, empezando por ``41``.
        data_lengths: Bytes de datos de cada PID conocido (de ``pids.yaml``). Es
            imprescindible: el mensaje no indica dónde termina cada PID.

    Returns:
        Datos crudos de cada PID presente en la respuesta.

    Raises:
        ProtocolError: Si el SID es incorrecto, aparece un PID desconocido o faltan bytes.
    """
    _expect_sid(payload, Obd2Service.CURRENT_DATA)
    result: dict[int, bytes] = {}
    position = 1
    while position < len(payload):
        pid = payload[position]
        length = data_lengths.get(pid, PID_SUPPORT_BYTES if is_support_pid(pid) else None)
        if length is None:
            raise ProtocolError(f"PID {pid:02X} sin longitud conocida; no se puede separar.")
        start, end = position + 1, position + 1 + length
        if end > len(payload):
            raise ProtocolError(f"Faltan bytes para el PID {pid:02X} ({payload.hex(' ')}).")
        result[pid] = payload[start:end]
        position = end
    return result


def build_current_data_response(values: Mapping[int, bytes]) -> bytes:
    """Construye una respuesta del servicio 01 (uso del simulador)."""
    body = b"".join(bytes([pid]) + data for pid, data in values.items())
    return bytes([response_sid(Obd2Service.CURRENT_DATA)]) + body


# --- PIDs de soporte (00, 20, 40, ...) ------------------------------------------------------


def is_support_pid(pid: int) -> bool:
    """``True`` si ``pid`` es un PID de soporte (00, 20, 40, ..., E0)."""
    return pid % PID_SUPPORT_RANGE == 0


def decode_supported_pids(support_pid: int, mask: bytes) -> set[int]:
    """Decodifica la máscara de 32 bits de un PID de soporte.

    El bit más significativo del primer byte corresponde a ``support_pid + 1`` y el menos
    significativo del cuarto a ``support_pid + 0x20`` (que indica si existe el siguiente
    rango). SAE J1979 Anexo A.

    Raises:
        ProtocolError: Si la máscara no tiene 4 bytes.
    """
    if len(mask) != PID_SUPPORT_BYTES:
        raise ProtocolError(f"Máscara de soporte de {len(mask)} bytes; se esperaban 4.")
    value = int.from_bytes(mask, "big")
    total_bits = PID_SUPPORT_BYTES * _BITS_PER_BYTE
    return {
        support_pid + offset + 1
        for offset in range(total_bits)
        if value & (1 << (total_bits - 1 - offset))
    }


def encode_supported_pids(support_pid: int, supported: Iterable[int]) -> bytes:
    """Construye la máscara de 32 bits de un PID de soporte (uso del simulador).

    Incluye automáticamente el bit del siguiente PID de soporte si hay PIDs soportados
    más allá de este rango.
    """
    supported = set(supported)
    total_bits = PID_SUPPORT_BYTES * _BITS_PER_BYTE
    value = 0
    for offset in range(total_bits):
        pid = support_pid + offset + 1
        is_next_range = offset == total_bits - 1
        if pid in supported or (is_next_range and any(p > pid for p in supported)):
            value |= 1 << (total_bits - 1 - offset)
    return value.to_bytes(PID_SUPPORT_BYTES, "big")


# --- Servicios 03 / 07 / 0A: códigos de avería ----------------------------------------------


def decode_dtc(raw: bytes) -> str:
    """Convierte 2 bytes en un código SAE J2012 (p. ej. ``01 33`` → ``P0133``).

    Bits 15-14: sistema (P/C/B/U). Bits 13-12: primer dígito (0-3). Resto: 3 dígitos hex.

    Raises:
        ProtocolError: Si ``raw`` no tiene 2 bytes.
    """
    if len(raw) != DTC_BYTES:
        raise ProtocolError(f"Un DTC ocupa {DTC_BYTES} bytes, llegaron {len(raw)}.")
    letter = DTC_SYSTEM_LETTERS[raw[0] >> 6]
    first_digit = (raw[0] >> 4) & 0x03
    return f"{letter}{first_digit}{raw[0] & 0x0F:X}{raw[1]:02X}"


def encode_dtc(code: str) -> bytes:
    """Convierte un código SAE J2012 en sus 2 bytes (inversa de :func:`decode_dtc`).

    Raises:
        ValueError: Si el código no tiene el formato ``[PCBU][0-3][0-9A-F]{3}``.
    """
    code = code.strip().upper()
    if len(code) != _DTC_CODE_LENGTH or code[0] not in DTC_SYSTEM_LETTERS or code[1] not in "0123":
        raise ValueError(f"Código DTC inválido: '{code}'.")
    try:
        low = int(code[2:], 16)
    except ValueError:
        raise ValueError(f"Código DTC inválido: '{code}'.") from None
    high = (DTC_SYSTEM_LETTERS.index(code[0]) << 6) | (int(code[1]) << 4) | (low >> 8)
    return bytes([high, low & 0xFF])


def parse_dtc_response(payload: bytes, service: int, *, has_count_byte: bool) -> list[str]:
    """Decodifica la respuesta a un servicio 03, 07 o 0A.

    Args:
        payload: Respuesta completa (``43 ...``, ``47 ...`` o ``4A ...``).
        service: Servicio consultado.
        has_count_byte: ``True`` sobre CAN, donde el 2.º byte es la cantidad de DTCs.

    Returns:
        Códigos en formato SAE J2012. Se descartan los rellenos ``00 00``.

    Raises:
        ProtocolError: Si el mensaje está mal formado.
    """
    _expect_sid(payload, service)
    body = payload[1:]
    if has_count_byte:
        if not body:
            raise ProtocolError("Falta el byte de cantidad de DTCs.")
        count, body = body[0], body[1:]
        if len(body) < count * DTC_BYTES:
            raise ProtocolError(f"Se anunciaron {count} DTCs pero faltan bytes.")
        body = body[: count * DTC_BYTES]
    if len(body) % DTC_BYTES:
        raise ProtocolError(f"Longitud de DTCs impar ({payload.hex(' ')}).")
    pairs = (body[i : i + DTC_BYTES] for i in range(0, len(body), DTC_BYTES))
    return [decode_dtc(pair) for pair in pairs if pair != b"\x00\x00"]


def build_dtc_response(service: int, codes: Sequence[str], *, has_count_byte: bool) -> bytes:
    """Construye una respuesta a un servicio 03/07/0A (uso del simulador)."""
    count = bytes([len(codes)]) if has_count_byte else b""
    return bytes([response_sid(service)]) + count + b"".join(encode_dtc(c) for c in codes)


# --- Servicio 02: freeze frame --------------------------------------------------------------


def build_freeze_frame_request(pid: int, frame: int = 0) -> bytes:
    """Petición del servicio 02 para un PID de un freeze frame (``02 PID FRAME``)."""
    return bytes([Obd2Service.FREEZE_FRAME, pid, frame])


def parse_freeze_frame_response(
    payload: bytes, data_lengths: Mapping[int, int]
) -> tuple[int, int, bytes]:
    """Decodifica ``42 PID FRAME datos``.

    El PID 02 (DTC que originó el freeze frame) tiene longitud fija de 2 bytes.

    Returns:
        ``(pid, frame, datos)``.

    Raises:
        ProtocolError: Si el mensaje está mal formado o el PID es desconocido.
    """
    _expect_sid(payload, Obd2Service.FREEZE_FRAME)
    if len(payload) < 3:
        raise ProtocolError(f"Respuesta de freeze frame demasiado corta ({payload.hex(' ')}).")
    pid, frame = payload[1], payload[2]
    length = DTC_BYTES if pid == FREEZE_FRAME_DTC_PID else data_lengths.get(pid)
    if length is None and is_support_pid(pid):
        length = PID_SUPPORT_BYTES
    if length is None:
        raise ProtocolError(f"PID {pid:02X} sin longitud conocida.")
    data = payload[3 : 3 + length]
    if len(data) != length:
        raise ProtocolError(f"Faltan bytes para el PID {pid:02X} del freeze frame.")
    return pid, frame, data


def build_freeze_frame_response(pid: int, frame: int, data: bytes) -> bytes:
    """Construye ``42 PID FRAME datos`` (uso del simulador)."""
    return bytes([response_sid(Obd2Service.FREEZE_FRAME), pid, frame]) + data


# --- Servicio 09: VIN -----------------------------------------------------------------------


def build_vin_request() -> bytes:
    """Petición del VIN: ``09 02``."""
    return bytes([Obd2Service.VEHICLE_INFO, VIN_INFOTYPE])


def parse_vin_response(payload: bytes) -> str:
    """Extrae el VIN de ``49 02 NODI <17 ASCII>`` (formato CAN, SAE J1979 §6.9).

    Se toman los últimos 17 bytes, lo que tolera rellenos iniciales que algunos
    adaptadores o ECUs agregan.

    Raises:
        ProtocolError: Si el mensaje no corresponde o el VIN no es ASCII imprimible.
    """
    _expect_sid(payload, Obd2Service.VEHICLE_INFO)
    if len(payload) < 2 or payload[1] != VIN_INFOTYPE:
        raise ProtocolError(f"No es una respuesta de VIN ({payload.hex(' ')}).")
    raw = payload[-VIN_LENGTH:]
    if len(payload) < 3 + VIN_LENGTH or not all(
        _ASCII_FIRST_VISIBLE <= b <= _ASCII_LAST_VISIBLE for b in raw
    ):
        raise ProtocolError(f"VIN inválido ({payload.hex(' ')}).")
    return raw.decode("ascii")


def build_vin_response(vin: str) -> bytes:
    """Construye ``49 02 01 <VIN>`` (uso del simulador).

    Raises:
        ValueError: Si el VIN no tiene 17 caracteres ASCII.
    """
    if len(vin) != VIN_LENGTH or not vin.isascii():
        raise ValueError(f"El VIN debe tener {VIN_LENGTH} caracteres ASCII.")
    return (
        bytes([response_sid(Obd2Service.VEHICLE_INFO), VIN_INFOTYPE, VIN_DATA_ITEMS]) + vin.encode()
    )


# --- Servicio 04: borrado -------------------------------------------------------------------


def build_clear_dtc_request() -> bytes:
    """Petición de borrado de DTCs: ``04``."""
    return bytes([Obd2Service.CLEAR_DTC])


def is_clear_dtc_confirmation(payload: bytes) -> bool:
    """``True`` si ``payload`` confirma el borrado (``44``)."""
    return payload[:1] == bytes([response_sid(Obd2Service.CLEAR_DTC)])
