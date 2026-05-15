"""Validation tests for ``Fireplace.set_*`` setters.

These exercise pure parameter validation — they do NOT submit any HTTP
requests because the validation happens before ``_write_batch``.
"""

from __future__ import annotations

import pytest

from pynapoleon import const as C
from pynapoleon.errors import NapoleonValueError


@pytest.mark.set_params
@pytest.mark.parametrize("bad", [-1, 0, 6, 99])
async def test_set_flame_speed_rejects_out_of_range(fireplace_factory, bad):
    fp, _, _ = fireplace_factory()
    with pytest.raises(NapoleonValueError):
        await fp.set_flame_speed(bad)


@pytest.mark.set_params
@pytest.mark.parametrize("good", [1, 3, 5])
async def test_set_flame_speed_accepts_in_range(fireplace_factory, good):
    fp, _, _ = fireplace_factory()
    await fp.set_flame_speed(good)


@pytest.mark.set_params
@pytest.mark.parametrize("bad", [-1, 5, 6, 99])
async def test_set_orange_flame_rejects_out_of_range(fireplace_factory, bad):
    fp, _, _ = fireplace_factory()
    with pytest.raises(NapoleonValueError):
        await fp.set_orange_flame(bad)


@pytest.mark.set_params
@pytest.mark.parametrize("bad", [-1, 5, 6, 99])
async def test_set_yellow_flame_rejects_out_of_range(fireplace_factory, bad):
    fp, _, _ = fireplace_factory()
    with pytest.raises(NapoleonValueError):
        await fp.set_yellow_flame(bad)


@pytest.mark.set_params
@pytest.mark.parametrize("bad", [-1, 3, 99])
async def test_set_heater_rejects_unknown(fireplace_factory, bad):
    fp, _, _ = fireplace_factory()
    with pytest.raises(NapoleonValueError):
        await fp.set_heater(bad)


@pytest.mark.set_params
@pytest.mark.parametrize("good", list(C.HEATER_VALUES))
async def test_set_heater_accepts_known(fireplace_factory, good):
    fp, _, _ = fireplace_factory()
    await fp.set_heater(good)


@pytest.mark.set_params
@pytest.mark.parametrize("bad_c", [17, 0, 31, -5])
async def test_set_setpoint_rejects_out_of_range(fireplace_factory, bad_c):
    fp, _, _ = fireplace_factory()
    with pytest.raises(NapoleonValueError):
        await fp.set_setpoint_c(bad_c)


@pytest.mark.set_params
async def test_set_setpoint_writes_celsius_minus_offset(fireplace_factory):
    fp, client, _ = fireplace_factory()
    await fp.set_setpoint_c(23)
    args, kwargs = client.ayla_request.call_args
    payload = kwargs["json"]
    assert payload == {
        "batch_datapoints": [
            {
                "datapoint": {"value": 5},
                "dsn": "AC000W032261383",
                "name": "set_temperature",
            }
        ]
    }


@pytest.mark.set_params
@pytest.mark.parametrize(
    ("user_value", "wire_value"),
    [(0, 5), (1, 4), (2, 3), (3, 2), (4, 1)],
)
async def test_set_orange_flame_inverts_wire_value(
    fireplace_factory, user_value, wire_value
):
    """User passes the natural scale; pynapoleon writes the inverted wire value."""
    fp, client, _ = fireplace_factory()
    await fp.set_orange_flame(user_value)
    args, kwargs = client.ayla_request.call_args
    payload = kwargs["json"]
    assert payload == {
        "batch_datapoints": [
            {
                "datapoint": {"value": wire_value},
                "dsn": "AC000W032261383",
                "name": "orange_flame",
            }
        ]
    }


@pytest.mark.set_params
@pytest.mark.parametrize(
    ("user_value", "wire_value"),
    [(0, 5), (1, 4), (2, 3), (3, 2), (4, 1)],
)
async def test_set_yellow_flame_inverts_wire_value(
    fireplace_factory, user_value, wire_value
):
    fp, client, _ = fireplace_factory()
    await fp.set_yellow_flame(user_value)
    args, kwargs = client.ayla_request.call_args
    payload = kwargs["json"]
    assert payload == {
        "batch_datapoints": [
            {
                "datapoint": {"value": wire_value},
                "dsn": "AC000W032261383",
                "name": "yellow_flame",
            }
        ]
    }


@pytest.mark.set_params
@pytest.mark.parametrize("bad_rgb", [(-1, 0, 0), (0, 256, 0), (0, 0, 999)])
async def test_set_ember_bed_rgb_rejects_out_of_range(fireplace_factory, bad_rgb):
    fp, _, _ = fireplace_factory()
    with pytest.raises(NapoleonValueError):
        await fp.set_ember_bed_rgb(bad_rgb)


@pytest.mark.set_params
@pytest.mark.parametrize("bad_rgb", [(-1, 0, 0), (0, 256, 0)])
async def test_set_top_light_rgb_rejects_out_of_range(fireplace_factory, bad_rgb):
    fp, _, _ = fireplace_factory()
    with pytest.raises(NapoleonValueError):
        await fp.set_top_light_rgb(bad_rgb)


@pytest.mark.set_params
@pytest.mark.parametrize("bad", [-1, 5, 99])
async def test_set_ember_bed_brightness_rejects_out_of_range(fireplace_factory, bad):
    fp, _, _ = fireplace_factory()
    with pytest.raises(NapoleonValueError):
        await fp.set_ember_bed_brightness(bad)


@pytest.mark.set_params
async def test_apply_favourite_rejects_unknown(fireplace_factory):
    fp, _, _ = fireplace_factory()
    with pytest.raises(NapoleonValueError):
        await fp.apply_favourite("not_a_real_scene")


@pytest.mark.set_params
@pytest.mark.parametrize("slot", list(C.FAVOURITES))
async def test_apply_favourite_writes_name_and_active(fireplace_factory, slot):
    fp, client, _ = fireplace_factory()
    await fp.apply_favourite(slot)
    args, kwargs = client.ayla_request.call_args
    payload = kwargs["json"]
    names = {dp["name"]: dp["datapoint"]["value"] for dp in payload["batch_datapoints"]}
    assert names == {
        "current_viewing_favourites": slot,
        "favourite_active": 1,
    }
