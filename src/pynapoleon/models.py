"""Typed data models for pynapoleon."""

from __future__ import annotations

from dataclasses import dataclass

from .const import MANUFACTURER, SCHEDULE_CONST_FIELD
from .errors import NapoleonValueError


@dataclass
class FireplaceState:
    """Snapshot of a fireplace's properties (Celsius for setpoint)."""

    power: bool | None = None
    flame_speed: int | None = None
    orange_flame: int | None = None
    yellow_flame: int | None = None
    heater: int | None = None
    setpoint_c: int | None = None
    eco_mode: bool | None = None
    boost_mode: bool | None = None
    ember_bed_rgb: tuple[int, int, int] | None = None
    ember_bed_brightness: int | None = None
    ember_bed_cycling: bool | None = None
    top_light_rgb: tuple[int, int, int] | None = None
    top_light_cycling: bool | None = None
    current_favourite: str | None = None


@dataclass
class FireplaceInfo:
    """Static-ish identification metadata, suitable for HA ``device_info``.

    All fields are optional because Ayla does not always populate every
    attribute. Consumers should treat empty strings the same as ``None``.
    """

    dsn: str
    name: str
    manufacturer: str = MANUFACTURER
    model: str | None = None
    oem_model: str | None = None
    sw_version: str | None = None
    mac: str | None = None
    lan_ip: str | None = None


@dataclass
class DaySchedule:
    """One day in the weekly schedule.

    Wire format is six space-separated integers:
        ``"sH sM 5 eH eM enabled"``

    The middle ``5`` is constant across all observed captures. Its meaning is
    unknown, but the value MUST be preserved byte-for-byte on writes.
    """

    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    enabled: bool
    # Preserves the constant middle field. Defaults to the only observed value.
    middle: int = SCHEDULE_CONST_FIELD

    @classmethod
    def parse(cls, raw: str) -> DaySchedule:
        parts = raw.strip().split()
        if len(parts) != 6:
            raise NapoleonValueError(
                f"day_schedule must have 6 fields, got {len(parts)}: {raw!r}"
            )
        try:
            sh, sm, mid, eh, em, en = (int(p) for p in parts)
        except ValueError as exc:
            raise NapoleonValueError(
                f"day_schedule fields must be integers: {raw!r}"
            ) from exc
        return cls(
            start_hour=sh,
            start_minute=sm,
            end_hour=eh,
            end_minute=em,
            enabled=bool(en),
            middle=mid,
        )

    def encode(self) -> str:
        return (
            f"{self.start_hour} {self.start_minute} {self.middle} "
            f"{self.end_hour} {self.end_minute} {1 if self.enabled else 0}"
        )
