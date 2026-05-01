"""Tests for ``Fireplace._write_batch`` HTTP error routing and URL selection."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pynapoleon.errors import (
    NapoleonApiError,
    NapoleonAuthError,
    NapoleonNotFoundError,
)


@pytest.mark.set_params
async def test_write_batch_posts_to_ads_url_with_dsn(fireplace_factory):
    fp, client, _ = fireplace_factory()
    await fp.set_power(True)
    args, kwargs = client.ayla_request.call_args
    method, url = args
    assert method == "post"
    assert url == "https://ads-field.aylanetworks.com/apiv1/batch_datapoints.json"
    payload = kwargs["json"]
    assert payload == {
        "batch_datapoints": [
            {
                "datapoint": {"value": 1},
                "dsn": "AC000W032261383",
                "name": "power_on_off",
            }
        ]
    }


@pytest.mark.set_params
async def test_write_batch_uses_eu_url_when_europe(fireplace_factory):
    fp, client, ayla_dev = fireplace_factory()
    ayla_dev.europe = True
    await fp.set_power(False)
    args, _ = client.ayla_request.call_args
    _, url = args
    assert url == "https://ads-eu.aylanetworks.com/apiv1/batch_datapoints.json"


@pytest.mark.set_params
async def test_write_batch_no_op_for_empty_values(fireplace_factory):
    fp, client, _ = fireplace_factory()
    await fp._write_batch({})
    assert client.ayla_request.await_count == 0


@pytest.mark.set_params
@pytest.mark.parametrize("status", [401, 403])
async def test_write_batch_401_403_raises_auth_error(
    fireplace_factory, fake_response, status
):
    fp, _, _ = fireplace_factory(response=fake_response(status=status, body="forbidden"))
    with pytest.raises(NapoleonAuthError):
        await fp.set_power(True)


@pytest.mark.set_params
@pytest.mark.parametrize("status", [400, 404, 422, 500, 503])
async def test_write_batch_4xx_5xx_raises_api_error(
    fireplace_factory, fake_response, status
):
    fp, _, _ = fireplace_factory(response=fake_response(status=status, body="boom"))
    with pytest.raises(NapoleonApiError) as exc_info:
        await fp.set_power(True)
    assert exc_info.value.status == status
    assert "boom" in exc_info.value.body


@pytest.mark.set_params
async def test_resolve_set_name_raises_for_unknown_property(fireplace_factory):
    fp, _, _ = fireplace_factory()
    with pytest.raises(NapoleonNotFoundError):
        fp._resolve_set_name("nonexistent_property")


@pytest.mark.set_params
async def test_set_power_combines_into_single_batch(fireplace_factory):
    fp, client, _ = fireplace_factory()
    await fp.set_ember_bed_rgb((10, 20, 30))
    # Single HTTP call for all three RGB channels.
    assert client.ayla_request.await_count == 1
    args, kwargs = client.ayla_request.call_args
    names = [dp["name"] for dp in kwargs["json"]["batch_datapoints"]]
    assert sorted(names) == ["ember_bed_blue", "ember_bed_green", "ember_bed_red"]


@pytest.mark.set_params
async def test_refresh_recovers_from_auth_expiring(fireplace_factory):
    """If the underlying device update raises AylaAuthExpiringError once, the
    Fireplace should refresh the token and retry the update transparently."""
    from ayla_iot_unofficial.exc import AylaAuthExpiringError

    fp, client, ayla_dev = fireplace_factory(property_values={"power_on_off": 1})

    # First call raises, second succeeds.
    ayla_dev.async_update = AsyncMock(side_effect=[AylaAuthExpiringError("expired"), None])

    # Inject a stub ayla_api with refresh_auth that succeeds.
    fake_ayla = AsyncMock()
    fake_ayla.async_refresh_auth = AsyncMock()
    client._ayla = fake_ayla

    state = await fp.refresh()
    assert ayla_dev.async_update.await_count == 2
    assert fake_ayla.async_refresh_auth.await_count == 1
    assert state.power is True
