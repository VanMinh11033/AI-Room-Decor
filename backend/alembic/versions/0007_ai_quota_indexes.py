"""ai quota indexes

Revision ID: 0007_ai_quota_indexes
Revises: 0006_product_image_candidates
Create Date: 2026-11-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_ai_quota_indexes"
down_revision: str | None = "0006_product_image_candidates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tối ưu hóa truy vấn kiểm tra hạn mức ngày theo user và theo toàn hệ thống
    op.create_index(
        "ix_ai_usage_logs_user_provider_created",
        "ai_usage_logs",
        ["user_id", "provider", "created_at"],
    )
    op.create_index(
        "ix_ai_usage_logs_provider_created",
        "ai_usage_logs",
        ["provider", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_logs_provider_created", table_name="ai_usage_logs")
    op.drop_index("ix_ai_usage_logs_user_provider_created", table_name="ai_usage_logs")
