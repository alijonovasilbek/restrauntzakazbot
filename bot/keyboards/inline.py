from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def menu_pagination_keyboard(page: int, has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    buttons = []
    if has_prev:
        buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"menu_page:{page - 1}"))
    if has_next:
        buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"menu_page:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [])


def food_actions_keyboard(food_id: int, in_stock: bool) -> InlineKeyboardMarkup:
    if in_stock:
        rows = [[InlineKeyboardButton(text="➕ Savatga qo'shish", callback_data=f"cart_add:{food_id}")]]
    else:
        rows = [[InlineKeyboardButton(text="❌ Tugagan", callback_data="noop")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_keyboard(food_ids: list[int]) -> InlineKeyboardMarkup:
    rows = []
    for food_id in food_ids:
        rows.append(
            [
                InlineKeyboardButton(text="➖", callback_data=f"cart_dec:{food_id}"),
                InlineKeyboardButton(text="➕", callback_data=f"cart_inc:{food_id}"),
                InlineKeyboardButton(text="🗑", callback_data=f"cart_remove:{food_id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="✅ Buyurtma berish", callback_data="checkout:start")])
    rows.append([InlineKeyboardButton(text="🧹 Tozalash", callback_data="cart_clear")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def saved_address_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Avvalgi manzilni ishlatish", callback_data="address:use_saved")],
            [InlineKeyboardButton(text="Yangi manzil kiritish", callback_data="address:new")],
        ]
    )


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Ovqat qo'shish", callback_data="admin:add_food")],
            [InlineKeyboardButton(text="📝 Ovqatlarni boshqarish", callback_data="admin:foods")],
            [InlineKeyboardButton(text="🎁 Aksiyalar", callback_data="admin:promotions")],
            [InlineKeyboardButton(text="📢 Send today's menu", callback_data="admin:broadcast")],
        ]
    )


def admin_food_manage_keyboard(food_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"admin_food:edit:{food_id}"),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_food:delete:{food_id}"),
            ]
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


def admin_promotions_keyboard(promotions: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="➕ Aksiya qo'shish", callback_data="promotion:add")]]
    for promo in promotions:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{'🟢' if promo['is_active'] else '⚪️'} {promo['name']}",
                    callback_data=f"promotion:toggle:{promo['id']}:{0 if promo['is_active'] else 1}",
                ),
                InlineKeyboardButton(text="🗑", callback_data=f"promotion:delete:{promo['id']}"),
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
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Bonus yo'q", callback_data="promotion_bonus:skip")]]
    )
