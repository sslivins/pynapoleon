"""Pure-function encoding tests (no network)."""

from __future__ import annotations

import pytest

from pynapoleon.device import decode_setpoint_c, encode_setpoint_c
from pynapoleon.errors import NapoleonValueError
from pynapoleon.models import DaySchedule


@pytest.mark.unit
@pytest.mark.parametrize(
    ("celsius", "wire"),
    [(18, 0), (19, 1), (23, 5), (30, 12)],
)
def test_setpoint_round_trip(celsius: int, wire: int) -> None:
    assert encode_setpoint_c(celsius) == wire
    assert decode_setpoint_c(wire) == celsius


@pytest.mark.unit
def test_setpoint_below_min_rejected() -> None:
    with pytest.raises(NapoleonValueError):
        encode_setpoint_c(17)


@pytest.mark.unit
def test_day_schedule_round_trip() -> None:
    raw = "8 30 5 22 0 1"
    sched = DaySchedule.parse(raw)
    assert sched.start_hour == 8
    assert sched.start_minute == 30
    assert sched.middle == 5
    assert sched.end_hour == 22
    assert sched.end_minute == 0
    assert sched.enabled is True
    assert sched.encode() == raw


@pytest.mark.unit
def test_day_schedule_disabled_round_trip() -> None:
    raw = "0 0 5 0 0 0"
    sched = DaySchedule.parse(raw)
    assert sched.enabled is False
    assert sched.encode() == raw


@pytest.mark.unit
@pytest.mark.parametrize("bad", ["1 2 3 4 5", "a b c d e f", "8 30 5 22 0"])
def test_day_schedule_bad_format(bad: str) -> None:
    with pytest.raises(NapoleonValueError):
        DaySchedule.parse(bad)
