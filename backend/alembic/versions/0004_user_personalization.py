"""user personalization

Revision ID: 0004_user_personalization
Revises: 0003_room_image_analysis
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_personalization"
down_revision: str | None = "0003_room_image_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def create_preference_link_table(table_name: str, right_table: str, right_column: str) -> None:
    op.create_table(
        table_name,
        sa.Column("room_preference_id", sa.Integer(), nullable=False),
        sa.Column(right_column, sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.ForeignKeyConstraint(["room_preference_id"], ["room_preferences.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint([right_column], [f"{right_table}.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("room_preference_id", right_column),
    )
    op.create_index(f"ix_{table_name}_preference_id", table_name, ["room_preference_id"])
    op.create_index(f"ix_{table_name}_{right_column}", table_name, [right_column])


def upgrade() -> None:
    op.create_table(
        "room_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("budget_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("budget_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="VND"),
        sa.Column("purpose", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["room_project_id"], ["room_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_project_id"),
    )
    op.create_index("ix_room_preferences_room_project_id", "room_preferences", ["room_project_id"])
    op.create_index("ix_room_preferences_user_id", "room_preferences", ["user_id"])

    create_preference_link_table("room_preference_styles", "styles", "style_id")
    create_preference_link_table("room_preference_colors", "colors", "color_id")
    create_preference_link_table("room_preference_materials", "materials", "material_id")
    create_preference_link_table("room_preference_categories", "categories", "category_id")


def downgrade() -> None:
    op.drop_table("room_preference_categories")
    op.drop_table("room_preference_materials")
    op.drop_table("room_preference_colors")
    op.drop_table("room_preference_styles")
    op.drop_table("room_preferences")
