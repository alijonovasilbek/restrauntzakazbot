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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}

    if "is_admin" not in columns:
        op.add_column(
            "users",
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        return

    op.execute(sa.text("UPDATE users SET is_admin = false WHERE is_admin IS NULL"))
    op.alter_column(
        "users",
        "is_admin",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_admin" in columns:
        op.drop_column("users", "is_admin")
