from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

from bot.config import settings


def order_display_id(order_id: int) -> str:
    """Returns a short, non-sequential code shown to users instead of the real order ID.
    Example: order 51 → 'K7NQ2X'
    """
    raw = hashlib.sha256(f"bon-{order_id}".encode()).digest()
    code = base64.urlsafe_b64encode(raw).decode()
    alnum = "".join(c for c in code if c.isalnum())
    return alnum[:6].upper()


ORDER_STATUS_LABELS = {
    "pending_payment": "To'lov kutilmoqda",
    "payment_submitted": "Chek yuborilgan",
    "accepted": "Qabul qilingan",
    "rejected": "Rad etilgan",
    "canceled": "Bekor qilingan",
    "preparing": "Tayyorlanmoqda",
    "delivered": "Yetkazilgan",
}

PAYMENT_STATUS_LABELS = {
    "pending": "To'lov kutilmoqda",
    "submitted": "Chek tekshirilmoqda",
    "paid": "Tasdiqlangan",
    "rejected": "Rad etilgan",
    "refunded": "Qaytarilgan",
}


def format_food(food: dict) -> str:
    quantity_text = "Tugagan" if int(food["quantity"]) <= 0 else str(food["quantity"])
    return f"{food['name']}\nNarx: {food['price']} so'm\nSoni: {quantity_text}\nTavsif: {food['description'] or '-'}"


def format_menu_browser(items: list[dict], page: int, total: int, per_page: int) -> str:
    start = page * per_page + 1
    end = min(start + len(items) - 1, total)
    lines = [f"Bugungi menyu ({start}-{end}/{total}):", ""]
    for index, item in enumerate(items, start=start):
        stock = "Tugagan" if int(item["quantity"]) <= 0 else f"{item['quantity']} ta"
        lines.append(f"{index}. {item['name']} - {item['price']} so'm ({stock})")
    lines.append("")
    lines.append("Pastdagi tugmalardan ovqatni tanlang.")
    return "\n".join(lines)


def format_menu_item(food: dict, index: int, total: int) -> str:
    quantity = int(food["quantity"])
    lines = [
        f"{index + 1}/{total}",
        food["name"],
        f"Narx: {food['price']} so'm",
    ]
    if quantity <= 0:
        lines.append("Qolmadi")
    elif quantity <= 3:
        lines.append(f"Oxirgi {quantity} ta qoldi")
    lines.append(f"Tavsif: {food['description'] or '-'}")
    return "\n".join(lines)


def format_cart(cart: dict[str, dict], bonus_items: list[str] | None = None) -> str:
    if not cart:
        return "Savat bo'sh."
    lines = ["Savat:"]
    total = 0
    for index, item in enumerate(cart.values(), start=1):
        line_total = item["price"] * item["quantity"]
        total += line_total
        lines.append(f"{index}. {item['name']} x {item['quantity']} = {line_total} so'm")
    if bonus_items:
        lines.append("")
        lines.append("Bonus:")
        for bonus_text in bonus_items:
            lines.append(bonus_text)
    lines.append(f"\nJami: {total} so'm")
    return "\n".join(lines)


def format_address_label(address: dict | None) -> str:
    if not address:
        return "Saqlangan manzil"
    title = (address.get("title") or "").strip()
    address_text = (address.get("address_text") or "").strip()
    if address_text:
        return address_text[:48]
    if title:
        return title[:48]
    return f"{float(address['latitude']):.5f}, {float(address['longitude']):.5f}"


def _format_order_datetime(created_at) -> str:
    if not isinstance(created_at, datetime):
        return str(created_at or "-")
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=ZoneInfo("UTC"))
    local_dt = created_at.astimezone(ZoneInfo(settings.tz))
    return local_dt.strftime("%d.%m.%Y %H:%M")


def format_order_summary(order: dict, items: list[dict], index: int | None = None) -> str:
    order_status = ORDER_STATUS_LABELS.get(str(order["status"]), str(order["status"]))
    payment_status = PAYMENT_STATUS_LABELS.get(str(order["payment_status"]), str(order["payment_status"]))
    created_text = _format_order_datetime(order.get("created_at"))
    disp = order_display_id(int(order["id"]))
    title = f"{index}. Buyurtma #{disp}" if index is not None else f"Buyurtma #{disp}"
    lines = [title, f"Sana: {created_text}", f"Holat: {order_status}", f"To'lov: {payment_status}", ""]
    for item in items:
        lines.append(f"- {item['food_name']} x {item['quantity']} = {item['line_total']} so'm")
    lines.append(f"\nJami: {order['total_price']} so'm")
    return "\n".join(lines)


def format_orders_page(orders_with_items: list[tuple[dict, list[dict]]], page: int, total_pages: int) -> str:
    lines = [f"Buyurtmalarim ({page + 1}/{total_pages})", ""]
    for index, (order, items) in enumerate(orders_with_items, start=1):
        lines.append(format_order_summary(order, items, index=index))
        lines.append("")
    return "\n".join(lines).strip()
