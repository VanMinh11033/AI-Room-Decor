from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.product import ProductRead


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemRead(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    product: ProductRead | None = None


class CartRead(BaseModel):
    id: int
    items: list[CartItemRead] = Field(default_factory=list)
    subtotal: Decimal = Decimal("0")
    total_items: int = 0
