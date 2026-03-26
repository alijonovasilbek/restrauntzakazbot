from __future__ import annotations

from typing import Any

from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection


class DatabaseSession:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def fetch_one(self, statement: Any) -> RowMapping | None:
        result = await self.connection.execute(statement)
        return result.mappings().first()

    async def fetch_all(self, statement: Any) -> list[RowMapping]:
        result = await self.connection.execute(statement)
        return list(result.mappings().all())

    async def execute(self, statement: Any, params: Any | None = None) -> Any:
        if params is None:
            return await self.connection.execute(statement)
        return await self.connection.execute(statement, params)
