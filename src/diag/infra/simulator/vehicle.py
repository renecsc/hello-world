"""Esquema del archivo de vehículo simulado (``definitions/vehicles/sim/*.yaml``).

Un vehículo simulado declara sus ECUs, qué señales entrega cada una (con su generador),
sus códigos de avería y su freeze frame. Los PIDs soportados se **deducen** de las señales
configuradas: no hay que mantener dos listas.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from diag.core.protocols.constants import VIN_LENGTH
from diag.infra.simulator.generators import GeneratorSpec


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SimDtcs(_StrictModel):
    """Códigos de avería iniciales de una ECU, en formato SAE J2012 (``P0171``)."""

    stored: list[str] = Field(default_factory=list)
    pending: list[str] = Field(default_factory=list)
    permanent: list[str] = Field(default_factory=list)


class SimFreezeFrame(_StrictModel):
    """Freeze frame 0: DTC que lo originó y valores físicos de las señales en ese instante."""

    dtc: str
    values: dict[str, float] = Field(min_length=1)


class SimEcu(_StrictModel):
    """Una ECU simulada."""

    name: str
    request_id: int = Field(ge=0)
    response_id: int = Field(ge=0)
    provides_vin: bool = False
    signals: dict[str, GeneratorSpec] = Field(default_factory=dict)
    dtcs: SimDtcs = Field(default_factory=SimDtcs)
    freeze_frame: SimFreezeFrame | None = None


class SimVehicleFile(_StrictModel):
    """Contenido de un archivo de vehículo simulado."""

    schema_version: Literal[1]
    name: str
    vin: str = Field(min_length=VIN_LENGTH, max_length=VIN_LENGTH)
    protocol: str
    has_can_count_byte: bool = True
    ecus: list[SimEcu] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> SimVehicleFile:
        ids = [e.response_id for e in self.ecus]
        if len(ids) != len(set(ids)):
            raise ValueError("hay ECUs con el mismo response_id")
        return self
