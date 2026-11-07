"""room image analysis

Revision ID: 0003_room_image_analysis
Revises: 0002_product_catalog_attributes
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_room_image_analysis"
down_revision: str | None = "0002_product_catalog_attributes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("room_projects", sa.Column("room_image_path", sa.String(length=1000), nullable=True))
    op.add_column("room_projects", sa.Column("image_original_filename", sa.String(length=255), nullable=True))
    op.add_column("room_projects", sa.Column("image_content_type", sa.String(length=100), nullable=True))
    op.add_column("room_projects", sa.Column("image_size_bytes", sa.Integer(), nullable=True))
    op.add_column("room_projects", sa.Column("image_checksum", sa.String(length=64), nullable=True))
    op.create_index("ix_room_projects_image_checksum", "room_projects", ["image_checksum"])

    op.create_table(
        "room_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("image_checksum", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("room_type", sa.String(length=100), nullable=True),
        sa.Column("dominant_colors", sa.JSON(), nullable=True),
        sa.Column("existing_objects", sa.JSON(), nullable=True),
        sa.Column("empty_areas", sa.JSON(), nullable=True),
        sa.Column("lighting", sa.JSON(), nullable=True),
        sa.Column("design_characteristics", sa.JSON(), nullable=True),
        sa.Column("layout_summary", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["room_project_id"], ["room_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_room_analyses_image_checksum", "room_analyses", ["image_checksum"])
    op.create_index("ix_room_analyses_room_project_id", "room_analyses", ["room_project_id"])
    op.create_index("ix_room_analyses_room_type", "room_analyses", ["room_type"])
    op.create_index("ix_room_analyses_status", "room_analyses", ["status"])
    op.create_index("ix_room_analyses_user_id", "room_analyses", ["user_id"])

    op.add_column("ai_usage_logs", sa.Column("latency_ms", sa.Integer(), nullable=True))
    op.add_column("ai_usage_logs", sa.Column("error_code", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_usage_logs", "error_code")
    op.drop_column("ai_usage_logs", "latency_ms")
    op.drop_table("room_analyses")
    op.drop_index("ix_room_projects_image_checksum", table_name="room_projects")
    op.drop_column("room_projects", "image_checksum")
    op.drop_column("room_projects", "image_size_bytes")
    op.drop_column("room_projects", "image_content_type")
    op.drop_column("room_projects", "image_original_filename")
    op.drop_column("room_projects", "room_image_path")
