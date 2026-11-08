"""Carga de definiciones: las reales son válidas y los errores indican archivo y línea (RS-12)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from diag.core.definitions.loader import DefinitionError, Definitions, load_pids

from ..conftest import DEFINITIONS


def test_real_definitions_load(definitions: Definitions) -> None:
    rpm_pid, rpm = definitions.pids.signal("engine_rpm")
    assert rpm_pid.pid == 0x0C
    assert rpm.unit == "rpm"
    # Un PID con dos señales (sonda O2).
    o2 = definitions.pids.pid(0x14)
    assert o2 is not None
    assert [s.key for s in o2.signals] == ["o2_b1s1_voltage", "o2_b1s1_trim"]


def _write_pids(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "pids.yaml"
    path.write_text(dedent(body), encoding="utf-8")
    return path


def _load_error(path: Path, definitions: Definitions) -> DefinitionError:
    with pytest.raises(DefinitionError) as info:
        load_pids(path, definitions.units)
    return info.value


SIGNAL = """\
  - id: "0C"
    bytes: 2
    signals:
      - key: engine_rpm
        name: {{ es: "RPM" }}
        formula: "{formula}"
        unit: "{unit}"
        range: {{ min: 0, max: 16383.75 }}
        category: engine
"""


def test_formula_error_has_line(tmp_path: Path, definitions: Definitions) -> None:
    body = "schema_version: 1\npids:\n" + SIGNAL.format(formula="(A*256 + C)/4", unit="rpm")
    error = _load_error(_write_pids(tmp_path, body), definitions)
    issue = error.issues[0]
    assert issue.path.name == "pids.yaml"
    assert issue.line == 3  # inicio del PID: ahí se conocen los bytes disponibles
    assert "señal 'engine_rpm'" in issue.message
    assert "Variable 'C' no permitida" in issue.message


def test_unknown_unit_is_reported(tmp_path: Path, definitions: Definitions) -> None:
    body = "schema_version: 1\npids:\n" + SIGNAL.format(formula="A*256 + B", unit="rev/s")
    error = _load_error(_write_pids(tmp_path, body), definitions)
    assert error.issues[0].line == 9  # línea de 'unit:'
    assert "rev/s" in error.issues[0].message


def test_unquoted_pid_is_rejected(tmp_path: Path, definitions: Definitions) -> None:
    body = "schema_version: 1\npids:\n" + SIGNAL.format(formula="A", unit="rpm").replace(
        '"0C"', "10"
    )
    error = _load_error(_write_pids(tmp_path, body), definitions)
    assert error.issues[0].location == "pids.0.id"
    assert error.issues[0].line == 3


def test_duplicate_signal_keys(tmp_path: Path, definitions: Definitions) -> None:
    entry = SIGNAL.format(formula="A*256 + B", unit="rpm")
    body = "schema_version: 1\npids:\n" + entry + entry.replace('"0C"', '"0D"')
    error = _load_error(_write_pids(tmp_path, body), definitions)
    assert "claves de señal duplicadas: engine_rpm" in error.issues[0].message


def test_unknown_field_is_rejected(tmp_path: Path, definitions: Definitions) -> None:
    entry = SIGNAL.format(formula="A", unit="rpm").replace("bytes: 2", "bytes: 2\n    byts: 2")
    error = _load_error(_write_pids(tmp_path, "schema_version: 1\npids:\n" + entry), definitions)
    assert error.issues[0].location == "pids.0.byts"


def test_invalid_yaml(tmp_path: Path, definitions: Definitions) -> None:
    error = _load_error(_write_pids(tmp_path, "pids: [\n"), definitions)
    assert "YAML inválido" in error.issues[0].message


def test_message_lists_file_and_line(tmp_path: Path, definitions: Definitions) -> None:
    body = "schema_version: 1\npids:\n" + SIGNAL.format(formula="A", unit="rev/s")
    error = _load_error(_write_pids(tmp_path, body), definitions)
    assert f"{tmp_path / 'pids.yaml'}:9" in str(error)


def test_definitions_dir_exists() -> None:
    assert (DEFINITIONS / "units.yaml").is_file()
