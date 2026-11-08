"""Codificación/decodificación OBD2 según SAE J1979, con ejemplos de la norma."""

from __future__ import annotations

import pytest

from diag.core.protocols import obd2
from diag.core.protocols.constants import Obd2Service


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b"\x01\x33", "P0133"),
        (b"\x41\x23", "C0123"),
        (b"\x92\x34", "B1234"),
        (b"\xc1\x00", "U0100"),
        (b"\x3f\xff", "P3FFF"),
    ],
)
def test_dtc_roundtrip(raw: bytes, code: str) -> None:
    assert obd2.decode_dtc(raw) == code
    assert obd2.encode_dtc(code) == raw


@pytest.mark.parametrize("code", ["X0100", "P4000", "P01", "P01G0"])
def test_encode_dtc_rejects_invalid(code: str) -> None:
    with pytest.raises(ValueError):
        obd2.encode_dtc(code)


def test_supported_pids_example() -> None:
    # Ejemplo clásico: respuesta 41 00 BE 1F A8 13.
    expected = {
        0x01,
        0x03,
        0x04,
        0x05,
        0x06,
        0x07,
        0x0C,
        0x0D,
        0x0E,
        0x0F,
        0x10,
        0x11,
        0x13,
        0x15,
        0x1C,
        0x1F,
        0x20,
    }
    assert obd2.decode_supported_pids(0x00, bytes.fromhex("BE1FA813")) == expected
    assert obd2.encode_supported_pids(0x00, expected) == bytes.fromhex("BE1FA813")


def test_supported_mask_sets_next_range_flag() -> None:
    mask = obd2.encode_supported_pids(0x00, {0x0C, 0x42})
    assert 0x20 in obd2.decode_supported_pids(0x00, mask)


def test_multi_pid_response() -> None:
    payload = bytes.fromhex("41 0C 1A F8 05 7B 0D 32".replace(" ", ""))
    data = obd2.parse_current_data_response(payload, {0x0C: 2, 0x05: 1, 0x0D: 1})
    assert data == {0x0C: b"\x1a\xf8", 0x05: b"\x7b", 0x0D: b"\x32"}


@pytest.mark.parametrize(
    "payload",
    [
        bytes.fromhex("410C1A"),  # faltan bytes
        bytes.fromhex("41FF00"),  # PID desconocido
        bytes.fromhex("420C1AF8"),  # SID equivocado
        b"",
    ],
)
def test_malformed_current_data(payload: bytes) -> None:
    with pytest.raises(obd2.ProtocolError):
        obd2.parse_current_data_response(payload, {0x0C: 2})


def test_request_limits() -> None:
    assert obd2.build_current_data_request([0x0C, 0x0D]) == b"\x01\x0c\x0d"
    with pytest.raises(ValueError):
        obd2.build_current_data_request(list(range(7)))


def test_dtc_response_can_and_legacy() -> None:
    can = bytes.fromhex("43020133C123")
    legacy = bytes.fromhex("430133C1230000")
    service = Obd2Service.STORED_DTC
    assert obd2.parse_dtc_response(can, service, has_count_byte=True) == ["P0133", "U0123"]
    assert obd2.parse_dtc_response(legacy, service, has_count_byte=False) == ["P0133", "U0123"]


def test_dtc_response_build_roundtrip() -> None:
    payload = obd2.build_dtc_response(0x07, ["P0300", "P0171"], has_count_byte=True)
    assert obd2.parse_dtc_response(payload, 0x07, has_count_byte=True) == ["P0300", "P0171"]


def test_vin_roundtrip() -> None:
    payload = obd2.build_vin_response("1HGCM82633A004352")
    assert obd2.parse_vin_response(payload) == "1HGCM82633A004352"


def test_vin_invalid() -> None:
    with pytest.raises(obd2.ProtocolError):
        obd2.parse_vin_response(bytes.fromhex("490201") + b"\x00" * 17)


def test_negative_response() -> None:
    assert obd2.negative_response_code(bytes.fromhex("7F0131"), 0x01) == 0x31
    assert obd2.negative_response_code(bytes.fromhex("410C1AF8"), 0x01) is None


def test_freeze_frame_roundtrip() -> None:
    payload = obd2.build_freeze_frame_response(0x0C, 0, b"\x1a\xf8")
    assert obd2.parse_freeze_frame_response(payload, {0x0C: 2}) == (0x0C, 0, b"\x1a\xf8")
