from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from bot.config import settings


def _user_webapp_button() -> KeyboardButton | None:
    if not settings.webapp_base_url:
        return None
    return KeyboardButton(text="🌐 WebApp", web_app=WebAppInfo(url=f"{settings.webapp_base_url.rstrip('/')}/web/app"))


def _admin_webapp_button() -> KeyboardButton | None:
    if not settings.webapp_base_url:
        return None
    return KeyboardButton(text="🌐 WebApp", web_app=WebAppInfo(url=f"{settings.webapp_base_url.rstrip('/')}/web/app"))


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🍽 Bugungi menyu")],
        [KeyboardButton(text="🛒 Savat"), KeyboardButton(text="📦 Buyurtmalarim")],
    ]
    webapp_button = _user_webapp_button()
    if webapp_button:
        keyboard.append([webapp_button])
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard: list[list[KeyboardButton]] = [
        [KeyboardButton(text="🖥 Admin Panel")],
    ]
    if settings.webapp_base_url:
        base = settings.webapp_base_url.rstrip("/")
        keyboard.append([KeyboardButton(text="🌐 WebApp", web_app=WebAppInfo(url=f"{base}/web/app"))])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def admin_panel_reply_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🍲 Ovqat qo'shish"), KeyboardButton(text="📝 Ovqatlarni boshqarish")],
        [KeyboardButton(text="🎁 Aksiyalar"), KeyboardButton(text="📢 Bugungi menyuni yuborish")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="💳 Kartalarni tahrirlash")],
        [KeyboardButton(text="📋 Buyurtmalar")],
    ]
    admin_webapp_button = _admin_webapp_button()
    if admin_webapp_button:
        keyboard.append([admin_webapp_button])
    keyboard.append([KeyboardButton(text="⬅️ Asosiy menyu")])
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
