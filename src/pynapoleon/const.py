"""Constants for the Napoleon fireplace API.

All values were extracted from a mitmproxy capture of the official Napoleon
mobile app. The Napoleon backend is the Ayla Networks IoT platform; these are
Ayla property names on a Napoleon-tenant device.
"""

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
MANUFACTURER = "Napoleon"

# ---------------------------------------------------------------------------
# Ayla application credentials
# ---------------------------------------------------------------------------
# Shipped inside the Napoleon mobile app — not cryptographic secrets, anyone
# with mitmproxy can extract them. Consumers may override.
DEFAULT_APP_ID = "smarthome_dev-rA-hQ-id"
DEFAULT_APP_SECRET = (
    "smarthome_dev-BBeF7xY8xfKBfNcFIx-rhQhA2YY-h64jEJ5ZhCy9GOaWiy0XkbnGc1g"
)

# ---------------------------------------------------------------------------
# Property names (Ayla property "name" field)
# ---------------------------------------------------------------------------
PROP_POWER = "power_on_off"
PROP_FLAME_SPEED = "flame_speed"
PROP_ORANGE_FLAME = "orange_flame"
PROP_YELLOW_FLAME = "yellow_flame"
PROP_HEATER = "heater"
PROP_SET_TEMPERATURE = "set_temperature"
PROP_ECO_MODE = "eco_mode"
PROP_BOOST_MODE = "boost_mode"

PROP_EMBER_BED_RED = "ember_bed_red"
PROP_EMBER_BED_GREEN = "ember_bed_green"
PROP_EMBER_BED_BLUE = "ember_bed_blue"
PROP_EMBER_BED_BRIGHTNESS = "ember_bed_brightness"
PROP_EMBER_BED_CYCLING = "ember_bed_cycling"

PROP_TOP_LIGHT_RED = "top_light_red"
PROP_TOP_LIGHT_GREEN = "top_light_green"
PROP_TOP_LIGHT_BLUE = "top_light_blue"
PROP_TOP_LIGHT_CYCLING = "top_light_cycling"

PROP_CURRENT_FAVOURITE = "current_viewing_favourites"
PROP_FAVOURITE_ACTIVE = "favourite_active"

# Day schedules — `'sH sM 5 eH eM enabled'` — middle 5 is constant, meaning
# unknown but must be preserved on write.
SCHEDULE_PROPS = (
    "monday_schedule",
    "tuesday_schedule",
    "wednesday_schedule",
    "thursday_schedule",
    "friday_schedule",
    "saturday_schedule",
    "sunday_schedule",
)
SCHEDULE_CONST_FIELD = 5

# ---------------------------------------------------------------------------
# Explicit property → wire (Ayla) name map for writes
# ---------------------------------------------------------------------------
# ayla-iot-unofficial collapses ``SET_xxx`` properties down to ``xxx`` in its
# public ``properties_full`` dict via ``_clean_property_name``. The wire name
# we need for ``batch_datapoints.json`` and the single-property ``datapoints``
# endpoint is whatever the Napoleon backend stores — we extracted these
# verbatim from the mitm capture.
#
# Observation from the capture: every property on the Napoleon tenant is
# written with a *lowercase* name and (with one exception) **no** ``set_``
# prefix. The single exception is the user setpoint, whose Ayla name is
# already ``set_temperature``. ayla-iot-unofficial's ``_clean_property_name``
# only strips *uppercase* ``SET_``/``GET_`` prefixes, so the cleaned key
# remains ``set_temperature`` in ``properties_full`` — the wire name and the
# read-side key are identical.
#
# This map is therefore the source of truth — do NOT derive the wire name
# from the cleaned property name.
SET_PROPERTY_NAMES: dict[str, str] = {
    PROP_POWER: "power_on_off",
    PROP_FLAME_SPEED: "flame_speed",
    PROP_ORANGE_FLAME: "orange_flame",
    PROP_YELLOW_FLAME: "yellow_flame",
    PROP_HEATER: "heater",
    PROP_SET_TEMPERATURE: "set_temperature",
    PROP_ECO_MODE: "eco_mode",
    PROP_BOOST_MODE: "boost_mode",
    PROP_EMBER_BED_RED: "ember_bed_red",
    PROP_EMBER_BED_GREEN: "ember_bed_green",
    PROP_EMBER_BED_BLUE: "ember_bed_blue",
    PROP_EMBER_BED_BRIGHTNESS: "ember_bed_brightness",
    PROP_EMBER_BED_CYCLING: "ember_bed_cycling",
    PROP_TOP_LIGHT_RED: "top_light_red",
    PROP_TOP_LIGHT_GREEN: "top_light_green",
    PROP_TOP_LIGHT_BLUE: "top_light_blue",
    PROP_TOP_LIGHT_CYCLING: "top_light_cycling",
    PROP_CURRENT_FAVOURITE: "current_viewing_favourites",
    PROP_FAVOURITE_ACTIVE: "favourite_active",
    "monday_schedule": "monday_schedule",
    "tuesday_schedule": "tuesday_schedule",
    "wednesday_schedule": "wednesday_schedule",
    "thursday_schedule": "thursday_schedule",
    "friday_schedule": "friday_schedule",
    "saturday_schedule": "saturday_schedule",
    "sunday_schedule": "sunday_schedule",
}

# ---------------------------------------------------------------------------
# Temperature encoding
# ---------------------------------------------------------------------------
# `set_temperature` is transmitted as integer (°C - 18). 0 is the lowest value
# the app permits (= 18 °C). The upper bound is unverified — observed max
# value on the wire was 5 (= 23 °C). Setting it conservatively at 30 °C until
# live tests confirm the real ceiling; values above this are rejected.
TEMP_OFFSET_C = 18
TEMP_MIN_C = 18
TEMP_MAX_C = 30

# ---------------------------------------------------------------------------
# Capability ranges (inclusive on both ends)
# ---------------------------------------------------------------------------
FLAME_SPEED_RANGE = (1, 5)
FLAME_COLOUR_RANGE = (0, 5)  # orange_flame, yellow_flame
EMBER_BED_BRIGHTNESS_RANGE = (0, 4)
RGB_CHANNEL_RANGE = (0, 255)

# ---------------------------------------------------------------------------
# Favourite scene slot identifiers
# ---------------------------------------------------------------------------
FAVOURITES = ("partytime", "campfirewarmth", "summerday", "glowingsunset")

# ---------------------------------------------------------------------------
# Heater values
# ---------------------------------------------------------------------------
# Observed: 1, 2. Assumption (unverified): 0 = off.
HEATER_VALUES = (0, 1, 2)

# ---------------------------------------------------------------------------
# Set of properties that identify a Napoleon fireplace among other Ayla
# devices on the same account. Used to filter out non-fireplace devices in
# :meth:`NapoleonClient.fireplaces`.
# ---------------------------------------------------------------------------
NAPOLEON_REQUIRED_PROPERTIES = frozenset(
    {
        PROP_POWER,
        PROP_FLAME_SPEED,
    }
)
