import enum
from datetime import datetime
from pathlib import Path

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


class PaymentMethod(str, enum.Enum):
    COD = "COD"
    VNPAY = "VNPAY"


class PaymentStatus(str, enum.Enum):
    UNPAID = "UNPAID"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class ShippingFeeStatus(str, enum.Enum):
    CALCULATED = "CALCULATED"
    PENDING_CALCULATION = "PENDING_CALCULATION"
    AWAITING_CUSTOMER_CONFIRMATION = "AWAITING_CUSTOMER_CONFIRMATION"
    CUSTOMER_CONFIRMED = "CUSTOMER_CONFIRMED"


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

    @property
    def is_reference_ready(self) -> bool:
        this_file = Path(__file__).resolve()
        p_slug = self.slug or ""
        # 1. Skill Bridge packaged clean reference images (30 verified catalog references)
        skill_clean = this_file.parents[1] / "ai" / "skill_bridge" / "product_references_clean"
        if skill_clean.is_dir() and p_slug:
            for ext in (".jpg", ".png", ".webp"):
                if (skill_clean / f"{self.id}_{p_slug}{ext}").is_file():
                    return True

        # 2. Local storage clean references fallback
        for parent_idx in (2, 3):
            try:
                storage_clean = this_file.parents[parent_idx] / "storage" / "product_references_clean"
                if storage_clean.is_dir() and p_slug:
                    for ext in (".jpg", ".png", ".webp"):
                        if (storage_clean / f"{self.id}_{p_slug}{ext}").is_file():
                            return True
            except IndexError:
                pass

        # 3. Primary image fallback if available on disk
        if self.images:
            primary = next((img for img in self.images if img.is_primary), self.images[0])
            if primary and primary.image_url:
                for parent_idx in (2, 3):
                    try:
                        img_path = this_file.parents[parent_idx] / primary.image_url.lstrip("/")
                        if img_path.is_file():
                            return True
                    except IndexError:
                        pass
        return False

    @property
    def is_composite_ready(self) -> bool:
        project_root = Path(__file__).resolve().parents[3]
        verified_dir = project_root / "storage" / "verified_catalog_cutouts"
        p_slug = self.slug or ""
        return self.id in {1, 6, 9, 16, 19, 21, 28} and (verified_dir / f"{self.id}_{p_slug}.png").is_file()


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

    @property
    def generation_mode(self) -> str:
        prompt_text = self.prompt or ""
        if "[MODE: AI_PHOTOREALISTIC_PREVIEW]" in prompt_text:
            return "AI_PHOTOREALISTIC_PREVIEW"
        if "[MODE: CATALOG_ACCURATE]" in prompt_text:
            return "CATALOG_ACCURATE"
        if self.provider in ("gemini", "cloudflare", "openai", "qwencloud", "gemini_manual_import"):
            return "AI_PHOTOREALISTIC_PREVIEW"
        return "CATALOG_ACCURATE"

    @property
    def is_ai_preview(self) -> bool:
        return self.generation_mode == "AI_PHOTOREALISTIC_PREVIEW"

    @property
    def verification_status(self) -> str:
        prompt_text = self.prompt or ""
        # 1. Fallback & Rejected always take precedence
        if "[STATUS: COMPOSITE_FALLBACK]" in prompt_text:
            return "COMPOSITE_FALLBACK"
        if "[STATUS: REJECTED]" in prompt_text:
            return "REJECTED"
        if "[STATUS: FAILED]" in prompt_text:
            return "FAILED"
        # 2. Strict Constraint: AI Preview can NEVER be marked VERIFIED
        if self.is_ai_preview:
            return "NEEDS_REVIEW"
        # 3. Composite engine catalog accurate mode
        if "[STATUS: VERIFIED]" in prompt_text or self.provider == "composite":
            return "VERIFIED"
        return "VERIFIED"

    @property
    def verification_details(self) -> dict:
        is_manual = self.provider == "gemini_manual_import" or "GEMINI_WEB_APP_MANUAL" in (self.prompt or "")
        is_exact = not self.is_ai_preview and self.verification_status == "VERIFIED"
        source_label = "Ảnh phối cảnh tạo bằng ứng dụng Gemini — nhập thủ công" if is_manual else (
            "Bản xem trước AI · Trạng thái: NEEDS_REVIEW" if self.is_ai_preview else (
                "Thiết kế Chuẩn Catalog 100% · Trạng thái: VERIFIED" if is_exact else "Bản ghép xem trước Offline – Không phải ảnh AI Photorealistic"
            )
        )
        details = {
            "mode": self.generation_mode,
            "status": self.verification_status,
            "provider": self.provider,
            "is_catalog_exact": is_exact,
            "is_photorealistic": bool(self.is_ai_preview),
            "source_type": "GEMINI_WEB_APP_MANUAL" if is_manual else ("API" if self.is_ai_preview else "COMPOSITE"),
            "source_label": source_label,
            "api_used": False if (is_manual or self.provider == "composite") else True,
            "referenced_product_ids": [p.id for p in self.products] if getattr(self, "products", None) else [],
            "verified_product_ids": [p.id for p in self.products] if (getattr(self, "products", None) and is_exact) else [],
        }
        try:
            from app.ai.skill_bridge import parse_skill_metadata
            _, meta = parse_skill_metadata(self.prompt)
            if meta is not None:
                details.update({
                    "skill_version": meta.version,
                    "quality_score": meta.quality_score,
                    "component_scores": meta.component_scores,
                    "referenced_product_ids": meta.referenced_product_ids or details["referenced_product_ids"],
                    "verified_product_ids": meta.verified_product_ids,
                    "hard_gates_passed": meta.hard_gates_passed,
                    "neuron_estimate": meta.neuron_estimate,
                    "warnings": meta.warnings,
                    "provenance": meta.provenance,
                })
        except Exception:
            pass
        return details

    @property
    def quality_score(self) -> float | None:
        return self.verification_details.get("quality_score")

    @property
    def warnings(self) -> list[str]:
        return self.verification_details.get("warnings") or []


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
    recipient_name: Mapped[str] = mapped_column(String(100), nullable=False, default="N/A", server_default="N/A")
    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False, default="", server_default="")
    province: Mapped[str] = mapped_column(String(100), nullable=False, default="", server_default="")
    ward: Mapped[str] = mapped_column(String(100), nullable=False, default="", server_default="")
    street_address: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    delivery_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(String(500))
    subtotal_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    shipping_fee: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    shipping_fee_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ShippingFeeStatus.CALCULATED.value, server_default=ShippingFeeStatus.CALCULATED.value
    )
    total_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    payment_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PaymentMethod.COD.value, server_default=PaymentMethod.COD.value, index=True
    )
    payment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PaymentStatus.UNPAID.value, server_default=PaymentStatus.UNPAID.value, index=True
    )

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
