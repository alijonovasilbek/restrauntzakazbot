from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from bot.config import settings

engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)


@asynccontextmanager
async def get_connection() -> AsyncConnection:
    async with engine.begin() as connection:
        yield connection
