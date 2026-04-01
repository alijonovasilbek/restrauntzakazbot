from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import from_url as redis_from_url
import uvicorn

from bot.config import settings
from bot.database.engine import get_connection
from bot.database.session import DatabaseSession
from bot.logging_config import configure_logging
from bot.middlewares.admin import AdminFlagMiddleware
from bot.middlewares.db import DbSessionMiddleware
from bot.repositories.user_repository import UserRepository
from bot.routers import admin, common, user
from bot.shared import set_dispatcher
from bot.web.app import app as web_app


async def main() -> None:
    configure_logging()
    async with get_connection() as connection:
        await UserRepository(DatabaseSession(connection)).bootstrap_legacy_admins(settings.legacy_admin_ids)
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    if settings.use_redis:
        storage = RedisStorage(redis=redis_from_url(settings.redis_url))
    dp = Dispatcher(storage=storage)
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(AdminFlagMiddleware())
    set_dispatcher(dp)
    dp.include_router(common.router)
    dp.include_router(user.router)
    dp.include_router(admin.router)
    web_server = uvicorn.Server(
        uvicorn.Config(
            app=web_app,
            host=settings.web_host,
            port=settings.web_port,
            log_level="info",
        )
    )
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(dp.start_polling(bot))
            tg.create_task(web_server.serve())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
