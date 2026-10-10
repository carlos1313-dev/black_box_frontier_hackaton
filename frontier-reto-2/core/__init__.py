"""Núcleo del servicio: función pura sin HTTP."""

from .commands import handle
from .state import State

__all__ = ["State", "handle"]
