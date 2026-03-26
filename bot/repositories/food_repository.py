from __future__ import annotations

from datetime import date

from sqlalchemy import delete, insert, select, update

from bot.database.session import DatabaseSession
from bot.models.tables import foods


class FoodRepository:
    def __init__(self, db: DatabaseSession) -> None:
        self.db = db

    async def create(self, payload: dict) -> int:
        result = await self.db.execute(insert(foods).values(**payload).returning(foods.c.id))
        return int(result.scalar_one())

    async def list_today(self, today: date, offset: int = 0, limit: int = 5):
        return await self.db.fetch_all(
            select(foods).where(foods.c.menu_date == today, foods.c.is_active.is_(True)).order_by(foods.c.id.asc()).offset(offset).limit(limit)
        )

    async def count_today(self, today: date) -> int:
        rows = await self.db.fetch_all(select(foods.c.id).where(foods.c.menu_date == today, foods.c.is_active.is_(True)))
        return len(rows)

    async def list_today_all(self, today: date):
        return await self.db.fetch_all(select(foods).where(foods.c.menu_date == today, foods.c.is_active.is_(True)).order_by(foods.c.id.asc()))

    async def get_by_id(self, food_id: int):
        return await self.db.fetch_one(select(foods).where(foods.c.id == food_id))

    async def update(self, food_id: int, payload: dict) -> None:
        await self.db.execute(update(foods).where(foods.c.id == food_id).values(**payload))

    async def delete(self, food_id: int) -> None:
        await self.db.execute(delete(foods).where(foods.c.id == food_id))

    async def reduce_stock(self, food_id: int, quantity: int) -> None:
        food = await self.get_by_id(food_id)
        if not food:
            raise ValueError("Food not found")
        new_quantity = int(food["quantity"]) - quantity
        if new_quantity < 0:
            raise ValueError("Insufficient stock")
        await self.update(food_id, {"quantity": new_quantity})

    async def increase_stock(self, food_id: int, quantity: int) -> None:
        food = await self.get_by_id(food_id)
        if not food:
            raise ValueError("Food not found")
        await self.update(food_id, {"quantity": int(food["quantity"]) + quantity})
