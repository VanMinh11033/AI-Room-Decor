"""product catalog attributes

Revision ID: 0002_product_catalog_attributes
Revises: 0001_initial_schema
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_product_catalog_attributes"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def create_lookup_table(name: str, with_hex: bool = False) -> None:
    columns = [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
    ]
    if with_hex:
        columns.append(sa.Column("hex_code", sa.String(length=20), nullable=True))
    else:
        columns.append(sa.Column("description", sa.Text(), nullable=True))
    columns.extend(
        [
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            *timestamp_columns(),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
            sa.UniqueConstraint("slug"),
        ]
    )
    op.create_table(name, *columns)
    op.create_index(f"ix_{name}_is_active", name, ["is_active"])
    op.create_index(f"ix_{name}_name", name, ["name"])
    op.create_index(f"ix_{name}_slug", name, ["slug"])


def create_junction_table(name: str, right_table: str, right_column: str) -> None:
    op.create_table(
        name,
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column(right_column, sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint([right_column], [f"{right_table}.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("product_id", right_column),
    )
    op.create_index(f"ix_{name}_product_id", name, ["product_id"])
    op.create_index(f"ix_{name}_{right_column}", name, [right_column])


def upgrade() -> None:
    create_lookup_table("materials")
    create_lookup_table("styles")
    create_lookup_table("room_types")
    create_lookup_table("colors", with_hex=True)

    op.add_column("products", sa.Column("slug", sa.String(length=280), nullable=True))
    op.add_column("products", sa.Column("weight", sa.Numeric(10, 2), nullable=True))
    op.add_column("products", sa.Column("tags", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("searchable_text", sa.Text(), nullable=True))
    op.add_column(
        "products",
        sa.Column("status", sa.Enum("DRAFT", "ACTIVE", "INACTIVE", name="productstatus"), nullable=False, server_default="ACTIVE"),
    )
    op.add_column("product_images", sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("UPDATE products SET slug = 'product-' || id WHERE slug IS NULL")
    else:
        op.execute("UPDATE products SET slug = CONCAT('product-', id) WHERE slug IS NULL")
    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column("slug", existing_type=sa.String(length=280), nullable=False)
    op.create_index("ix_products_slug", "products", ["slug"], unique=True)
    op.create_index("ix_products_status", "products", ["status"])
    op.create_index("ix_product_images_is_primary", "product_images", ["is_primary"])

    create_junction_table("product_materials", "materials", "material_id")
    create_junction_table("product_styles", "styles", "style_id")
    create_junction_table("product_room_types", "room_types", "room_type_id")
    create_junction_table("product_colors", "colors", "color_id")


def downgrade() -> None:
    op.drop_table("product_colors")
    op.drop_table("product_room_types")
    op.drop_table("product_styles")
    op.drop_table("product_materials")
    op.drop_index("ix_product_images_is_primary", table_name="product_images")
    op.drop_index("ix_products_status", table_name="products")
    op.drop_index("ix_products_slug", table_name="products")
    op.drop_column("product_images", "is_primary")
    op.drop_column("products", "status")
    op.drop_column("products", "searchable_text")
    op.drop_column("products", "tags")
    op.drop_column("products", "weight")
    op.drop_column("products", "slug")
    op.drop_table("colors")
    op.drop_table("room_types")
    op.drop_table("styles")
    op.drop_table("materials")
