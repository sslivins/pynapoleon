"""pynapoleon — Python client for Napoleon Astound-series fireplaces."""

from .client import NapoleonClient
from .device import Fireplace, decode_setpoint_c, encode_setpoint_c
from .errors import (
    NapoleonApiError,
    NapoleonAuthError,
    NapoleonConnectionError,
    NapoleonError,
    NapoleonNotFoundError,
    NapoleonValueError,
)
from .models import DaySchedule, FireplaceInfo, FireplaceState

__version__ = "0.0.2"

__all__ = [
    "DaySchedule",
    "Fireplace",
    "FireplaceInfo",
    "FireplaceState",
    "NapoleonApiError",
    "NapoleonAuthError",
    "NapoleonClient",
    "NapoleonConnectionError",
    "NapoleonError",
    "NapoleonNotFoundError",
    "NapoleonValueError",
    "__version__",
    "decode_setpoint_c",
    "encode_setpoint_c",
]
