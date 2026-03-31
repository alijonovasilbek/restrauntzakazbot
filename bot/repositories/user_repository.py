from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from bot.database.session import DatabaseSession
from bot.models.tables import users


class UserRepository:
    def __init__(self, db: DatabaseSession) -> None:
        self.db = db

    async def upsert(self, telegram_id: int, full_name: str, username: str | None) -> None:
        await self.db.execute(
            insert(users)
            .values(telegram_id=telegram_id, full_name=full_name, username=username)
            .on_conflict_do_update(
                index_elements=[users.c.telegram_id],
                set_={"full_name": full_name, "username": username},
            )
        )

    async def get_by_telegram_id(self, telegram_id: int):
        return await self.db.fetch_one(select(users).where(users.c.telegram_id == telegram_id))

    async def get_by_id(self, user_id: int):
        return await self.db.fetch_one(select(users).where(users.c.id == user_id))

    async def set_phone(self, telegram_id: int, phone: str) -> None:
        await self.db.execute(update(users).where(users.c.telegram_id == telegram_id).values(phone=phone))

    async def set_last_ordered(self, telegram_id: int, last_ordered_at) -> None:
        await self.db.execute(update(users).where(users.c.telegram_id == telegram_id).values(last_ordered_at=last_ordered_at))

    async def list_all(self):
        return await self.db.fetch_all(select(users).order_by(users.c.id.asc()))
