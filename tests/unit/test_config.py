"""Configuración: precedencia default < local < entorno, y rutas resueltas."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from diag.config import load_settings

from ..conftest import ROOT


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    target.mkdir()
    shutil.copy(ROOT / "config" / "default.yaml", target / "default.yaml")
    return target


def test_defaults_and_relative_paths(config_dir: Path) -> None:
    settings = load_settings(config_dir)
    assert settings.obd2.max_pids_per_request == 6
    assert settings.definitions.pids == config_dir.parent / "definitions" / "obd2" / "pids.yaml"


def test_local_overrides_default(config_dir: Path) -> None:
    (config_dir / "local.yaml").write_text("obd2:\n  max_pids_per_request: 1\n", encoding="utf-8")
    assert load_settings(config_dir).obd2.max_pids_per_request == 1


def test_environment_overrides_local(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (config_dir / "local.yaml").write_text("simulator:\n  seed: 1\n", encoding="utf-8")
    monkeypatch.setenv("DIAG_SIMULATOR__SEED", "42")
    assert load_settings(config_dir).simulator.seed == 42


def test_invalid_value_fails(config_dir: Path) -> None:
    (config_dir / "local.yaml").write_text("obd2:\n  max_pids_per_request: 9\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_settings(config_dir)
