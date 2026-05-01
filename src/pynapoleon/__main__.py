"""Smoke / debugging CLI: ``python -m pynapoleon``.

Subcommands:

* ``login``                 — verify credentials work, exit 0 / non-zero
* ``list``                  — list discovered fireplaces (DSN + name)
* ``state [--dsn DSN]``     — print the current state of one fireplace as JSON
* ``set <prop> <value> [--dsn DSN]``
                            — write a single property (e.g. ``power on``,
                              ``flame_speed 3``, ``setpoint_c 20``,
                              ``favourite partytime``)

DSN resolution: ``--dsn`` flag → ``NAPOLEON_DSN`` env var → auto-pick when
the account has exactly one fireplace; otherwise the CLI exits with a
helpful list of devices.

This is intended as a developer / smoke tool, NOT a long-lived process,
so each invocation does exactly one ``login()`` and one ``close()``.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import sys
from typing import Any

from . import const as C
from .client import NapoleonClient
from .device import Fireplace
from .errors import NapoleonAuthError, NapoleonError, NapoleonValueError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _maybe_load_dotenv() -> None:
    """Best-effort load of ``.env`` next to the CWD.

    ``python-dotenv`` is a *test* extra, so we import it optionally — when
    the package is installed normally (e.g. from PyPI) the CLI still works
    using only the real process environment.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _env(name: str) -> str | None:
    """Return ``os.environ[name]`` only when it is set AND non-empty.

    Empty-string secrets in CI must NOT override the constants in
    :mod:`pynapoleon.const`.
    """
    val = os.environ.get(name)
    return val if val else None


def _build_client_from_env() -> NapoleonClient:
    email = _env("NAPOLEON_EMAIL")
    password = _env("NAPOLEON_PASSWORD")
    if not email or not password:
        raise SystemExit(
            "NAPOLEON_EMAIL and NAPOLEON_PASSWORD must be set "
            "(via process env or a .env file)."
        )
    kwargs: dict[str, Any] = {}
    app_id = _env("NAPOLEON_APP_ID")
    app_secret = _env("NAPOLEON_APP_SECRET")
    if (app_id is None) != (app_secret is None):
        raise SystemExit(
            "NAPOLEON_APP_ID and NAPOLEON_APP_SECRET must be set together "
            "(or both omitted to use the built-in defaults)."
        )
    if app_id and app_secret:
        kwargs["app_id"] = app_id
        kwargs["app_secret"] = app_secret
    return NapoleonClient(email, password, **kwargs)


def _resolve_fireplace(
    fireplaces: list[Fireplace], dsn: str | None
) -> Fireplace:
    if dsn:
        for fp in fireplaces:
            if fp.dsn == dsn:
                return fp
        raise SystemExit(
            f"DSN {dsn!r} not found. Visible fireplaces: "
            + ", ".join(fp.dsn for fp in fireplaces)
        )
    if len(fireplaces) == 1:
        return fireplaces[0]
    if not fireplaces:
        raise SystemExit("No Napoleon fireplaces found on this account.")
    listing = "\n".join(f"  {fp.dsn}\t{fp.name}" for fp in fireplaces)
    raise SystemExit(
        "Multiple fireplaces found; specify one with --dsn or NAPOLEON_DSN:\n"
        + listing
    )


def _state_to_json(fp: Fireplace) -> str:
    payload = {
        "dsn": fp.dsn,
        "name": fp.name,
        "state": dataclasses.asdict(fp.state),
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# `set` value parsing
# ---------------------------------------------------------------------------
_BOOL_ON = {"on", "true", "1", "yes"}
_BOOL_OFF = {"off", "false", "0", "no"}


def _parse_bool(s: str) -> bool:
    low = s.strip().lower()
    if low in _BOOL_ON:
        return True
    if low in _BOOL_OFF:
        return False
    raise NapoleonValueError(f"expected on/off, got {s!r}")


def _parse_int(s: str) -> int:
    try:
        return int(s.strip(), 0)
    except ValueError as exc:
        raise NapoleonValueError(f"expected integer, got {s!r}") from exc


async def _apply_set(fp: Fireplace, prop: str, value: str) -> None:
    p = prop.strip().lower()
    if p == "power":
        await fp.set_power(_parse_bool(value))
    elif p == "flame_speed":
        await fp.set_flame_speed(_parse_int(value))
    elif p == "orange_flame":
        await fp.set_orange_flame(_parse_int(value))
    elif p == "yellow_flame":
        await fp.set_yellow_flame(_parse_int(value))
    elif p == "heater":
        await fp.set_heater(_parse_int(value))
    elif p in ("setpoint_c", "setpoint"):
        await fp.set_setpoint_c(_parse_int(value))
    elif p == "eco":
        await fp.set_eco_mode(_parse_bool(value))
    elif p == "boost":
        await fp.set_boost_mode(_parse_bool(value))
    elif p == "ember_brightness":
        await fp.set_ember_bed_brightness(_parse_int(value))
    elif p == "ember_cycling":
        await fp.set_ember_bed_cycling(_parse_bool(value))
    elif p == "top_light_cycling":
        await fp.set_top_light_cycling(_parse_bool(value))
    elif p == "favourite":
        await fp.apply_favourite(value.strip().lower())
    else:
        raise NapoleonValueError(
            f"unknown set property {prop!r}. Supported: power, flame_speed, "
            "orange_flame, yellow_flame, heater, setpoint_c, eco, boost, "
            "ember_brightness, ember_cycling, top_light_cycling, favourite"
        )


# ---------------------------------------------------------------------------
# Subcommand runners
# ---------------------------------------------------------------------------
async def _cmd_login(_args: argparse.Namespace) -> int:
    client = _build_client_from_env()
    try:
        await client.login()
        print(f"OK {client._email}")  # noqa: SLF001  (CLI diagnostic only)
        return 0
    finally:
        await client.close()


async def _cmd_list(_args: argparse.Namespace) -> int:
    client = _build_client_from_env()
    try:
        await client.login()
        fireplaces = await client.fireplaces()
        if not fireplaces:
            print("(no Napoleon fireplaces found)")
            return 0
        for fp in fireplaces:
            print(f"{fp.dsn}\t{fp.name}")
        return 0
    finally:
        await client.close()


async def _cmd_state(args: argparse.Namespace) -> int:
    dsn = args.dsn or _env("NAPOLEON_DSN")
    client = _build_client_from_env()
    try:
        await client.login()
        fireplaces = await client.fireplaces()
        fp = _resolve_fireplace(fireplaces, dsn)
        await fp.refresh()
        print(_state_to_json(fp))
        return 0
    finally:
        await client.close()


async def _cmd_set(args: argparse.Namespace) -> int:
    dsn = args.dsn or _env("NAPOLEON_DSN")
    client = _build_client_from_env()
    try:
        await client.login()
        fireplaces = await client.fireplaces()
        fp = _resolve_fireplace(fireplaces, dsn)
        await _apply_set(fp, args.prop, args.value)
        print(f"OK {fp.dsn} {args.prop}={args.value}")
        return 0
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# argparse plumbing
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pynapoleon",
        description="Smoke / debug CLI for the Napoleon (Ayla) cloud API.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="verify credentials")
    sub.add_parser("list", help="list discovered fireplaces")

    p_state = sub.add_parser("state", help="dump current state as JSON")
    p_state.add_argument("--dsn", help="device serial; auto-picked if only one")

    p_set = sub.add_parser("set", help="write one property")
    p_set.add_argument("--dsn", help="device serial; auto-picked if only one")
    p_set.add_argument("prop", help=f"property name (favourites: {C.FAVOURITES})")
    p_set.add_argument("value", help="value (on/off, int, or favourite slot)")

    return parser


_DISPATCH = {
    "login": _cmd_login,
    "list": _cmd_list,
    "state": _cmd_state,
    "set": _cmd_set,
}


def main(argv: list[str] | None = None) -> int:
    _maybe_load_dotenv()
    parser = _build_parser()
    args = parser.parse_args(argv)
    runner = _DISPATCH[args.cmd]
    try:
        return asyncio.run(runner(args))
    except NapoleonAuthError as exc:
        print(f"auth error: {exc}", file=sys.stderr)
        return 2
    except NapoleonValueError as exc:
        print(f"value error: {exc}", file=sys.stderr)
        return 3
    except NapoleonError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
