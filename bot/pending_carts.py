"""
Bot va FastAPI bir xil processda ishlaydi (asyncio.TaskGroup).
Shuning uchun oddiy dict orqali cart ma'lumotlarini ulashish mumkin.
"""
from __future__ import annotations

_pending: dict[int, list[dict]] = {}


def save(telegram_id: int, items: list[dict]) -> None:
    _pending[telegram_id] = items


def pop(telegram_id: int) -> list[dict] | None:
    return _pending.pop(telegram_id, None)
