from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🍽 Bugungi menyu")],
        [KeyboardButton(text="🛒 Savat"), KeyboardButton(text="📦 Buyurtmalarim")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard: list[list[KeyboardButton]] = [
        [KeyboardButton(text="🖥 Admin Panel")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def admin_panel_reply_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🍲 Ovqat qo'shish"), KeyboardButton(text="📝 Ovqatlarni boshqarish")],
        [KeyboardButton(text="🎁 Aksiyalar"), KeyboardButton(text="📢 Bugungi menyuni yuborish")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="⚙️ Settings")],
        [KeyboardButton(text="📋 Buyurtmalar")],
        [KeyboardButton(text="⬅️ Asosiy menyu")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def request_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefonni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def request_location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)],
            [KeyboardButton(text="✍️ Manzilni yozaman")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
