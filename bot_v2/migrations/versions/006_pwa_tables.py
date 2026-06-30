"""create pwa tables

Revision ID: 006_pwa_tables
Revises: 005_barakah_system
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = "006_pwa_tables"
down_revision = "005_barakah_system"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS pwa_users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            tg_id BIGINT UNIQUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS pwa_tracker (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            data JSONB NOT NULL DEFAULT '{}',
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, date)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS pwa_wheel (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
            scores JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS pwa_ship (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            scores JSONB NOT NULL DEFAULT '{}',
            avg FLOAT NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS pwa_analytics (
            id BIGSERIAL PRIMARY KEY,
            uid TEXT NOT NULL,
            event TEXT NOT NULL,
            screen TEXT,
            ts TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS pwa_analytics")
    op.execute("DROP TABLE IF EXISTS pwa_ship")
    op.execute("DROP TABLE IF EXISTS pwa_wheel")
    op.execute("DROP TABLE IF EXISTS pwa_tracker")
    op.execute("DROP TABLE IF EXISTS pwa_users")
