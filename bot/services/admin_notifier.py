from __future__ import annotations

from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile

from bot.config import settings
from bot.keyboards.inline import admin_order_review_keyboard
from bot.utils.formatters import ORDER_STATUS_LABELS, PAYMENT_STATUS_LABELS, order_display_id


def order_map_link(latitude: float, longitude: float) -> str:
    return f"https://maps.google.com/?q={latitude},{longitude}"


def delivery_fee_label(delivery_fee: int) -> str:
    return "🚚 + Yetkazib berish narxi" if int(delivery_fee) < 0 else f"🚚 {delivery_fee} so'm"


def bonus_label(promotion_summary: str | None) -> str:
    if not promotion_summary:
        return "🎁 Bonus: yo'q"
    if "Bonus:" in promotion_summary:
        _, bonus_part = promotion_summary.split("Bonus:", 1)
        bonus_part = bonus_part.strip()
        if bonus_part:
            return f"🎁 Bonus:\n{bonus_part}"
    return "🎁 Bonus: yo'q"


class AdminNotifier:
    def build_order_text(self, order: dict, items: list[dict], user: dict, payment: dict | None) -> str:
        has_location = float(order["location_latitude"]) != 0.0 or float(order["location_longitude"]) != 0.0
        location_text = order_map_link(order["location_latitude"], order["location_longitude"]) if has_location else "x"
        address_text = "x" if has_location else (order["location_text"] or "x")
        order_status = ORDER_STATUS_LABELS.get(str(order["status"]), str(order["status"]))
        payment_status = PAYMENT_STATUS_LABELS.get(str(order["payment_status"]), str(order["payment_status"]))
        display_id = order_display_id(int(order["id"]))
        lines = [
            "Yangi buyurtma",
            f"Buyurtma ID: {display_id}",
            f"Foydalanuvchi: {user['full_name']}",
            f"Username: @{user['username']}" if user["username"] else "Username: -",
            f"Telefon: {order['phone']}",
            f"Lokatsiya: {location_text}",
            f"Manzil: {address_text}",
            "",
            "Mahsulotlar:",
        ]
        for item in items:
            lines.append(f"- {item['food_name']} x {item['quantity']} = {item['line_total']} so'm")
        lines.extend(
            [
                "",
                f"Holat: {order_status}",
                f"To'lov holati: {payment_status}",
                delivery_fee_label(int(order['delivery_fee'])),
                f"Chegirma: {order['discount_amount']} so'm",
                f"Jami: {order['total_price']} so'm",
                bonus_label(order["promotion_summary"]),
            ]
        )
        return "\n".join(lines)

    async def notify_new_order(self, bot: Bot, order: dict, items: list[dict], user: dict, payment: dict | None) -> int:
        text = self.build_order_text(order, items, user, payment)
        markup = admin_order_review_keyboard(int(order["id"]))
        if payment and payment["type"] == "photo":
            message = await bot.send_photo(settings.admin_group_id, photo=payment["file_id"], caption=text, reply_markup=markup)
        elif payment and payment["type"] == "web_upload":
            message = await bot.send_document(
                settings.admin_group_id,
                document=FSInputFile(Path(str(payment["file_id"]))),
                caption=text,
                reply_markup=markup,
            )
        elif payment:
            message = await bot.send_document(settings.admin_group_id, document=payment["file_id"], caption=text, reply_markup=markup)
        else:
            message = await bot.send_message(settings.admin_group_id, text, reply_markup=markup)
        return int(message.message_id)

    async def refresh_order_message(self, bot: Bot, message, order: dict, items: list[dict], user: dict, payment: dict | None) -> None:
        text = self.build_order_text(order, items, user, payment)
        if getattr(message, "photo", None) or getattr(message, "document", None):
            await message.edit_caption(caption=text, reply_markup=None)
            return
        await message.edit_text(text, reply_markup=None)
