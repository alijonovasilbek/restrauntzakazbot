from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.fsm.states import AdminFoodStates, AdminPromotionStates
from bot.keyboards.inline import (
    admin_food_edit_fields_keyboard,
    admin_food_manage_keyboard,
    admin_panel_keyboard,
    admin_promotions_keyboard,
    promotion_type_keyboard,
    skip_bonus_keyboard,
    yes_no_keyboard,
)
from bot.models.enums import OrderStatus, PaymentStatus, PromotionType
from bot.repositories.food_repository import FoodRepository
from bot.repositories.order_repository import OrderRepository
from bot.repositories.promotion_repository import PromotionRepository
from bot.repositories.user_repository import UserRepository
from bot.services.broadcast_service import BroadcastService
from bot.services.menu_service import today_local_date
from bot.utils.formatters import format_food

router = Router()


def _is_admin(is_admin: bool) -> bool:
    return is_admin


@router.message(F.text == "🔐 Admin panel")
async def admin_panel_handler(message: Message, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        return
    await message.answer("Admin panel", reply_markup=admin_panel_keyboard())


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
async def add_food_image(message: Message, state: FSMContext) -> None:
    await state.update_data(food_image=message.photo[-1].file_id)
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


@router.callback_query(F.data == "admin:foods")
async def admin_foods_list(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    foods = await FoodRepository(db).list_today_all(today_local_date())
    if not foods:
        await callback.message.answer("Bugungi ovqatlar yo'q.")
    for food in foods:
        text = format_food(food)
        markup = admin_food_manage_keyboard(int(food["id"]))
        if food["image_file_id"]:
            await callback.message.answer_photo(food["image_file_id"], caption=text, reply_markup=markup)
        else:
            await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_food:delete:"))
async def admin_food_delete(callback: CallbackQuery, db, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    food_id = int(callback.data.split(":")[2])
    await FoodRepository(db).delete(food_id)
    await callback.message.answer("Ovqat o'chirildi.")
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
    _, _, food_id_raw, field_name = callback.data.split(":")
    await state.update_data(edit_food_id=int(food_id_raw), edit_field=field_name)
    await state.set_state(AdminFoodStates.waiting_edit_value)
    await callback.message.answer("Yangi qiymatni yuboring." if field_name != "image" else "Yangi rasmni yuboring.")
    await callback.answer()


@router.message(AdminFoodStates.waiting_edit_value)
async def admin_food_edit_value(message: Message, state: FSMContext, db) -> None:
    data = await state.get_data()
    field = data["edit_field"]
    payload = {}
    if field == "image":
        if not message.photo:
            await message.answer("Rasm yuboring.")
            return
        payload["image_file_id"] = message.photo[-1].file_id
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
    await FoodRepository(db).update(int(data["edit_food_id"]), payload)
    await state.clear()
    await message.answer("Ovqat yangilandi.")


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_today_menu(callback: CallbackQuery, db, bot, is_admin: bool) -> None:
    if not _is_admin(is_admin):
        await callback.answer()
        return
    foods = await FoodRepository(db).list_today_all(today_local_date())
    users = await UserRepository(db).list_all()
    if not foods:
        await callback.message.answer("Broadcast uchun bugungi menyu yo'q.")
        await callback.answer()
        return
    sent, failed = await BroadcastService().broadcast_menu(bot, users, foods)
    await callback.message.answer(f"Broadcast yakunlandi. Yuborildi: {sent}, xato: {failed}")
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
        await callback.message.answer("Necha so'mdan boshlab bonus berilsin? Faqat son yuboring.")
    else:
        await state.set_state(AdminPromotionStates.waiting_config)
        await callback.message.answer(
            "Config JSON yuboring. Masalan: {\"food_id\": 1, \"buy_quantity\": 3, \"free_quantity\": 1}"
        )
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
    await _create_quantity_promotion(state, db, None)
    await callback.message.answer("Aksiya yaratildi.")
    await callback.answer()


@router.message(AdminPromotionStates.waiting_bonus_item)
async def promotion_bonus_item(message: Message, state: FSMContext, db) -> None:
    bonus_name = (message.text or "").strip()
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
                "free_item_name": bonus_name,
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
    data = await state.get_data()
    await PromotionRepository(db).create(
        {
            "name": data["promotion_name"],
            "promotion_type": PromotionType.FREE_ITEM_BY_TOTAL,
            "config": {
                "min_total": int(message.text),
                "free_item_name": "Kompot",
            },
            "is_active": True,
        }
    )
    await state.clear()
    await message.answer("Aksiya yaratildi.")


@router.message(AdminPromotionStates.waiting_config)
async def promotion_add_config(message: Message, state: FSMContext, db) -> None:
    import json

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
    if order["status"] in {OrderStatus.ACCEPTED, OrderStatus.REJECTED}:
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
            else "Payment rejected, please try again."
        )
        await bot.send_message(customer["telegram_id"], text)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Yangilandi")
