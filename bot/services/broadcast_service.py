from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from bot.config import settings


class BroadcastService:
    async def broadcast_menu(
        self,
        bot: Bot,
        users: list[dict],
        foods: list[dict],
        promotions: list[dict] | None = None,
        credentials: dict | None = None,
    ) -> tuple[int, int]:
        success = 0
        failed = 0
        menu_text = self._build_menu_text(foods, promotions or [], credentials or {})

        for user in users:
            delivered = False
            while True:
                try:
                    await bot.send_message(chat_id=user["telegram_id"], text=menu_text)
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

    @staticmethod
    def _build_menu_text(foods: list[dict], promotions: list[dict], credentials: dict) -> str:
        lines = ["🍽 Bugungi menyu", ""]
        for index, food in enumerate(foods, start=1):
            price = int(food.get("price") or 0)
            lines.append(f"{index}. {food['name']} - {price:,} so'm".replace(",", " "))

        promo_lines = BroadcastService._promotion_lines(promotions)
        if promo_lines:
            lines.append("")
            lines.append("🎁 Bonus va aksiyalar:")
            lines.extend(promo_lines)

        order_accept_until = str(credentials.get("order_accept_until") or "11:30")
        delivery_start_time = str(credentials.get("delivery_start_time") or "12:00")
        delivery_end_time = str(credentials.get("delivery_end_time") or "14:00")

        lines.append("")
        lines.append("⏰ Buyurtma va yetkazib berish vaqti:")
        lines.append(f"📝 Zakazlarni {order_accept_until} gacha qabul qilamiz.")
        lines.append(f"🚚 {delivery_start_time} dan {delivery_end_time} gacha yetkazib beramiz.")
        lines.append("")
        lines.append("📲 Buyurtma berish uchun botdagi menyudan foydalaning.")
        return "\n".join(lines)

    @staticmethod
    def _promotion_lines(promotions: list[dict]) -> list[str]:
        lines: list[str] = []
        for promo in promotions:
            name = str(promo.get("name") or "Aksiya").strip()
            config = promo.get("config") or {}
            bonus_text = str(config.get("bonus_text") or config.get("free_item_name") or "").strip()

            if str(promo.get("promotion_type")) == "free_delivery_by_quantity":
                min_quantity = int(config.get("min_quantity") or 0)
                text = f"🚚 {name}: {min_quantity} ta va undan ko'p buyurtmada"
                if bool(config.get("free_delivery")):
                    text += " yetkazib berish bepul"
                if bonus_text:
                    text += f"; bonus: {bonus_text}"
                lines.append(text)
                continue

            if str(promo.get("promotion_type")) == "free_item_by_total":
                min_total = int(config.get("min_total") or 0)
                text = f"🎉 {name}: {min_total:,} so'mdan boshlab".replace(",", " ")
                if bonus_text:
                    text += f" bonus: {bonus_text}"
                lines.append(text)
                continue

            if str(promo.get("promotion_type")) == "buy_x_get_y":
                buy_quantity = int(config.get("buy_quantity") or 0)
                free_quantity = int(config.get("free_quantity") or 0)
                text = f"🎁 {name}: {buy_quantity} ta olsangiz {free_quantity} ta bonus"
                if bonus_text:
                    text += f" ({bonus_text})"
                lines.append(text)
                continue

            if bonus_text:
                lines.append(f"✨ {name}: {bonus_text}")
            else:
                lines.append(f"✨ {name}")
        return lines
