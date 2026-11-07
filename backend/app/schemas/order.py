from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.product import ProductRead
from app.schemas.user import UserRead


class OrderCreate(BaseModel):
    shipping_address: str | None = Field(None, max_length=500)


class OrderStatusUpdate(BaseModel):
    status: str


class OrderItemRead(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    product: ProductRead | None = None


class OrderRead(BaseModel):
    id: int
    user_id: int
    status: str
    total_amount: Decimal
    shipping_address: str | None = None
    customer: UserRead | None = None
    items: list[OrderItemRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class OrderListResponse(BaseModel):
    total: int
    items: list[OrderRead]
