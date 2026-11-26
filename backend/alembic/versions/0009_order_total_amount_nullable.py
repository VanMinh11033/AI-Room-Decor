"""order total_amount nullable for bulky items

Revision ID: 0009_order_total_amount_nullable
Revises: 0008_cod_checkout_upgrade
Create Date: 2026-11-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009_order_total_amount_nullable"
down_revision: str | None = "0008_cod_checkout_upgrade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Allow total_amount to be null when bulky furniture shipping fee is pending quotation
    with op.batch_alter_table("orders") as batch_op:
        batch_op.alter_column(
            "total_amount",
            existing_type=sa.Numeric(precision=12, scale=2),
            nullable=True,
        )


def downgrade() -> None:
    # Revert total_amount to NOT NULL with default 0
    with op.batch_alter_table("orders") as batch_op:
        batch_op.alter_column(
            "total_amount",
            existing_type=sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        )
