"""add credentials table

Revision ID: 20260328_0002
Revises: 20260326_0001
Create Date: 2026-03-28 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_0002"
down_revision = "20260326_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_card_number", sa.String(length=64), nullable=False),
        sa.Column("payment_card_owner", sa.String(length=255), nullable=False),
        sa.Column("order_accept_until", sa.String(length=16), nullable=False),
        sa.Column("delivery_start_time", sa.String(length=16), nullable=False),
        sa.Column("delivery_end_time", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("credentials")
