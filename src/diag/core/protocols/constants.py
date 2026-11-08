"""Constantes de protocolo definidas por normas.

Este es el **único** lugar del código donde se permiten valores numéricos de protocolo
(RNF-06). Cada constante cita la norma de la que proviene. Todo lo que no sea una norma
(PIDs concretos, direcciones de ECUs de una marca, umbrales...) vive en ``definitions/``.

Normas citadas:
    - SAE J1979 / ISO 15031-5: servicios de diagnóstico OBD2 (modos 01-0A).
    - ISO 15765-4: OBD2 sobre CAN (identificadores CAN de diagnóstico).
    - ISO 14229-1: UDS (respuesta negativa y sus códigos).
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final


class Obd2Service(IntEnum):
    """Identificadores de servicio (modos) OBD2. SAE J1979, sección 6."""

    CURRENT_DATA = 0x01
    """Datos actuales del tren motriz (datos en vivo)."""
    FREEZE_FRAME = 0x02
    """Datos congelados (freeze frame) en el momento de registrar un DTC."""
    STORED_DTC = 0x03
    """Códigos de avería confirmados (almacenados)."""
    CLEAR_DTC = 0x04
    """Borrado de códigos de avería e información de diagnóstico."""
    PENDING_DTC = 0x07
    """Códigos de avería pendientes (detectados en el ciclo actual o el anterior)."""
    VEHICLE_INFO = 0x09
    """Información del vehículo (VIN, calibraciones...)."""
    PERMANENT_DTC = 0x0A
    """Códigos de avería permanentes (no se borran con el servicio 04)."""


POSITIVE_RESPONSE_OFFSET: Final = 0x40
"""Una respuesta positiva lleva ``servicio + 0x40`` (SAE J1979 §6.1; ISO 14229-1 §7.5)."""

NEGATIVE_RESPONSE_SID: Final = 0x7F
"""SID de respuesta negativa: ``7F <servicio> <NRC>`` (ISO 14229-1 §7.5.2)."""

MAX_PIDS_PER_REQUEST_CAN: Final = 6
"""Máximo de PIDs en una sola petición de servicio 01/02 sobre CAN (SAE J1979 §6.1.2)."""

PID_SUPPORT_RANGE: Final = 0x20
"""Cada PID de soporte (00, 20, 40...) describe los 32 PIDs siguientes (SAE J1979 Anexo A)."""

PID_SUPPORT_BYTES: Final = 4
"""Bytes de datos de un PID de soporte: máscara de 32 bits (SAE J1979 Anexo A)."""

VIN_INFOTYPE: Final = 0x02
"""``InfoType`` del VIN en el servicio 09 (SAE J1979 §6.9)."""

VIN_LENGTH: Final = 17
"""Longitud del VIN en caracteres ASCII (ISO 3779)."""

FREEZE_FRAME_DTC_PID: Final = 0x02
"""PID 02 del servicio 02: DTC que originó el freeze frame (SAE J1979 Anexo A)."""

DTC_BYTES: Final = 2
"""Bytes por DTC en los servicios 03/07/0A (SAE J1979 §6.3)."""

DTC_SYSTEM_LETTERS: Final = ("P", "C", "B", "U")
"""Letra del sistema según los 2 bits altos del primer byte del DTC (SAE J2012):
P = tren motriz, C = chasis, B = carrocería, U = red."""

# --- ISO 15765-4: identificadores CAN de 11 bits ---------------------------------------
CAN_FUNCTIONAL_REQUEST_ID_11BIT: Final = 0x7DF
"""Identificador funcional (a todas las ECUs OBD) en CAN de 11 bits (ISO 15765-4 §6.3.2)."""

CAN_PHYSICAL_REQUEST_BASE_11BIT: Final = 0x7E0
"""Primer identificador físico de petición, ECU #1 (ISO 15765-4 §6.3.2). Rango 7E0-7E7."""

CAN_RESPONSE_OFFSET_11BIT: Final = 0x08
"""La respuesta de una ECU usa ``id_petición_física + 8`` (ISO 15765-4 §6.3.2). Rango 7E8-7EF."""

CAN_MAX_OBD_ECUS: Final = 8
"""ECUs OBD direccionables en CAN de 11 bits (ISO 15765-4 §6.3.2)."""

# --- ISO 14229-1 Anexo A: códigos de respuesta negativa (NRC) usados ----------------------
NRC_SERVICE_NOT_SUPPORTED: Final = 0x11
"""El servicio solicitado no está soportado por la ECU."""

NRC_REQUEST_OUT_OF_RANGE: Final = 0x31
"""El parámetro solicitado (PID/DID) está fuera de rango o no está soportado."""

LAST_SUPPORT_PID: Final = 0xE0
"""Último PID de soporte del servicio 01: ``E0`` describe los PIDs E1-FF (SAE J1979 Anexo A)."""

VIN_DATA_ITEMS: Final = 0x01
"""Campo NODI de la respuesta 09/02 sobre CAN: el VIN es 1 elemento de datos (SAE J1979 §6.9)."""
