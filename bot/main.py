from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import from_url as redis_from_url

from bot.config import settings
from bot.logging_config import configure_logging
from bot.middlewares.admin import AdminFlagMiddleware
from bot.middlewares.db import DbSessionMiddleware
from bot.routers import admin, common, user


async def main() -> None:
    configure_logging()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    if settings.use_redis:
        storage = RedisStorage(redis=redis_from_url(settings.redis_url))
    dp = Dispatcher(storage=storage)
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(AdminFlagMiddleware())
    dp.include_router(common.router)
    dp.include_router(user.router)
    dp.include_router(admin.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
