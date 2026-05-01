"""High-level Napoleon client.

Wraps an :mod:`ayla-iot-unofficial` session with Napoleon-specific defaults
(app id/secret, property mapping) and exposes :class:`Fireplace` objects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aiohttp
from ayla_iot_unofficial import AylaApi
from ayla_iot_unofficial.exc import (
    AylaAuthError,
    AylaAuthExpiringError,
    AylaNotAuthedError,
)

from .const import DEFAULT_APP_ID, DEFAULT_APP_SECRET, NAPOLEON_REQUIRED_PROPERTIES
from .errors import (
    NapoleonAuthError,
    NapoleonConnectionError,
)

if TYPE_CHECKING:
    from .device import Fireplace


class NapoleonClient:
    """Async client for the Napoleon (Ayla) cloud."""

    def __init__(
        self,
        email: str,
        password: str,
        app_id: str = DEFAULT_APP_ID,
        app_secret: str = DEFAULT_APP_SECRET,
        *,
        europe: bool = False,
        websession: aiohttp.ClientSession | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._app_id = app_id
        self._app_secret = app_secret
        self._europe = europe
        self._external_session = websession
        self._ayla: AylaApi | None = None
        # Whether *we* allocated the underlying websession (and thus must
        # close it). When the caller injects a session we never close it.
        self._owns_session = False

    async def __aenter__(self) -> NapoleonClient:
        await self.login()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @property
    def ayla_api(self) -> AylaApi:
        """Underlying Ayla API session (for power users / tests)."""
        if self._ayla is None:
            raise NapoleonAuthError("client is not logged in; call login() first")
        return self._ayla

    async def login(self) -> None:
        """Authenticate against the Ayla cloud."""
        if self._ayla is not None:
            return
        ayla = AylaApi(
            self._email,
            self._password,
            self._app_id,
            self._app_secret,
            europe=self._europe,
            websession=self._external_session,
        )
        try:
            await ayla.async_sign_in()
        except AylaAuthError as exc:
            raise NapoleonAuthError(str(exc)) from exc
        except aiohttp.ClientError as exc:
            raise NapoleonConnectionError(f"sign-in failed: {exc}") from exc
        self._ayla = ayla
        # If the caller didn't provide a websession, ensure_session() will have
        # lazily created one which we own.
        self._owns_session = self._external_session is None

    async def ayla_request(
        self, method: str, url: str, **kwargs: Any
    ) -> aiohttp.ClientResponse:
        """Issue an Ayla API request, retrying once on token expiry.

        ``ayla-iot-unofficial`` raises :class:`AylaAuthExpiringError` /
        :class:`AylaNotAuthedError` when the access token is past (or near)
        its TTL. We catch those, refresh, and retry exactly once. Any further
        auth failure is escalated to :class:`NapoleonAuthError`.
        """
        ayla = self.ayla_api
        try:
            return await ayla.async_request(method, url, **kwargs)
        except (AylaAuthExpiringError, AylaNotAuthedError):
            try:
                await ayla.async_refresh_auth()
            except AylaAuthError as exc:
                raise NapoleonAuthError(
                    f"token refresh failed: {exc}"
                ) from exc
            try:
                return await ayla.async_request(method, url, **kwargs)
            except (AylaAuthExpiringError, AylaNotAuthedError) as exc:
                raise NapoleonAuthError(
                    f"still unauthenticated after refresh: {exc}"
                ) from exc
        except aiohttp.ClientError as exc:
            raise NapoleonConnectionError(
                f"{method.upper()} {url} failed: {exc}"
            ) from exc

    async def fireplaces(self) -> list[Fireplace]:
        """Return all Napoleon fireplaces visible to this account.

        Each returned :class:`Fireplace` has its property cache pre-populated
        via one ``async_update()`` call. Non-Napoleon Ayla devices on the
        same account (if any) are filtered out — a device is considered a
        Napoleon fireplace only when its property catalog contains the keys
        in :data:`pynapoleon.const.NAPOLEON_REQUIRED_PROPERTIES`.
        """
        from .device import Fireplace  # local import avoids cycle

        ayla = self.ayla_api
        try:
            devices = await ayla.async_get_devices()
        except (AylaAuthExpiringError, AylaNotAuthedError):
            await ayla.async_refresh_auth()
            devices = await ayla.async_get_devices()
        except aiohttp.ClientError as exc:
            raise NapoleonConnectionError(
                f"listing devices failed: {exc}"
            ) from exc

        fireplaces: list[Fireplace] = []
        for dev in devices:
            try:
                await dev.async_update()
            except (AylaAuthExpiringError, AylaNotAuthedError):
                await ayla.async_refresh_auth()
                await dev.async_update()
            except aiohttp.ClientError as exc:
                raise NapoleonConnectionError(
                    f"refreshing device {getattr(dev, 'serial_number', '?')}"
                    f" failed: {exc}"
                ) from exc

            if not _looks_like_napoleon(dev):
                continue
            fireplaces.append(Fireplace(self, dev))
        return fireplaces

    async def close(self) -> None:
        """Sign out and release the underlying Ayla session."""
        ayla = self._ayla
        self._ayla = None
        if ayla is None:
            return
        try:
            await ayla.async_sign_out()
        except Exception:
            # Best-effort sign-out; never let cleanup mask a real error.
            pass
        if self._owns_session:
            session = getattr(ayla, "websession", None)
            if session is not None and not session.closed:
                await session.close()
        self._owns_session = False


def _looks_like_napoleon(ayla_device: Any) -> bool:
    """Return True iff ``ayla_device`` exposes the Napoleon property surface."""
    full = getattr(ayla_device, "properties_full", None) or {}
    if not full:
        return False
    return NAPOLEON_REQUIRED_PROPERTIES.issubset(full.keys())
