"""High-level :class:`Fireplace` device class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aiohttp

from . import const as C
from .errors import (
    NapoleonApiError,
    NapoleonConnectionError,
    NapoleonNotFoundError,
    NapoleonValueError,
)
from .models import FireplaceInfo, FireplaceState

if TYPE_CHECKING:
    from ayla_iot_unofficial.device import Device as AylaDevice

    from .client import NapoleonClient


# ---------------------------------------------------------------------------
# Setpoint helpers (pure functions — easy to unit test)
# ---------------------------------------------------------------------------
def encode_setpoint_c(celsius: int) -> int:
    """Encode a Celsius setpoint into the wire integer (``°C - 18``)."""
    if celsius < C.TEMP_MIN_C:
        raise NapoleonValueError(
            f"set_temperature must be >= {C.TEMP_MIN_C} °C, got {celsius}"
        )
    if celsius > C.TEMP_MAX_C:
        raise NapoleonValueError(
            f"set_temperature must be <= {C.TEMP_MAX_C} °C, got {celsius}"
        )
    return celsius - C.TEMP_OFFSET_C


def decode_setpoint_c(raw: int) -> int:
    """Decode a wire integer back into Celsius."""
    return raw + C.TEMP_OFFSET_C


# ---------------------------------------------------------------------------
# Fireplace device
# ---------------------------------------------------------------------------
class Fireplace:
    """A single Napoleon fireplace, backed by an Ayla ``Device``."""

    def __init__(self, client: NapoleonClient, ayla_device: AylaDevice) -> None:
        self._client = client
        self._ayla_device = ayla_device
        self._state = FireplaceState()

    # -- identity ----------------------------------------------------------
    @property
    def dsn(self) -> str:
        # ayla_iot_unofficial exposes the device serial as ``_device_serial_number``
        # via the ``serial_number`` property; both are stable across versions.
        return self._ayla_device.serial_number

    @property
    def name(self) -> str:
        return self._ayla_device.name or self.dsn

    @property
    def ayla_device(self) -> AylaDevice:
        return self._ayla_device

    @property
    def info(self) -> FireplaceInfo:
        """Static device metadata for HA ``device_info`` registration.

        ayla-iot-unofficial 1.5 stores ``mac`` and ``lan_ip`` only as private
        instance attributes (``_device_mac_address`` / ``_device_ip_address``)
        and does not surface ``sw_version`` at all. We pull what we can and
        leave the rest as ``None`` rather than fabricate values.
        """
        dev = self._ayla_device

        def _str_or_none(v: Any) -> str | None:
            return str(v) if v else None

        return FireplaceInfo(
            dsn=self.dsn,
            name=self.name,
            model=_str_or_none(
                getattr(dev, "device_model_number", None)
                or getattr(dev, "oem_model_number", None)
            ),
            oem_model=_str_or_none(getattr(dev, "oem_model_number", None)),
            sw_version=None,
            mac=_str_or_none(getattr(dev, "_device_mac_address", None)),
            lan_ip=_str_or_none(getattr(dev, "_device_ip_address", None)),
        )

    @property
    def is_online(self) -> bool | None:
        """Whether the device is currently reachable from the cloud.

        ayla-iot-unofficial 1.5 does not surface a connection-status field on
        :class:`Device`, so we always return ``None`` for now. HA callers
        should treat ``None`` as "unknown" and avoid setting availability
        based on this value.
        """
        return None

    # -- state access ------------------------------------------------------
    @property
    def state(self) -> FireplaceState:
        return self._state

    async def refresh(self) -> FireplaceState:
        """Fetch the current property values and rebuild :attr:`state`.

        Token expiry is handled transparently by retrying once after
        :meth:`AylaApi.async_refresh_auth`.
        """
        from ayla_iot_unofficial.exc import (
            AylaAuthError,
            AylaAuthExpiringError,
            AylaNotAuthedError,
        )
        from .errors import NapoleonAuthError

        ayla = self._client.ayla_api
        try:
            await self._ayla_device.async_update()
        except (AylaAuthExpiringError, AylaNotAuthedError):
            try:
                await ayla.async_refresh_auth()
            except AylaAuthError as exc:
                raise NapoleonAuthError(f"token refresh failed: {exc}") from exc
            await self._ayla_device.async_update()
        except aiohttp.ClientError as exc:
            raise NapoleonConnectionError(
                f"refreshing device {self.dsn} failed: {exc}"
            ) from exc

        self._state = self._build_state()
        return self._state

    def _build_state(self) -> FireplaceState:
        pv = self._ayla_device.property_values

        def _get(name: str) -> Any:
            try:
                return pv[name]
            except (KeyError, AttributeError, TypeError):
                return None

        def _bool(v: Any) -> bool | None:
            return None if v is None else bool(int(v))

        def _int(v: Any) -> int | None:
            return None if v is None else int(v)

        def _rgb(r: Any, g: Any, b: Any) -> tuple[int, int, int] | None:
            if r is None or g is None or b is None:
                return None
            return (int(r), int(g), int(b))

        raw_setpoint = _get(C.PROP_SET_TEMPERATURE)
        setpoint_c = (
            decode_setpoint_c(int(raw_setpoint)) if raw_setpoint is not None else None
        )

        return FireplaceState(
            power=_bool(_get(C.PROP_POWER)),
            flame_speed=_int(_get(C.PROP_FLAME_SPEED)),
            orange_flame=_int(_get(C.PROP_ORANGE_FLAME)),
            yellow_flame=_int(_get(C.PROP_YELLOW_FLAME)),
            heater=_int(_get(C.PROP_HEATER)),
            setpoint_c=setpoint_c,
            eco_mode=_bool(_get(C.PROP_ECO_MODE)),
            boost_mode=_bool(_get(C.PROP_BOOST_MODE)),
            ember_bed_rgb=_rgb(
                _get(C.PROP_EMBER_BED_RED),
                _get(C.PROP_EMBER_BED_GREEN),
                _get(C.PROP_EMBER_BED_BLUE),
            ),
            ember_bed_brightness=_int(_get(C.PROP_EMBER_BED_BRIGHTNESS)),
            ember_bed_cycling=_bool(_get(C.PROP_EMBER_BED_CYCLING)),
            top_light_rgb=_rgb(
                _get(C.PROP_TOP_LIGHT_RED),
                _get(C.PROP_TOP_LIGHT_GREEN),
                _get(C.PROP_TOP_LIGHT_BLUE),
            ),
            top_light_cycling=_bool(_get(C.PROP_TOP_LIGHT_CYCLING)),
            current_favourite=_get(C.PROP_CURRENT_FAVOURITE),
        )

    # -- write helpers -----------------------------------------------------
    def _resolve_set_name(self, prop: str) -> str:
        """Return the SET-prefixed wire name for ``prop``.

        Looks up the explicit :data:`pynapoleon.const.SET_PROPERTY_NAMES` map
        first (the source of truth derived from the mitm capture). If the
        property isn't in the map we conservatively raise — silently writing
        to ``GET_xxx`` would be a no-op on the device.
        """
        try:
            return C.SET_PROPERTY_NAMES[prop]
        except KeyError as exc:
            raise NapoleonNotFoundError(
                f"property {prop!r} has no known SET-prefixed Ayla name; "
                "extend pynapoleon.const.SET_PROPERTY_NAMES to support it"
            ) from exc

    @property
    def _batch_url(self) -> str:
        dev = self._ayla_device
        # ayla-iot-unofficial>=1.5.0 exposes ``ads_url`` / ``eu_ads_url`` as
        # module-level constants on the device; older versions used class
        # attributes. Either way, the regional ADS host is the right base.
        base = (
            dev.eu_ads_url
            if getattr(dev, "europe", False)
            else dev.ads_url
        )
        return f"{base}/apiv1/batch_datapoints.json"

    async def _write_batch(self, values: dict[str, Any]) -> None:
        """Submit a single ``apiv1/batch_datapoints.json`` request.

        Routes through :meth:`NapoleonClient.ayla_request` so token expiry is
        handled transparently. Non-2xx responses are escalated as
        :class:`NapoleonApiError` (or :class:`NapoleonAuthError` for 401/403).
        """
        if not values:
            return
        datapoints = [
            {
                "datapoint": {"value": v},
                "dsn": self.dsn,
                "name": self._resolve_set_name(prop),
            }
            for prop, v in values.items()
        ]
        payload = {"batch_datapoints": datapoints}
        resp = await self._client.ayla_request(
            "post", self._batch_url, json=payload
        )
        try:
            body = await resp.text()
            status = resp.status
        finally:
            resp.release()

        if status in (401, 403):
            from .errors import NapoleonAuthError

            raise NapoleonAuthError(
                f"batch_datapoints rejected (HTTP {status}): {body[:512]}"
            )
        if status >= 400:
            raise NapoleonApiError(status, body)

    # -- public setters ----------------------------------------------------
    async def set_power(self, on: bool) -> None:
        await self._write_batch({C.PROP_POWER: 1 if on else 0})

    async def set_flame_speed(self, value: int) -> None:
        lo, hi = C.FLAME_SPEED_RANGE
        if not lo <= value <= hi:
            raise NapoleonValueError(
                f"flame_speed must be {lo}..{hi}, got {value}"
            )
        await self._write_batch({C.PROP_FLAME_SPEED: value})

    async def set_orange_flame(self, value: int) -> None:
        lo, hi = C.FLAME_COLOUR_RANGE
        if not lo <= value <= hi:
            raise NapoleonValueError(
                f"orange_flame must be {lo}..{hi}, got {value}"
            )
        await self._write_batch({C.PROP_ORANGE_FLAME: value})

    async def set_yellow_flame(self, value: int) -> None:
        lo, hi = C.FLAME_COLOUR_RANGE
        if not lo <= value <= hi:
            raise NapoleonValueError(
                f"yellow_flame must be {lo}..{hi}, got {value}"
            )
        await self._write_batch({C.PROP_YELLOW_FLAME: value})

    async def set_heater(self, value: int) -> None:
        if value not in C.HEATER_VALUES:
            raise NapoleonValueError(
                f"heater must be one of {C.HEATER_VALUES}, got {value}"
            )
        await self._write_batch({C.PROP_HEATER: value})

    async def set_setpoint_c(self, celsius: int) -> None:
        await self._write_batch(
            {C.PROP_SET_TEMPERATURE: encode_setpoint_c(celsius)}
        )

    async def set_eco_mode(self, on: bool) -> None:
        await self._write_batch({C.PROP_ECO_MODE: 1 if on else 0})

    async def set_boost_mode(self, on: bool) -> None:
        await self._write_batch({C.PROP_BOOST_MODE: 1 if on else 0})

    async def set_ember_bed_rgb(self, rgb: tuple[int, int, int]) -> None:
        r, g, b = rgb
        lo, hi = C.RGB_CHANNEL_RANGE
        for ch in (r, g, b):
            if not lo <= ch <= hi:
                raise NapoleonValueError(
                    f"ember_bed RGB channels must be {lo}..{hi}, got {rgb}"
                )
        await self._write_batch(
            {
                C.PROP_EMBER_BED_RED: r,
                C.PROP_EMBER_BED_GREEN: g,
                C.PROP_EMBER_BED_BLUE: b,
            }
        )

    async def set_ember_bed_brightness(self, value: int) -> None:
        lo, hi = C.EMBER_BED_BRIGHTNESS_RANGE
        if not lo <= value <= hi:
            raise NapoleonValueError(
                f"ember_bed_brightness must be {lo}..{hi}, got {value}"
            )
        await self._write_batch({C.PROP_EMBER_BED_BRIGHTNESS: value})

    async def set_ember_bed_cycling(self, on: bool) -> None:
        await self._write_batch({C.PROP_EMBER_BED_CYCLING: 1 if on else 0})

    async def set_top_light_rgb(self, rgb: tuple[int, int, int]) -> None:
        r, g, b = rgb
        lo, hi = C.RGB_CHANNEL_RANGE
        for ch in (r, g, b):
            if not lo <= ch <= hi:
                raise NapoleonValueError(
                    f"top_light RGB channels must be {lo}..{hi}, got {rgb}"
                )
        await self._write_batch(
            {
                C.PROP_TOP_LIGHT_RED: r,
                C.PROP_TOP_LIGHT_GREEN: g,
                C.PROP_TOP_LIGHT_BLUE: b,
            }
        )

    async def set_top_light_cycling(self, on: bool) -> None:
        await self._write_batch({C.PROP_TOP_LIGHT_CYCLING: 1 if on else 0})

    async def apply_favourite(self, slot: str) -> None:
        if slot not in C.FAVOURITES:
            raise NapoleonValueError(
                f"favourite must be one of {C.FAVOURITES}, got {slot!r}"
            )
        await self._write_batch(
            {
                C.PROP_CURRENT_FAVOURITE: slot,
                C.PROP_FAVOURITE_ACTIVE: 1,
            }
        )
