from __future__ import annotations

from dataclasses import dataclass

from bot.models.enums import PromotionType


@dataclass
class PromotionResult:
    discount_amount: int
    delivery_fee: int
    summary: list[str]
    bonus_items: list[str]


class PromotionService:
    def __init__(self, default_delivery_fee: int) -> None:
        self.default_delivery_fee = default_delivery_fee

    def apply(self, cart_items: list[dict], promotions: list[dict]) -> PromotionResult:
        subtotal = sum(item["price"] * item["quantity"] for item in cart_items)
        total_quantity = sum(item["quantity"] for item in cart_items)
        delivery_fee = self.default_delivery_fee
        discount = 0
        summary: list[str] = []
        bonus_items: list[str] = []
        for promo in promotions:
            promo_type = promo["promotion_type"]
            config = promo["config"]
            if promo_type == PromotionType.FREE_DELIVERY_BY_QUANTITY and total_quantity >= int(config.get("min_quantity", 0)):
                if bool(config.get("free_delivery", True)):
                    delivery_fee = 0
                    summary.append(f"{promo['name']}: bepul yetkazib berish")
                gift_name = str(config.get("free_item_name", "")).strip()
                if gift_name:
                    bonus_items.append(gift_name)
                    summary.append(f"{promo['name']}: bonus {gift_name}")
            elif promo_type == PromotionType.FREE_ITEM_BY_TOTAL and subtotal >= int(config.get("min_total", 0)):
                gift_name = str(config.get("free_item_name", "Sovg'a ichimlik"))
                bonus_items.append(gift_name)
                summary.append(f"{promo['name']}: {gift_name}")
            elif promo_type == PromotionType.BUY_X_GET_Y:
                target_food_id = int(config.get("food_id", 0))
                buy_qty = int(config.get("buy_quantity", 0))
                free_qty = int(config.get("free_quantity", 0))
                for item in cart_items:
                    if item["food_id"] == target_food_id and buy_qty > 0 and item["quantity"] >= buy_qty:
                        free_units = (item["quantity"] // buy_qty) * free_qty
                        discount += free_units * item["price"]
                        summary.append(f"{promo['name']}: {free_units} ta tekin {item['name']}")
                        break
        return PromotionResult(discount_amount=discount, delivery_fee=delivery_fee, summary=summary, bonus_items=bonus_items)
