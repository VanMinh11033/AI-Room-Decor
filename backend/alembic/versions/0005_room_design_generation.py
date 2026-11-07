"""room design generation

Revision ID: 0005_room_design_generation
Revises: 0004_user_personalization
Create Date: 2026-09-04 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_room_design_generation"
down_revision: str | None = "0004_user_personalization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "room_design_generations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("source_image_path", sa.String(length=1000), nullable=False),
        sa.Column("generated_image_url", sa.String(length=1000), nullable=True),
        sa.Column("generated_image_path", sa.String(length=1000), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["room_project_id"], ["room_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_room_design_generations_error_code", "room_design_generations", ["error_code"], unique=False)
    op.create_index("ix_room_design_generations_project_created", "room_design_generations", ["room_project_id", "created_at"], unique=False)
    op.create_index("ix_room_design_generations_room_project_id", "room_design_generations", ["room_project_id"], unique=False)
    op.create_index("ix_room_design_generations_status", "room_design_generations", ["status"], unique=False)
    op.create_index("ix_room_design_generations_user_id", "room_design_generations", ["user_id"], unique=False)
    op.create_index("ix_room_design_generations_user_status", "room_design_generations", ["user_id", "status"], unique=False)

    op.create_table(
        "room_design_generation_products",
        sa.Column("generation_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["generation_id"], ["room_design_generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("generation_id", "product_id"),
    )


def downgrade() -> None:
    op.drop_table("room_design_generation_products")
    op.drop_index("ix_room_design_generations_user_status", table_name="room_design_generations")
    op.drop_index("ix_room_design_generations_user_id", table_name="room_design_generations")
    op.drop_index("ix_room_design_generations_status", table_name="room_design_generations")
    op.drop_index("ix_room_design_generations_room_project_id", table_name="room_design_generations")
    op.drop_index("ix_room_design_generations_project_created", table_name="room_design_generations")
    op.drop_index("ix_room_design_generations_error_code", table_name="room_design_generations")
    op.drop_table("room_design_generations")
