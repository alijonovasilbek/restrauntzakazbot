from __future__ import annotations

from sqlalchemy import insert, select, update

from bot.config import settings
from bot.database.session import DatabaseSession
from bot.models.tables import credentials


DEFAULT_CREDENTIALS = {
    "payment_card_number": settings.payment_card_number,
    "payment_card_owner": settings.payment_card_owner,
    "order_accept_until": "11:30",
    "delivery_start_time": "12:00",
    "delivery_end_time": "14:00",
}


class CredentialRepository:
    def __init__(self, db: DatabaseSession) -> None:
        self.db = db

    async def get(self):
        record = await self.db.fetch_one(select(credentials).where(credentials.c.id == 1))
        if record:
            return record
        await self.db.execute(insert(credentials).values(id=1, **DEFAULT_CREDENTIALS))
        return await self.db.fetch_one(select(credentials).where(credentials.c.id == 1))

    async def update(self, payload: dict) -> None:
        existing = await self.get()
        if not existing:
            await self.db.execute(insert(credentials).values(id=1, **DEFAULT_CREDENTIALS, **payload))
            return
        await self.db.execute(update(credentials).where(credentials.c.id == 1).values(**payload))
