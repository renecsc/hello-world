"""Modelos del dominio de diagnóstico.

Son objetos inmutables (``frozen``) sin lógica de E/S. Representan lo que se intercambia
entre capas: peticiones y respuestas de diagnóstico, muestras de señales, códigos de avería
e información del vehículo.

Las *definiciones* (qué es un PID, cómo se decodifica) no están aquí: viven en
``diag.core.definitions``, porque se cargan desde archivos de datos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class EcuAddress:
    """Dirección de una ECU en el bus.

    Attributes:
        request_id: Identificador al que se envían las peticiones (p. ej. CAN 0x7E0).
        response_id: Identificador desde el que responde la ECU (p. ej. CAN 0x7E8).
    """

    request_id: int
    response_id: int

    def __str__(self) -> str:
        return f"{self.request_id:03X}/{self.response_id:03X}"


@dataclass(frozen=True, slots=True)
class DiagRequest:
    """Petición de diagnóstico completa (ya sin segmentar en tramas).

    Attributes:
        payload: Bytes del mensaje, empezando por el identificador de servicio.
        target: ECU destino. ``None`` indica petición **funcional** (a todas las ECUs).
    """

    payload: bytes
    target: EcuAddress | None = None


@dataclass(frozen=True, slots=True)
class DiagResponse:
    """Respuesta de diagnóstico completa de una ECU.

    Attributes:
        source_id: Identificador desde el que respondió la ECU (p. ej. CAN 0x7E8).
        payload: Bytes del mensaje, empezando por el identificador de servicio de respuesta.
    """

    source_id: int
    payload: bytes


@dataclass(frozen=True, slots=True)
class Sample:
    """Valor de una señal en un instante.

    Attributes:
        signal: Clave estable de la señal (``key`` en la definición, p. ej. ``engine_rpm``).
        value: Valor físico en la **unidad base** de la definición (RS-15).
        unit: Símbolo de la unidad base (p. ej. ``rpm``, ``V``).
        t_monotonic: Instante de adquisición en segundos de reloj monotónico (RS-21).
        source_id: ECU que entregó el dato.
    """

    signal: str
    value: float
    unit: str
    t_monotonic: float
    source_id: int


class DtcKind(StrEnum):
    """Tipo de código de avería según el servicio OBD2 con que se leyó (SAE J1979)."""

    STORED = "stored"
    """Confirmado (servicio 03)."""
    PENDING = "pending"
    """Pendiente (servicio 07)."""
    PERMANENT = "permanent"
    """Permanente (servicio 0A)."""


@dataclass(frozen=True, slots=True)
class Dtc:
    """Código de avería.

    Attributes:
        code: Código en formato SAE J2012, p. ej. ``P0301``.
        kind: Tipo (almacenado, pendiente, permanente).
        source_id: ECU que lo reportó.
    """

    code: str
    kind: DtcKind
    source_id: int


@dataclass(frozen=True, slots=True)
class VehicleInfo:
    """Información de identificación del vehículo (RU-02).

    Attributes:
        vin: Número de identificación del vehículo, si la ECU lo entrega.
        ecus: Identificadores de respuesta de las ECUs OBD que contestaron.
        protocol: Descripción del protocolo detectado por el adaptador.
    """

    vin: str | None
    ecus: tuple[int, ...] = field(default_factory=tuple)
    protocol: str | None = None


@dataclass(frozen=True, slots=True)
class FreezeFrame:
    """Datos congelados en el momento en que una ECU registró un DTC (RU-41).

    Attributes:
        source_id: ECU que entregó el freeze frame.
        dtc: Código que lo originó (``None`` si la ECU no lo informa).
        values: Valores de las señales en ese instante. ``t_monotonic`` de cada muestra
            es el momento de la *lectura*, no el del evento.
    """

    source_id: int
    dtc: str | None
    values: tuple[Sample, ...]
