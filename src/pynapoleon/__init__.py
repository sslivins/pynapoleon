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

__version__ = "0.0.1"

__all__ = [
    "NapoleonClient",
    "Fireplace",
    "FireplaceInfo",
    "FireplaceState",
    "DaySchedule",
    "encode_setpoint_c",
    "decode_setpoint_c",
    "NapoleonError",
    "NapoleonAuthError",
    "NapoleonApiError",
    "NapoleonConnectionError",
    "NapoleonNotFoundError",
    "NapoleonValueError",
    "__version__",
]
