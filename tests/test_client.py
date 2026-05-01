"""Tests for ``NapoleonClient`` login lifecycle and device filtering."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from ayla_iot_unofficial.exc import (
    AylaAuthError,
    AylaAuthExpiringError,
    AylaNotAuthedError,
)

from pynapoleon.client import NapoleonClient, _looks_like_napoleon
from pynapoleon.errors import NapoleonAuthError, NapoleonConnectionError


def _make_ayla_device_stub(
    *,
    serial: str,
    properties_full: dict | None = None,
):
    dev = MagicMock(name=f"AylaDevice<{serial}>")
    dev.serial_number = serial
    dev.name = serial
    dev.async_update = AsyncMock()
    dev.properties_full = properties_full or {}
    dev.property_values = {}
    dev.europe = False
    dev.ads_url = "https://ads-field.aylanetworks.com"
    dev.eu_ads_url = "https://ads-eu.aylanetworks.com"
    return dev


@pytest.mark.unit
def test_looks_like_napoleon_positive():
    dev = _make_ayla_device_stub(
        serial="AC1",
        properties_full={
            "power_on_off": object(),
            "flame_speed": object(),
            "extra": object(),
        },
    )
    assert _looks_like_napoleon(dev) is True


@pytest.mark.unit
def test_looks_like_napoleon_missing_required():
    dev = _make_ayla_device_stub(
        serial="AC2",
        properties_full={"power_on_off": object()},  # no flame_speed
    )
    assert _looks_like_napoleon(dev) is False


@pytest.mark.unit
def test_looks_like_napoleon_empty():
    dev = _make_ayla_device_stub(serial="AC3", properties_full={})
    assert _looks_like_napoleon(dev) is False


@pytest.mark.unit
def test_looks_like_napoleon_none():
    dev = MagicMock()
    dev.properties_full = None
    assert _looks_like_napoleon(dev) is False


@pytest.mark.auth
async def test_login_translates_auth_error():
    client = NapoleonClient("e", "p")
    fake_ayla = AsyncMock()
    fake_ayla.async_sign_in = AsyncMock(side_effect=AylaAuthError("bad creds"))
    with patch("pynapoleon.client.AylaApi", return_value=fake_ayla):
        with pytest.raises(NapoleonAuthError):
            await client.login()


@pytest.mark.auth
async def test_login_translates_connection_error():
    client = NapoleonClient("e", "p")
    fake_ayla = AsyncMock()
    fake_ayla.async_sign_in = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("dns")
    )
    with patch("pynapoleon.client.AylaApi", return_value=fake_ayla):
        with pytest.raises(NapoleonConnectionError):
            await client.login()


@pytest.mark.auth
async def test_login_idempotent():
    client = NapoleonClient("e", "p")
    fake_ayla = AsyncMock()
    fake_ayla.async_sign_in = AsyncMock()
    with patch("pynapoleon.client.AylaApi", return_value=fake_ayla) as ctor:
        await client.login()
        await client.login()  # second call is a no-op
    assert ctor.call_count == 1
    assert fake_ayla.async_sign_in.await_count == 1


@pytest.mark.auth
async def test_ayla_request_retries_on_auth_expiring():
    client = NapoleonClient("e", "p")
    expected = MagicMock()
    fake_ayla = AsyncMock()
    fake_ayla.async_request = AsyncMock(
        side_effect=[AylaAuthExpiringError("expiring"), expected]
    )
    fake_ayla.async_refresh_auth = AsyncMock()
    client._ayla = fake_ayla
    result = await client.ayla_request("get", "https://example/api")
    assert result is expected
    assert fake_ayla.async_request.await_count == 2
    assert fake_ayla.async_refresh_auth.await_count == 1


@pytest.mark.auth
async def test_ayla_request_retries_on_not_authed():
    client = NapoleonClient("e", "p")
    expected = MagicMock()
    fake_ayla = AsyncMock()
    fake_ayla.async_request = AsyncMock(
        side_effect=[AylaNotAuthedError("expired"), expected]
    )
    fake_ayla.async_refresh_auth = AsyncMock()
    client._ayla = fake_ayla
    result = await client.ayla_request("post", "https://example/api")
    assert result is expected


@pytest.mark.auth
async def test_ayla_request_refresh_failure_translates():
    client = NapoleonClient("e", "p")
    fake_ayla = AsyncMock()
    fake_ayla.async_request = AsyncMock(
        side_effect=AylaAuthExpiringError("expiring")
    )
    fake_ayla.async_refresh_auth = AsyncMock(
        side_effect=AylaAuthError("refresh denied")
    )
    client._ayla = fake_ayla
    with pytest.raises(NapoleonAuthError):
        await client.ayla_request("get", "https://x/y")


@pytest.mark.auth
async def test_ayla_request_translates_client_error():
    client = NapoleonClient("e", "p")
    fake_ayla = AsyncMock()
    fake_ayla.async_request = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("eof")
    )
    client._ayla = fake_ayla
    with pytest.raises(NapoleonConnectionError):
        await client.ayla_request("get", "https://x/y")


@pytest.mark.auth
async def test_ayla_request_persistent_auth_failure_after_refresh():
    client = NapoleonClient("e", "p")
    fake_ayla = AsyncMock()
    fake_ayla.async_request = AsyncMock(
        side_effect=[
            AylaAuthExpiringError("expiring"),
            AylaNotAuthedError("still expired"),
        ]
    )
    fake_ayla.async_refresh_auth = AsyncMock()
    client._ayla = fake_ayla
    with pytest.raises(NapoleonAuthError):
        await client.ayla_request("get", "https://x/y")


@pytest.mark.unit
def test_ayla_api_property_requires_login():
    client = NapoleonClient("e", "p")
    with pytest.raises(NapoleonAuthError):
        _ = client.ayla_api


@pytest.mark.auth
async def test_ayla_request_unwraps_request_context_manager():
    """Regression: ayla-iot-unofficial's ``async_request`` is ``async def``
    that returns ``session.request(...)`` *without* awaiting it, so awaiting
    the coroutine yields an aiohttp ``_RequestContextManager``. Our wrapper
    must await that manager a second time so callers receive a real
    ``ClientResponse`` (with ``.status``, ``.text()``, ``.release()`` etc.).
    Bug surfaced as
    ``'_BaseRequestContextManager' object has no attribute 'release'``.
    """
    from aiohttp.client import _RequestContextManager

    expected = MagicMock(name="ClientResponse")

    async def _fake_request_coro():
        return expected

    cm = _RequestContextManager(_fake_request_coro())
    fake_ayla = AsyncMock()
    fake_ayla.async_request = AsyncMock(return_value=cm)
    client = NapoleonClient("e", "p")
    client._ayla = fake_ayla

    result = await client.ayla_request("get", "https://example/api")

    assert result is expected



    client = NapoleonClient("e", "p")
    fire = _make_ayla_device_stub(
        serial="AC_FIRE",
        properties_full={
            "power_on_off": object(),
            "flame_speed": object(),
        },
    )
    not_fire = _make_ayla_device_stub(
        serial="VAC1",
        properties_full={"unrelated": object()},
    )
    fake_ayla = AsyncMock()
    fake_ayla.async_get_devices = AsyncMock(return_value=[fire, not_fire])
    client._ayla = fake_ayla

    fps = await client.fireplaces()
    assert len(fps) == 1
    assert fps[0].dsn == "AC_FIRE"
    # Both devices should have been refreshed (ayla 1.5 returns possibly-stale
    # devices), even the non-fireplace.
    assert fire.async_update.await_count == 1
    assert not_fire.async_update.await_count == 1


@pytest.mark.unit
async def test_fireplaces_translates_connection_error_on_list():
    client = NapoleonClient("e", "p")
    fake_ayla = AsyncMock()
    fake_ayla.async_get_devices = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("dns")
    )
    client._ayla = fake_ayla
    with pytest.raises(NapoleonConnectionError):
        await client.fireplaces()


@pytest.mark.unit
async def test_fireplaces_recovers_from_auth_expiry():
    client = NapoleonClient("e", "p")
    fire = _make_ayla_device_stub(
        serial="AC_FIRE",
        properties_full={"power_on_off": object(), "flame_speed": object()},
    )
    fake_ayla = AsyncMock()
    fake_ayla.async_get_devices = AsyncMock(
        side_effect=[AylaAuthExpiringError("x"), [fire]]
    )
    fake_ayla.async_refresh_auth = AsyncMock()
    client._ayla = fake_ayla
    fps = await client.fireplaces()
    assert len(fps) == 1
    assert fake_ayla.async_refresh_auth.await_count == 1


@pytest.mark.unit
async def test_close_releases_owned_session():
    """Close should sign out and close the websession iff we own it."""
    client = NapoleonClient("e", "p")
    fake_ayla = AsyncMock()
    fake_ayla.async_sign_out = AsyncMock()
    fake_session = MagicMock()
    fake_session.closed = False
    fake_session.close = AsyncMock()
    fake_ayla.websession = fake_session
    client._ayla = fake_ayla
    client._owns_session = True
    await client.close()
    assert fake_ayla.async_sign_out.await_count == 1
    assert fake_session.close.await_count == 1
    assert client._ayla is None


@pytest.mark.unit
async def test_close_does_not_close_external_session():
    client = NapoleonClient("e", "p", websession=MagicMock())
    fake_ayla = AsyncMock()
    fake_ayla.async_sign_out = AsyncMock()
    fake_session = MagicMock()
    fake_session.closed = False
    fake_session.close = AsyncMock()
    fake_ayla.websession = fake_session
    client._ayla = fake_ayla
    # Default _owns_session is False after __init__
    await client.close()
    assert fake_session.close.await_count == 0
