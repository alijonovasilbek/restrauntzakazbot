from __future__ import annotations

from sqlalchemy import delete, insert, select, update

from bot.database.session import DatabaseSession
from bot.models.tables import promotions


class PromotionRepository:
    def __init__(self, db: DatabaseSession) -> None:
        self.db = db

    async def create(self, payload: dict) -> int:
        result = await self.db.execute(insert(promotions).values(**payload).returning(promotions.c.id))
        return int(result.scalar_one())

    async def list_active(self):
        return await self.db.fetch_all(select(promotions).where(promotions.c.is_active.is_(True)).order_by(promotions.c.id.asc()))

    async def list_all(self):
        return await self.db.fetch_all(select(promotions).order_by(promotions.c.id.asc()))

    async def toggle(self, promotion_id: int, is_active: bool) -> None:
        await self.db.execute(update(promotions).where(promotions.c.id == promotion_id).values(is_active=is_active))

    async def delete(self, promotion_id: int) -> None:
        await self.db.execute(delete(promotions).where(promotions.c.id == promotion_id))
