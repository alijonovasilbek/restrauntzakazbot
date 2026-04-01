from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from bot.database.engine import get_connection
from bot.database.session import DatabaseSession
from bot.repositories.user_repository import UserRepository


class AdminFlagMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None:
            data["is_admin"] = False
            return await handler(event, data)

        async with get_connection() as connection:
            db = DatabaseSession(connection)
            data["is_admin"] = await UserRepository(db).is_admin(user.id)
        return await handler(event, data)
