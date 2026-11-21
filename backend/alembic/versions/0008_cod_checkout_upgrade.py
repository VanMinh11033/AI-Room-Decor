"""cod checkout upgrade

Revision ID: 0008_cod_checkout_upgrade
Revises: 0007_ai_quota_indexes
Create Date: 2026-11-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_cod_checkout_upgrade"
down_revision: str | None = "0007_ai_quota_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add structured recipient and shipping columns to orders table
    op.add_column("orders", sa.Column("recipient_name", sa.String(length=100), nullable=False, server_default="N/A"))
    op.add_column("orders", sa.Column("recipient_phone", sa.String(length=20), nullable=False, server_default=""))
    op.add_column("orders", sa.Column("province", sa.String(length=100), nullable=False, server_default=""))
    op.add_column("orders", sa.Column("ward", sa.String(length=100), nullable=False, server_default=""))
    op.add_column("orders", sa.Column("street_address", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("orders", sa.Column("delivery_notes", sa.String(length=500), nullable=True))
    op.add_column("orders", sa.Column("subtotal_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("shipping_fee", sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column("orders", sa.Column("shipping_fee_status", sa.String(length=50), nullable=False, server_default="CALCULATED"))
    op.add_column("orders", sa.Column("payment_method", sa.String(length=20), nullable=False, server_default="COD"))
    op.add_column("orders", sa.Column("payment_status", sa.String(length=20), nullable=False, server_default="UNPAID"))

    # 2. Create index on payment_status and payment_method
    op.create_index("ix_orders_payment_status", "orders", ["payment_status"])
    op.create_index("ix_orders_payment_method", "orders", ["payment_method"])


def downgrade() -> None:
    op.drop_index("ix_orders_payment_method", table_name="orders")
    op.drop_index("ix_orders_payment_status", table_name="orders")
    op.drop_column("orders", "payment_status")
    op.drop_column("orders", "payment_method")
    op.drop_column("orders", "shipping_fee_status")
    op.drop_column("orders", "shipping_fee")
    op.drop_column("orders", "subtotal_amount")
    op.drop_column("orders", "delivery_notes")
    op.drop_column("orders", "street_address")
    op.drop_column("orders", "ward")
    op.drop_column("orders", "province")
    op.drop_column("orders", "recipient_phone")
    op.drop_column("orders", "recipient_name")
