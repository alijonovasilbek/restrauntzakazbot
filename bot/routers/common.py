from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.reply import admin_menu_keyboard, main_menu_keyboard
from bot.repositories.user_repository import UserRepository

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, db, is_admin: bool) -> None:
    await UserRepository(db).upsert(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
    )
    await message.answer(
        "Assalomu alaykum. Buyurtma berish uchun menyudan foydalaning.",
        reply_markup=admin_menu_keyboard() if is_admin else main_menu_keyboard(),
    )
