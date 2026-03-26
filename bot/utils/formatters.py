from __future__ import annotations


ORDER_STATUS_LABELS = {
    "pending_payment": "To'lov kutilmoqda",
    "payment_submitted": "Chek yuborilgan",
    "accepted": "Qabul qilingan",
    "rejected": "Rad etilgan",
    "preparing": "Tayyorlanmoqda",
    "delivered": "Yetkazilgan",
}

PAYMENT_STATUS_LABELS = {
    "pending": "To'lov kutilmoqda",
    "submitted": "Chek tekshirilmoqda",
    "paid": "Tasdiqlangan",
    "rejected": "Rad etilgan",
}


def format_food(food: dict) -> str:
    quantity_text = "Tugagan" if int(food["quantity"]) <= 0 else str(food["quantity"])
    return f"{food['name']}\nNarx: {food['price']} so'm\nSoni: {quantity_text}\nTavsif: {food['description'] or '-'}"


def format_cart(cart: dict[str, dict]) -> str:
    if not cart:
        return "Savat bo'sh."
    lines = ["Savat:"]
    total = 0
    for item in cart.values():
        line_total = item["price"] * item["quantity"]
        total += line_total
        lines.append(f"- {item['name']} x {item['quantity']} = {line_total} so'm")
    lines.append(f"\nJami: {total} so'm")
    return "\n".join(lines)


def format_order_summary(order: dict, items: list[dict]) -> str:
    order_status = ORDER_STATUS_LABELS.get(str(order["status"]), str(order["status"]))
    payment_status = PAYMENT_STATUS_LABELS.get(str(order["payment_status"]), str(order["payment_status"]))
    lines = [f"Buyurtma #{order['id']}", f"Holat: {order_status}", f"To'lov: {payment_status}", ""]
    for item in items:
        lines.append(f"- {item['food_name']} x {item['quantity']} = {item['line_total']} so'm")
    lines.append(f"\nJami: {order['total_price']} so'm")
    return "\n".join(lines)
