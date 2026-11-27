"""Create system_settings table for runtime governance flags.

Revision ID: 20261126_0006
Revises: 20261126_0005
Create Date: 2026-11-26 22:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261126_0006"
down_revision: str | None = "20261126_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"
    json_type: sa.types.TypeEngine[object] = postgresql.JSONB() if is_pg else sa.JSON()

    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=96), primary_key=True, nullable=False),
        sa.Column("value", json_type, nullable=False),
        sa.Column("updated_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
