from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from bot.config import settings
from bot.models.enums import OrderStatus, PaymentStatus
from bot.repositories.address_repository import AddressRepository
from bot.repositories.food_repository import FoodRepository
from bot.repositories.order_repository import OrderRepository
from bot.repositories.promotion_repository import PromotionRepository
from bot.repositories.user_repository import UserRepository
from bot.services.promotion_service import PromotionService


class OrderService:
    def __init__(
        self,
        *,
        user_repo: UserRepository,
        address_repo: AddressRepository,
        food_repo: FoodRepository,
        order_repo: OrderRepository,
        promotion_repo: PromotionRepository,
    ) -> None:
        self.user_repo = user_repo
        self.address_repo = address_repo
        self.food_repo = food_repo
        self.order_repo = order_repo
        self.promotion_repo = promotion_repo
        self.promotion_service = PromotionService(settings.default_delivery_fee)

    async def create_order(
        self,
        *,
        telegram_id: int,
        phone: str,
        latitude: float,
        longitude: float,
        address_text: str | None,
        cart_items: list[dict],
    ) -> tuple[int, dict]:
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            raise ValueError("User not found")
        for item in cart_items:
            food = await self.food_repo.get_by_id(item["food_id"])
            if not food:
                raise ValueError(f"Food {item['food_id']} topilmadi")
            if int(food["quantity"]) < int(item["quantity"]):
                raise ValueError(f"{food['name']} uchun yetarli qoldiq yo'q")

        address_id = await self.address_repo.create(
            {
                "user_id": user["id"],
                "title": "Last used address",
                "latitude": latitude,
                "longitude": longitude,
                "address_text": address_text,
                "is_default": True,
            }
        )
        promotions = await self.promotion_repo.list_active()
        applied = self.promotion_service.apply(cart_items, promotions)
        subtotal = sum(item["price"] * item["quantity"] for item in cart_items)
        total_price = max(subtotal - applied.discount_amount, 0) + applied.delivery_fee
        items_payload = [
            {
                "food_id": item["food_id"],
                "food_name": item["name"],
                "unit_price": item["price"],
                "quantity": item["quantity"],
                "line_total": item["price"] * item["quantity"],
            }
            for item in cart_items
        ]
        now = datetime.now(ZoneInfo(settings.tz))
        order_id = await self.order_repo.create_order(
            {
                "user_id": user["id"],
                "status": OrderStatus.PENDING_PAYMENT,
                "payment_status": PaymentStatus.PENDING,
                "total_price": total_price,
                "delivery_fee": applied.delivery_fee,
                "discount_amount": applied.discount_amount,
                "promotion_summary": "\n".join(applied.summary) if applied.summary else None,
                "phone": phone,
                "address_id": address_id,
                "location_latitude": latitude,
                "location_longitude": longitude,
                "location_text": address_text,
                "created_at": now,
                "updated_at": now,
            },
            items_payload,
        )
        await self.user_repo.set_phone(telegram_id, phone)
        await self.user_repo.set_last_ordered(telegram_id, now)
        for item in cart_items:
            await self.food_repo.reduce_stock(item["food_id"], item["quantity"])

        return order_id, {
            "subtotal": subtotal,
            "delivery_fee": applied.delivery_fee,
            "discount_amount": applied.discount_amount,
            "total_price": total_price,
            "promotion_summary": applied.summary,
            "bonus_items": applied.bonus_items,
        }
