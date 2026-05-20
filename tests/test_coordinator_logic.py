"""Tests for the coordinator's energy-accumulation logic.

These are pure-logic tests that do NOT require a real device or
Home Assistant runtime — the ``SolarManagerApiClient`` is stubbed
so we can feed controlled payloads into the coordinator.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.solar_manager_local.models import DeviceData, PointData
from custom_components.solar_manager_local.coordinator import (
    SolarManagerDataCoordinator,
)


def _make_coordinator() -> SolarManagerDataCoordinator:
    """Build a coordinator with stubbed HA dependencies."""
    entry = AsyncMock()
    entry.entry_id = "test_entry"
    entry.data = {
        "base_url": "http://fake",
        "api_key": "fake-key",
    }

    hass = AsyncMock()
    hass.data = {}

    with patch(
        "custom_components.solar_manager_local.coordinator.async_get_clientsession"
    ), patch(
        "homeassistant.helpers.frame.report_usage"
    ):
        coord = SolarManagerDataCoordinator(hass, entry)

    return coord


def _fake_point(
    pW: float = 100,
    cW: float = 50,
    pWh: float = 10,
    t: str = "2025-01-01T00:00:00",
) -> PointData:
    return PointData(
        production_power_w=pW,
        consumption_power_w=cW,
        interval_production_wh=pWh,
        timestamp=t,
        devices=[],
        raw={"pW": pW, "cW": cW, "pWh": pWh, "t": t},
    )


async def _update(coord: SolarManagerDataCoordinator, point: PointData) -> PointData:
    """Simulate a coordinator update cycle with the given API payload."""
    client = AsyncMock()
    client.async_get_point = AsyncMock(return_value=point)
    coord._client = client
    return await coord._async_update_data()


# ------------------------------------------------------------------
# Basic accumulation
# ------------------------------------------------------------------


async def test_accumulates_energy() -> None:
    coord = _make_coordinator()
    await _update(coord, _fake_point(pWh=500, t="t1"))
    assert coord.produced_energy_kwh == pytest.approx(0.5)

    await _update(coord, _fake_point(pWh=500, t="t2"))
    assert coord.produced_energy_kwh == pytest.approx(1.0)


async def test_deduplicates_same_timestamp() -> None:
    coord = _make_coordinator()
    await _update(coord, _fake_point(pWh=500, t="t1"))
    await _update(coord, _fake_point(pWh=500, t="t1"))
    # Second call has same timestamp → should NOT accumulate
    assert coord.produced_energy_kwh == pytest.approx(0.5)


async def test_negative_pWh_ignored() -> None:
    coord = _make_coordinator()
    await _update(coord, _fake_point(pWh=-100, t="t1"))
    assert coord.produced_energy_kwh == pytest.approx(0.0)


# ------------------------------------------------------------------
# set_initial_produced_energy_kwh
# ------------------------------------------------------------------


async def test_set_initial_positive() -> None:
    coord = _make_coordinator()
    coord.set_initial_produced_energy_kwh(42.5)
    assert coord.produced_energy_kwh == pytest.approx(42.5)

    await _update(coord, _fake_point(pWh=1000, t="t1"))
    assert coord.produced_energy_kwh == pytest.approx(43.5)


async def test_set_initial_negative_rejected() -> None:
    coord = _make_coordinator()
    coord.set_initial_produced_energy_kwh(-1.0)
    assert coord.produced_energy_kwh == pytest.approx(0.0)


# ------------------------------------------------------------------
# Data passthrough
# ------------------------------------------------------------------


async def test_data_contains_point_data() -> None:
    coord = _make_coordinator()
    result = await _update(coord, _fake_point(pWh=200, t="t1"))
    assert isinstance(result, PointData)
    assert coord.produced_energy_kwh == pytest.approx(0.2)


async def test_original_fields_preserved() -> None:
    coord = _make_coordinator()
    result = await _update(coord, _fake_point(pW=123, cW=456, pWh=0, t="t1"))
    assert result.production_power_w == 123
    assert result.consumption_power_w == 456


def test_device_data_parses_optional_soc() -> None:
    battery = DeviceData.from_dict({"_id": "battery-1", "power": -500, "soc": 74})
    assert battery.soc == pytest.approx(74)

    consumer = DeviceData.from_dict({"_id": "consumer-1", "power": 120})
    assert consumer.soc is None


def test_point_data_parses_soc_from_regular_device() -> None:
    point = PointData.from_dict(
        {
            "devices": [
                {
                    "_id": "65730a15aa8f51290b7d472c",
                    "activeDevice": -1,
                    "eWh": 14.28,
                    "iWh": 0,
                    "power": -5270,
                    "signal": "connected",
                    "soc": 20,
                }
            ]
        }
    )

    assert point.devices[0].device_id == "65730a15aa8f51290b7d472c"
    assert point.devices[0].power == pytest.approx(-5270)
    assert point.devices[0].soc == pytest.approx(20)
