"""initial schema

Revision ID: 20260326_0001
Revises:
Create Date: 2026-03-26 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260326_0001"
down_revision = None
branch_labels = None
depends_on = None

order_status = sa.Enum(
    "pending_payment",
    "payment_submitted",
    "accepted",
    "rejected",
    "preparing",
    "delivered",
    name="order_status",
)
promotion_type = sa.Enum("free_delivery_by_quantity", "free_item_by_total", "buy_x_get_y", name="promotion_type")
payment_status = sa.Enum("pending", "submitted", "paid", "rejected", name="payment_status")


def upgrade() -> None:
    bind = op.get_bind()
    order_status.create(bind, checkfirst=True)
    promotion_type.create(bind, checkfirst=True)
    payment_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_ordered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "foods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("menu_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("image_file_id", sa.String(length=255), nullable=True),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("menu_date", "name", name="uq_food_menu_date_name"),
    )
    op.create_index("ix_foods_menu_date", "foods", ["menu_date"], unique=False)
    op.create_table(
        "promotions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("promotion_type", promotion_type, nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "user_addresses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("address_text", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", order_status, nullable=False),
        sa.Column("payment_status", payment_status, nullable=False),
        sa.Column("total_price", sa.Integer(), nullable=False),
        sa.Column("delivery_fee", sa.Integer(), nullable=False),
        sa.Column("discount_amount", sa.Integer(), nullable=False),
        sa.Column("promotion_summary", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("address_id", sa.Integer(), sa.ForeignKey("user_addresses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("location_latitude", sa.Float(), nullable=False),
        sa.Column("location_longitude", sa.Float(), nullable=False),
        sa.Column("location_text", sa.Text(), nullable=True),
        sa.Column("admin_group_message_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("food_id", sa.Integer(), sa.ForeignKey("foods.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("food_name", sa.String(length=255), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_total", sa.Integer(), nullable=False),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("user_addresses")
    op.drop_table("promotions")
    op.drop_index("ix_foods_menu_date", table_name="foods")
    op.drop_table("foods")
    op.drop_table("users")
    bind = op.get_bind()
    payment_status.drop(bind, checkfirst=True)
    promotion_type.drop(bind, checkfirst=True)
    order_status.drop(bind, checkfirst=True)
