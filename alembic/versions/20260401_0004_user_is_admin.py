"""add missing users.is_admin column

Revision ID: 20260401_0004
Revises: 20260328_0003
Create Date: 2026-04-01 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260401_0004"
down_revision = "20260328_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")
