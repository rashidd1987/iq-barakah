"""Add user language

Revision ID: 002
Revises: 001
Create Date: 2026-05-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("language_code", sa.String(8), nullable=False, server_default="ru"),
    )


def downgrade() -> None:
    op.drop_column("users", "language_code")
