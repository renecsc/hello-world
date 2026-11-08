"""Puerto ``Adapter``: interfaz de diagnóstico con el vehículo (RS-02).

Un ``Adapter`` envía **mensajes de diagnóstico completos** y devuelve las respuestas de
las ECUs. La segmentación en tramas (ISO-TP) es responsabilidad de la implementación:
un ELM327/STN la hace en el propio chip; un adaptador CAN nativo usará
``diag.core.protocols.isotp`` (fase 3). Así las capas superiores (OBD2, UDS) son idénticas
para cualquier hardware, y el simulador implementa este mismo puerto (RS-06).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from diag.core.domain.models import DiagRequest, DiagResponse


@dataclass(frozen=True, slots=True)
class AdapterInfo:
    """Datos que el adaptador informa al conectarse.

    Attributes:
        name: Nombre/versión del adaptador (p. ej. ``ELM327 v1.5``, ``Simulador``).
        protocol: Protocolo de vehículo detectado (p. ej. ``ISO 15765-4 CAN 11/500``).
        has_can_count_byte: ``True`` si las respuestas a 03/07/0A incluyen el byte de
            cantidad de DTCs, cosa que ocurre sobre CAN (SAE J1979 §6.3).
    """

    name: str
    protocol: str
    has_can_count_byte: bool


@runtime_checkable
class Adapter(Protocol):
    """Interfaz de diagnóstico, independiente del hardware."""

    async def connect(self) -> AdapterInfo:
        """Inicializa el adaptador y detecta el protocolo del vehículo.

        Returns:
            Información del adaptador y del protocolo detectado.

        Raises:
            ConnectionError: Si no se puede establecer comunicación.
        """
        ...

    async def disconnect(self) -> None:
        """Libera el adaptador. Debe poder llamarse aunque no haya conexión."""
        ...

    async def request(self, req: DiagRequest) -> list[DiagResponse]:
        """Envía una petición y recoge todas las respuestas recibidas a tiempo.

        Args:
            req: Petición. Si ``req.target`` es ``None`` es funcional y pueden responder
                varias ECUs.

        Returns:
            Respuestas recibidas, posiblemente vacía (ninguna ECU contestó). Incluye las
            respuestas negativas (``7F``); interpretarlas es tarea de la capa de protocolo.

        Raises:
            ConnectionError: Si se perdió la comunicación con el adaptador.
        """
        ...
