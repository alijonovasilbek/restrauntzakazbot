from __future__ import annotations

from calendar import monthrange
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def menu_carousel_keyboard(food_id: int, index: int, total: int, in_stock: bool) -> InlineKeyboardMarkup:
    prev_index = total - 1 if index == 0 else index - 1
    next_index = 0 if index == total - 1 else index + 1
    add_button = (
        InlineKeyboardButton(text="Savatga qo'shish", callback_data=f"cart_add:{food_id}")
        if in_stock
        else InlineKeyboardButton(text="Tugagan", callback_data="noop")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️", callback_data=f"menu_nav:{prev_index}"),
                add_button,
                InlineKeyboardButton(text="➡️", callback_data=f"menu_nav:{next_index}"),
            ],
            [InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="noop")],
        ]
    )


def cart_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for index, item in enumerate(items, start=1):
        food_id = int(item["food_id"])
        rows.append(
            [
                InlineKeyboardButton(text=str(index), callback_data="noop"),
                InlineKeyboardButton(text="➖", callback_data=f"cart_dec:{food_id}"),
                InlineKeyboardButton(text="➕", callback_data=f"cart_inc:{food_id}"),
                InlineKeyboardButton(text="🗑", callback_data=f"cart_remove:{food_id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="✅ Buyurtma berish", callback_data="checkout:start")])
    rows.append([InlineKeyboardButton(text="🧹 Tozalash", callback_data="cart_clear")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def orders_pagination_keyboard(page: int, has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    buttons = []
    if has_prev:
        buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"orders_page:{page - 1}"))
    if has_next:
        buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"orders_page:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [])


def admin_date_picker_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    month_title = f"{year}-{month:02d}"
    rows: list[list[InlineKeyboardButton]] = [[InlineKeyboardButton(text=month_title, callback_data="noop")]]
    weekday_labels = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
    rows.append([InlineKeyboardButton(text=label, callback_data="noop") for label in weekday_labels])

    first_weekday, days_in_month = monthrange(year, month)
    first_weekday = (first_weekday + 1) % 7
    week: list[InlineKeyboardButton] = []
    for _ in range(first_weekday):
        week.append(InlineKeyboardButton(text=" ", callback_data="noop"))
    for day in range(1, days_in_month + 1):
        selected = date(year, month, day)
        week.append(InlineKeyboardButton(text=str(day), callback_data=f"admin_foods_date:{selected.isoformat()}"))
        if len(week) == 7:
            rows.append(week)
            week = []
    if week:
        while len(week) < 7:
            week.append(InlineKeyboardButton(text=" ", callback_data="noop"))
        rows.append(week)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    rows.append(
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"admin_foods_month:{prev_year}-{prev_month:02d}"),
            InlineKeyboardButton(text="Bugun", callback_data=f"admin_foods_date:{date.today().isoformat()}"),
            InlineKeyboardButton(text="➡️", callback_data=f"admin_foods_month:{next_year}-{next_month:02d}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_statistics_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Bugun", callback_data="admin_stats:today"),
                InlineKeyboardButton(text="Haftalik", callback_data="admin_stats:week"),
            ],
            [
                InlineKeyboardButton(text="Oylik", callback_data="admin_stats:month"),
                InlineKeyboardButton(text="Sana tanlash", callback_data="admin_stats:pick_date"),
            ],
        ]
    )


def admin_statistics_date_picker_keyboard(year: int, month: int, today: date) -> InlineKeyboardMarkup:
    month_title = f"{year}-{month:02d}"
    rows: list[list[InlineKeyboardButton]] = [[InlineKeyboardButton(text=month_title, callback_data="noop")]]
    weekday_labels = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
    rows.append([InlineKeyboardButton(text=label, callback_data="noop") for label in weekday_labels])

    first_weekday, days_in_month = monthrange(year, month)
    first_weekday = (first_weekday + 1) % 7
    week: list[InlineKeyboardButton] = []
    for _ in range(first_weekday):
        week.append(InlineKeyboardButton(text=" ", callback_data="noop"))
    for day in range(1, days_in_month + 1):
        selected = date(year, month, day)
        week.append(InlineKeyboardButton(text=str(day), callback_data=f"admin_stats_date:{selected.isoformat()}"))
        if len(week) == 7:
            rows.append(week)
            week = []
    if week:
        while len(week) < 7:
            week.append(InlineKeyboardButton(text=" ", callback_data="noop"))
        rows.append(week)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    rows.append(
        [
            InlineKeyboardButton(text="<", callback_data=f"admin_stats_month:{prev_year}-{prev_month:02d}"),
            InlineKeyboardButton(text="Bugun", callback_data=f"admin_stats_date:{today.isoformat()}"),
            InlineKeyboardButton(text=">", callback_data=f"admin_stats_month:{next_year}-{next_month:02d}"),
        ]
    )
    rows.append([InlineKeyboardButton(text="Ortga", callback_data="admin_stats:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_food_manage_keyboard(food_id: int, selected_date: str, index: int, total: int) -> InlineKeyboardMarkup:
    prev_index = total - 1 if index == 0 else index - 1
    next_index = 0 if index == total - 1 else index + 1
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Tahrirlash", callback_data=f"admin_food:edit:{food_id}"),
                InlineKeyboardButton(text="O'chirish", callback_data=f"admin_food:delete:{food_id}"),
            ],
            [
                InlineKeyboardButton(text="⬅️", callback_data=f"admin_foods_page:{selected_date}:{prev_index}"),
                InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="noop"),
                InlineKeyboardButton(text="➡️", callback_data=f"admin_foods_page:{selected_date}:{next_index}"),
            ],
        ]
    )


def admin_food_edit_fields_keyboard(food_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Nomi", callback_data=f"admin_food_field:{food_id}:name")],
            [InlineKeyboardButton(text="Rasm", callback_data=f"admin_food_field:{food_id}:image")],
            [InlineKeyboardButton(text="Narx", callback_data=f"admin_food_field:{food_id}:price")],
            [InlineKeyboardButton(text="Soni", callback_data=f"admin_food_field:{food_id}:quantity")],
            [InlineKeyboardButton(text="Tavsif", callback_data=f"admin_food_field:{food_id}:description")],
        ]
    )


def admin_credentials_edit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Karta raqami", callback_data="admin_credentials:payment_card_number")],
            [InlineKeyboardButton(text="Karta egasi", callback_data="admin_credentials:payment_card_owner")],
            [InlineKeyboardButton(text="Zakaz qabul vaqti", callback_data="admin_credentials:order_accept_until")],
            [InlineKeyboardButton(text="Yetkazish boshlanishi", callback_data="admin_credentials:delivery_start_time")],
            [InlineKeyboardButton(text="Yetkazish tugashi", callback_data="admin_credentials:delivery_end_time")],
        ]
    )


def admin_promotions_keyboard(promotions: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="➕ Aksiya qo'shish", callback_data="promotion:add")]]
    for promo in promotions:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{'🟢' if promo['is_active'] else '⚪️'} {promo['name']}",
                    callback_data=f"promotion:toggle:{promo['id']}:{0 if promo['is_active'] else 1}",
                ),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"promotion:delete:{promo['id']}"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_order_review_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"order_review:accept:{order_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"order_review:reject:{order_id}"),
            ]
        ]
    )


def admin_order_manage_keyboard(order_id: int, index: int, total: int, status: str, payment_status: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if status == "payment_submitted":
        rows.append(
            [
                InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"order_review:accept:{order_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"order_review:reject:{order_id}"),
            ]
        )
    elif status == "accepted":
        rows.append([InlineKeyboardButton(text="↩️ Bekor qilish", callback_data=f"admin_order_cancel:{order_id}:{index}")])

    if total > 1:
        prev_index = total - 1 if index == 0 else index - 1
        next_index = 0 if index == total - 1 else index + 1
        rows.append(
            [
                InlineKeyboardButton(text="⬅️", callback_data=f"admin_orders_page:{prev_index}"),
                InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="noop"),
                InlineKeyboardButton(text="➡️", callback_data=f"admin_orders_page:{next_index}"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def promotion_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Soni bo'yicha aksiya", callback_data="promotion_type:free_delivery_by_quantity")],
            [InlineKeyboardButton(text="Jami summa bo'yicha bonus", callback_data="promotion_type:free_item_by_total")],
            [InlineKeyboardButton(text="Buy X Get Y", callback_data="promotion_type:buy_x_get_y")],
        ]
    )


def yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Ha", callback_data=f"{prefix}:yes"),
                InlineKeyboardButton(text="Yo'q", callback_data=f"{prefix}:no"),
            ]
        ]
    )


def skip_bonus_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Bonus yo'q", callback_data="promotion_bonus:skip")]])
