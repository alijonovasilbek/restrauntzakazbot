from __future__ import annotations

from datetime import date
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy.exc import IntegrityError

from bot.fsm.states import AdminCredentialStates, AdminFoodStates, AdminPromotionStates
from bot.keyboards.inline import (
    admin_credentials_edit_keyboard,
    admin_date_picker_keyboard,
    admin_food_edit_fields_keyboard,
    admin_food_manage_keyboard,
    admin_order_manage_keyboard,
    admin_promotions_keyboard,
    admin_statistics_date_picker_keyboard,
    admin_statistics_keyboard,
    promotion_type_keyboard,
    skip_bonus_keyboard,
    yes_no_keyboard,
)
from bot.keyboards.reply import admin_menu_keyboard, admin_panel_reply_keyboard, main_menu_keyboard
from bot.models.enums import OrderStatus, PaymentStatus, PromotionType
from bot.repositories.credential_repository import CredentialRepository
from bot.repositories.food_repository import FoodRepository
from bot.repositories.order_repository import OrderRepository
from bot.repositories.promotion_repository import PromotionRepository
from bot.repositories.user_repository import UserRepository
from bot.services.broadcast_service import BroadcastService
from bot.services.credential_service import CredentialService
from bot.services.image_service import ImageService
from bot.services.menu_service import today_local_date
from bot.config import settings
from bot.utils.formatters import format_food, format_order_summary

router = Router()


def _is_admin(is_admin: bool) -> bool:
    return is_admin


def _credential_field_label(field_name: str) -> str:
    labels = {
        "payment_card_number": "Karta raqami",
        "payment_card_owner": "Karta egasi",
        "order_accept_until": "Zakaz qabul qilish vaqti",
        "delivery_start_time": "Yetkazib berish boshlanishi",
        "delivery_end_time": "Yetkazib berish tugashi",
    }
    return labels.get(field_name, field_name)


async def _safe_edit_text(message: Message, text: str, reply_markup) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def _show_credentials(message: Message, db) -> None:
    credentials = await CredentialService(CredentialRepository(db)).get_credentials()
    text = (
        "To'lov va yetkazib berish sozlamalari:\n\n"
        f"💳 Karta raqami: {credentials['payment_card_number']}\n"
        f"👤 Karta egasi: {credentials['payment_card_owner']}\n"
        f"📝 Zakaz qabul qilish: {credentials['order_accept_until']} gacha\n"
        f"🚚 Yetkazib berish: {credentials['delivery_start_time']} - {credentials['delivery_end_time']}"
    )
    await message.answer(text, reply_markup=admin_credentials_edit_keyboard())


async def _show_admin_order(message: Message, db, index: int = 0, *, edit: bool = False) -> None:
    order_repo = OrderRepository(db)
    user_repo = UserRepository(db)
    orders = await order_repo.list_all_orders()
    if not orders:
        await message.answer("Buyurtmalar hali yo'q.")
        return
    index = max(0, min(index, len(orders) - 1))
    order = orders[index]
    items = await order_repo.get_items(int(order["id"]))
    user = await user_repo.get_by_id(int(order["user_id"]))
    text = format_order_summary(order, items)
    customer_lines = [
        f"Mijoz: {(user['full_name'] if user else '-')}",
        f"Telefon: {order['phone']}",
    ]
    username = f"@{user['username']}" if user and user.get("username") else "-"
    customer_lines.append(f"Username: {username}")
    address = order["location_text"] or f"{float(order['location_latitude']):.5f}, {float(order['location_longitude']):.5f}"
    customer_lines.append(f"Manzil: {address}")
    text = "\n".join(customer_lines) + "\n\n" + text
    markup = admin_order_manage_keyboard(
        int(order["id"]),
        index,
        len(orders),
        str(order["status"]),
        str(order["payment_status"]),
    )
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _render_statistics(message: Message, db, start_local: datetime, end_local: datetime, title: str, *, edit: bool = False) -> None:
    repo = OrderRepository(db)
    orders = await repo.list_orders_between(start_local, end_local)
    order_ids = [int(order["id"]) for order in orders]
    items = await repo.list_items_for_orders(order_ids)

    sold_by_food: dict[str, int] = {}
    for item in items:
        sold_by_food[item["food_name"]] = sold_by_food.get(item["food_name"], 0) + int(item["quantity"])

    paid_total = sum(int(order["total_price"]) for order in orders if str(order["payment_status"]) == PaymentStatus.PAID.value)
    pending_total = sum(int(order["total_price"]) for order in orders if str(order["payment_status"]) != PaymentStatus.PAID.value)
    accepted_count = sum(1 for order in orders if str(order["status"]) == OrderStatus.ACCEPTED.value)
    submitted_count = sum(1 for order in orders if str(order["payment_status"]) == PaymentStatus.SUBMITTED.value)

    lines = [
        title,
        f"Buyurtmalar soni: {len(orders)}",
        f"Qabul qilinganlar: {accepted_count}",
        f"Chek yuborilganlar: {submitted_count}",
        f"Tasdiqlangan tushum: {paid_total} so'm",
        f"Kutilayotgan tushum: {pending_total} so'm",
        "",
        "Sotilgan ovqatlar:",
    ]
    if sold_by_food:
        for name, quantity in sorted(sold_by_food.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"- {name}: {quantity} dona")
    else:
        lines.append("- Hali sotuv bo'lmadi")

    text = "\n".join(lines)
    markup = admin_statistics_keyboard()
    if edit:
        await _safe_edit_text(message, text, markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _show_statistics_for_period(message: Message, db, period: str, *, edit: bool = False) -> None:
    tz = ZoneInfo(settings.tz)
    now = datetime.now(tz)
    today = now.date()

    if period == "today":
        start_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        title = f"Bugungi statistika ({today.strftime('%d.%m.%Y')})"
    elif period == "week":
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=7)
        start_local = datetime.combine(start_date, datetime.min.time(), tzinfo=tz)
        end_local = datetime.combine(end_date, datetime.min.time(), tzinfo=tz)
        title = f"Haftalik statistika ({start_date.strftime('%d.%m.%Y')} - {(end_date - timedelta(days=1)).strftime('%d.%m.%Y')})"
    elif period == "month":
        start_date = today.replace(day=1)
        if start_date.month == 12:
            end_date = date(start_date.year + 1, 1, 1)
        else:
            end_date = date(start_date.year, start_date.month + 1, 1)
        start_local = datetime.combine(start_date, datetime.min.time(), tzinfo=tz)
        end_local = datetime.combine(end_date, datetime.min.time(), tzinfo=tz)
        title = f"Oylik statistika ({start_date.strftime('%m.%Y')})"
    else:
        raise ValueError(f"Unknown statistics period: {period}")

    await _render_statistics(message, db, start_local, end_local, title, edit=edit)


async def _show_statistics_date_picker(message: Message, *, edit: bool = False, year: int | None = None, month: int | None = None) -> None:
    today = today_local_date()
    text = "Statistika uchun sanani tanlang:"
    markup = admin_statistics_date_picker_keyboard(year or today.year, month or today.month, today)
    if edit:
        await _safe_edit_text(message, text, markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _show_food_dates(message: Message, year: int, month: int) -> None:
    await message.answer(
        "Ovqatlar qaysi sana uchun ko'rsatilsin?",
        reply_markup=admin_date_picker_keyboard(year, month),
    )


async def _show_food_for_date(message: Message, db, selected_date: date, index: int = 0, *, edit: bool = False) -> None:
    foods = await FoodRepository(db).list_by_date(selected_date, include_inactive=True)
    if not foods:
        await message.answer(f"{selected_date.isoformat()} sanasida ovqat yo'q.")
        return
    index = max(0, min(index, len(foods) - 1))
    food = foods[index]
    status_line = "Holati: aktiv" if food["is_active"] else "Holati: yashirilgan"
    text = f"{format_food(food)}\nSana: {selected_date.isoformat()}\n{status_line}"
    markup = admin_food_manage_keyboard(int(food["id"]), selected_date.isoformat(), index, len(foods))
    if edit and food["image_file_id"]:
        await message.edit_media(
            media=InputMediaPhoto(media=food["image_file_id"], caption=text),
            reply_markup=markup,
        )
    elif edit:
        await message.edit_text(text, reply_markup=markup)
    elif food["image_file_id"]:
        await message.answer_photo(food["image_file_id"], caption=text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.message(F.text == "🖥 Admin Panel")
async def admin_panel_handler(message: Message, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        return
    await message.answer("Admin panel", reply_markup=admin_panel_reply_keyboard())


@router.message(F.text == "⬅️ Asosiy menyu")
async def back_to_main_menu(message: Message, is_admin: bool) -> None:
    await message.answer(
        "Asosiy menyu",
        reply_markup=admin_menu_keyboard() if _is_admin(is_admin) else main_menu_keyboard(),
    )


@router.message(F.text == "🍲 Ovqat qo'shish")
async def add_food_start_message(message: Message, state: FSMContext, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        return
    await state.set_state(AdminFoodStates.waiting_name)
    await message.answer("Ovqat nomini yuboring.")


@router.callback_query(F.data == "admin:add_food")
async def add_food_start(callback: CallbackQuery, state: FSMContext, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    await state.set_state(AdminFoodStates.waiting_name)
    await callback.message.answer("Ovqat nomini yuboring.")
    await callback.answer()


@router.message(AdminFoodStates.waiting_name)
async def add_food_name(message: Message, state: FSMContext) -> None:
    await state.update_data(food_name=message.text)
    await state.set_state(AdminFoodStates.waiting_image)
    await message.answer("Ovqat rasmi yuboring.")


@router.message(AdminFoodStates.waiting_image, F.photo)
async def add_food_image(message: Message, state: FSMContext, bot) -> None:
    normalized_file_id = await ImageService().normalize_and_store(bot, message.chat.id, message.photo[-1].file_id)
    await state.update_data(food_image=normalized_file_id)
    await state.set_state(AdminFoodStates.waiting_price)
    await message.answer("Narxni yuboring.")


@router.message(AdminFoodStates.waiting_price)
async def add_food_price(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.isdigit():
        await message.answer("Narx raqam bo'lishi kerak.")
        return
    await state.update_data(food_price=int(message.text))
    await state.set_state(AdminFoodStates.waiting_quantity)
    await message.answer("Miqdorini yuboring.")


@router.message(AdminFoodStates.waiting_quantity)
async def add_food_quantity(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.isdigit():
        await message.answer("Miqdor raqam bo'lishi kerak.")
        return
    await state.update_data(food_quantity=int(message.text))
    await state.set_state(AdminFoodStates.waiting_description)
    await message.answer("Tavsif yuboring.")


@router.message(AdminFoodStates.waiting_description)
async def add_food_description(message: Message, state: FSMContext, db) -> None:
    data = await state.get_data()
    food_id = await FoodRepository(db).create(
        {
            "menu_date": today_local_date(),
            "name": data["food_name"],
            "image_file_id": data["food_image"],
            "price": data["food_price"],
            "quantity": data["food_quantity"],
            "description": message.text,
            "is_active": True,
        }
    )
    await state.clear()
    await message.answer(f"Ovqat qo'shildi. ID: {food_id}")


@router.message(F.text == "📝 Ovqatlarni boshqarish")
async def admin_foods_list_message(message: Message, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        return
    today = today_local_date()
    await _show_food_dates(message, today.year, today.month)


@router.callback_query(F.data == "admin:foods")
async def admin_foods_list(callback: CallbackQuery, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    today = today_local_date()
    await _show_food_dates(callback.message, today.year, today.month)
    await callback.answer()


@router.callback_query(F.data == "admin_foods_pick_date")
async def admin_foods_pick_date(callback: CallbackQuery, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    today = today_local_date()
    await callback.message.answer(
        "Sanani tanlang:",
        reply_markup=admin_date_picker_keyboard(today.year, today.month),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_foods_month:"))
async def admin_foods_month(callback: CallbackQuery, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    year_raw, month_raw = callback.data.split(":")[1].split("-")
    year = int(year_raw)
    month = int(month_raw)
    await callback.message.edit_text(
        "Ovqatlar qaysi sana uchun ko'rsatilsin?",
        reply_markup=admin_date_picker_keyboard(year, month),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_foods_date:"))
async def admin_foods_date(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    selected_date = date.fromisoformat(callback.data.split(":")[1])
    await _show_food_for_date(callback.message, db, selected_date, index=0)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_foods_page:"))
async def admin_foods_page(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    _, selected_date_raw, index_raw = callback.data.split(":")
    selected_date = date.fromisoformat(selected_date_raw)
    index = int(index_raw)
    await _show_food_for_date(callback.message, db, selected_date, index=index, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_food:delete:"))
async def admin_food_delete(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    food_id = int(callback.data.split(":")[2])
    repo = FoodRepository(db)
    food = await repo.get_by_id(food_id)
    if not food:
        await callback.answer("Ovqat topilmadi", show_alert=True)
        return
    selected_date = food["menu_date"]
    foods_before = await repo.list_by_date(selected_date, include_inactive=True)
    current_index = next((index for index, item in enumerate(foods_before) if int(item["id"]) == food_id), 0)
    if not bool(food["is_active"]):
        try:
            await repo.delete(food_id)
            await callback.message.answer("Yashirilgan ovqat DB'dan o'chirildi.")
        except IntegrityError:
            await callback.message.answer("Bu ovqat buyurtmalarda ishlatilgan, DB'dan to'liq o'chirib bo'lmadi.")
            await callback.answer()
            return
    else:
        await repo.deactivate(food_id)
        await callback.message.answer("Ovqat menyudan olib tashlandi.")
    foods_after = await repo.list_by_date(selected_date, include_inactive=True)
    try:
        await callback.message.delete()
    except Exception:
        pass
    if foods_after:
        next_index = min(current_index, len(foods_after) - 1)
        await _show_food_for_date(callback.message, db, selected_date, index=next_index)
    else:
        await callback.message.answer(f"{selected_date.isoformat()} sanasida ovqat yo'q.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_food:edit:"))
async def admin_food_edit(callback: CallbackQuery, state: FSMContext, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    food_id = int(callback.data.split(":")[2])
    await state.update_data(edit_food_id=food_id)
    await callback.message.answer("Qaysi maydonni tahrirlaysiz?", reply_markup=admin_food_edit_fields_keyboard(food_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_food_field:"))
async def admin_food_edit_field(callback: CallbackQuery, state: FSMContext, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Maydonni ochib bo'lmadi", show_alert=True)
        return
    _, food_id_raw, field_name = parts
    await state.update_data(edit_food_id=int(food_id_raw), edit_field=field_name)
    await state.set_state(AdminFoodStates.waiting_edit_value)
    await callback.message.answer("Yangi qiymatni yuboring." if field_name != "image" else "Yangi rasmni yuboring.")
    await callback.answer()


@router.message(AdminFoodStates.waiting_edit_value)
async def admin_food_edit_value(message: Message, state: FSMContext, db, bot) -> None:
    data = await state.get_data()
    field = data["edit_field"]
    payload = {}
    if field == "image":
        if not message.photo:
            await message.answer("Rasm yuboring.")
            return
        payload["image_file_id"] = await ImageService().normalize_and_store(bot, message.chat.id, message.photo[-1].file_id)
    elif field == "name":
        payload["name"] = message.text
    elif field == "price":
        if not message.text or not message.text.isdigit():
            await message.answer("Narx raqam bo'lishi kerak.")
            return
        payload["price"] = int(message.text)
    elif field == "quantity":
        if not message.text or not message.text.isdigit():
            await message.answer("Miqdor raqam bo'lishi kerak.")
            return
        payload["quantity"] = int(message.text)
    elif field == "description":
        payload["description"] = message.text
    try:
        await FoodRepository(db).update(int(data["edit_food_id"]), payload)
    except IntegrityError:
        await message.answer("Bu qiymatni saqlab bo'lmadi. Shu sana uchun bunday nomli ovqat allaqachon mavjud.")
        return
    await state.clear()
    await message.answer("Ovqat yangilandi.")


@router.message(F.text == "📢 Bugungi menyuni yuborish")
async def broadcast_today_menu_message(message: Message, db, bot, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        return
    foods = await FoodRepository(db).list_today_all(today_local_date())
    users = await UserRepository(db).list_all()
    promotions = await PromotionRepository(db).list_active()
    credentials = await CredentialService(CredentialRepository(db)).get_credentials()
    if not foods:
        await message.answer("Broadcast uchun bugungi menyu yo'q.")
        return
    sent, failed = await BroadcastService().broadcast_menu(bot, users, foods, promotions, credentials)
    await message.answer(f"Broadcast yakunlandi. Yuborildi: {sent}, xato: {failed}")


@router.message(F.text == "💳 Kartalarni tahrirlash")
async def credentials_message(message: Message, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        return
    await _show_credentials(message, db)


@router.message(F.text == "📋 Buyurtmalar")
async def admin_orders_message(message: Message, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        return
    await _show_admin_order(message, db)


@router.callback_query(F.data.startswith("admin_credentials:"))
async def credentials_edit_start(callback: CallbackQuery, state: FSMContext, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    field_name = callback.data.split(":")[1]
    credentials = await CredentialService(CredentialRepository(db)).get_credentials()
    await state.set_state(AdminCredentialStates.waiting_value)
    await state.update_data(credential_field=field_name)
    await callback.message.answer(
        f"{_credential_field_label(field_name)} uchun yangi qiymatni yuboring.\n"
        f"Hozirgi qiymat: {credentials[field_name]}"
    )
    await callback.answer()


@router.message(AdminCredentialStates.waiting_value)
async def credentials_edit_value(message: Message, state: FSMContext, db) -> None:
    data = await state.get_data()
    field_name = data.get("credential_field")
    value = (message.text or "").strip()
    if not field_name or not value:
        await message.answer("Qiymatni yuboring.")
        return
    if field_name in {"order_accept_until", "delivery_start_time", "delivery_end_time"}:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError:
            await message.answer("Vaqtni HH:MM formatida yuboring. Masalan: 11:30")
            return
    await CredentialRepository(db).update({field_name: value})
    await state.clear()
    await message.answer(f"{_credential_field_label(field_name)} yangilandi.")
    await _show_credentials(message, db)


@router.callback_query(F.data.startswith("admin_orders_page:"))
async def admin_orders_page(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    index = int(callback.data.split(":")[1])
    await _show_admin_order(callback.message, db, index=index, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_order_cancel:"))
async def admin_order_cancel(callback: CallbackQuery, db, is_admin: bool, bot) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    _, order_id_raw, index_raw = callback.data.split(":")
    order_id = int(order_id_raw)
    index = int(index_raw)
    order_repo = OrderRepository(db)
    food_repo = FoodRepository(db)
    user_repo = UserRepository(db)
    order = await order_repo.get_order(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    if order["status"] != OrderStatus.ACCEPTED:
        await callback.answer("Faqat qabul qilingan buyurtmani bekor qilish mumkin.", show_alert=True)
        return
    items = await order_repo.get_items(order_id)
    for item in items:
        await food_repo.increase_stock(int(item["food_id"]), int(item["quantity"]))
    await order_repo.update_status(order_id, status=OrderStatus.CANCELED, payment_status=PaymentStatus.REFUNDED)
    customer = await user_repo.get_by_id(int(order["user_id"]))
    if customer:
        await bot.send_message(customer["telegram_id"], f"Buyurtma #{order_id} bekor qilindi. To'lov summasi qaytariladi.")
    await _show_admin_order(callback.message, db, index=index, edit=True)
    await callback.answer("Buyurtma bekor qilindi")


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_today_menu(callback: CallbackQuery, db, bot, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    foods = await FoodRepository(db).list_today_all(today_local_date())
    users = await UserRepository(db).list_all()
    promotions = await PromotionRepository(db).list_active()
    credentials = await CredentialService(CredentialRepository(db)).get_credentials()
    if not foods:
        await callback.message.answer("Broadcast uchun bugungi menyu yo'q.")
        await callback.answer()
        return
    sent, failed = await BroadcastService().broadcast_menu(bot, users, foods, promotions, credentials)
    await callback.message.answer(f"Broadcast yakunlandi. Yuborildi: {sent}, xato: {failed}")
    await callback.answer()


@router.message(F.text == "🎁 Aksiyalar")
async def promotion_list_message(message: Message, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        return
    promotions = await PromotionRepository(db).list_all()
    await message.answer("Aksiyalar boshqaruvi.", reply_markup=admin_promotions_keyboard(promotions))


@router.message(F.text == "📊 Statistika")
async def today_statistics(message: Message, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        return
    await _show_statistics_for_period(message, db, "today")


@router.callback_query(F.data == "admin_stats:today")
async def statistics_today_callback(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    await _show_statistics_for_period(callback.message, db, "today", edit=True)
    await callback.answer()


@router.callback_query(F.data == "admin_stats:week")
async def statistics_week_callback(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    await _show_statistics_for_period(callback.message, db, "week", edit=True)
    await callback.answer()


@router.callback_query(F.data == "admin_stats:month")
async def statistics_month_callback(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    await _show_statistics_for_period(callback.message, db, "month", edit=True)
    await callback.answer()


@router.callback_query(F.data.in_({"admin_stats:pick_date", "admin_stats:menu"}))
async def statistics_pick_date_callback(callback: CallbackQuery, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    await _show_statistics_date_picker(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_stats_month:"))
async def statistics_month_picker(callback: CallbackQuery, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    year_raw, month_raw = callback.data.split(":")[1].split("-")
    await _show_statistics_date_picker(callback.message, edit=True, year=int(year_raw), month=int(month_raw))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_stats_date:"))
async def statistics_date_callback(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    tz = ZoneInfo(settings.tz)
    selected_date = date.fromisoformat(callback.data.split(":")[1])
    start_local = datetime.combine(selected_date, datetime.min.time(), tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    title = f"Sana bo'yicha statistika ({selected_date.strftime('%d.%m.%Y')})"
    await _render_statistics(callback.message, db, start_local, end_local, title, edit=True)
    await callback.answer()


@router.callback_query(F.data == "admin:promotions")
async def promotion_list(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    promotions = await PromotionRepository(db).list_all()
    await callback.message.answer("Aksiyalar boshqaruvi.", reply_markup=admin_promotions_keyboard(promotions))
    await callback.answer()


@router.callback_query(F.data == "promotion:add")
async def promotion_add_start(callback: CallbackQuery, state: FSMContext, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    await state.clear()
    await state.set_state(AdminPromotionStates.waiting_name)
    await callback.message.answer("Aksiya nomini yuboring.")
    await callback.answer()


@router.message(AdminPromotionStates.waiting_name)
async def promotion_add_name(message: Message, state: FSMContext) -> None:
    await state.update_data(promotion_name=message.text)
    await state.set_state(AdminPromotionStates.waiting_type)
    await message.answer("Aksiya turini tanlang.", reply_markup=promotion_type_keyboard())


@router.callback_query(AdminPromotionStates.waiting_type, F.data.startswith("promotion_type:"))
async def promotion_add_type(callback: CallbackQuery, state: FSMContext) -> None:
    promo_type = callback.data.split(":")[1]
    await state.update_data(promotion_type=promo_type)
    if promo_type == PromotionType.FREE_DELIVERY_BY_QUANTITY.value:
        await state.set_state(AdminPromotionStates.waiting_min_quantity)
        await callback.message.answer("Nechta ovqatdan boshlab aksiya ishlasin? Faqat son yuboring.")
    elif promo_type == PromotionType.FREE_ITEM_BY_TOTAL.value:
        await state.set_state(AdminPromotionStates.waiting_min_total)
        await callback.message.answer("Necha so'mdan boshlab bonus ishlasin? Faqat son yuboring.")
    else:
        await state.set_state(AdminPromotionStates.waiting_config)
        await callback.message.answer('Config JSON yuboring. Masalan: {"food_id": 1, "buy_quantity": 3, "free_quantity": 1}')
    await callback.answer()


@router.message(AdminPromotionStates.waiting_min_quantity)
async def promotion_min_quantity(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.isdigit():
        await message.answer("Faqat son yuboring.")
        return
    await state.update_data(promotion_min_quantity=int(message.text))
    await state.set_state(AdminPromotionStates.waiting_free_delivery)
    await message.answer("Bu aksiya yetkazib berishni bepul qilsinmi?", reply_markup=yes_no_keyboard("promotion_delivery"))


@router.callback_query(AdminPromotionStates.waiting_free_delivery, F.data.startswith("promotion_delivery:"))
async def promotion_free_delivery(callback: CallbackQuery, state: FSMContext) -> None:
    is_free_delivery = callback.data.endswith(":yes")
    await state.update_data(promotion_free_delivery=is_free_delivery)
    await state.set_state(AdminPromotionStates.waiting_bonus_item)
    await callback.message.answer(
        "Bonus mahsulot nomini yuboring. Kerak bo'lmasa 'Bonus yo'q' tugmasini bosing.",
        reply_markup=skip_bonus_keyboard(),
    )
    await callback.answer()


@router.callback_query(AdminPromotionStates.waiting_bonus_item, F.data == "promotion_bonus:skip")
async def promotion_bonus_skip(callback: CallbackQuery, state: FSMContext, db) -> None:
    data = await state.get_data()
    if data.get("promotion_type") == PromotionType.FREE_ITEM_BY_TOTAL.value:
        await _create_total_promotion(state, db, None)
    else:
        await _create_quantity_promotion(state, db, None)
    await callback.message.answer("Aksiya yaratildi.")
    await callback.answer()


@router.message(AdminPromotionStates.waiting_bonus_item)
async def promotion_bonus_item(message: Message, state: FSMContext, db) -> None:
    bonus_name = (message.text or "").strip()
    data = await state.get_data()
    if data.get("promotion_type") == PromotionType.FREE_ITEM_BY_TOTAL.value:
        await _create_total_promotion(state, db, bonus_name or None)
    else:
        await _create_quantity_promotion(state, db, bonus_name or None)
    await message.answer("Aksiya yaratildi.")


async def _create_quantity_promotion(state: FSMContext, db, bonus_name: str | None) -> None:
    data = await state.get_data()
    await PromotionRepository(db).create(
        {
            "name": data["promotion_name"],
            "promotion_type": PromotionType.FREE_DELIVERY_BY_QUANTITY,
            "config": {
                "min_quantity": data["promotion_min_quantity"],
                "free_delivery": data.get("promotion_free_delivery", False),
                "bonus_text": bonus_name,
            },
            "is_active": True,
        }
    )
    await state.clear()


async def _create_total_promotion(state: FSMContext, db, bonus_text: str | None) -> None:
    data = await state.get_data()
    await PromotionRepository(db).create(
        {
            "name": data["promotion_name"],
            "promotion_type": PromotionType.FREE_ITEM_BY_TOTAL,
            "config": {
                "min_total": data["promotion_min_total"],
                "bonus_text": bonus_text,
            },
            "is_active": True,
        }
    )
    await state.clear()


@router.message(AdminPromotionStates.waiting_min_total)
async def promotion_min_total(message: Message, state: FSMContext, db) -> None:
    if not message.text or not message.text.isdigit():
        await message.answer("Faqat son yuboring.")
        return
    await state.update_data(promotion_min_total=int(message.text))
    await state.set_state(AdminPromotionStates.waiting_bonus_item)
    await message.answer(
        "Bonus matnini yuboring. Bir nechta qator yozsangiz ham bo'ladi.\nKerak bo'lmasa 'Bonus yo'q' tugmasini bosing.",
        reply_markup=skip_bonus_keyboard(),
    )


@router.message(AdminPromotionStates.waiting_config)
async def promotion_add_config(message: Message, state: FSMContext, db) -> None:
    try:
        config = json.loads(message.text)
    except json.JSONDecodeError:
        await message.answer("JSON noto'g'ri.")
        return
    data = await state.get_data()
    await PromotionRepository(db).create(
        {
            "name": data["promotion_name"],
            "promotion_type": PromotionType(data["promotion_type"]),
            "config": config,
            "is_active": True,
        }
    )
    await state.clear()
    await message.answer("Aksiya yaratildi.")


@router.callback_query(F.data.startswith("promotion:toggle:"))
async def promotion_toggle(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    _, _, promotion_id, active_flag = callback.data.split(":")
    await PromotionRepository(db).toggle(int(promotion_id), bool(int(active_flag)))
    await callback.message.answer("Aksiya holati yangilandi.")
    await callback.answer()


@router.callback_query(F.data.startswith("promotion:delete:"))
async def promotion_delete(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    promotion_id = int(callback.data.split(":")[2])
    await PromotionRepository(db).delete(promotion_id)
    await callback.message.answer("Aksiya o'chirildi.")
    await callback.answer()


@router.callback_query(F.data.startswith("order_review:"))
async def review_order(callback: CallbackQuery, db, is_admin: bool, bot) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    _, decision, order_id_raw = callback.data.split(":")
    order_id = int(order_id_raw)
    order_repo = OrderRepository(db)
    user_repo = UserRepository(db)
    food_repo = FoodRepository(db)
    order = await order_repo.get_order(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    if order["status"] in {OrderStatus.ACCEPTED, OrderStatus.REJECTED, OrderStatus.CANCELED}:
        await callback.answer("Bu buyurtma allaqachon ko'rib chiqilgan.", show_alert=True)
        return
    if decision == "accept" and order["status"] != OrderStatus.PAYMENT_SUBMITTED:
        await callback.answer("Avval foydalanuvchi to'lov chekini yuborishi kerak.", show_alert=True)
        return

    if decision == "accept":
        new_status = OrderStatus.ACCEPTED
        payment_status = PaymentStatus.PAID
    else:
        new_status = OrderStatus.REJECTED
        payment_status = PaymentStatus.REJECTED
        items = await order_repo.get_items(order_id)
        for item in items:
            await food_repo.increase_stock(int(item["food_id"]), int(item["quantity"]))

    await order_repo.update_status(order_id, status=new_status, payment_status=payment_status)
    customer = await user_repo.get_by_id(order["user_id"])
    if customer:
        text = (
            f"Buyurtma #{order_id} qabul qilindi. Tez orada tayyorlanadi."
            if decision == "accept"
            else f"Buyurtma #{order_id} rad etildi."
        )
        await bot.send_message(customer["telegram_id"], text)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Yangilandi")
