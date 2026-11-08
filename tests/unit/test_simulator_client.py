"""Integración núcleo + simulador: cliente OBD2 contra el vehículo virtual."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from diag.core.definitions.loader import DefinitionError, Definitions
from diag.core.domain.models import DiagRequest, DtcKind, EcuAddress
from diag.core.ports.adapter import Adapter
from diag.infra.simulator.adapter import SimulatedAdapter, load_sim_vehicle
from diag.services.obd2_client import NotConnectedError, Obd2Client

from ..conftest import SIM_VEHICLE, FakeClock

ECM, TCM = 0x7E8, 0x7E9


@pytest.fixture
def adapter(definitions: Definitions, clock: FakeClock) -> SimulatedAdapter:
    return load_sim_vehicle(SIM_VEHICLE, definitions.pids, seed=1, clock=clock)


@pytest.fixture
async def client(
    adapter: SimulatedAdapter, definitions: Definitions, clock: FakeClock
) -> Obd2Client:
    c = Obd2Client(adapter, definitions.pids, clock=clock)
    await c.connect()
    return c


def test_simulator_implements_port(adapter: SimulatedAdapter) -> None:
    assert isinstance(adapter, Adapter)


async def test_identification(adapter: SimulatedAdapter, definitions: Definitions) -> None:
    info = await Obd2Client(adapter, definitions.pids).connect()
    assert info.vin == "SIM00000000000001"
    assert info.ecus == (ECM, TCM)


async def test_supported_signals_prefer_lowest_ecu(client: Obd2Client) -> None:
    signals = client.supported_signals()
    assert signals["engine_rpm"] == ECM
    assert signals["vehicle_speed"] == ECM  # ambas ECUs lo soportan; gana el ECM
    assert "fuel_pressure" not in signals  # definido en pids.yaml pero no en el vehículo


async def test_read_signals(client: Obd2Client, clock: FakeClock) -> None:
    clock.advance(10)
    samples = {
        s.signal: s for s in await client.read_signals(["ltft_b1", "engine_rpm", "o2_b1s1_voltage"])
    }
    assert set(samples) == {"ltft_b1", "engine_rpm", "o2_b1s1_voltage"}
    assert samples["ltft_b1"].value == pytest.approx(18.0, abs=0.8)  # resolución 0,78 %
    assert 600 < samples["engine_rpm"].value < 900
    assert samples["engine_rpm"].unit == "rpm"
    assert samples["engine_rpm"].t_monotonic == clock.now
    assert samples["engine_rpm"].source_id == ECM


async def test_read_many_signals_in_chunks(
    adapter: SimulatedAdapter, definitions: Definitions
) -> None:
    c = Obd2Client(adapter, definitions.pids, max_pids_per_request=1)
    await c.connect()
    keys = list(c.supported_signals())
    assert {s.signal for s in await c.read_signals(keys)} == set(keys)


async def test_unsupported_signal(client: Obd2Client) -> None:
    with pytest.raises(KeyError):
        await client.read_signals(["fuel_pressure"])


async def test_dtcs_and_clear(client: Obd2Client) -> None:
    dtcs = await client.read_all_dtcs()
    assert {(d.code, d.kind) for d in dtcs} == {
        ("P0171", DtcKind.STORED),
        ("P0171", DtcKind.PERMANENT),
    }
    assert set(await client.clear_dtcs()) == {ECM, TCM}
    remaining = await client.read_all_dtcs()
    # Los permanentes no se borran con el servicio 04 (SAE J1979).
    assert [(d.code, d.kind) for d in remaining] == [("P0171", DtcKind.PERMANENT)]
    assert await client.read_freeze_frames() == []


async def test_freeze_frame(client: Obd2Client) -> None:
    [frame] = await client.read_freeze_frames()
    assert frame.source_id == ECM
    assert frame.dtc == "P0171"
    values = {s.signal: s.value for s in frame.values}
    assert values["engine_rpm"] == pytest.approx(742)
    assert values["coolant_temp"] == pytest.approx(89)
    assert values["maf"] == pytest.approx(2.15)


async def test_physical_unsupported_gets_negative_response(adapter: SimulatedAdapter) -> None:
    await adapter.connect()
    [response] = await adapter.request(DiagRequest(b"\x01\x0a", EcuAddress(0x7E0, ECM)))
    assert response.payload == bytes.fromhex("7F0131")
    assert await adapter.request(DiagRequest(b"\x01\x0a")) == []  # funcional: silencio


async def test_requires_connection(definitions: Definitions, adapter: SimulatedAdapter) -> None:
    with pytest.raises(NotConnectedError):
        await Obd2Client(adapter, definitions.pids).read_signals(["engine_rpm"])
    with pytest.raises(ConnectionError):
        await adapter.request(DiagRequest(b"\x01\x00"))


def test_seed_makes_simulation_reproducible(definitions: Definitions) -> None:
    clock_a, clock_b = FakeClock(), FakeClock()
    a = load_sim_vehicle(SIM_VEHICLE, definitions.pids, seed=7, clock=clock_a)
    b = load_sim_vehicle(SIM_VEHICLE, definitions.pids, seed=7, clock=clock_b)
    gen_a = a._ecus[0].generators["timing_advance"]
    gen_b = b._ecus[0].generators["timing_advance"]
    assert [gen_a.value(t / 10) for t in range(50)] == [gen_b.value(t / 10) for t in range(50)]


def test_incomplete_pid_is_reported(tmp_path: Path, definitions: Definitions) -> None:
    data = yaml.safe_load(SIM_VEHICLE.read_text(encoding="utf-8"))
    del data["ecus"][0]["signals"]["o2_b1s1_trim"]
    data["ecus"][0]["signals"]["no_existe"] = {"generator": "constant", "value": 1}
    broken = tmp_path / "vehiculo.yaml"
    broken.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DefinitionError) as info:
        load_sim_vehicle(broken, definitions.pids)
    messages = [str(i) for i in info.value.issues]
    assert any("o2_b1s1_trim" in m for m in messages)
    assert any("no_existe" in m and "no definida" in m for m in messages)
