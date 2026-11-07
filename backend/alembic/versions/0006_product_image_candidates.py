"""product image candidates

Revision ID: 0006_product_image_candidates
Revises: 0005_room_design_generation
Create Date: 2026-10-09 00:00:00.000000

Additive migration: creates a new ``product_image_candidates`` table to hold
staged product images pending admin approval. It does not alter any existing
table, so existing V1/V2 data and the ProductImage table are untouched.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_product_image_candidates"
down_revision: str | None = "0005_room_design_generation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_image_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_page_url", sa.String(length=1000), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=False),
        sa.Column("local_path", sa.String(length=1000), nullable=False),
        sa.Column("license", sa.String(length=255), nullable=True),
        sa.Column("license_url", sa.String(length=1000), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("creator", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="PENDING", nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("file_format", sa.String(length=20), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("semantic_decision", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_image_candidates_product_id", "product_image_candidates", ["product_id"], unique=False)
    op.create_index("ix_product_image_candidates_status", "product_image_candidates", ["status"], unique=False)
    op.create_index("ix_product_image_candidates_file_hash", "product_image_candidates", ["file_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_product_image_candidates_file_hash", table_name="product_image_candidates")
    op.drop_index("ix_product_image_candidates_status", table_name="product_image_candidates")
    op.drop_index("ix_product_image_candidates_product_id", table_name="product_image_candidates")
    op.drop_table("product_image_candidates")
