from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from bot.config import settings


class BroadcastService:
    async def broadcast_menu(self, bot: Bot, users: list[dict], foods: list[dict]) -> tuple[int, int]:
        success = 0
        failed = 0
        for user in users:
            delivered = False
            while True:
                try:
                    await bot.send_message(chat_id=user["telegram_id"], text="🍽 Bugungi menyu")
                    for food in foods:
                        text = f"{food['name']}\nNarx: {food['price']} so'm\nTavsif: {food['description'] or '-'}"
                        if food["image_file_id"]:
                            await bot.send_photo(chat_id=user["telegram_id"], photo=food["image_file_id"], caption=text)
                        else:
                            await bot.send_message(chat_id=user["telegram_id"], text=text)
                        await asyncio.sleep(settings.broadcast_delay_seconds)
                    delivered = True
                    break
                except TelegramRetryAfter as exc:
                    await asyncio.sleep(exc.retry_after)
                except TelegramForbiddenError:
                    break
                except Exception:
                    break
            if delivered:
                success += 1
            else:
                failed += 1
        return success, failed
