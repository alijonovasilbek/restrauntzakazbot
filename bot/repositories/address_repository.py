from __future__ import annotations

from sqlalchemy import insert, select, update

from bot.database.session import DatabaseSession
from bot.models.tables import user_addresses


class AddressRepository:
    def __init__(self, db: DatabaseSession) -> None:
        self.db = db

    async def create(self, payload: dict) -> int:
        await self.db.execute(update(user_addresses).where(user_addresses.c.user_id == payload["user_id"]).values(is_default=False))
        result = await self.db.execute(insert(user_addresses).values(**payload).returning(user_addresses.c.id))
        return int(result.scalar_one())

    async def get_default(self, user_id: int):
        return await self.db.fetch_one(
            select(user_addresses).where(user_addresses.c.user_id == user_id, user_addresses.c.is_default.is_(True)).order_by(user_addresses.c.id.desc()).limit(1)
        )
