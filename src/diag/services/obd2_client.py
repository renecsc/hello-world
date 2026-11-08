"""Cliente OBD2 genérico: casos de uso sobre cualquier ``Adapter`` (RU-02, RU-10, RU-40, RU-41).

Orquesta peticiones y respuestas usando las funciones puras de
:mod:`diag.core.protocols.obd2` y las definiciones de ``pids.yaml``. No sabe si del otro
lado hay un ELM327, un adaptador CAN o el simulador.

Direccionamiento: el descubrimiento se hace con peticiones **funcionales** (todas las ECUs
OBD contestan); el resto, con peticiones **físicas** a la ECU que soporta cada dato, para
no cargar el bus con respuestas duplicadas. La dirección física se deriva de la de
respuesta según ISO 15765-4 (CAN 11 bits). El direccionamiento de 29 bits se agregará con
UDS (fase 3).

Robustez: una respuesta mal formada de una ECU se registra en el log y se descarta; no
interrumpe la lectura del resto (importante en una adquisición continua).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable, Sequence
from typing import Final

from diag.core.decoding.signals import decode_pid
from diag.core.definitions.loader import PidCatalog
from diag.core.domain.models import (
    DiagRequest,
    DiagResponse,
    Dtc,
    DtcKind,
    EcuAddress,
    FreezeFrame,
    Sample,
    VehicleInfo,
)
from diag.core.ports.adapter import Adapter, AdapterInfo
from diag.core.protocols import obd2
from diag.core.protocols.constants import (
    CAN_RESPONSE_OFFSET_11BIT,
    FREEZE_FRAME_DTC_PID,
    LAST_SUPPORT_PID,
    MAX_PIDS_PER_REQUEST_CAN,
    PID_SUPPORT_RANGE,
    Obd2Service,
)

logger = logging.getLogger(__name__)

#: Servicio OBD2 que se usa para leer cada tipo de DTC (SAE J1979).
DTC_SERVICES: Final = {
    DtcKind.STORED: Obd2Service.STORED_DTC,
    DtcKind.PENDING: Obd2Service.PENDING_DTC,
    DtcKind.PERMANENT: Obd2Service.PERMANENT_DTC,
}

#: Código que indica "sin DTC" en el PID 02 del freeze frame.
_NO_DTC: Final = "P0000"


class NotConnectedError(RuntimeError):
    """Se intentó usar el cliente antes de :meth:`Obd2Client.connect`."""


class Obd2Client:
    """Cliente OBD2 genérico.

    Args:
        adapter: Cualquier implementación del puerto ``Adapter``.
        pids: Catálogo de PIDs (``pids.yaml``).
        clock: Reloj monotónico en segundos para las marcas de tiempo (RS-21).
        max_pids_per_request: PIDs por petición del servicio 01. Algunos adaptadores o ECUs
            antiguas solo aceptan 1; se configura, no se fija en el código.
    """

    def __init__(
        self,
        adapter: Adapter,
        pids: PidCatalog,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_pids_per_request: int = MAX_PIDS_PER_REQUEST_CAN,
    ) -> None:
        if not 1 <= max_pids_per_request <= MAX_PIDS_PER_REQUEST_CAN:
            raise ValueError(
                f"max_pids_per_request debe estar entre 1 y {MAX_PIDS_PER_REQUEST_CAN}."
            )
        self._adapter = adapter
        self._pids = pids
        self._clock = clock
        self._chunk = max_pids_per_request
        self._info: AdapterInfo | None = None
        self._supported: dict[int, set[int]] = {}

    # --- Conexión e identificación -------------------------------------------------------

    async def connect(self) -> VehicleInfo:
        """Conecta, descubre las ECUs y sus PIDs soportados, y lee el VIN (RU-02).

        Returns:
            Identificación del vehículo.

        Raises:
            ConnectionError: Si el adaptador no conecta.
        """
        self._info = await self._adapter.connect()
        self._supported = await self._discover_supported_pids()
        vin = await self.read_vin()
        logger.info(
            "Conectado: %s, ECUs %s, VIN %s",
            self._info.protocol,
            [f"{e:03X}" for e in self._supported],
            vin,
        )
        return VehicleInfo(vin=vin, ecus=tuple(self._supported), protocol=self._info.protocol)

    async def disconnect(self) -> None:
        """Desconecta el adaptador."""
        await self._adapter.disconnect()
        self._info = None

    async def read_vin(self) -> str | None:
        """Lee el VIN (servicio 09/02). ``None`` si ninguna ECU lo entrega."""
        for response in await self._send(DiagRequest(obd2.build_vin_request())):
            try:
                return obd2.parse_vin_response(response.payload)
            except obd2.ProtocolError as exc:
                self._discard(response, exc)
        return None

    async def _discover_supported_pids(self) -> dict[int, set[int]]:
        """Recorre los PIDs de soporte (00, 20, 40...) mientras alguna ECU indique más rangos."""
        supported: dict[int, set[int]] = {}
        support_pid = 0
        while support_pid <= LAST_SUPPORT_PID:
            request = DiagRequest(obd2.build_current_data_request([support_pid]))
            for response in await self._send(request):
                try:
                    data = obd2.parse_current_data_response(response.payload, {})
                    mask = data[support_pid]
                    supported.setdefault(response.source_id, set()).update(
                        obd2.decode_supported_pids(support_pid, mask)
                    )
                except (obd2.ProtocolError, KeyError) as exc:
                    self._discard(response, exc)
            next_range = support_pid + PID_SUPPORT_RANGE
            if not any(next_range in pids for pids in supported.values()):
                break
            support_pid = next_range
        return dict(sorted(supported.items()))

    # --- Datos en vivo ------------------------------------------------------------------

    def supported_signals(self) -> dict[str, int]:
        """Señales disponibles en el vehículo y la ECU que entrega cada una (RU-10).

        Solo incluye señales definidas en ``pids.yaml``. Si varias ECUs soportan el mismo
        PID se usa la de menor identificador (normalmente el ECM).

        Returns:
            ``{clave_señal: id_respuesta_ecu}``, en el orden de ``pids.yaml``.
        """
        result: dict[str, int] = {}
        for spec in self._pids.pids:
            source = next((ecu for ecu, pids in self._supported.items() if spec.pid in pids), None)
            if source is not None:
                for signal in spec.signals:
                    result[signal.key] = source
        return result

    async def read_signals(self, keys: Iterable[str]) -> list[Sample]:
        """Lee el valor actual de las señales indicadas.

        Agrupa las señales por ECU y empaqueta varios PIDs por petición. Una señal de un PID
        con varias señales (p. ej. sonda O2) se obtiene "gratis" al leer cualquiera de ellas,
        pero solo se devuelven las pedidas.

        Raises:
            KeyError: Si alguna señal no existe o el vehículo no la soporta.
            NotConnectedError: Si no hay conexión.
        """
        self._require_connection()
        wanted = list(dict.fromkeys(keys))
        available = self.supported_signals()
        by_ecu: dict[int, list[int]] = {}
        for key in wanted:
            if key not in available:
                raise KeyError(f"Señal no soportada por el vehículo: '{key}'.")
            pid = self._pids.signal(key)[0].pid
            pids = by_ecu.setdefault(available[key], [])
            if pid not in pids:
                pids.append(pid)

        wanted_set = set(wanted)
        lengths = self._pids.data_lengths()
        samples: list[Sample] = []
        for ecu, pids in by_ecu.items():
            for chunk in _chunks(pids, self._chunk):
                request = DiagRequest(obd2.build_current_data_request(chunk), _address(ecu))
                for response in await self._send(request):
                    samples.extend(self._decode_samples(response, lengths, wanted_set))
        return samples

    def _decode_samples(
        self, response: DiagResponse, lengths: dict[int, int], wanted: set[str]
    ) -> list[Sample]:
        """Decodifica una respuesta del servicio 01 en muestras de las señales pedidas."""
        if obd2.negative_response_code(response.payload, Obd2Service.CURRENT_DATA) is not None:
            logger.debug(
                "ECU %03X: respuesta negativa %s", response.source_id, response.payload.hex()
            )
            return []
        try:
            data = obd2.parse_current_data_response(response.payload, lengths)
        except obd2.ProtocolError as exc:
            self._discard(response, exc)
            return []
        t = self._clock()
        samples = []
        for pid, raw in data.items():
            spec = self._pids.pid(pid)
            if spec is None:
                continue
            for key, value in decode_pid(spec, raw).items():
                if key in wanted:
                    unit = self._pids.signal(key)[1].unit
                    samples.append(Sample(key, value, unit, t, response.source_id))
        return samples

    # --- Códigos de avería ----------------------------------------------------------------

    async def read_dtcs(self, kind: DtcKind) -> list[Dtc]:
        """Lee los DTCs de un tipo en todas las ECUs OBD (RU-40)."""
        info = self._require_connection()
        service = DTC_SERVICES[kind]
        dtcs: list[Dtc] = []
        for response in await self._send(DiagRequest(bytes([service]))):
            try:
                codes = obd2.parse_dtc_response(
                    response.payload, service, has_count_byte=info.has_can_count_byte
                )
            except obd2.ProtocolError as exc:
                self._discard(response, exc)
                continue
            dtcs.extend(Dtc(code, kind, response.source_id) for code in codes)
        return dtcs

    async def read_all_dtcs(self) -> list[Dtc]:
        """Lee DTCs almacenados, pendientes y permanentes."""
        result: list[Dtc] = []
        for kind in DtcKind:
            result.extend(await self.read_dtcs(kind))
        return result

    async def clear_dtcs(self) -> list[int]:
        """Borra los DTCs (servicio 04).

        **Acción con efecto en el vehículo**: también borra el freeze frame y los monitores de
        preparación. La confirmación del técnico la pide la capa de interfaz (RNF-04).

        Returns:
            Identificadores de las ECUs que confirmaron el borrado.
        """
        self._require_connection()
        responses = await self._send(DiagRequest(obd2.build_clear_dtc_request()))
        return [r.source_id for r in responses if obd2.is_clear_dtc_confirmation(r.payload)]

    async def read_freeze_frames(self) -> list[FreezeFrame]:
        """Lee el freeze frame 0 de cada ECU que tenga uno (RU-41)."""
        self._require_connection()
        lengths = self._pids.data_lengths()
        frames = []
        for ecu in self._supported:
            dtc = await self._freeze_frame_dtc(ecu, lengths)
            if dtc is None:
                continue
            supported = await self._freeze_frame_supported(ecu, lengths)
            values: list[Sample] = []
            for pid in sorted(supported):
                spec = self._pids.pid(pid)
                if spec is None:
                    continue
                request = DiagRequest(obd2.build_freeze_frame_request(pid), _address(ecu))
                for response in await self._send(request):
                    try:
                        _, _, raw = obd2.parse_freeze_frame_response(response.payload, lengths)
                    except obd2.ProtocolError as exc:
                        self._discard(response, exc)
                        continue
                    t = self._clock()
                    for key, value in decode_pid(spec, raw).items():
                        unit = self._pids.signal(key)[1].unit
                        values.append(Sample(key, value, unit, t, ecu))
            frames.append(FreezeFrame(source_id=ecu, dtc=dtc, values=tuple(values)))
        return frames

    async def _freeze_frame_dtc(self, ecu: int, lengths: dict[int, int]) -> str | None:
        """DTC que originó el freeze frame 0 de una ECU, o ``None`` si no hay."""
        request = DiagRequest(obd2.build_freeze_frame_request(FREEZE_FRAME_DTC_PID), _address(ecu))
        for response in await self._send(request):
            try:
                _, _, raw = obd2.parse_freeze_frame_response(response.payload, lengths)
            except obd2.ProtocolError:
                continue  # incluye respuestas negativas: la ECU no tiene freeze frame
            code = obd2.decode_dtc(raw)
            return None if code == _NO_DTC else code
        return None

    async def _freeze_frame_supported(self, ecu: int, lengths: dict[int, int]) -> set[int]:
        """PIDs disponibles en el freeze frame 0 de una ECU."""
        supported: set[int] = set()
        support_pid = 0
        while support_pid <= LAST_SUPPORT_PID:
            request = DiagRequest(obd2.build_freeze_frame_request(support_pid), _address(ecu))
            responses = await self._send(request)
            for response in responses:
                try:
                    _, _, mask = obd2.parse_freeze_frame_response(response.payload, lengths)
                    supported |= obd2.decode_supported_pids(support_pid, mask)
                except obd2.ProtocolError as exc:
                    self._discard(response, exc)
            next_range = support_pid + PID_SUPPORT_RANGE
            if next_range not in supported:
                break
            support_pid = next_range
        return {p for p in supported if not obd2.is_support_pid(p)}

    # --- Utilidades ---------------------------------------------------------------------

    def _require_connection(self) -> AdapterInfo:
        if self._info is None:
            raise NotConnectedError("Llame a connect() antes de usar el cliente.")
        return self._info

    async def _send(self, request: DiagRequest) -> list[DiagResponse]:
        logger.debug("→ %s %s", request.target or "funcional", request.payload.hex(" "))
        responses = await self._adapter.request(request)
        for r in responses:
            logger.debug("← %03X %s", r.source_id, r.payload.hex(" "))
        return responses

    @staticmethod
    def _discard(response: DiagResponse, error: Exception) -> None:
        logger.warning("ECU %03X: respuesta descartada (%s)", response.source_id, error)


def _address(response_id: int) -> EcuAddress:
    """Dirección física de una ECU a partir de su id de respuesta (ISO 15765-4, 11 bits)."""
    return EcuAddress(response_id - CAN_RESPONSE_OFFSET_11BIT, response_id)


def _chunks(items: Sequence[int], size: int) -> Iterable[list[int]]:
    """Divide ``items`` en listas de hasta ``size`` elementos."""
    for start in range(0, len(items), size):
        yield list(items[start : start + size])
