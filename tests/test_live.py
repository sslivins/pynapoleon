"""Live integration smoke test.

Runs only when ``pytest -m live`` is requested AND credentials are present
in the environment (loaded from ``.env`` if available). Read-only — does
NOT toggle the user's actual fireplace.

Important: a single failed login here would burn one of the limited
wrong-password attempts on the user's Napoleon / Ayla account, so this
test does **exactly one** ``login()`` and never retries.
"""

from __future__ import annotations

import os

import pytest

from pynapoleon.client import NapoleonClient


pytestmark = pytest.mark.live


def _load_env() -> tuple[str | None, str | None, str | None]:
    """Load ``.env`` if present, then read the live-creds vars."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv()

    def _nz(name: str) -> str | None:
        v = os.environ.get(name)
        return v if v else None

    return _nz("NAPOLEON_EMAIL"), _nz("NAPOLEON_PASSWORD"), _nz("NAPOLEON_DSN")


async def test_live_login_and_state_readonly() -> None:
    """Log in, list devices, refresh one — never write."""
    email, password, dsn = _load_env()
    if not email or not password:
        pytest.skip(
            "NAPOLEON_EMAIL / NAPOLEON_PASSWORD not set; skipping live test"
        )

    # Optional app-id/secret overrides — only forward when BOTH are set.
    app_id = os.environ.get("NAPOLEON_APP_ID") or None
    app_secret = os.environ.get("NAPOLEON_APP_SECRET") or None
    kwargs: dict[str, str] = {}
    if app_id and app_secret:
        kwargs["app_id"] = app_id
        kwargs["app_secret"] = app_secret

    client = NapoleonClient(email, password, **kwargs)
    try:
        # Exactly ONE login attempt. Do not wrap in try/except for retry.
        await client.login()

        fireplaces = await client.fireplaces()
        assert fireplaces, "no Napoleon fireplaces visible to this account"

        if dsn:
            matches = [fp for fp in fireplaces if fp.dsn == dsn]
            assert matches, (
                f"NAPOLEON_DSN={dsn} not found. "
                f"Available: {[fp.dsn for fp in fireplaces]}"
            )
            fp = matches[0]
        else:
            fp = fireplaces[0]

        state = await fp.refresh()
        assert state.power is not None, (
            f"refresh() returned a state with no power flag: {state!r}"
        )
    finally:
        await client.close()
