from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
import io

from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from bot.config import settings
from bot.database.engine import get_connection
from bot.database.session import DatabaseSession
from bot.models.enums import OrderStatus, PaymentStatus, PromotionType
from bot.repositories.address_repository import AddressRepository
from bot.repositories.credential_repository import CredentialRepository
from bot.repositories.food_repository import FoodRepository
from bot.repositories.order_repository import OrderRepository
from bot.repositories.promotion_repository import PromotionRepository
from bot.repositories.user_repository import UserRepository
from bot.services.admin_notifier import AdminNotifier
from bot.services.broadcast_service import BroadcastService
from bot.services.credential_service import CredentialService
from bot.services.menu_service import today_local_date
from bot.fsm.states import CheckoutStates
from bot.keyboards.reply import request_location_keyboard, request_phone_keyboard
from bot.pending_carts import save as pending_save
from bot.services.order_service import OrderService
from bot.services.promotion_service import PromotionService
from bot.shared import get_dispatcher
from bot.utils.formatters import order_display_id


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"
RECEIPTS_DIR = UPLOADS_DIR / "receipts"
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Zakaz WebApp")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


async def get_db() -> DatabaseSession:
    async with get_connection() as connection:
        yield DatabaseSession(connection)


def require_admin(telegram_id: int) -> None:
    if telegram_id not in settings.admin_ids:
        raise HTTPException(status_code=403, detail="Admin access required")


def _serialize_food(food: dict) -> dict:
    return {
        "id": int(food["id"]),
        "menu_date": food["menu_date"].isoformat(),
        "name": str(food["name"]),
        "image_file_id": str(food["image_file_id"] or ""),
        "price": int(food["price"]),
        "quantity": int(food["quantity"]),
        "description": str(food["description"] or ""),
        "is_active": bool(food["is_active"]),
    }


def _serialize_promotion(promo: dict) -> dict:
    return {
        "id": int(promo["id"]),
        "name": str(promo["name"]),
        "promotion_type": str(promo["promotion_type"]),
        "config": promo["config"],
        "is_active": bool(promo["is_active"]),
    }


def _serialize_order(order: dict, items: list[dict], user: dict | None) -> dict:
    return {
        "id": int(order["id"]),
        "display_id": order_display_id(int(order["id"])),
        "status": str(order["status"]),
        "payment_status": str(order["payment_status"]),
        "total_price": int(order["total_price"]),
        "delivery_fee": int(order["delivery_fee"]),
        "discount_amount": int(order["discount_amount"]),
        "phone": str(order["phone"]),
        "location_text": str(order["location_text"] or ""),
        "created_at": order["created_at"].isoformat() if order.get("created_at") else "",
        "user": {
            "id": int(user["id"]) if user else 0,
            "full_name": str(user["full_name"]) if user else "",
            "username": str(user["username"] or "") if user else "",
            "telegram_id": int(user["telegram_id"]) if user else 0,
        },
        "items": [
            {
                "food_id": int(item["food_id"]),
                "food_name": str(item["food_name"]),
                "unit_price": int(item["unit_price"]),
                "quantity": int(item["quantity"]),
                "line_total": int(item["line_total"]),
            }
            for item in items
        ],
    }


async def _get_credentials_dict(db: DatabaseSession) -> dict:
    return await CredentialService(CredentialRepository(db)).get_credentials()


async def _stats_for_period(db: DatabaseSession, period: str, selected_date: date | None = None) -> dict:
    tz = ZoneInfo(settings.tz)
    now = datetime.now(tz)
    today = now.date()
    if period == "today":
        start_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        label = f"Bugun ({today.isoformat()})"
    elif period == "week":
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=7)
        start_local = datetime.combine(start_date, datetime.min.time(), tzinfo=tz)
        end_local = datetime.combine(end_date, datetime.min.time(), tzinfo=tz)
        label = f"Hafta ({start_date.isoformat()} - {(end_date - timedelta(days=1)).isoformat()})"
    elif period == "month":
        start_date = today.replace(day=1)
        if start_date.month == 12:
            end_date = date(start_date.year + 1, 1, 1)
        else:
            end_date = date(start_date.year, start_date.month + 1, 1)
        start_local = datetime.combine(start_date, datetime.min.time(), tzinfo=tz)
        end_local = datetime.combine(end_date, datetime.min.time(), tzinfo=tz)
        label = f"Oy ({start_date.strftime('%Y-%m')})"
    elif period == "date" and selected_date:
        start_local = datetime.combine(selected_date, datetime.min.time(), tzinfo=tz)
        end_local = start_local + timedelta(days=1)
        label = f"Sana ({selected_date.isoformat()})"
    else:
        raise HTTPException(status_code=400, detail="Invalid period")

    repo = OrderRepository(db)
    orders = await repo.list_orders_between(start_local, end_local)
    order_ids = [int(order["id"]) for order in orders]
    items = await repo.list_items_for_orders(order_ids)
    sold_by_food: dict[str, int] = {}
    for item in items:
        sold_by_food[str(item["food_name"])] = sold_by_food.get(str(item["food_name"]), 0) + int(item["quantity"])

    return {
        "label": label,
        "orders_count": len(orders),
        "accepted_count": sum(1 for order in orders if str(order["status"]) == OrderStatus.ACCEPTED.value),
        "submitted_count": sum(1 for order in orders if str(order["payment_status"]) == PaymentStatus.SUBMITTED.value),
        "paid_total": sum(int(order["total_price"]) for order in orders if str(order["payment_status"]) == PaymentStatus.PAID.value),
        "pending_total": sum(int(order["total_price"]) for order in orders if str(order["payment_status"]) != PaymentStatus.PAID.value),
        "sold_by_food": sold_by_food,
    }


@app.post("/api/user/cart/send")
async def send_cart_to_bot(
    telegram_id: int = Form(...),
    items_json: str = Form(...),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    """
    Webapp savatchasini qabul qilib, FSM state ni o'rnatadi va
    botda to'g'ridan-to'g'ri telefon yoki lokatsiya so'raydi.
    """
    if telegram_id <= 0:
        raise HTTPException(status_code=400, detail="Telegram foydalanuvchi aniqlanmadi")
    try:
        raw_items = json.loads(items_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Noto'g'ri format") from exc
    if not isinstance(raw_items, list) or not raw_items:
        raise HTTPException(status_code=400, detail="Savatcha bo'sh")

    # 1. Stokni tekshirib, validated list tuzamiz
    food_repo = FoodRepository(db)
    validated: list[dict] = []
    for raw in raw_items:
        food_id  = int(raw.get("food_id", 0))
        quantity = int(raw.get("quantity", 0))
        if food_id <= 0 or quantity <= 0:
            continue
        food = await food_repo.get_by_id(food_id)
        if not food or not bool(food["is_active"]):
            raise HTTPException(status_code=400, detail=f"Mahsulot topilmadi: {raw.get('name', '')}")
        if int(food["quantity"]) < quantity:
            raise HTTPException(status_code=400, detail=f"{food['name']}: yetarli qoldiq yo'q")
        validated.append({
            "food_id":  int(food["id"]),
            "name":     str(food["name"]),
            "price":    int(food["price"]),
            "quantity": quantity,
        })
    if not validated:
        raise HTTPException(status_code=400, detail="Savatcha bo'sh yoki noto'g'ri")

    # 2. Aksiyalarni hisoblash
    promotions = await PromotionRepository(db).list_active()
    promo = PromotionService(settings.default_delivery_fee).apply(validated, promotions)

    # 3. Xabar matni: mahsulotlar + aksiyalar
    item_lines = "\n".join(
        f"- {i['name']} x {i['quantity']} = {i['price'] * i['quantity']:,} so'm"
        for i in validated
    )
    bonus_lines = ""
    if promo.bonus_items:
        bonus_lines = "\n🎁 Bonus:\n" + "\n".join(f"+ {b}" for b in promo.bonus_items)
    if promo.delivery_fee == 0:
        bonus_lines += "\n🚚 Yetkazib berish bepul!"

    # 4. Foydalanuvchi ma'lumotlari
    user = await UserRepository(db).get_by_telegram_id(telegram_id)
    has_phone = bool(user and user.get("phone"))

    # 5. FSM state ni bevosita o'rnatamiz
    dp = get_dispatcher()
    if dp is None:
        raise HTTPException(status_code=500, detail="Bot hali tayyor emas")

    bot_id = int(settings.bot_token.split(":")[0])
    key    = StorageKey(bot_id=bot_id, chat_id=telegram_id, user_id=telegram_id)
    ctx    = FSMContext(storage=dp.storage, key=key)

    if has_phone:
        await ctx.update_data(checkout_phone=str(user["phone"]))
        await ctx.set_state(CheckoutStates.waiting_location)
        next_step = "📍 Lokatsiyani yuboring yoki manzilni matn ko'rinishida yozing."
        reply_kb  = request_location_keyboard()
    else:
        await ctx.set_state(CheckoutStates.waiting_phone)
        next_step = "📱 Birinchi buyurtma uchun telefon raqamingizni yuboring."
        reply_kb  = request_phone_keyboard()

    # FSM ga cartni saqlaymiz — cart_service.get_cart() reads state.data["cart"]
    await ctx.update_data(cart={str(i["food_id"]): i for i in validated})

    # 6. Bot xabari
    total = sum(i["price"] * i["quantity"] for i in validated)
    text  = (
        f"📦 <b>Mahsulotlar:</b>\n{item_lines}"
        f"{bonus_lines}\n\n"
        f"<b>Jami: {total:,} so'm</b>\n\n"
        f"{next_step}"
    )
    bot = Bot(token=settings.bot_token)
    try:
        await bot.send_message(telegram_id, text, parse_mode="HTML", reply_markup=reply_kb)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Bot xabari yuborilmadi") from exc
    finally:
        await bot.session.close()

    return {"ok": True}


@app.get("/api/image/{file_id}")
async def proxy_image(file_id: str) -> Response:
    """Telegram file_id bo'yicha rasmni brauzerga uzatadi."""
    bot = Bot(token=settings.bot_token)
    try:
        file = await bot.get_file(file_id)
        buf = io.BytesIO()
        await bot.download_file(file.file_path, destination=buf)
        buf.seek(0)
        return Response(content=buf.read(), media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        raise HTTPException(status_code=404, detail="Rasm topilmadi")
    finally:
        await bot.session.close()


@app.get("/", response_class=RedirectResponse)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/web/app")


@app.get("/web/app", response_class=HTMLResponse)
async def webapp_entry() -> HTMLResponse:
    html = """
    <!doctype html>
    <html lang="uz">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Bon Appétit</title>
      <script src="https://telegram.org/js/telegram-web-app.js"></script>
      <style>
        body{margin:0;font-family:'Segoe UI',system-ui,sans-serif;background:#fff;color:#2d3e2e;display:grid;place-items:center;min-height:100vh}
        .box{padding:32px 28px;border-radius:24px;background:#fff;border:1px solid #c8e6c9;box-shadow:0 12px 40px rgba(60,120,60,.10);max-width:360px;text-align:center}
        .logo{font-size:38px;font-weight:800;background:linear-gradient(135deg,#2e7d32,#66bb6a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:6px}
        .sub{font-size:13px;color:#7a9a7e;letter-spacing:.08em}
        .dot{display:inline-block;width:8px;height:8px;background:#66bb6a;border-radius:50%;margin:18px 4px 0;animation:blink 1.2s ease infinite}
        .dot:nth-child(2){animation-delay:.2s}.dot:nth-child(3){animation-delay:.4s}
        @keyframes blink{0%,80%,100%{opacity:.2}40%{opacity:1}}
      </style>
    </head>
    <body>
      <div class="box">
        <div class="logo">Bon Appétit</div>
        <div class="sub">Yuklanmoqda</div>
        <div><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
      </div>
      <script>
        async function boot() {
          const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
          if (tg) tg.ready();
          const user = tg && tg.initDataUnsafe ? tg.initDataUnsafe.user : null;
          if (!user || !user.id) {
            window.location.replace('/web/user');
            return;
          }
          const res = await fetch(`/api/webapp/resolve?telegram_id=${user.id}`);
          const data = await res.json();
          const target = data.role === 'admin' ? '/web/admin' : '/web/user';
          window.location.replace(`${target}?tg_id=${user.id}&full_name=${encodeURIComponent(user.first_name || '')}&username=${encodeURIComponent(user.username || '')}`);
        }
        boot();
      </script>
    </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/web/user", response_class=HTMLResponse)
async def user_page(request: Request) -> HTMLResponse:
    template = templates.get_template("user.html")
    return HTMLResponse(template.render({"request": request}))


@app.get("/web/admin", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    template = templates.get_template("admin.html")
    return HTMLResponse(template.render({"request": request}))


@app.get("/api/webapp/resolve")
async def resolve_webapp_role(telegram_id: int) -> dict:
    return {"role": "admin" if telegram_id in settings.admin_ids else "user"}


@app.post("/api/user/sync")
async def user_sync(
    telegram_id: int = Form(...),
    full_name: str = Form(...),
    username: str = Form(default=""),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    await UserRepository(db).upsert(telegram_id=telegram_id, full_name=full_name, username=username or None)
    user = await UserRepository(db).get_by_telegram_id(telegram_id)
    return {"user": {"id": int(user["id"]), "telegram_id": int(user["telegram_id"]), "full_name": str(user["full_name"]), "username": str(user["username"] or "")}}


@app.get("/api/user/menu")
async def user_menu(menu_date: str | None = Query(default=None), db: DatabaseSession = Depends(get_db)) -> dict:
    selected_date = date.fromisoformat(menu_date) if menu_date else today_local_date()
    foods = await FoodRepository(db).list_by_date(selected_date)
    promotions = await PromotionRepository(db).list_active()
    credentials = await _get_credentials_dict(db)
    return {
        "menu_date": selected_date.isoformat(),
        "foods": [_serialize_food(food) for food in foods],
        "promotions": [_serialize_promotion(promo) for promo in promotions],
        "credentials": credentials,
    }


@app.get("/api/user/orders")
async def user_orders(telegram_id: int, db: DatabaseSession = Depends(get_db)) -> dict:
    user = await UserRepository(db).get_by_telegram_id(telegram_id)
    if not user:
        return {"orders": []}
    repo = OrderRepository(db)
    orders = await repo.list_user_orders(int(user["id"]))
    payload = []
    for order in orders:
        items = await repo.get_items(int(order["id"]))
        payload.append(_serialize_order(order, items, user))
    return {"orders": payload}


@app.post("/api/user/orders")
async def create_user_order(
    telegram_id: int = Form(...),
    full_name: str = Form(...),
    username: str = Form(default=""),
    phone: str = Form(...),
    address_text: str = Form(...),
    items_json: str = Form(...),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    if telegram_id <= 0:
        raise HTTPException(status_code=400, detail="Telegram foydalanuvchi aniqlanmadi")
    if not phone.strip():
        raise HTTPException(status_code=400, detail="Telefon raqam kiritilishi shart")
    if not address_text.strip():
        raise HTTPException(status_code=400, detail="Manzil kiritilishi shart")

    await UserRepository(db).upsert(telegram_id=telegram_id, full_name=full_name, username=username or None)
    try:
        raw_items = json.loads(items_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Savat ma'lumotini o'qib bo'lmadi") from exc

    if not isinstance(raw_items, list) or not raw_items:
        raise HTTPException(status_code=400, detail="Savatcha bo'sh")

    cart_items: list[dict] = []
    food_repo = FoodRepository(db)
    for raw_item in raw_items:
        food_id = int(raw_item.get("food_id", 0))
        quantity = int(raw_item.get("quantity", 0))
        if food_id <= 0 or quantity <= 0:
            raise HTTPException(status_code=400, detail="Savatdagi mahsulot soni noto'g'ri")

        food = await food_repo.get_by_id(food_id)
        if not food or not bool(food["is_active"]):
            raise HTTPException(status_code=400, detail="Mahsulot topilmadi")
        if food["menu_date"] != today_local_date():
            raise HTTPException(status_code=400, detail=f"{food['name']} bugungi menyuda emas")
        if int(food["quantity"]) < quantity:
            raise HTTPException(status_code=400, detail=f"{food['name']} uchun yetarli qoldiq yo'q")
        cart_items.append(
            {
                "food_id": int(food["id"]),
                "name": str(food["name"]),
                "price": int(food["price"]),
                "quantity": quantity,
            }
        )

    service = OrderService(
        user_repo=UserRepository(db),
        address_repo=AddressRepository(db),
        food_repo=food_repo,
        order_repo=OrderRepository(db),
        promotion_repo=PromotionRepository(db),
    )
    try:
        order_id, pricing = await service.create_order(
            telegram_id=telegram_id,
            phone=phone.strip(),
            latitude=0.0,
            longitude=0.0,
            address_text=address_text.strip(),
            cart_items=cart_items,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    credentials = await _get_credentials_dict(db)
    return {"order_id": order_id, "pricing": pricing, "credentials": credentials}


@app.post("/api/user/orders/{order_id}/receipt")
async def upload_receipt(
    order_id: int,
    telegram_id: int = Form(...),
    receipt: UploadFile = File(...),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    order_repo = OrderRepository(db)
    user_repo = UserRepository(db)
    order = await order_repo.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user or int(user["id"]) != int(order["user_id"]):
        raise HTTPException(status_code=403, detail="Order access denied")

    suffix = Path(receipt.filename or "receipt.bin").suffix or ".bin"
    receipt_path = RECEIPTS_DIR / f"{uuid4().hex}{suffix}"
    content = await receipt.read()
    receipt_path.write_bytes(content)

    await order_repo.create_payment(order_id, str(receipt_path), "web_upload")
    await order_repo.update_status(order_id, status=OrderStatus.PAYMENT_SUBMITTED, payment_status=PaymentStatus.SUBMITTED)
    updated_order = await order_repo.get_order(order_id)
    items = await order_repo.get_items(order_id)
    payment = await order_repo.get_latest_payment(order_id)
    bot = Bot(token=settings.bot_token)
    try:
        admin_message_id = await AdminNotifier().notify_new_order(bot, updated_order, items, user, payment)
        await order_repo.update_status(order_id, admin_group_message_id=admin_message_id)
    finally:
        await bot.session.close()
    return {"ok": True}


@app.get("/api/admin/bootstrap")
async def admin_bootstrap(telegram_id: int, db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    foods = await FoodRepository(db).list_today_all(today_local_date(), include_inactive=True)
    promotions = await PromotionRepository(db).list_all()
    credentials = await _get_credentials_dict(db)
    stats = await _stats_for_period(db, "today")
    order_repo = OrderRepository(db)
    user_repo = UserRepository(db)
    orders = await order_repo.list_all_orders()
    serialized_orders = []
    for order in orders[:20]:
        items = await order_repo.get_items(int(order["id"]))
        user = await user_repo.get_by_id(int(order["user_id"]))
        serialized_orders.append(_serialize_order(order, items, user))
    return {
        "foods": [_serialize_food(food) for food in foods],
        "promotions": [_serialize_promotion(promo) for promo in promotions],
        "credentials": credentials,
        "stats": stats,
        "orders": serialized_orders,
    }


@app.get("/api/admin/foods")
async def admin_foods(telegram_id: int, menu_date: str | None = None, db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    selected_date = date.fromisoformat(menu_date) if menu_date else today_local_date()
    foods = await FoodRepository(db).list_by_date(selected_date, include_inactive=True)
    return {"foods": [_serialize_food(food) for food in foods]}


@app.post("/api/admin/foods")
async def admin_food_create(
    telegram_id: int = Form(...),
    menu_date: str = Form(...),
    name: str = Form(...),
    price: int = Form(...),
    quantity: int = Form(...),
    description: str = Form(default=""),
    image_file_id: str = Form(default=""),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    require_admin(telegram_id)
    food_id = await FoodRepository(db).create(
        {
            "menu_date": date.fromisoformat(menu_date),
            "name": name,
            "image_file_id": image_file_id or None,
            "price": price,
            "quantity": quantity,
            "description": description,
            "is_active": True,
        }
    )
    return {"id": food_id}


@app.put("/api/admin/foods/{food_id}")
async def admin_food_update(food_id: int, payload: dict, telegram_id: int = Query(...), db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    if "menu_date" in payload:
        payload["menu_date"] = date.fromisoformat(payload["menu_date"])
    await FoodRepository(db).update(food_id, payload)
    return {"ok": True}


@app.post("/api/admin/foods/{food_id}/deactivate")
async def admin_food_deactivate(food_id: int, telegram_id: int = Form(...), db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    await FoodRepository(db).deactivate(food_id)
    return {"ok": True}


@app.get("/api/admin/promotions")
async def admin_promotions(telegram_id: int, db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    promotions = await PromotionRepository(db).list_all()
    return {"promotions": [_serialize_promotion(promo) for promo in promotions]}


@app.post("/api/admin/promotions")
async def admin_promotion_create(
    telegram_id: int = Form(...),
    name: str = Form(...),
    promotion_type: str = Form(...),
    config_json: str = Form(...),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    require_admin(telegram_id)
    promotion_id = await PromotionRepository(db).create(
        {
            "name": name,
            "promotion_type": PromotionType(promotion_type),
            "config": json.loads(config_json),
            "is_active": True,
        }
    )
    return {"id": promotion_id}


@app.post("/api/admin/promotions/{promotion_id}/toggle")
async def admin_promotion_toggle(
    promotion_id: int,
    telegram_id: int = Form(...),
    is_active: int = Form(...),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    require_admin(telegram_id)
    await PromotionRepository(db).toggle(promotion_id, bool(is_active))
    return {"ok": True}


@app.delete("/api/admin/promotions/{promotion_id}")
async def admin_promotion_delete(promotion_id: int, telegram_id: int = Query(...), db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    await PromotionRepository(db).delete(promotion_id)
    return {"ok": True}


@app.get("/api/admin/credentials")
async def admin_credentials(telegram_id: int, db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    return await _get_credentials_dict(db)


@app.put("/api/admin/credentials")
async def admin_credentials_update(payload: dict, telegram_id: int = Query(...), db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    await CredentialRepository(db).update(payload)
    return {"ok": True}


@app.get("/api/admin/stats")
async def admin_stats(
    telegram_id: int,
    period: str = Query(default="today"),
    selected_date: str | None = Query(default=None),
    db: DatabaseSession = Depends(get_db),
) -> dict:
    require_admin(telegram_id)
    date_value = date.fromisoformat(selected_date) if selected_date else None
    return await _stats_for_period(db, period, date_value)


@app.get("/api/admin/orders")
async def admin_orders(telegram_id: int, db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    order_repo = OrderRepository(db)
    user_repo = UserRepository(db)
    orders = await order_repo.list_all_orders()
    payload = []
    for order in orders:
        items = await order_repo.get_items(int(order["id"]))
        user = await user_repo.get_by_id(int(order["user_id"]))
        payload.append(_serialize_order(order, items, user))
    return {"orders": payload}


async def _notify_customer(telegram_id: int, text: str) -> None:
    bot = Bot(token=settings.bot_token)
    try:
        await bot.send_message(telegram_id, text)
    finally:
        await bot.session.close()


@app.post("/api/admin/orders/{order_id}/accept")
async def admin_order_accept(order_id: int, telegram_id: int = Form(...), db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    repo = OrderRepository(db)
    order = await repo.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if str(order["status"]) != OrderStatus.PAYMENT_SUBMITTED.value:
        raise HTTPException(status_code=400, detail="Order cannot be accepted")
    await repo.update_status(order_id, status=OrderStatus.ACCEPTED, payment_status=PaymentStatus.PAID)
    customer = await UserRepository(db).get_by_id(int(order["user_id"]))
    if customer:
        await _notify_customer(int(customer["telegram_id"]), f"Buyurtma #{order_display_id(order_id)} qabul qilindi. Tez orada tayyorlanadi.")
    return {"ok": True}


@app.post("/api/admin/orders/{order_id}/reject")
async def admin_order_reject(order_id: int, telegram_id: int = Form(...), db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    repo = OrderRepository(db)
    food_repo = FoodRepository(db)
    order = await repo.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if str(order["status"]) in {OrderStatus.REJECTED.value, OrderStatus.CANCELED.value}:
        raise HTTPException(status_code=400, detail="Order already closed")
    items = await repo.get_items(order_id)
    for item in items:
        await food_repo.increase_stock(int(item["food_id"]), int(item["quantity"]))
    await repo.update_status(order_id, status=OrderStatus.REJECTED, payment_status=PaymentStatus.REJECTED)
    customer = await UserRepository(db).get_by_id(int(order["user_id"]))
    if customer:
        await _notify_customer(int(customer["telegram_id"]), f"Buyurtma #{order_display_id(order_id)} rad etildi.")
    return {"ok": True}


@app.post("/api/admin/orders/{order_id}/cancel")
async def admin_order_cancel(order_id: int, telegram_id: int = Form(...), db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    repo = OrderRepository(db)
    food_repo = FoodRepository(db)
    order = await repo.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if str(order["status"]) != OrderStatus.ACCEPTED.value:
        raise HTTPException(status_code=400, detail="Only accepted orders can be canceled")
    items = await repo.get_items(order_id)
    for item in items:
        await food_repo.increase_stock(int(item["food_id"]), int(item["quantity"]))
    await repo.update_status(order_id, status=OrderStatus.CANCELED, payment_status=PaymentStatus.REFUNDED)
    customer = await UserRepository(db).get_by_id(int(order["user_id"]))
    if customer:
        await _notify_customer(int(customer["telegram_id"]), f"Buyurtma #{order_display_id(order_id)} bekor qilindi. To'lov summasi qaytariladi.")
    return {"ok": True}


@app.post("/api/admin/broadcast")
async def admin_broadcast(telegram_id: int = Form(...), db: DatabaseSession = Depends(get_db)) -> dict:
    require_admin(telegram_id)
    foods = await FoodRepository(db).list_today_all(today_local_date())
    users = await UserRepository(db).list_all()
    promotions = await PromotionRepository(db).list_active()
    credentials = await _get_credentials_dict(db)
    if not foods:
        raise HTTPException(status_code=400, detail="Bugungi menyu yo'q")
    bot = Bot(token=settings.bot_token)
    try:
        sent, failed = await BroadcastService().broadcast_menu(bot, users, foods, promotions, credentials)
    finally:
        await bot.session.close()
    return {"sent": sent, "failed": failed}
