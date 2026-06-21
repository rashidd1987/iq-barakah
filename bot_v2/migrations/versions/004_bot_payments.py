"""Rename bot payments table to bot_payments (avoid conflict with CRM payments table)

Revision ID: 004
Revises: 003
Create Date: 2026-06-21

"""
from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tariff_id", sa.String(32), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("yoo_payment_id", sa.String(128), nullable=True, unique=True),
        sa.Column("tg_charge_id", sa.String(128), nullable=True),
        sa.Column("email_used", sa.String(256), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="'pending'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bot_payments_user_id", "bot_payments", ["user_id"])
    op.create_index("ix_bot_payments_status", "bot_payments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_bot_payments_status", "bot_payments")
    op.drop_index("ix_bot_payments_user_id", "bot_payments")
    op.drop_table("bot_payments")
