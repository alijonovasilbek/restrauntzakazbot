from __future__ import annotations

from sqlalchemy import BIGINT, JSON, Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, MetaData, String, Table, Text, UniqueConstraint, func

from bot.models.enums import OrderStatus, PaymentStatus, PromotionType

metadata = MetaData()


def enum_values(enum_cls: type) -> list[str]:
    return [item.value for item in enum_cls]

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("telegram_id", BIGINT, nullable=False, unique=True),
    Column("full_name", String(255), nullable=False),
    Column("username", String(255)),
    Column("phone", String(32)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_ordered_at", DateTime(timezone=True)),
)

foods = Table(
    "foods",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("menu_date", Date, nullable=False, index=True),
    Column("name", String(255), nullable=False),
    Column("image_file_id", String(255)),
    Column("price", Integer, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("description", Text),
    Column("is_active", Boolean, nullable=False, default=True, server_default="true"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("menu_date", "name", name="uq_food_menu_date_name"),
)

promotions = Table(
    "promotions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("promotion_type", Enum(PromotionType, name="promotion_type", values_callable=enum_values), nullable=False),
    Column("config", JSON, nullable=False),
    Column("is_active", Boolean, nullable=False, default=True, server_default="true"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

credentials = Table(
    "credentials",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("payment_card_number", String(64), nullable=False),
    Column("payment_card_owner", String(255), nullable=False),
    Column("order_accept_until", String(16), nullable=False),
    Column("delivery_start_time", String(16), nullable=False),
    Column("delivery_end_time", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
)

user_addresses = Table(
    "user_addresses",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("title", String(255)),
    Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False),
    Column("address_text", Text),
    Column("is_default", Boolean, nullable=False, default=True, server_default="true"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

orders = Table(
    "orders",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("status", Enum(OrderStatus, name="order_status", values_callable=enum_values), nullable=False),
    Column("payment_status", Enum(PaymentStatus, name="payment_status", values_callable=enum_values), nullable=False),
    Column("total_price", Integer, nullable=False),
    Column("delivery_fee", Integer, nullable=False),
    Column("discount_amount", Integer, nullable=False),
    Column("promotion_summary", Text),
    Column("phone", String(32), nullable=False),
    Column("address_id", ForeignKey("user_addresses.id", ondelete="SET NULL")),
    Column("location_latitude", Float, nullable=False),
    Column("location_longitude", Float, nullable=False),
    Column("location_text", Text),
    Column("admin_group_message_id", BIGINT),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
)

order_items = Table(
    "order_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("order_id", ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
    Column("food_id", ForeignKey("foods.id", ondelete="RESTRICT"), nullable=False),
    Column("food_name", String(255), nullable=False),
    Column("unit_price", Integer, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("line_total", Integer, nullable=False),
)

payments = Table(
    "payments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("order_id", ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
    Column("file_id", String(255), nullable=False),
    Column("type", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
