"""Tests for ``Fireplace._build_state`` (read-side property decoding)."""

from __future__ import annotations

import pytest


@pytest.mark.get_params
async def test_refresh_decodes_full_property_snapshot(
    fireplace_factory, setpoint_property_values
):
    fp, _, ayla_dev = fireplace_factory(property_values=setpoint_property_values)
    state = await fp.refresh()
    assert ayla_dev.async_update.await_count == 1

    assert state.power is True
    assert state.flame_speed == 3
    assert state.orange_flame == 2
    assert state.yellow_flame == 4
    assert state.heater == 1
    assert state.setpoint_c == 23  # 5 + 18
    assert state.eco_mode is False
    assert state.boost_mode is True
    assert state.ember_bed_rgb == (255, 128, 0)
    assert state.ember_bed_brightness == 3
    assert state.ember_bed_cycling is True
    assert state.top_light_rgb == (10, 20, 30)
    assert state.top_light_cycling is False
    assert state.current_favourite == "partytime"


@pytest.mark.get_params
async def test_refresh_handles_missing_properties_as_none(fireplace_factory):
    fp, _, _ = fireplace_factory(property_values={})
    state = await fp.refresh()
    assert state.power is None
    assert state.setpoint_c is None
    assert state.ember_bed_rgb is None
    assert state.top_light_rgb is None


@pytest.mark.get_params
async def test_refresh_handles_partial_rgb_as_none(fireplace_factory):
    pv = {
        "ember_bed_red": 100,
        # green missing → entire rgb tuple should be None
        "ember_bed_blue": 50,
    }
    fp, _, _ = fireplace_factory(property_values=pv)
    state = await fp.refresh()
    assert state.ember_bed_rgb is None


@pytest.mark.get_params
def test_info_pulls_metadata_from_ayla_device(fireplace_factory):
    fp, _, _ = fireplace_factory()
    info = fp.info
    assert info.dsn == "AC000W032261383"
    assert info.name == "Living Room"
    assert info.manufacturer == "Napoleon"
    assert info.mac == "aa:bb:cc:dd:ee:ff"
    assert info.lan_ip == "192.168.1.99"
    assert info.sw_version is None  # ayla 1.5 doesn't surface this


@pytest.mark.get_params
def test_is_online_returns_none_until_supported(fireplace_factory):
    fp, _, _ = fireplace_factory()
    assert fp.is_online is None
