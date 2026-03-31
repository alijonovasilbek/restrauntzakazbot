from __future__ import annotations

import json

from aiogram import F, Router
from bot.pending_carts import pop as pending_pop
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ContentType, InputMediaPhoto, Message

from bot.config import settings
from bot.fsm.states import CheckoutStates
from bot.keyboards.inline import cart_keyboard, menu_carousel_keyboard, orders_pagination_keyboard
from bot.keyboards.reply import main_menu_keyboard, request_location_keyboard, request_phone_keyboard
from bot.models.enums import OrderStatus, PaymentStatus
from bot.repositories.address_repository import AddressRepository
from bot.repositories.credential_repository import CredentialRepository
from bot.repositories.food_repository import FoodRepository
from bot.repositories.order_repository import OrderRepository
from bot.repositories.promotion_repository import PromotionRepository
from bot.repositories.user_repository import UserRepository
from bot.services.admin_notifier import AdminNotifier
from bot.services.cart_service import CartService
from bot.services.image_service import ImageService
from bot.services.credential_service import CredentialService
from bot.services.menu_service import today_local_date
from bot.services.order_service import OrderService
from bot.services.promotion_service import PromotionService
from bot.utils.formatters import format_cart, format_menu_item, format_orders_page, order_display_id

router = Router()
cart_service = CartService()
ORDERS_PER_PAGE = 3


def _delivery_fee_label(delivery_fee: int) -> str:
    return "🚚 + Yetkazib berish narxi" if delivery_fee < 0 else f"🚚 {delivery_fee} so'm"


def _bonus_text(summary_lines: list[str], bonus_items: list[str]) -> str:
    if bonus_items:
        return "🎁 Bonus:\n" + "\n".join(bonus_items)
    return "🎁 Bonus: yo'q"


async def _show_menu(message: Message, db, page: int = 0) -> None:
    items = await FoodRepository(db).list_today_all(today_local_date())
    total = len(items)
    if not items:
        await message.answer("Bugungi menyu hali qo'shilmagan.")
        return
    food = items[page]
    photo = await ImageService().normalize_from_file_id(message.bot, food["image_file_id"])
    await message.answer_photo(
        photo=photo,
        caption=format_menu_item(food, page, total),
        reply_markup=menu_carousel_keyboard(int(food["id"]), page, total, int(food["quantity"]) > 0),
    )


async def _update_menu_carousel(callback: CallbackQuery, db, index: int) -> None:
    items = await FoodRepository(db).list_today_all(today_local_date())
    total = len(items)
    if not items:
        await callback.answer("Bugungi menyu bo'sh", show_alert=True)
        return
    if index < 0 or index >= total:
        index = 0
    food = items[index]
    photo = await ImageService().normalize_from_file_id(callback.bot, food["image_file_id"])
    await callback.message.edit_media(
        media=InputMediaPhoto(media=photo, caption=format_menu_item(food, index, total)),
        reply_markup=menu_carousel_keyboard(int(food["id"]), index, total, int(food["quantity"]) > 0),
    )


async def _show_or_update_cart_message(message: Message, state: FSMContext, db=None) -> None:
    cart = await cart_service.get_cart(state)
    bonus_items: list[str] = []
    if cart and db is not None:
        promotions = await PromotionRepository(db).list_active()
        promo_result = PromotionService(settings.default_delivery_fee).apply(list(cart.values()), promotions)
        bonus_items = promo_result.bonus_items
    text = format_cart(cart, bonus_items)
    markup = cart_keyboard(list(cart.values())) if cart else None
    chat_id, message_id = await cart_service.get_cart_message_meta(state)

    if chat_id and message_id:
        try:
            await message.bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
            )
            if not cart:
                await cart_service.clear_cart_message_meta(state)
            return
        except TelegramBadRequest:
            await cart_service.clear_cart_message_meta(state)

    sent = await message.answer(text, reply_markup=markup)
    if cart:
        await cart_service.set_cart_message_meta(state, sent.chat.id, sent.message_id)


async def _build_orders_page(db, user_id: int, page: int) -> tuple[str, object | None]:
    repo = OrderRepository(db)
    orders = await repo.list_user_orders(user_id)
    if not orders:
        return "Buyurtmalaringiz yo'q.", None
    total_pages = (len(orders) + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * ORDERS_PER_PAGE
    chunk = orders[start : start + ORDERS_PER_PAGE]
    orders_with_items = []
    for order in chunk:
        items = await repo.get_items(int(order["id"]))
        orders_with_items.append((order, items))
    markup = orders_pagination_keyboard(page, has_prev=page > 0, has_next=page < total_pages - 1)
    return format_orders_page(orders_with_items, page, total_pages), markup


@router.message(F.text == "🍽 Bugungi menyu")
async def todays_menu_handler(message: Message, db) -> None:
    await _show_menu(message, db, page=0)


@router.callback_query(F.data.startswith("menu_nav:"))
async def menu_nav_handler(callback: CallbackQuery, db) -> None:
    index = int(callback.data.split(":")[1])
    await _update_menu_carousel(callback, db, index)
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
    await _show_or_update_cart_message(callback.message, state, db)
    await callback.answer("Savatga qo'shildi")


@router.message(F.text == "🛒 Savat")
async def cart_view_handler(message: Message, state: FSMContext, db) -> None:
    await _show_or_update_cart_message(message, state, db)


@router.callback_query(F.data == "cart_clear")
async def cart_clear_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await cart_service.clear(state)
    await _show_or_update_cart_message(callback.message, state)
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
    await _show_or_update_cart_message(callback.message, state, db)
    await callback.answer()


@router.callback_query(F.data == "checkout:start")
async def checkout_start_handler(callback: CallbackQuery, state: FSMContext, db) -> None:
    cart = await cart_service.get_cart(state)
    if not cart:
        await callback.answer("Savat bo'sh", show_alert=True)
        return
    user = await UserRepository(db).get_by_telegram_id(callback.from_user.id)
    if not user or not user["phone"]:
        await state.set_state(CheckoutStates.waiting_phone)
        await callback.message.answer("Birinchi buyurtma uchun telefon yuboring.", reply_markup=request_phone_keyboard())
    else:
        await state.update_data(checkout_phone=user["phone"])
        await state.set_state(CheckoutStates.waiting_location)
        await callback.message.answer("Lokatsiyani yuboring yoki manzilni yozing.", reply_markup=request_location_keyboard())
    await callback.answer()


@router.message(CheckoutStates.waiting_phone, F.contact)
async def phone_received_handler(message: Message, state: FSMContext, db) -> None:
    phone = message.contact.phone_number
    await UserRepository(db).set_phone(message.from_user.id, phone)
    await state.update_data(checkout_phone=phone)
    await state.set_state(CheckoutStates.waiting_location)
    await message.answer("Endi lokatsiyani yuboring yoki manzilni yozing.", reply_markup=request_location_keyboard())


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
    await cart_service.clear_cart_message_meta(state)
    await state.update_data(active_order_id=order_id)
    await state.set_state(CheckoutStates.waiting_receipt)
    credentials = await CredentialService(CredentialRepository(db)).get_credentials()
    item_lines = [f"- {item['name']} x {item['quantity']} = {item['price'] * item['quantity']} so'm" for item in cart.values()]
    bonus_text = _bonus_text(list(pricing["promotion_summary"]), pricing["bonus_items"])
    await message.answer(
        (
            f"Buyurtma #{order_display_id(order_id)} yaratildi.\n"
            f"\nMahsulotlar:\n" + "\n".join(item_lines) + "\n\n"
            f"Jami: {pricing['total_price']} so'm\n"
            f"{_delivery_fee_label(pricing['delivery_fee'])}\n"
            f"Chegirma: {pricing['discount_amount']} so'm\n"
            f"{bonus_text}\n\n"
            f"💳 Karta raqami: <code>{credentials['payment_card_number']}</code>\n"
            f"👤 Karta egasi: {credentials['payment_card_owner']}\n\n"
            "To'lov qilgach, chekni rasm yoki PDF ko'rinishida yuboring."
        ),
        reply_markup=main_menu_keyboard(),
    )


@router.message(CheckoutStates.waiting_location, F.location)
async def location_received_handler(message: Message, state: FSMContext, db) -> None:
    await _finalize_order(message, state, db, message.from_user.id, message.location.latitude, message.location.longitude, None)


@router.message(CheckoutStates.waiting_location, F.text)
async def address_text_received_handler(message: Message, state: FSMContext, db) -> None:
    text = (message.text or "").strip()
    if text == "✍️ Manzilni yozaman":
        await message.answer("Manzilni matn ko'rinishida yuboring. Masalan: Xadra 9, 2-podyezd.")
        return
    await _finalize_order(message, state, db, message.from_user.id, 0.0, 0.0, text)


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
    await message.answer("Lokatsiyani yuboring yoki manzilni matn qilib yozing.")


@router.message(CheckoutStates.waiting_receipt)
async def receipt_fallback_handler(message: Message) -> None:
    await message.answer("Chekni rasm yoki PDF ko'rinishida yuboring.")


@router.message(F.web_app_data)
async def webapp_checkout_handler(message: Message, state: FSMContext, db) -> None:
    """WebApp 'Botda buyurtma berish' tugmasi bosilganda cart JSON keladi."""
    raw = message.web_app_data.data if message.web_app_data else ""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        await message.answer("WebApp ma'lumotini o'qib bo'lmadi.")
        return

    if payload.get("action") != "webapp_checkout":
        return

    raw_items: list[dict] = payload.get("items", [])
    if not raw_items:
        await message.answer("Savatcha bo'sh. Avval taom tanlang.")
        return

    food_repo = FoodRepository(db)
    cart_items: list[dict] = []
    for raw_item in raw_items:
        food_id  = int(raw_item.get("food_id", 0))
        quantity = int(raw_item.get("quantity", 0))
        if food_id <= 0 or quantity <= 0:
            continue
        food = await food_repo.get_by_id(food_id)
        if not food or not bool(food["is_active"]):
            await message.answer(f"'{raw_item.get('name', '')}' mahsuloti topilmadi.")
            return
        if int(food["quantity"]) < quantity:
            await message.answer(f"'{food['name']}' uchun yetarli qoldiq yo'q ({food['quantity']} ta mavjud).")
            return
        cart_items.append({
            "food_id":  int(food["id"]),
            "name":     str(food["name"]),
            "price":    int(food["price"]),
            "quantity": quantity,
        })

    if not cart_items:
        await message.answer("Savatcha ma'lumotlari noto'g'ri.")
        return

    await cart_service.save_cart(state, {str(i["food_id"]): i for i in cart_items})

    # Aksiyalarni hisoblaymiz
    promotions = await PromotionRepository(db).list_active()
    promo = PromotionService(settings.default_delivery_fee).apply(cart_items, promotions)
    item_lines = "\n".join(f"- {i['name']} x {i['quantity']} = {i['price'] * i['quantity']:,} so'm" for i in cart_items)
    bonus_lines = ""
    if promo.bonus_items:
        bonus_lines = "\n🎁 Bonus:\n" + "\n".join(f"+ {b}" for b in promo.bonus_items)
    if promo.delivery_fee == 0:
        bonus_lines += "\n🚚 Yetkazib berish bepul!"
    total = sum(i["price"] * i["quantity"] for i in cart_items)

    user = await UserRepository(db).get_by_telegram_id(message.from_user.id)
    if not user or not user["phone"]:
        await state.set_state(CheckoutStates.waiting_phone)
        await message.answer(
            f"📦 <b>Mahsulotlar:</b>\n{item_lines}{bonus_lines}\n\n"
            f"<b>Jami: {total:,} so'm</b>\n\n"
            "📱 Birinchi buyurtma uchun telefon raqamingizni yuboring.",
            parse_mode="HTML",
            reply_markup=request_phone_keyboard(),
        )
    else:
        await state.update_data(checkout_phone=user["phone"])
        await state.set_state(CheckoutStates.waiting_location)
        await message.answer(
            f"📦 <b>Mahsulotlar:</b>\n{item_lines}{bonus_lines}\n\n"
            f"<b>Jami: {total:,} so'm</b>\n\n"
            "📍 Lokatsiyani yuboring yoki manzilni matn ko'rinishida yozing.",
            parse_mode="HTML",
            reply_markup=request_location_keyboard(),
        )


@router.callback_query(F.data == "webapp_cart:start")
async def webapp_cart_start_handler(callback: CallbackQuery, state: FSMContext, db) -> None:
    """API fallback: foydalanuvchi 'Lokatsiya kiritish' tugmasini bosdi."""
    items = pending_pop(callback.from_user.id)
    if not items:
        await callback.answer("Savatcha topilmadi. Iltimos qayta urinib ko'ring.", show_alert=True)
        return

    # Stokni qayta tekshiramiz
    food_repo = FoodRepository(db)
    cart_items: list[dict] = []
    for raw_item in items:
        food_id  = int(raw_item.get("food_id", 0))
        quantity = int(raw_item.get("quantity", 0))
        food = await food_repo.get_by_id(food_id)
        if not food or not bool(food["is_active"]):
            await callback.message.answer(f"'{raw_item.get('name', '')}' hozir mavjud emas.")
            await callback.answer()
            return
        if int(food["quantity"]) < quantity:
            await callback.message.answer(
                f"'{food['name']}' uchun yetarli qoldiq yo'q ({food['quantity']} ta qoldi)."
            )
            await callback.answer()
            return
        cart_items.append({
            "food_id":  int(food["id"]),
            "name":     str(food["name"]),
            "price":    int(food["price"]),
            "quantity": quantity,
        })

    await cart_service.save_cart(state, {str(i["food_id"]): i for i in cart_items})
    await callback.message.delete()

    user = await UserRepository(db).get_by_telegram_id(callback.from_user.id)
    if not user or not user["phone"]:
        await state.set_state(CheckoutStates.waiting_phone)
        await callback.message.answer(
            "📱 Telefon raqamingizni yuboring.",
            reply_markup=request_phone_keyboard(),
        )
    else:
        await state.update_data(checkout_phone=user["phone"])
        await state.set_state(CheckoutStates.waiting_location)
        await callback.message.answer(
            "📍 Lokatsiyani yuboring yoki manzilni matn ko'rinishida yozing.",
            reply_markup=request_location_keyboard(),
        )
    await callback.answer()


@router.message(F.text == "📦 Buyurtmalarim")
async def my_orders_handler(message: Message, db) -> None:
    user = await UserRepository(db).get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Avval /start bosing.")
        return
    text, markup = await _build_orders_page(db, int(user["id"]), 0)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("orders_page:"))
async def orders_page_handler(callback: CallbackQuery, db) -> None:
    user = await UserRepository(db).get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Avval /start bosing.", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    text, markup = await _build_orders_page(db, int(user["id"]), page)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()
