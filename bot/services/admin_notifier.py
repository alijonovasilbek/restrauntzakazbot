from __future__ import annotations

from aiogram import Bot

from bot.config import settings
from bot.keyboards.inline import admin_order_review_keyboard


def order_map_link(latitude: float, longitude: float) -> str:
    return f"https://maps.google.com/?q={latitude},{longitude}"


class AdminNotifier:
    async def notify_new_order(self, bot: Bot, order: dict, items: list[dict], user: dict, payment: dict | None) -> int:
        lines = [
            "Yangi buyurtma",
            f"Buyurtma ID: {order['id']}",
            f"Foydalanuvchi: {user['full_name']}",
            f"Username: @{user['username']}" if user["username"] else "Username: -",
            f"Telefon: {order['phone']}",
            f"Lokatsiya: {order_map_link(order['location_latitude'], order['location_longitude'])}",
            f"Manzil: {order['location_text'] or '-'}",
            "",
            "Mahsulotlar:",
        ]
        for item in items:
            lines.append(f"- {item['food_name']} x {item['quantity']} = {item['line_total']} so'm")
        lines.extend(
            [
                "",
                f"Holat: {order['status']}",
                f"To'lov holati: {order['payment_status']}",
                f"Yetkazib berish: {order['delivery_fee']} so'm",
                f"Chegirma: {order['discount_amount']} so'm",
                f"Jami: {order['total_price']} so'm",
                f"Aksiya: {order['promotion_summary'] or '-'}",
            ]
        )
        text = "\n".join(lines)
        markup = admin_order_review_keyboard(int(order["id"]))
        if payment and payment["type"] == "photo":
            message = await bot.send_photo(settings.admin_group_id, photo=payment["file_id"], caption=text, reply_markup=markup)
        elif payment:
            message = await bot.send_document(settings.admin_group_id, document=payment["file_id"], caption=text, reply_markup=markup)
        else:
            message = await bot.send_message(settings.admin_group_id, text, reply_markup=markup)
        return int(message.message_id)
