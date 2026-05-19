"""Initial schema — все таблицы IQ Barakah

Revision ID: 001
Revises:
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="Telegram user ID"),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("is_female", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("occupation", sa.String(64), nullable=True),
        sa.Column("age", sa.String(8), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("pd_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── participants ───────────────────────────────────────────────
    op.create_table(
        "participants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("level", sa.String(4), nullable=False, comment="А / Б / В / Г"),
        sa.Column("week", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("vakt_level", sa.String(4), nullable=True, comment="Подуровень внутри ВАКТ"),
        sa.Column("activated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("graduated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_participants_is_active", "participants", ["is_active"])

    # ── diag_results ──────────────────────────────────────────────
    op.create_table(
        "diag_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scores", JSONB(), nullable=False, comment="[0,2,1,3,2,1,0,2]"),
        sa.Column("level_key", sa.String(4), nullable=False),
        sa.Column("pct", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_diag_results_user_id", "diag_results", ["user_id"])

    # ── payments ──────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tariff_id", sa.String(32), nullable=False,
                  comment="vakt / s1_full / s3_full / jamaat / leader"),
        sa.Column("amount", sa.Integer(), nullable=False, comment="В рублях"),
        sa.Column("yoo_payment_id", sa.String(128), nullable=True, unique=True),
        sa.Column("tg_charge_id", sa.String(128), nullable=True),
        sa.Column("email_used", sa.String(256), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="'pending'",
                  comment="pending / paid / failed / refunded"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_status", "payments", ["status"])

    # ── muhasaba_logs ─────────────────────────────────────────────
    op.create_table(
        "muhasaba_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answers", JSONB(), nullable=False, comment="[{q, a}, ...]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_muhasaba_user_date", "muhasaba_logs", ["user_id", "created_at"])

    # ── week_acks ─────────────────────────────────────────────────
    op.create_table(
        "week_acks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.String(4), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("acked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "level", "week", name="uq_week_ack"),
    )

    # ── pairs ─────────────────────────────────────────────────────
    op.create_table(
        "pairs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uid1", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uid2", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paired_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("dissolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("uid1", "uid2", name="uq_pair"),
    )
    op.create_index("ix_pairs_uid1", "pairs", ["uid1"])
    op.create_index("ix_pairs_uid2", "pairs", ["uid2"])

    # ── lesson_media ──────────────────────────────────────────────
    op.create_table(
        "lesson_media",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("level", sa.String(4), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(8), nullable=False, comment="video / audio"),
        sa.Column("value", sa.Text(), nullable=False, comment="file_id или URL"),
        sa.Column("set_by", sa.BigInteger(), nullable=True),
        sa.Column("set_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("level", "week", "media_type", name="uq_lesson_media"),
    )

    # ── tracker_records ───────────────────────────────────────────
    op.create_table(
        "tracker_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("habits", JSONB(), nullable=False, server_default="'{}'",
                  comment='{"namaz": {"fajr": true}, "daily": {...}}'),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "date", name="uq_tracker_day"),
    )
    op.create_index("ix_tracker_user_date", "tracker_records", ["user_id", "date"])

    # ── wheel_records ─────────────────────────────────────────────
    op.create_table(
        "wheel_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scores", JSONB(), nullable=False,
                  comment='{"iman":7,"time":5,"habits":6,"family":8,"health":6,"finance":4,"mission":3,"social":5}'),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_wheel_user_id", "wheel_records", ["user_id"])

    # ── bot_settings ──────────────────────────────────────────────
    op.create_table(
        "bot_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Seed default settings
    op.execute("INSERT INTO bot_settings (key, value) VALUES ('call_link', 'https://t.me/iqbarakah_bot')")
    op.execute("INSERT INTO bot_settings (key, value) VALUES ('friday_guest', NULL)")


def downgrade() -> None:
    op.drop_table("bot_settings")
    op.drop_table("wheel_records")
    op.drop_table("tracker_records")
    op.drop_table("lesson_media")
    op.drop_table("pairs")
    op.drop_table("week_acks")
    op.drop_table("muhasaba_logs")
    op.drop_table("payments")
    op.drop_table("diag_results")
    op.drop_table("participants")
    op.drop_table("users")
