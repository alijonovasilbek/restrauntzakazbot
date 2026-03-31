"""add canceled and refunded statuses

Revision ID: 20260328_0003
Revises: 20260328_0002
Create Date: 2026-03-28 00:10:00
"""

from __future__ import annotations

from alembic import op


revision = "20260328_0003"
down_revision = "20260328_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'canceled'")
    op.execute("ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'refunded'")


def downgrade() -> None:
    pass
