"""Bot va FastAPI o'rtasida Dispatcher ni ulashish uchun modul."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Dispatcher

_dp: "Dispatcher | None" = None


def set_dispatcher(dp: "Dispatcher") -> None:
    global _dp
    _dp = dp


def get_dispatcher() -> "Dispatcher | None":
    return _dp
