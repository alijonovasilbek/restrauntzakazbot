from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ContentType, Message

from bot.config import settings
from bot.fsm.states import CheckoutStates
from bot.keyboards.inline import cart_keyboard, food_actions_keyboard, menu_pagination_keyboard, saved_address_keyboard
from bot.keyboards.reply import main_menu_keyboard, request_location_keyboard, request_phone_keyboard
from bot.models.enums import OrderStatus, PaymentStatus
from bot.repositories.address_repository import AddressRepository
from bot.repositories.food_repository import FoodRepository
from bot.repositories.order_repository import OrderRepository
from bot.repositories.promotion_repository import PromotionRepository
from bot.repositories.user_repository import UserRepository
from bot.services.admin_notifier import AdminNotifier
from bot.services.cart_service import CartService
from bot.services.menu_service import today_local_date
from bot.services.order_service import OrderService
from bot.utils.formatters import format_cart, format_food, format_order_summary

router = Router()
cart_service = CartService()


async def _show_menu(message: Message, db, page: int = 0) -> None:
    repo = FoodRepository(db)
    today = today_local_date()
    limit = 5
    items = await repo.list_today(today, offset=page * limit, limit=limit)
    total = await repo.count_today(today)
    if not items:
        await message.answer("Bugungi menyu hali qo'shilmagan.")
        return
    for food in items:
        text = format_food(food)
        markup = food_actions_keyboard(int(food["id"]), int(food["quantity"]) > 0)
        if food["image_file_id"]:
            await message.answer_photo(food["image_file_id"], caption=text, reply_markup=markup)
        else:
            await message.answer(text, reply_markup=markup)
    has_prev = page > 0
    has_next = (page + 1) * limit < total
    if has_prev or has_next:
        await message.answer("Sahifalash:", reply_markup=menu_pagination_keyboard(page, has_prev, has_next))


@router.message(F.text == "🍽 Bugungi menyu")
async def todays_menu_handler(message: Message, db) -> None:
    await _show_menu(message, db, page=0)


@router.callback_query(F.data.startswith("menu_page:"))
async def menu_page_handler(callback: CallbackQuery, db) -> None:
    page = int(callback.data.split(":")[1])
    await callback.message.answer("Menyu sahifasi:")
    await _show_menu(callback.message, db, page=page)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("cart_add:"))
async def cart_add_handler(callback: CallbackQuery, state: FSMContext, db) -> None:
    food_id = int(callback.data.split(":")[1])
    food = await FoodRepository(db).get_by_id(food_id)
    if not food or int(food["quantity"]) <= 0:
        await callback.answer("Bu mahsulot tugagan", show_alert=True)
        return
    cart = await cart_service.get_cart(state)
    if cart.get(str(food_id), {}).get("quantity", 0) >= int(food["quantity"]):
        await callback.answer("Omborda bundan ko'p yo'q", show_alert=True)
        return
    await cart_service.add_item(state, food_id, food["name"], int(food["price"]))
    await callback.answer("Savatga qo'shildi")


@router.message(F.text == "🛒 Savat")
async def cart_view_handler(message: Message, state: FSMContext) -> None:
    cart = await cart_service.get_cart(state)
    markup = cart_keyboard([int(k) for k in cart.keys()]) if cart else None
    await message.answer(format_cart(cart), reply_markup=markup)


@router.callback_query(F.data == "cart_clear")
async def cart_clear_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await cart_service.clear(state)
    await callback.message.edit_text("Savat tozalandi.", reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.startswith("cart_inc:"))
@router.callback_query(F.data.startswith("cart_dec:"))
@router.callback_query(F.data.startswith("cart_remove:"))
async def cart_action_handler(callback: CallbackQuery, state: FSMContext, db) -> None:
    action, food_id_raw = callback.data.split(":")
    food_id = int(food_id_raw)
    if action == "cart_inc":
        food = await FoodRepository(db).get_by_id(food_id)
        if not food:
            await callback.answer("Mahsulot topilmadi", show_alert=True)
            return
        cart = await cart_service.get_cart(state)
        current_qty = cart.get(str(food_id), {}).get("quantity", 0)
        if current_qty >= int(food["quantity"]):
            await callback.answer("Omborda bundan ko'p yo'q", show_alert=True)
            return
        await cart_service.add_item(state, food_id, food["name"], int(food["price"]))
    elif action == "cart_dec":
        await cart_service.change_quantity(state, food_id, -1)
    elif action == "cart_remove":
        cart = await cart_service.get_cart(state)
        cart.pop(str(food_id), None)
        await cart_service.save_cart(state, cart)
    cart = await cart_service.get_cart(state)
    if cart:
        await callback.message.edit_text(format_cart(cart), reply_markup=cart_keyboard([int(k) for k in cart.keys()]))
    else:
        await callback.message.edit_text("Savat bo'sh.", reply_markup=None)
    await callback.answer()


@router.callback_query(F.data == "checkout:start")
async def checkout_start_handler(callback: CallbackQuery, state: FSMContext, db) -> None:
    cart = await cart_service.get_cart(state)
    if not cart:
        await callback.answer("Savat bo'sh", show_alert=True)
        return
    user_repo = UserRepository(db)
    address_repo = AddressRepository(db)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    default_address = await address_repo.get_default(user["id"]) if user else None
    if not user or not user["phone"]:
        await state.set_state(CheckoutStates.waiting_phone)
        await callback.message.answer("Birinchi buyurtma uchun telefon yuboring.", reply_markup=request_phone_keyboard())
    elif default_address:
        await state.update_data(checkout_phone=user["phone"])
        await state.set_state(CheckoutStates.waiting_location_choice)
        await callback.message.answer("Avvalgi manzil topildi.")
        await callback.message.answer("Manzilni tanlang:", reply_markup=saved_address_keyboard())
    else:
        await state.update_data(checkout_phone=user["phone"])
        await state.set_state(CheckoutStates.waiting_location)
        await callback.message.answer("Lokatsiyani yuboring.", reply_markup=request_location_keyboard())
    await callback.answer()


@router.message(CheckoutStates.waiting_phone, F.contact)
async def phone_received_handler(message: Message, state: FSMContext, db) -> None:
    phone = message.contact.phone_number
    await UserRepository(db).set_phone(message.from_user.id, phone)
    await state.update_data(checkout_phone=phone)
    await state.set_state(CheckoutStates.waiting_location)
    await message.answer("Endi lokatsiyani yuboring.", reply_markup=request_location_keyboard())


@router.callback_query(CheckoutStates.waiting_location_choice, F.data == "address:use_saved")
async def use_saved_address_handler(callback: CallbackQuery, state: FSMContext, db) -> None:
    user = await UserRepository(db).get_by_telegram_id(callback.from_user.id)
    address = await AddressRepository(db).get_default(user["id"])
    if not address:
        await state.set_state(CheckoutStates.waiting_location)
        await callback.message.answer("Saqlangan manzil topilmadi. Yangisini yuboring.", reply_markup=request_location_keyboard())
        await callback.answer()
        return
    await _finalize_order(
        callback.message,
        state,
        db,
        callback.from_user.id,
        float(address["latitude"]),
        float(address["longitude"]),
        address["address_text"],
    )
    await callback.answer()


@router.callback_query(CheckoutStates.waiting_location_choice, F.data == "address:new")
async def new_address_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CheckoutStates.waiting_location)
    await callback.message.answer("Yangi lokatsiyani yuboring.", reply_markup=request_location_keyboard())
    await callback.answer()


async def _finalize_order(message: Message, state: FSMContext, db, telegram_id: int, latitude: float, longitude: float, address_text: str | None) -> None:
    state_data = await state.get_data()
    phone = state_data.get("checkout_phone")
    cart = await cart_service.get_cart(state)
    if not phone:
        await message.answer("Telefon topilmadi. Qaytadan urinib ko'ring.")
        await state.clear()
        return
    service = OrderService(
        user_repo=UserRepository(db),
        address_repo=AddressRepository(db),
        food_repo=FoodRepository(db),
        order_repo=OrderRepository(db),
        promotion_repo=PromotionRepository(db),
    )
    try:
        order_id, pricing = await service.create_order(
            telegram_id=telegram_id,
            phone=phone,
            latitude=latitude,
            longitude=longitude,
            address_text=address_text,
            cart_items=list(cart.values()),
        )
    except ValueError as exc:
        await message.answer(str(exc), reply_markup=main_menu_keyboard())
        await state.clear()
        return
    await cart_service.clear(state)
    await state.update_data(active_order_id=order_id)
    await state.set_state(CheckoutStates.waiting_receipt)
    promo_lines = list(pricing["promotion_summary"])
    if pricing["bonus_items"]:
        promo_lines.append(f"Bonus: {', '.join(pricing['bonus_items'])}")
    promo_text = "\n".join(promo_lines) if promo_lines else "Aksiya yo'q"
    await message.answer(
        (
            f"Buyurtma #{order_id} yaratildi.\n"
            f"Jami: {pricing['total_price']} so'm\n"
            f"Yetkazib berish: {pricing['delivery_fee']} so'm\n"
            f"Chegirma: {pricing['discount_amount']} so'm\n"
            f"Aksiya: {promo_text}\n\n"
            f"To'lov uchun karta: {settings.payment_card_number}\n"
            f"Karta egasi: {settings.payment_card_owner}\n\n"
            "To'lov qilgach, chekni rasm yoki PDF ko'rinishida yuboring."
        ),
        reply_markup=main_menu_keyboard(),
    )


@router.message(CheckoutStates.waiting_location, F.location)
async def location_received_handler(message: Message, state: FSMContext, db) -> None:
    await _finalize_order(message, state, db, message.from_user.id, message.location.latitude, message.location.longitude, None)


@router.message(CheckoutStates.waiting_receipt, F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT}))
async def receipt_received_handler(message: Message, state: FSMContext, db, bot) -> None:
    data = await state.get_data()
    order_id = data.get("active_order_id")
    if not order_id:
        await message.answer("Aktiv buyurtma topilmadi.")
        await state.clear()
        return
    if message.photo:
        file_id = message.photo[-1].file_id
        receipt_type = "photo"
    elif message.document and ((message.document.mime_type or "") == "application/pdf" or (message.document.mime_type or "").startswith("image/")):
        file_id = message.document.file_id
        receipt_type = "document"
    else:
        await message.answer("Chekni rasm yoki PDF ko'rinishida yuboring.")
        return
    order_repo = OrderRepository(db)
    user_repo = UserRepository(db)
    await order_repo.create_payment(order_id, file_id, receipt_type)
    await order_repo.update_status(order_id, status=OrderStatus.PAYMENT_SUBMITTED, payment_status=PaymentStatus.SUBMITTED)
    order = await order_repo.get_order(order_id)
    items = await order_repo.get_items(order_id)
    payment = await order_repo.get_latest_payment(order_id)
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    admin_message_id = await AdminNotifier().notify_new_order(bot, order, items, user, payment)
    await order_repo.update_status(order_id, admin_group_message_id=admin_message_id)
    await message.answer("Chek qabul qilindi. Admin tasdiqlashini kuting.", reply_markup=main_menu_keyboard())
    await state.clear()


@router.message(CheckoutStates.waiting_phone)
async def phone_fallback_handler(message: Message) -> None:
    await message.answer("Telefonni kontakt tugmasi orqali yuboring.")


@router.message(CheckoutStates.waiting_location)
async def location_fallback_handler(message: Message) -> None:
    await message.answer("Lokatsiyani tugma orqali yuboring.")


@router.message(CheckoutStates.waiting_receipt)
async def receipt_fallback_handler(message: Message) -> None:
    await message.answer("Chekni rasm yoki PDF ko'rinishida yuboring.")


@router.message(F.text == "📦 Buyurtmalarim")
async def my_orders_handler(message: Message, db) -> None:
    user = await UserRepository(db).get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Avval /start bosing.")
        return
    orders = await OrderRepository(db).list_user_orders(user["id"])
    if not orders:
        await message.answer("Buyurtmalaringiz yo'q.")
        return
    for order in orders[:10]:
        items = await OrderRepository(db).get_items(int(order["id"]))
        await message.answer(format_order_summary(order, items))
