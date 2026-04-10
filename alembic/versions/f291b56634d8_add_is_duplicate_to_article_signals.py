"""add is_duplicate to article_signals

Revision ID: f291b56634d8
Revises: d16adf27d2eb
Create Date: 2026-04-09 19:36:38.005811

Adds is_duplicate BOOLEAN (default FALSE) to article_signals so the dedup
service can mark lower-confidence duplicate signals without deleting them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f291b56634d8'
down_revision: Union[str, Sequence[str], None] = 'd16adf27d2eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "article_signals",
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("article_signals", "is_duplicate")
