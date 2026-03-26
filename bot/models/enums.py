from __future__ import annotations

from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAYMENT_SUBMITTED = "payment_submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PREPARING = "preparing"
    DELIVERED = "delivered"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PAID = "paid"
    REJECTED = "rejected"


class PromotionType(StrEnum):
    FREE_DELIVERY_BY_QUANTITY = "free_delivery_by_quantity"
    FREE_ITEM_BY_TOTAL = "free_item_by_total"
    BUY_X_GET_Y = "buy_x_get_y"
