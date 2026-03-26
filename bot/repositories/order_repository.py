from __future__ import annotations

from sqlalchemy import insert, select, update

from bot.database.session import DatabaseSession
from bot.models.tables import order_items, orders, payments


class OrderRepository:
    def __init__(self, db: DatabaseSession) -> None:
        self.db = db

    async def create_order(self, payload: dict, items: list[dict]) -> int:
        result = await self.db.execute(insert(orders).values(**payload).returning(orders.c.id))
        order_id = int(result.scalar_one())
        if items:
            await self.db.execute(insert(order_items), [{**item, "order_id": order_id} for item in items])
        return order_id

    async def get_order(self, order_id: int):
        return await self.db.fetch_one(select(orders).where(orders.c.id == order_id))

    async def get_items(self, order_id: int):
        return await self.db.fetch_all(select(order_items).where(order_items.c.order_id == order_id).order_by(order_items.c.id.asc()))

    async def list_user_orders(self, user_id: int):
        return await self.db.fetch_all(select(orders).where(orders.c.user_id == user_id).order_by(orders.c.id.desc()))

    async def update_status(self, order_id: int, *, status=None, payment_status=None, admin_group_message_id=None) -> None:
        values = {}
        if status is not None:
            values["status"] = status
        if payment_status is not None:
            values["payment_status"] = payment_status
        if admin_group_message_id is not None:
            values["admin_group_message_id"] = admin_group_message_id
        if values:
            await self.db.execute(update(orders).where(orders.c.id == order_id).values(**values))

    async def create_payment(self, order_id: int, file_id: str, receipt_type: str) -> int:
        result = await self.db.execute(
            insert(payments).values(order_id=order_id, file_id=file_id, type=receipt_type).returning(payments.c.id)
        )
        return int(result.scalar_one())

    async def get_latest_payment(self, order_id: int):
        return await self.db.fetch_one(
            select(payments).where(payments.c.order_id == order_id).order_by(payments.c.id.desc()).limit(1)
        )
