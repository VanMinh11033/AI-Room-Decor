import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, JSON, Numeric, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class RoleName(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ProductStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ProductImageCandidateStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[RoleName] = mapped_column(Enum(RoleName), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255))

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)

    role: Mapped[Role] = relationship(back_populates="users")
    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    cart: Mapped["Cart"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(500))
    preferred_style: Mapped[str | None] = mapped_column(String(100))
    preferred_colors: Mapped[str | None] = mapped_column(String(255))
    preferred_materials: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(back_populates="profile")


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


product_materials = Table(
    "product_materials",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("material_id", ForeignKey("materials.id", ondelete="CASCADE"), primary_key=True),
)

product_styles = Table(
    "product_styles",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("style_id", ForeignKey("styles.id", ondelete="CASCADE"), primary_key=True),
)

product_room_types = Table(
    "product_room_types",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("room_type_id", ForeignKey("room_types.id", ondelete="CASCADE"), primary_key=True),
)

product_colors = Table(
    "product_colors",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("color_id", ForeignKey("colors.id", ondelete="CASCADE"), primary_key=True),
)

room_preference_styles = Table(
    "room_preference_styles",
    Base.metadata,
    Column("room_preference_id", ForeignKey("room_preferences.id", ondelete="CASCADE"), primary_key=True),
    Column("style_id", ForeignKey("styles.id", ondelete="CASCADE"), primary_key=True),
    Column("priority", Integer, default=2, nullable=False),
)

room_preference_colors = Table(
    "room_preference_colors",
    Base.metadata,
    Column("room_preference_id", ForeignKey("room_preferences.id", ondelete="CASCADE"), primary_key=True),
    Column("color_id", ForeignKey("colors.id", ondelete="CASCADE"), primary_key=True),
    Column("priority", Integer, default=2, nullable=False),
)

room_preference_materials = Table(
    "room_preference_materials",
    Base.metadata,
    Column("room_preference_id", ForeignKey("room_preferences.id", ondelete="CASCADE"), primary_key=True),
    Column("material_id", ForeignKey("materials.id", ondelete="CASCADE"), primary_key=True),
    Column("priority", Integer, default=2, nullable=False),
)

room_preference_categories = Table(
    "room_preference_categories",
    Base.metadata,
    Column("room_preference_id", ForeignKey("room_preferences.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
    Column("priority", Integer, default=2, nullable=False),
)

room_design_generation_products = Table(
    "room_design_generation_products",
    Base.metadata,
    Column("generation_id", ForeignKey("room_design_generations.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


class Material(Base, TimestampMixin):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    products: Mapped[list["Product"]] = relationship(secondary=product_materials, back_populates="materials")


class Style(Base, TimestampMixin):
    __tablename__ = "styles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    products: Mapped[list["Product"]] = relationship(secondary=product_styles, back_populates="styles")


class RoomType(Base, TimestampMixin):
    __tablename__ = "room_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    products: Mapped[list["Product"]] = relationship(secondary=product_room_types, back_populates="room_types")


class Color(Base, TimestampMixin):
    __tablename__ = "colors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    hex_code: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    products: Mapped[list["Product"]] = relationship(secondary=product_colors, back_populates="colors")


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_search", "name", "style", "color", "material", "room_type"),
        Index("ix_products_price_active", "price", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(280), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, index=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    style: Mapped[str | None] = mapped_column(String(100), index=True)
    color: Mapped[str | None] = mapped_column(String(100), index=True)
    material: Mapped[str | None] = mapped_column(String(100), index=True)
    room_type: Mapped[str | None] = mapped_column(String(100), index=True)
    width: Mapped[float | None] = mapped_column(Numeric(10, 2))
    height: Mapped[float | None] = mapped_column(Numeric(10, 2))
    depth: Mapped[float | None] = mapped_column(Numeric(10, 2))
    weight: Mapped[float | None] = mapped_column(Numeric(10, 2))
    tags: Mapped[str | None] = mapped_column(Text)
    searchable_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProductStatus] = mapped_column(Enum(ProductStatus), default=ProductStatus.ACTIVE, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    category: Mapped[Category] = relationship(back_populates="products")
    images: Mapped[list["ProductImage"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    image_candidates: Mapped[list["ProductImageCandidate"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    materials: Mapped[list[Material]] = relationship(secondary=product_materials, back_populates="products")
    styles: Mapped[list[Style]] = relationship(secondary=product_styles, back_populates="products")
    room_types: Mapped[list[RoomType]] = relationship(secondary=product_room_types, back_populates="products")
    colors: Mapped[list[Color]] = relationship(secondary=product_colors, back_populates="products")


class ProductImage(Base, TimestampMixin):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    product: Mapped[Product] = relationship(back_populates="images")


class ProductImageCandidate(Base, TimestampMixin):
    __tablename__ = "product_image_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_page_url: Mapped[str | None] = mapped_column(String(1000))
    image_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    local_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    license: Mapped[str | None] = mapped_column(String(255))
    license_url: Mapped[str | None] = mapped_column(String(1000))
    attribution: Mapped[str | None] = mapped_column(Text)
    creator: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    file_format: Mapped[str | None] = mapped_column(String(20))
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    semantic_decision: Mapped[str | None] = mapped_column(String(50))

    product: Mapped[Product] = relationship(back_populates="image_candidates")


class RoomProject(Base, TimestampMixin):
    __tablename__ = "room_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    room_type: Mapped[str | None] = mapped_column(String(100), index=True)
    room_image_url: Mapped[str | None] = mapped_column(String(1000))
    room_image_path: Mapped[str | None] = mapped_column(String(1000))
    image_original_filename: Mapped[str | None] = mapped_column(String(255))
    image_content_type: Mapped[str | None] = mapped_column(String(100))
    image_size_bytes: Mapped[int | None] = mapped_column(Integer)
    image_checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", nullable=False, index=True)

    user: Mapped[User] = relationship()
    analyses: Mapped[list["RoomAnalysis"]] = relationship(back_populates="room_project", cascade="all, delete-orphan")
    preference: Mapped["RoomPreference | None"] = relationship(back_populates="room_project", uselist=False, cascade="all, delete-orphan")
    design_generations: Mapped[list["RoomDesignGeneration"]] = relationship(
        back_populates="room_project", cascade="all, delete-orphan"
    )

    @property
    def preference_configured(self) -> bool:
        return self.preference is not None


class RoomAnalysis(Base, TimestampMixin):
    __tablename__ = "room_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_project_id: Mapped[int] = mapped_column(ForeignKey("room_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    image_checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(150), nullable=False)
    room_type: Mapped[str | None] = mapped_column(String(100), index=True)
    dominant_colors: Mapped[dict | list | None] = mapped_column(JSON)
    existing_objects: Mapped[dict | list | None] = mapped_column(JSON)
    empty_areas: Mapped[dict | list | None] = mapped_column(JSON)
    lighting: Mapped[dict | None] = mapped_column(JSON)
    design_characteristics: Mapped[dict | list | None] = mapped_column(JSON)
    layout_summary: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    raw_response: Mapped[dict | list | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    room_project: Mapped[RoomProject] = relationship(back_populates="analyses")
    user: Mapped[User] = relationship()


class RoomPreference(Base, TimestampMixin):
    __tablename__ = "room_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_project_id: Mapped[int] = mapped_column(ForeignKey("room_projects.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    budget_min: Mapped[float | None] = mapped_column(Numeric(12, 2))
    budget_max: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="VND", nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)

    room_project: Mapped[RoomProject] = relationship(back_populates="preference")
    user: Mapped[User] = relationship()
    styles: Mapped[list[Style]] = relationship(secondary=room_preference_styles)
    colors: Mapped[list[Color]] = relationship(secondary=room_preference_colors)
    materials: Mapped[list[Material]] = relationship(secondary=room_preference_materials)
    categories: Mapped[list[Category]] = relationship(secondary=room_preference_categories)


class RoomDesignGeneration(Base, TimestampMixin):
    __tablename__ = "room_design_generations"
    __table_args__ = (
        Index("ix_room_design_generations_project_created", "room_project_id", "created_at"),
        Index("ix_room_design_generations_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_project_id: Mapped[int] = mapped_column(ForeignKey("room_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(150), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), default="v1", nullable=False)
    source_image_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    generated_image_url: Mapped[str | None] = mapped_column(String(1000))
    generated_image_path: Mapped[str | None] = mapped_column(String(1000))
    prompt: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(120), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    room_project: Mapped[RoomProject] = relationship(back_populates="design_generations")
    user: Mapped[User] = relationship()
    products: Mapped[list[Product]] = relationship(secondary=room_design_generation_products)


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    user: Mapped[User] = relationship(back_populates="cart")
    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    cart: Mapped[Cart] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False, index=True)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    shipping_address: Mapped[str | None] = mapped_column(String(500))

    user: Mapped[User] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class Favorite(Base, TimestampMixin):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_user_product_favorite"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)


class AIUsageLog(Base, TimestampMixin):
    __tablename__ = "ai_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    room_project_id: Mapped[int | None] = mapped_column(ForeignKey("room_projects.id"), index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(150), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)


class AdminAuditLog(Base, TimestampMixin):
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[str | None] = mapped_column(Text)
