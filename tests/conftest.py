"""Shared pytest fixtures."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pynapoleon.client import NapoleonClient
from pynapoleon.device import Fireplace


class FakeResponse:
    """Minimal aiohttp-like response stub for _write_batch tests."""

    def __init__(self, status: int = 200, body: str = "{}") -> None:
        self.status = status
        self._body = body

    async def text(self) -> str:
        return self._body

    def release(self) -> None:
        return None


def _make_fake_ayla_device(
    *,
    serial: str = "AC000W032261383",
    name: str | None = "Living Room",
    properties_full: dict[str, Any] | None = None,
    property_values: dict[str, Any] | None = None,
    europe: bool = False,
    ads_url: str = "https://ads-field.aylanetworks.com",
    eu_ads_url: str = "https://ads-eu.aylanetworks.com",
) -> MagicMock:
    """Return a MagicMock shaped like ayla_iot_unofficial.device.Device.

    Only the attributes pynapoleon actually touches are populated.
    """
    dev = MagicMock(name=f"AylaDevice<{serial}>")
    dev.serial_number = serial
    dev.name = name
    dev.oem_model_number = "ASTOUND"
    dev.device_model_number = "GVF42"
    dev._device_mac_address = "aa:bb:cc:dd:ee:ff"
    dev._device_ip_address = "192.168.1.99"
    dev.europe = europe
    dev.ads_url = ads_url
    dev.eu_ads_url = eu_ads_url
    dev.properties_full = properties_full or {}
    dev.property_values = property_values or {}
    dev.async_update = AsyncMock()
    return dev


@pytest.fixture
def fake_ayla_device():  # type: ignore[no-untyped-def]
    return _make_fake_ayla_device


@pytest.fixture
def fake_response():  # type: ignore[no-untyped-def]
    return FakeResponse


@pytest.fixture
def stub_client():  # type: ignore[no-untyped-def]
    """A NapoleonClient whose ``ayla_request`` is an AsyncMock returning a 200.

    Tests can override ``client.ayla_request.return_value`` /
    ``side_effect`` on a per-test basis.
    """

    def _build(response: FakeResponse | None = None) -> NapoleonClient:
        client = NapoleonClient("user@example.test", "pw")
        # Don't actually log in — install a stub Ayla session so that
        # ``client.ayla_api`` returns successfully, and patch the request seam.
        client._ayla = MagicMock(name="StubAylaApi")  # type: ignore[assignment]
        client._ayla.async_refresh_auth = AsyncMock()
        client.ayla_request = AsyncMock(  # type: ignore[method-assign]
            return_value=response or FakeResponse()
        )
        return client

    return _build


@pytest.fixture
def fireplace_factory(stub_client, fake_ayla_device):  # type: ignore[no-untyped-def]
    """Compose a Fireplace from a stub client + fake ayla device."""

    def _build(
        *,
        property_values: dict[str, Any] | None = None,
        properties_full: dict[str, Any] | None = None,
        response: FakeResponse | None = None,
    ) -> tuple[Fireplace, NapoleonClient, MagicMock]:
        client = stub_client(response=response)
        dev = fake_ayla_device(
            property_values=property_values,
            properties_full=properties_full,
        )
        return Fireplace(client, dev), client, dev

    return _build


@pytest.fixture
def setpoint_property_values() -> dict[str, Any]:
    """A typical Napoleon `property_values` snapshot."""
    return {
        "power_on_off": 1,
        "flame_speed": 3,
        "orange_flame": 2,
        "yellow_flame": 4,
        "heater": 1,
        "set_temperature": 5,
        "eco_mode": 0,
        "boost_mode": 1,
        "ember_bed_red": 255,
        "ember_bed_green": 128,
        "ember_bed_blue": 0,
        "ember_bed_brightness": 3,
        "ember_bed_cycling": 1,
        "top_light_red": 10,
        "top_light_green": 20,
        "top_light_blue": 30,
        "top_light_cycling": 0,
        "current_viewing_favourites": "partytime",
    }
