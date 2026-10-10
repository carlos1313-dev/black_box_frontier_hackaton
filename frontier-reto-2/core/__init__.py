"""Núcleo del servicio: función pura sin HTTP."""

from .commands import handle
from .http import Store, responder
from .state import State

__all__ = ["State", "Store", "handle", "responder"]
