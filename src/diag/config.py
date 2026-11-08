"""Configuración de la aplicación (RS-05, RNF-06; arquitectura §8).

Precedencia (el último gana):

1. ``config/default.yaml``: valores por defecto, versionados y documentados.
2. ``config/local.yaml``: ajustes del equipo, **no** versionado (opcional).
3. Variables de entorno ``DIAG_<SECCIÓN>__<CLAVE>``, p. ej. ``DIAG_SIMULATOR__SEED=42``.
   Es la vía para secretos (claves de API), que nunca van en archivos (RS-45).

Un valor inválido detiene el arranque con un mensaje que indica qué clave está mal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from diag.core.protocols.constants import MAX_PIDS_PER_REQUEST_CAN

DEFAULT_FILE = "default.yaml"
LOCAL_FILE = "local.yaml"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DefinitionsConfig(_Section):
    """Rutas de los archivos de definición."""

    units: Path
    pids: Path


class Obd2Config(_Section):
    """Parámetros del cliente OBD2."""

    max_pids_per_request: int = Field(ge=1, le=MAX_PIDS_PER_REQUEST_CAN)


class SimulatorConfig(_Section):
    """Parámetros del vehículo simulado."""

    vehicle: Path
    response_delay_s: float = Field(ge=0)
    seed: int | None = None


class LoggingConfig(_Section):
    """Nivel de registro."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    """Configuración completa. Se obtiene con :func:`load_settings`."""

    model_config = SettingsConfigDict(
        env_prefix="DIAG_", env_nested_delimiter="__", extra="forbid", frozen=True
    )

    definitions: DefinitionsConfig
    obd2: Obd2Config
    simulator: SimulatorConfig
    logging: LoggingConfig

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Los YAML llegan como argumentos de inicialización; las variables de entorno
        # deben ganarles, así que van primero (mayor prioridad).
        return env_settings, init_settings


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Combina dos diccionarios anidados; ``override`` gana en las hojas."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: la raíz debe ser un mapa clave: valor.")
    return data


def load_settings(config_dir: Path) -> Settings:
    """Carga la configuración desde ``config_dir`` y el entorno.

    Las rutas relativas se resuelven respecto a la carpeta padre de ``config_dir``
    (la raíz del proyecto), para que funcione igual desde cualquier directorio.

    Raises:
        FileNotFoundError: Si falta ``default.yaml``.
        pydantic.ValidationError: Si algún valor es inválido.
    """
    config_dir = config_dir.resolve()
    data = _read(config_dir / DEFAULT_FILE)
    local = config_dir / LOCAL_FILE
    if local.exists():
        data = _deep_merge(data, _read(local))

    settings = Settings(**data)
    root = config_dir.parent
    return settings.model_copy(
        update={
            "definitions": DefinitionsConfig(
                units=root / settings.definitions.units, pids=root / settings.definitions.pids
            ),
            "simulator": settings.simulator.model_copy(
                update={"vehicle": root / settings.simulator.vehicle}
            ),
        }
    )
