"""Create bot_payments table (safe, IF NOT EXISTS — CRM owns payments table)

Revision ID: 004
Revises: 003
Create Date: 2026-06-21

"""
from typing import Union
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS bot_payments (
            id          SERIAL PRIMARY KEY,
            user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tariff_id   VARCHAR(32) NOT NULL,
            amount      INTEGER NOT NULL,
            yoo_payment_id VARCHAR(128) UNIQUE,
            tg_charge_id   VARCHAR(128),
            email_used     VARCHAR(256),
            status      VARCHAR(32) NOT NULL DEFAULT 'pending',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            paid_at     TIMESTAMPTZ
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_bot_payments_user_id ON bot_payments (user_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_bot_payments_status ON bot_payments (status)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_bot_payments_status")
    op.execute("DROP INDEX IF EXISTS ix_bot_payments_user_id")
    # Намеренно НЕ дропаем таблицу в downgrade — данные важнее
