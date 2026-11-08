"""Adaptador simulado: un vehículo virtual que responde como ECUs reales (RU-03, RS-06).

Implementa el puerto :class:`~diag.core.ports.adapter.Adapter`, así que el resto del
sistema no distingue entre el simulador y un adaptador físico. Los mensajes se generan con
las **mismas** funciones de :mod:`diag.core.protocols.obd2` que usa el cliente para
interpretarlos, y los valores se codifican con las mismas fórmulas de ``pids.yaml``.

Comportamiento (SAE J1979 / ISO 15765-4):

- Petición funcional (``target=None``): responde cada ECU que tenga datos; una ECU que no
  soporta lo pedido **no responde**.
- Petición física: si la ECU no soporta lo pedido, responde ``7F <SID> <NRC>``.
- Servicio 04 borra DTCs almacenados, pendientes y el freeze frame; los permanentes quedan
  (así lo establece la norma).
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from diag.core.decoding.signals import EncodingError, PidEncoder
from diag.core.definitions.loader import (
    DefinitionError,
    DefinitionIssue,
    PidCatalog,
    validate_file,
)
from diag.core.domain.models import DiagRequest, DiagResponse
from diag.core.ports.adapter import AdapterInfo
from diag.core.protocols import obd2
from diag.core.protocols.constants import (
    FREEZE_FRAME_DTC_PID,
    NEGATIVE_RESPONSE_SID,
    NRC_REQUEST_OUT_OF_RANGE,
    NRC_SERVICE_NOT_SUPPORTED,
    VIN_INFOTYPE,
    Obd2Service,
)
from diag.infra.simulator.generators import Generator
from diag.infra.simulator.vehicle import SimEcu, SimVehicleFile

_SIMULATOR_NAME = "Simulador diag"


@dataclass
class _EcuState:
    """Estado mutable de una ECU simulada durante la sesión."""

    spec: SimEcu
    generators: dict[str, Generator]
    encoders: dict[int, PidEncoder]
    dtcs: dict[Obd2Service, list[str]]
    freeze_frame: dict[int, bytes] = field(default_factory=dict)
    freeze_frame_dtc: str | None = None

    @property
    def supported_pids(self) -> set[int]:
        return set(self.encoders)


class SimulatedAdapter:
    """Vehículo simulado que implementa el puerto ``Adapter``.

    Args:
        vehicle: Definición validada del vehículo (ver :func:`load_sim_vehicle`).
        pids: Catálogo de PIDs, para codificar valores con las fórmulas oficiales.
        response_delay_s: Retardo artificial por petición, para imitar el bus real.
        seed: Semilla de los generadores aleatorios (``None`` = no reproducible).
        clock: Reloj monotónico en segundos; inyectable para pruebas.

    Raises:
        DefinitionError: Si el vehículo usa señales que no existen o no son simulables.
    """

    def __init__(
        self,
        vehicle: SimVehicleFile,
        pids: PidCatalog,
        *,
        response_delay_s: float = 0.0,
        seed: int | None = None,
        clock: Callable[[], float] = time.monotonic,
        source: Path | None = None,
    ) -> None:
        self.vehicle = vehicle
        self._pids = pids
        self._delay = response_delay_s
        self._rng = random.Random(seed)
        self._clock = clock
        self._t0: float | None = None
        self._ecus = [self._build_ecu(ecu, index, source) for index, ecu in enumerate(vehicle.ecus)]

    # --- Puerto Adapter ---------------------------------------------------------------------

    async def connect(self) -> AdapterInfo:
        """Inicia la simulación; el tiempo de los generadores empieza a contar aquí."""
        self._t0 = self._clock()
        return AdapterInfo(
            name=_SIMULATOR_NAME,
            protocol=self.vehicle.protocol,
            has_can_count_byte=self.vehicle.has_can_count_byte,
        )

    async def disconnect(self) -> None:
        """Detiene la simulación."""
        self._t0 = None

    async def request(self, req: DiagRequest) -> list[DiagResponse]:
        """Responde como lo harían las ECUs del vehículo.

        Raises:
            ConnectionError: Si no se llamó antes a :meth:`connect`.
        """
        if self._t0 is None:
            raise ConnectionError("Simulador no conectado.")
        if self._delay:
            await asyncio.sleep(self._delay)
        t = self._clock() - self._t0
        targets = (
            self._ecus
            if req.target is None
            else [e for e in self._ecus if e.spec.request_id == req.target.request_id]
        )
        responses = []
        for ecu in targets:
            payload = self._handle(ecu, req.payload, t, functional=req.target is None)
            if payload is not None:
                responses.append(DiagResponse(source_id=ecu.spec.response_id, payload=payload))
        return responses

    # --- Construcción y validación ----------------------------------------------------------

    def _build_ecu(self, ecu: SimEcu, index: int, source: Path | None) -> _EcuState:
        """Valida una ECU contra el catálogo de PIDs y prepara sus generadores."""
        path = source or Path("<vehículo simulado>")
        issues: list[DefinitionIssue] = []

        def issue(location: str, message: str) -> None:
            issues.append(DefinitionIssue(path, None, f"ecus.{index}.{location}", message))

        encoders: dict[int, PidEncoder] = {}
        for key in ecu.signals:
            try:
                pid_spec, _ = self._pids.signal(key)
            except KeyError:
                issue(f"signals.{key}", "señal no definida en pids.yaml")
                continue
            if pid_spec.pid in encoders:
                continue
            missing = {s.key for s in pid_spec.signals} - set(ecu.signals)
            if missing:
                issue(
                    f"signals.{key}",
                    f"el PID {pid_spec.id} también requiere: {', '.join(sorted(missing))}",
                )
                continue
            try:
                encoders[pid_spec.pid] = PidEncoder(pid_spec)
            except EncodingError as exc:
                issue(f"signals.{key}", str(exc))

        all_codes = [*ecu.dtcs.stored, *ecu.dtcs.pending, *ecu.dtcs.permanent]
        if ecu.freeze_frame:
            all_codes.append(ecu.freeze_frame.dtc)
        for code in all_codes:
            try:
                obd2.encode_dtc(code)
            except ValueError as exc:
                issue("dtcs", str(exc))

        freeze_frame: dict[int, bytes] = {}
        if ecu.freeze_frame:
            freeze_frame = self._encode_freeze_frame(ecu.freeze_frame.values, issue)

        if issues:
            raise DefinitionError(issues)

        return _EcuState(
            spec=ecu,
            generators={k: g.build(self._rng) for k, g in ecu.signals.items()},
            encoders=encoders,
            dtcs={
                Obd2Service.STORED_DTC: list(ecu.dtcs.stored),
                Obd2Service.PENDING_DTC: list(ecu.dtcs.pending),
                Obd2Service.PERMANENT_DTC: list(ecu.dtcs.permanent),
            },
            freeze_frame=freeze_frame,
            freeze_frame_dtc=ecu.freeze_frame.dtc if ecu.freeze_frame else None,
        )

    def _encode_freeze_frame(
        self, values: dict[str, float], issue: Callable[[str, str], None]
    ) -> dict[int, bytes]:
        """Codifica los valores del freeze frame por PID."""
        by_pid: dict[int, PidEncoder] = {}
        for key in values:
            try:
                pid_spec, _ = self._pids.signal(key)
            except KeyError:
                issue(f"freeze_frame.values.{key}", "señal no definida en pids.yaml")
                continue
            missing = {s.key for s in pid_spec.signals} - set(values)
            if missing:
                issue(
                    f"freeze_frame.values.{key}",
                    f"el PID {pid_spec.id} también requiere: {', '.join(sorted(missing))}",
                )
                continue
            try:
                by_pid.setdefault(pid_spec.pid, PidEncoder(pid_spec))
            except EncodingError as exc:
                issue(f"freeze_frame.values.{key}", str(exc))
        return {pid: encoder.encode(values) for pid, encoder in by_pid.items()}

    # --- Atención de servicios --------------------------------------------------------------

    def _handle(
        self, ecu: _EcuState, payload: bytes, t: float, *, functional: bool
    ) -> bytes | None:
        """Atiende una petición en una ECU. ``None`` = la ECU no responde."""
        if not payload:
            return None
        service = payload[0]
        result: bytes | None
        nrc = NRC_REQUEST_OUT_OF_RANGE
        if service == Obd2Service.CURRENT_DATA:
            result = self._current_data(ecu, payload[1:], t)
        elif service == Obd2Service.FREEZE_FRAME:
            result = self._freeze_frame(ecu, payload[1:])
        elif service in (
            Obd2Service.STORED_DTC,
            Obd2Service.PENDING_DTC,
            Obd2Service.PERMANENT_DTC,
        ):
            result = obd2.build_dtc_response(
                service,
                ecu.dtcs[Obd2Service(service)],
                has_count_byte=self.vehicle.has_can_count_byte,
            )
        elif service == Obd2Service.CLEAR_DTC:
            ecu.dtcs[Obd2Service.STORED_DTC].clear()
            ecu.dtcs[Obd2Service.PENDING_DTC].clear()
            ecu.freeze_frame.clear()
            ecu.freeze_frame_dtc = None
            result = bytes([obd2.response_sid(Obd2Service.CLEAR_DTC)])
        elif service == Obd2Service.VEHICLE_INFO:
            wants_vin = payload[1:2] == bytes([VIN_INFOTYPE])
            result = (
                obd2.build_vin_response(self.vehicle.vin)
                if wants_vin and ecu.spec.provides_vin
                else None
            )
        else:
            result, nrc = None, NRC_SERVICE_NOT_SUPPORTED

        if result is None and not functional:
            return bytes([NEGATIVE_RESPONSE_SID, service, nrc])
        return result

    def _current_data(self, ecu: _EcuState, pids: bytes, t: float) -> bytes | None:
        """Servicio 01: datos actuales calculados por los generadores en el instante ``t``."""
        values: dict[int, bytes] = {}
        for pid in pids:
            if obd2.is_support_pid(pid):
                values[pid] = obd2.encode_supported_pids(pid, ecu.supported_pids)
            elif pid in ecu.encoders:
                encoder = ecu.encoders[pid]
                physical = {s.key: ecu.generators[s.key].value(t) for s in encoder.spec.signals}
                values[pid] = encoder.encode(physical)
        return obd2.build_current_data_response(values) if values else None

    def _freeze_frame(self, ecu: _EcuState, args: bytes) -> bytes | None:
        """Servicio 02: solo existe el freeze frame 0, y solo si hay DTC que lo originó."""
        if len(args) < 2 or ecu.freeze_frame_dtc is None or args[1] != 0:
            return None
        pid, frame = args[0], args[1]
        if pid == FREEZE_FRAME_DTC_PID:
            data = obd2.encode_dtc(ecu.freeze_frame_dtc)
        elif obd2.is_support_pid(pid):
            # El PID 02 (DTC del freeze frame) también se informa como soportado.
            data = obd2.encode_supported_pids(pid, {*ecu.freeze_frame, FREEZE_FRAME_DTC_PID})
        elif pid in ecu.freeze_frame:
            data = ecu.freeze_frame[pid]
        else:
            return None
        return obd2.build_freeze_frame_response(pid, frame, data)


def load_sim_vehicle(
    path: Path,
    pids: PidCatalog,
    *,
    response_delay_s: float = 0.0,
    seed: int | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> SimulatedAdapter:
    """Carga un vehículo simulado desde YAML y crea el adaptador.

    Raises:
        DefinitionError: Si el archivo es inválido o incoherente con ``pids.yaml``.
    """
    vehicle, _ = validate_file(SimVehicleFile, path)
    return SimulatedAdapter(
        vehicle, pids, response_delay_s=response_delay_s, seed=seed, clock=clock, source=path
    )
