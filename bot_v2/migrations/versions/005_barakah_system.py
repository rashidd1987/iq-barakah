"""add barakah system

Revision ID: 005_barakah_system
Revises: 004_bot_payments
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision = "005_barakah_system"
down_revision = "004_bot_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Новые колонки в users
    op.add_column("users", sa.Column("referral_code", sa.String(32), nullable=True, unique=True))
    op.add_column("users", sa.Column("referred_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True))
    op.add_column("users", sa.Column("barakah_balance", sa.Integer, nullable=False, server_default="0"))
    op.add_column("users", sa.Column("charity_consent", sa.Boolean, nullable=False, server_default="false"))
    op.create_index("ix_users_referral_code", "users", ["referral_code"], unique=True)

    # Таблица транзакций Баракатов
    op.create_table(
        "barakah_transactions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("ref_user_id", sa.BigInteger, nullable=True),
        sa.Column("payment_id", sa.Integer, sa.ForeignKey("bot_payments.id"), nullable=True),
        sa.Column("note", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("barakah_transactions")
    op.drop_index("ix_users_referral_code", "users")
    op.drop_column("users", "charity_consent")
    op.drop_column("users", "barakah_balance")
    op.drop_column("users", "referred_by")
    op.drop_column("users", "referral_code")
