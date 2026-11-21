import re
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.product import ProductRead
from app.schemas.user import UserRead

VIETNAMESE_PHONE_REGEX = re.compile(r"^(?:0|\+84)[35789]\d{8}$")


class OrderCreate(BaseModel):
    recipient_name: str = Field(..., min_length=2, max_length=100, description="Họ tên người nhận")
    recipient_phone: str = Field(..., min_length=9, max_length=15, description="Số điện thoại di động Việt Nam")
    province: str = Field(..., min_length=2, max_length=100, description="Tỉnh / Thành phố")
    ward: str = Field(..., min_length=2, max_length=100, description="Phường / Xã")
    street_address: str = Field(..., min_length=2, max_length=255, description="Số nhà, tên đường")
    delivery_notes: str | None = Field(None, max_length=500, description="Ghi chú giao hàng")
    payment_method: str = Field("COD", max_length=20, description="Phương thức thanh toán (chỉ hỗ trợ COD)")
    idempotency_key: str | None = Field(None, max_length=100, description="Khóa chống trùng lặp tạo đơn")

    @field_validator("recipient_phone")
    @classmethod
    def validate_vietnamese_phone(cls, v: str) -> str:
        clean = v.strip().replace(" ", "").replace(".", "").replace("-", "")
        if not VIETNAMESE_PHONE_REGEX.match(clean):
            raise ValueError("Số điện thoại không đúng định dạng di động Việt Nam (ví dụ: 0912345678 hoặc +84912345678)")
        return clean

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: str) -> str:
        method = v.strip().upper()
        if method != "COD":
            raise ValueError(
                "Hiện tại hệ thống chỉ hỗ trợ phương thức thanh toán khi nhận hàng (COD). "
                "Các phương thức thanh toán trực tuyến (VNPAY / Ví điện tử) đang chuẩn bị ra mắt."
            )
        return method


class OrderStatusUpdate(BaseModel):
    status: str


class AdminConfirmPayment(BaseModel):
    payment_status: str = Field("PAID", description="Trạng thái thanh toán mới (PAID)")
    note: str | None = Field(None, max_length=255, description="Ghi chú đối soát thu tiền")


class AdminUpdateShippingFee(BaseModel):
    shipping_fee: Decimal = Field(..., ge=0, description="Phí vận chuyển xác nhận cho hàng cồng kềnh")


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
    recipient_name: str
    recipient_phone: str
    province: str
    ward: str
    street_address: str
    delivery_notes: str | None = None
    shipping_address: str | None = None
    subtotal_amount: Decimal
    shipping_fee: Decimal | None = None
    shipping_fee_status: str = "CALCULATED"
    total_amount: Decimal | None = None
    payment_method: str = "COD"
    payment_status: str = "UNPAID"
    customer: UserRead | None = None
    items: list[OrderItemRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class OrderListResponse(BaseModel):
    total: int
    items: list[OrderRead]


class ShippingPreviewResponse(BaseModel):
    is_bulky: bool
    shipping_fee: Decimal | None
    shipping_fee_status: str
    subtotal: Decimal
    total_amount: Decimal | None
    bulky_items: list[str] = Field(default_factory=list)
    message: str
