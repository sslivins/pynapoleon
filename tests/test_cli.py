"""Unit tests for the ``pynapoleon`` CLI (``__main__``).

These exercise argument parsing, env handling, fireplace resolution, and
subcommand dispatch. The CLI is mocked end-to-end against
:class:`NapoleonClient` so no network calls happen here.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pynapoleon import __main__ as cli
from pynapoleon.errors import NapoleonAuthError, NapoleonError, NapoleonValueError
from pynapoleon.models import FireplaceState


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _mock_fp(dsn: str, name: str = "FP") -> MagicMock:
    fp = MagicMock()
    fp.dsn = dsn
    fp.name = name
    fp.state = FireplaceState(power=True, setpoint_c=20)
    fp.refresh = AsyncMock(return_value=fp.state)
    fp.set_power = AsyncMock()
    fp.set_flame_speed = AsyncMock()
    fp.set_orange_flame = AsyncMock()
    fp.set_yellow_flame = AsyncMock()
    fp.set_heater = AsyncMock()
    fp.set_setpoint_c = AsyncMock()
    fp.set_eco_mode = AsyncMock()
    fp.set_boost_mode = AsyncMock()
    fp.set_ember_bed_brightness = AsyncMock()
    fp.set_ember_bed_cycling = AsyncMock()
    fp.set_top_light_cycling = AsyncMock()
    fp.apply_favourite = AsyncMock()
    return fp


def _patch_client(monkeypatch: pytest.MonkeyPatch, fps: list[Any]) -> MagicMock:
    """Patch ``NapoleonClient`` so any constructor returns the same mock."""
    client = MagicMock()
    client._email = "user@example.com"
    client.login = AsyncMock()
    client.fireplaces = AsyncMock(return_value=fps)
    client.close = AsyncMock()
    monkeypatch.setattr(cli, "NapoleonClient", MagicMock(return_value=client))
    return client


def _set_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NAPOLEON_EMAIL", "user@example.com")
    monkeypatch.setenv("NAPOLEON_PASSWORD", "pw")
    monkeypatch.delenv("NAPOLEON_APP_ID", raising=False)
    monkeypatch.delenv("NAPOLEON_APP_SECRET", raising=False)
    monkeypatch.delenv("NAPOLEON_DSN", raising=False)
    # Prevent main() from loading the developer's local .env file mid-test.
    monkeypatch.setattr(cli, "_maybe_load_dotenv", lambda: None)


# ---------------------------------------------------------------------------
# parsers
# ---------------------------------------------------------------------------
class TestParsers:
    @pytest.mark.parametrize("s", ["on", "ON", "true", "1", "yes"])
    def test_parse_bool_true(self, s: str) -> None:
        assert cli._parse_bool(s) is True

    @pytest.mark.parametrize("s", ["off", "OFF", "false", "0", "no"])
    def test_parse_bool_false(self, s: str) -> None:
        assert cli._parse_bool(s) is False

    def test_parse_bool_invalid(self) -> None:
        with pytest.raises(NapoleonValueError):
            cli._parse_bool("maybe")

    def test_parse_int(self) -> None:
        assert cli._parse_int("3") == 3
        assert cli._parse_int(" 7 ") == 7

    def test_parse_int_invalid(self) -> None:
        with pytest.raises(NapoleonValueError):
            cli._parse_int("abc")


# ---------------------------------------------------------------------------
# env helpers
# ---------------------------------------------------------------------------
class TestEnv:
    def test_env_unset_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NAPOLEON_FOO", raising=False)
        assert cli._env("NAPOLEON_FOO") is None

    def test_env_empty_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NAPOLEON_FOO", "")
        assert cli._env("NAPOLEON_FOO") is None

    def test_env_set_returns_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NAPOLEON_FOO", "bar")
        assert cli._env("NAPOLEON_FOO") == "bar"


# ---------------------------------------------------------------------------
# build_client_from_env
# ---------------------------------------------------------------------------
class TestBuildClientFromEnv:
    def test_missing_creds_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NAPOLEON_EMAIL", raising=False)
        monkeypatch.delenv("NAPOLEON_PASSWORD", raising=False)
        with pytest.raises(SystemExit):
            cli._build_client_from_env()

    def test_empty_creds_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NAPOLEON_EMAIL", "")
        monkeypatch.setenv("NAPOLEON_PASSWORD", "")
        with pytest.raises(SystemExit):
            cli._build_client_from_env()

    def test_app_id_without_secret_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_creds(monkeypatch)
        monkeypatch.setenv("NAPOLEON_APP_ID", "x")
        monkeypatch.delenv("NAPOLEON_APP_SECRET", raising=False)
        with pytest.raises(SystemExit):
            cli._build_client_from_env()

    def test_empty_app_id_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_creds(monkeypatch)
        monkeypatch.setenv("NAPOLEON_APP_ID", "")
        monkeypatch.setenv("NAPOLEON_APP_SECRET", "")
        ctor = MagicMock()
        monkeypatch.setattr(cli, "NapoleonClient", ctor)
        cli._build_client_from_env()
        ctor.assert_called_once_with("user@example.com", "pw")

    def test_full_overrides_passed_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_creds(monkeypatch)
        monkeypatch.setenv("NAPOLEON_APP_ID", "myid")
        monkeypatch.setenv("NAPOLEON_APP_SECRET", "mysec")
        ctor = MagicMock()
        monkeypatch.setattr(cli, "NapoleonClient", ctor)
        cli._build_client_from_env()
        ctor.assert_called_once_with(
            "user@example.com", "pw", app_id="myid", app_secret="mysec"
        )


# ---------------------------------------------------------------------------
# resolve_fireplace
# ---------------------------------------------------------------------------
class TestResolveFireplace:
    def test_dsn_match(self) -> None:
        a, b = _mock_fp("AAA"), _mock_fp("BBB")
        assert cli._resolve_fireplace([a, b], "BBB") is b

    def test_dsn_not_found(self) -> None:
        with pytest.raises(SystemExit):
            cli._resolve_fireplace([_mock_fp("AAA")], "ZZZ")

    def test_single_auto_pick(self) -> None:
        a = _mock_fp("AAA")
        assert cli._resolve_fireplace([a], None) is a

    def test_multiple_no_dsn_errors(self) -> None:
        with pytest.raises(SystemExit):
            cli._resolve_fireplace([_mock_fp("AAA"), _mock_fp("BBB")], None)

    def test_empty_errors(self) -> None:
        with pytest.raises(SystemExit):
            cli._resolve_fireplace([], None)


# ---------------------------------------------------------------------------
# apply_set dispatch
# ---------------------------------------------------------------------------
class TestApplySet:
    @pytest.mark.parametrize(
        ("prop", "value", "method", "called_with"),
        [
            ("power", "on", "set_power", True),
            ("power", "off", "set_power", False),
            ("flame_speed", "3", "set_flame_speed", 3),
            ("orange_flame", "2", "set_orange_flame", 2),
            ("yellow_flame", "4", "set_yellow_flame", 4),
            ("heater", "1", "set_heater", 1),
            ("setpoint_c", "20", "set_setpoint_c", 20),
            ("setpoint", "21", "set_setpoint_c", 21),
            ("eco", "on", "set_eco_mode", True),
            ("boost", "off", "set_boost_mode", False),
            ("ember_brightness", "2", "set_ember_bed_brightness", 2),
            ("ember_cycling", "on", "set_ember_bed_cycling", True),
            ("top_light_cycling", "off", "set_top_light_cycling", False),
            ("favourite", "PartyTime", "apply_favourite", "partytime"),
        ],
    )
    async def test_dispatch(
        self, prop: str, value: str, method: str, called_with: Any
    ) -> None:
        fp = _mock_fp("AAA")
        await cli._apply_set(fp, prop, value)
        getattr(fp, method).assert_awaited_once_with(called_with)

    async def test_unknown_prop(self) -> None:
        fp = _mock_fp("AAA")
        with pytest.raises(NapoleonValueError):
            await cli._apply_set(fp, "nope", "1")


# ---------------------------------------------------------------------------
# state_to_json
# ---------------------------------------------------------------------------
def test_state_to_json_round_trips() -> None:
    fp = _mock_fp("AAA", "Living Room")
    fp.state = FireplaceState(power=True, setpoint_c=22, ember_bed_rgb=(1, 2, 3))
    out = json.loads(cli._state_to_json(fp))
    assert out["dsn"] == "AAA"
    assert out["name"] == "Living Room"
    assert out["state"]["power"] is True
    assert out["state"]["setpoint_c"] == 22


# ---------------------------------------------------------------------------
# main() end-to-end with mocked client
# ---------------------------------------------------------------------------
class TestMain:
    def test_login_ok(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _set_creds(monkeypatch)
        client = _patch_client(monkeypatch, [])
        rc = cli.main(["login"])
        assert rc == 0
        client.login.assert_awaited_once()
        client.close.assert_awaited_once()
        assert "OK user@example.com" in capsys.readouterr().out

    def test_login_auth_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_creds(monkeypatch)
        client = _patch_client(monkeypatch, [])
        client.login.side_effect = NapoleonAuthError("bad creds")
        rc = cli.main(["login"])
        assert rc == 2
        # Exactly ONE login attempt.
        assert client.login.await_count == 1

    def test_value_error_returns_3(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_creds(monkeypatch)
        _patch_client(monkeypatch, [_mock_fp("AAA")])
        rc = cli.main(["set", "nope", "1"])
        assert rc == 3

    def test_generic_error_returns_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_creds(monkeypatch)
        client = _patch_client(monkeypatch, [])
        client.login.side_effect = NapoleonError("kaboom")
        rc = cli.main(["login"])
        assert rc == 1

    def test_list_two(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _set_creds(monkeypatch)
        _patch_client(
            monkeypatch, [_mock_fp("AAA", "Living"), _mock_fp("BBB", "Den")]
        )
        rc = cli.main(["list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "AAA\tLiving" in out
        assert "BBB\tDen" in out

    def test_list_empty_prints_message(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _set_creds(monkeypatch)
        _patch_client(monkeypatch, [])
        rc = cli.main(["list"])
        assert rc == 0
        assert "no Napoleon fireplaces" in capsys.readouterr().out

    def test_state_auto_picks_single(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _set_creds(monkeypatch)
        fp = _mock_fp("AAA", "Living")
        _patch_client(monkeypatch, [fp])
        rc = cli.main(["state"])
        assert rc == 0
        fp.refresh.assert_awaited_once()
        out = json.loads(capsys.readouterr().out)
        assert out["dsn"] == "AAA"

    def test_state_multiple_without_dsn_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_creds(monkeypatch)
        _patch_client(
            monkeypatch, [_mock_fp("AAA"), _mock_fp("BBB")]
        )
        # SystemExit propagates through main() because it isn't a NapoleonError.
        with pytest.raises(SystemExit):
            cli.main(["state"])

    def test_state_uses_dsn_env(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _set_creds(monkeypatch)
        monkeypatch.setenv("NAPOLEON_DSN", "BBB")
        a, b = _mock_fp("AAA"), _mock_fp("BBB", "Den")
        _patch_client(monkeypatch, [a, b])
        rc = cli.main(["state"])
        assert rc == 0
        b.refresh.assert_awaited_once()
        a.refresh.assert_not_called()
        out = json.loads(capsys.readouterr().out)
        assert out["dsn"] == "BBB"

    def test_set_writes_property(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _set_creds(monkeypatch)
        fp = _mock_fp("AAA")
        _patch_client(monkeypatch, [fp])
        rc = cli.main(["set", "flame_speed", "4"])
        assert rc == 0
        fp.set_flame_speed.assert_awaited_once_with(4)
        assert "OK AAA flame_speed=4" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _maybe_load_dotenv silently passes when dotenv is absent
# ---------------------------------------------------------------------------
def test_maybe_load_dotenv_without_dotenv_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulate dotenv being unavailable; must not raise."""
    real_import = __import__

    def fake_import(
        name: str,
        globals_: dict[str, Any] | None = None,
        locals_: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "dotenv":
            raise ImportError("simulated")
        return real_import(name, globals_, locals_, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        cli._maybe_load_dotenv()  # should be a no-op
