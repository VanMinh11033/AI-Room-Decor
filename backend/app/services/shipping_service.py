from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence

from app.core.config import settings
from app.models.entities import CartItem, Product, ShippingFeeStatus


@dataclass
class ShippingAssessment:
    is_bulky: bool
    shipping_fee_status: str
    shipping_fee: Decimal | None
    subtotal: Decimal
    total_amount: Decimal | None
    bulky_items: list[str] = field(default_factory=list)
    message: str = ""


class ShippingService:
    def __init__(self, small_item_fee: float | None = None, bulky_categories: list[str] | None = None) -> None:
        self.small_item_fee = (
            Decimal(str(small_item_fee))
            if small_item_fee is not None
            else Decimal(str(settings.shipping_small_item_fee))
        )
        self.bulky_categories = (
            [c.lower() for c in bulky_categories]
            if bulky_categories is not None
            else settings.bulky_category_slugs
        )
        self.weight_threshold = float(settings.shipping_bulky_weight_threshold)

    def is_product_bulky(self, product: Product) -> bool:
        category_slug = ""
        if product.category and hasattr(product.category, "slug"):
            category_slug = str(product.category.slug or "").lower()
        elif hasattr(product, "category_id") and product.category_id:
            # Fallback if category object is not loaded but slug attribute exists
            category_slug = str(getattr(product, "category_slug", "")).lower()

        if category_slug and any(b in category_slug for b in self.bulky_categories):
            return True

        if product.weight is not None and float(product.weight) > self.weight_threshold:
            return True

        return False

    def assess_cart(self, items: Sequence[CartItem]) -> ShippingAssessment:
        subtotal = Decimal("0")
        bulky_items: list[str] = []

        for item in items:
            product = item.product
            unit_price = Decimal(str(product.price))
            subtotal += unit_price * item.quantity

            if self.is_product_bulky(product):
                bulky_items.append(product.name)

        is_bulky = len(bulky_items) > 0

        if is_bulky:
            return ShippingAssessment(
                is_bulky=True,
                shipping_fee_status=ShippingFeeStatus.PENDING_CALCULATION.value,
                shipping_fee=None,
                subtotal=subtotal,
                total_amount=None,  # Do not mark unknown shipping as 0!
                bulky_items=bulky_items,
                message="Đơn hàng có sản phẩm nội thất cồng kềnh. Phí vận chuyển cần nhân viên khảo sát và liên hệ xác nhận trước khi giao hàng.",
            )

        fee = self.small_item_fee
        return ShippingAssessment(
            is_bulky=False,
            shipping_fee_status=ShippingFeeStatus.CALCULATED.value,
            shipping_fee=fee,
            subtotal=subtotal,
            total_amount=subtotal + fee,
            bulky_items=[],
            message="Phí giao hàng tiêu chuẩn cho sản phẩm decor nhỏ gọn.",
        )
