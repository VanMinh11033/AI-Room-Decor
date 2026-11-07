from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.category import CategoryRead
from app.schemas.catalog import CatalogRead, ColorRead


class ProductImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    alt_text: str | None = None
    sort_order: int
    is_primary: bool


class ProductImageInput(BaseModel):
    image_url: str = Field(..., max_length=1000)
    alt_text: str | None = Field(None, max_length=255)
    sort_order: int = 0
    is_primary: bool = False


class ProductBase(BaseModel):
    category_id: int
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=280)
    description: str | None = None
    price: Decimal = Field(..., gt=0)
    stock_quantity: int = Field(0, ge=0)
    style: str | None = Field(None, max_length=100)
    color: str | None = Field(None, max_length=100)
    material: str | None = Field(None, max_length=100)
    room_type: str | None = Field(None, max_length=100)
    width: Decimal | None = Field(None, gt=0)
    height: Decimal | None = Field(None, gt=0)
    depth: Decimal | None = Field(None, gt=0)
    weight: Decimal | None = Field(None, gt=0)
    tags: str | None = None
    status: str = "ACTIVE"
    is_active: bool = True


class ProductCreate(ProductBase):
    images: list[ProductImageInput] = Field(default_factory=list)
    material_ids: list[int] = Field(default_factory=list)
    style_ids: list[int] = Field(default_factory=list)
    room_type_ids: list[int] = Field(default_factory=list)
    color_ids: list[int] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = Field(None, min_length=2, max_length=255)
    slug: str | None = Field(None, min_length=2, max_length=280)
    description: str | None = None
    price: Decimal | None = Field(None, gt=0)
    stock_quantity: int | None = Field(None, ge=0)
    style: str | None = Field(None, max_length=100)
    color: str | None = Field(None, max_length=100)
    material: str | None = Field(None, max_length=100)
    room_type: str | None = Field(None, max_length=100)
    width: Decimal | None = Field(None, gt=0)
    height: Decimal | None = Field(None, gt=0)
    depth: Decimal | None = Field(None, gt=0)
    weight: Decimal | None = Field(None, gt=0)
    tags: str | None = None
    status: str | None = None
    is_active: bool | None = None
    images: list[ProductImageInput] | None = None
    material_ids: list[int] | None = None
    style_ids: list[int] | None = None
    room_type_ids: list[int] | None = None
    color_ids: list[int] | None = None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: CategoryRead
    images: list[ProductImageRead] = Field(default_factory=list)
    materials: list[CatalogRead] = Field(default_factory=list)
    styles: list[CatalogRead] = Field(default_factory=list)
    room_types: list[CatalogRead] = Field(default_factory=list)
    colors: list[ColorRead] = Field(default_factory=list)
    searchable_text: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ProductRead]
