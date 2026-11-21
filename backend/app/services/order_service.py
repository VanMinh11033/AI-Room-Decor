import json
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.entities import (
    AdminAuditLog,
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    Product,
    ProductStatus,
    ShippingFeeStatus,
    User,
)
from app.schemas.order import (
    OrderCreate,
    OrderItemRead,
    OrderListResponse,
    OrderRead,
    ShippingPreviewResponse,
)
from app.schemas.product import ProductRead
from app.schemas.user import UserRead
from app.services.shipping_service import ShippingService


def _product_load_options():
    return (
        joinedload(Product.category),
        joinedload(Product.images),
        joinedload(Product.materials),
        joinedload(Product.styles),
        joinedload(Product.room_types),
        joinedload(Product.colors),
    )


def _cart_query(db: Session, user_id: int):
    return db.query(Cart).options(
        joinedload(Cart.items).joinedload(CartItem.product).options(*_product_load_options())
    ).filter(Cart.user_id == user_id)


def _order_query(db: Session):
    return db.query(Order).options(
        joinedload(Order.user),
        joinedload(Order.items).joinedload(OrderItem.product).options(*_product_load_options()),
    )


def _serialize_order(order: Order) -> OrderRead:
    items: list[OrderItemRead] = []
    for item in order.items:
        unit_price = Decimal(str(item.unit_price))
        items.append(
            OrderItemRead(
                id=item.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=unit_price,
                subtotal=unit_price * item.quantity,
                product=ProductRead.model_validate(item.product) if item.product else None,
            )
        )
    return OrderRead(
        id=order.id,
        user_id=order.user_id,
        status=order.status.value if hasattr(order.status, "value") else str(order.status),
        recipient_name=order.recipient_name or "N/A",
        recipient_phone=order.recipient_phone or "",
        province=order.province or "",
        ward=order.ward or "",
        street_address=order.street_address or "",
        delivery_notes=order.delivery_notes,
        shipping_address=order.shipping_address,
        subtotal_amount=Decimal(str(order.subtotal_amount or 0)),
        shipping_fee=Decimal(str(order.shipping_fee)) if order.shipping_fee is not None else None,
        shipping_fee_status=getattr(order, "shipping_fee_status", ShippingFeeStatus.CALCULATED.value)
        or ShippingFeeStatus.CALCULATED.value,
        total_amount=Decimal(str(order.total_amount)) if order.total_amount is not None else None,
        payment_method=order.payment_method or PaymentMethod.COD.value,
        payment_status=order.payment_status or PaymentStatus.UNPAID.value,
        customer=UserRead.model_validate(order.user) if order.user else None,
        items=items,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


class OrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.shipping_service = ShippingService()

    def get_shipping_preview(self, current_user: User) -> ShippingPreviewResponse:
        cart = _cart_query(self.db, current_user.id).first()
        if cart is None or not cart.items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")
        assessment = self.shipping_service.assess_cart(cart.items)
        return ShippingPreviewResponse(
            is_bulky=assessment.is_bulky,
            shipping_fee=assessment.shipping_fee,
            shipping_fee_status=assessment.shipping_fee_status,
            subtotal=assessment.subtotal,
            total_amount=assessment.total_amount,
            bulky_items=assessment.bulky_items,
            message=assessment.message,
        )

    def checkout(self, current_user: User, payload: OrderCreate) -> OrderRead:
        # Enforce COD only
        method = payload.payment_method.strip().upper()
        if method != PaymentMethod.COD.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hiện tại hệ thống chỉ hỗ trợ thanh toán khi nhận hàng (COD). Vui lòng chọn COD.",
            )

        # Concurrency / Idempotency lock on Cart
        cart = (
            self.db.query(Cart)
            .filter(Cart.user_id == current_user.id)
            .with_for_update()
            .first()
        )
        if cart is None or not cart.items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

        product_ids = [item.product_id for item in cart.items]
        # Lock products to prevent race conditions on stock
        products = {
            p.id: p
            for p in self.db.query(Product)
            .filter(Product.id.in_(product_ids))
            .with_for_update()
            .all()
        }

        # Validate product availability and stock
        for item in cart.items:
            product = products.get(item.product_id)
            if product is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A product is no longer available")
            if not product.is_active or product.status != ProductStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product '{product.name}' is not available",
                )
            if item.quantity < 1:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid quantity")
            if item.quantity > product.stock_quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for '{product.name}'",
                )

        # Shipping fee calculation (centralized policy, zero trust frontend)
        assessment = self.shipping_service.assess_cart(cart.items)
        subtotal = assessment.subtotal
        shipping_fee = assessment.shipping_fee
        shipping_fee_status = assessment.shipping_fee_status
        total_amount = assessment.total_amount

        full_address = f"{payload.street_address.strip()}, {payload.ward.strip()}, {payload.province.strip()}"

        order = Order(
            user_id=current_user.id,
            status=OrderStatus.PENDING,
            recipient_name=payload.recipient_name.strip(),
            recipient_phone=payload.recipient_phone.strip(),
            province=payload.province.strip(),
            ward=payload.ward.strip(),
            street_address=payload.street_address.strip(),
            delivery_notes=payload.delivery_notes.strip() if payload.delivery_notes else None,
            shipping_address=full_address,
            subtotal_amount=subtotal,
            shipping_fee=shipping_fee,
            shipping_fee_status=shipping_fee_status,
            total_amount=total_amount,
            payment_method=PaymentMethod.COD.value,
            payment_status=PaymentStatus.UNPAID.value,
        )
        self.db.add(order)
        self.db.flush()

        for item in cart.items:
            product = products[item.product_id]
            unit_price = Decimal(str(product.price))
            self.db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=item.quantity,
                    unit_price=unit_price,
                )
            )
            # Deduct inventory atomically
            product.stock_quantity -= item.quantity

        # Clear cart items completely
        for item in list(cart.items):
            self.db.delete(item)

        self.db.commit()
        return _serialize_order(self._get_owned_order(current_user, order.id))

    def list_orders(self, current_user: User) -> OrderListResponse:
        orders = (
            _order_query(self.db)
            .filter(Order.user_id == current_user.id)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .all()
        )
        return OrderListResponse(total=len(orders), items=[_serialize_order(order) for order in orders])

    def get_order(self, current_user: User, order_id: int) -> OrderRead:
        return _serialize_order(self._get_owned_order(current_user, order_id))

    def cancel_order(self, current_user: User, order_id: int) -> OrderRead:
        order = self._get_owned_order(current_user, order_id)
        if order.status == OrderStatus.CANCELLED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order already cancelled")
        if order.status != OrderStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending orders can be cancelled")

        # Prevent double stock restoration
        for item in order.items:
            product = self.db.get(Product, item.product_id)
            if product is not None:
                product.stock_quantity += item.quantity

        order.status = OrderStatus.CANCELLED
        # Cancelled orders cannot be marked as paid
        if order.payment_status != PaymentStatus.PAID.value:
            order.payment_status = PaymentStatus.UNPAID.value

        self.db.commit()
        return _serialize_order(self._get_owned_order(current_user, order_id))

    def admin_list_orders(self) -> OrderListResponse:
        orders = _order_query(self.db).order_by(Order.created_at.desc(), Order.id.desc()).all()
        return OrderListResponse(total=len(orders), items=[_serialize_order(order) for order in orders])

    def admin_get_order(self, order_id: int) -> OrderRead:
        return _serialize_order(self._admin_get_order(order_id))

    def admin_update_status(self, admin_user: User, order_id: int, status_value: str) -> OrderRead:
        try:
            new_status = OrderStatus(status_value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid order status") from exc

        order = self._admin_get_order(order_id)
        old_status = order.status

        # If transitioning to CANCELLED from non-cancelled, restore stock
        if new_status == OrderStatus.CANCELLED and old_status != OrderStatus.CANCELLED:
            for item in order.items:
                product = self.db.get(Product, item.product_id)
                if product is not None:
                    product.stock_quantity += item.quantity

        # If transitioning out of CANCELLED (not recommended, but if ever attempted), validate stock
        if old_status == OrderStatus.CANCELLED and new_status != OrderStatus.CANCELLED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot reactivate a cancelled order")

        # Guard: Cannot ship bulky orders without customer fee confirmation
        if new_status in (OrderStatus.SHIPPED, OrderStatus.COMPLETED):
            if order.shipping_fee_status in (
                ShippingFeeStatus.PENDING_CALCULATION.value,
                ShippingFeeStatus.AWAITING_CUSTOMER_CONFIRMATION.value,
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Không thể chuyển sang trạng thái giao hàng khi khách hàng chưa xác nhận mức phí vận chuyển hàng cồng kềnh.",
                )

        order.status = new_status

        # Do NOT auto-mark PaymentStatus as PAID on CONFIRMED/SHIPPED!
        # PaymentStatus remains UNPAID until admin explicitly confirms cash collection.

        # Record admin audit log
        self.db.add(
            AdminAuditLog(
                admin_user_id=admin_user.id,
                action="UPDATE_ORDER_STATUS",
                entity_type="order",
                entity_id=order.id,
                metadata_json=json.dumps({"old_status": old_status.value, "new_status": new_status.value}),
            )
        )

        self.db.commit()
        return _serialize_order(self._admin_get_order(order_id))

    def admin_confirm_payment(self, admin_user: User, order_id: int, payment_status_value: str, note: str | None = None) -> OrderRead:
        status_norm = payment_status_value.strip().upper()
        if status_norm not in (PaymentStatus.PAID.value, PaymentStatus.UNPAID.value):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid payment status")

        order = self._admin_get_order(order_id)
        if order.status == OrderStatus.CANCELLED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot confirm payment for a cancelled order")

        old_payment_status = order.payment_status
        order.payment_status = status_norm

        # If payment is confirmed PAID and order is SHIPPED, advance order to COMPLETED
        if status_norm == PaymentStatus.PAID.value and order.status in (OrderStatus.SHIPPED, OrderStatus.PROCESSING):
            order.status = OrderStatus.COMPLETED

        self.db.add(
            AdminAuditLog(
                admin_user_id=admin_user.id,
                action="CONFIRM_COD_PAYMENT",
                entity_type="order",
                entity_id=order.id,
                metadata_json=json.dumps({
                    "old_payment_status": old_payment_status,
                    "new_payment_status": status_norm,
                    "note": note or "Xác nhận thu tiền mặt COD",
                }),
            )
        )

        self.db.commit()
        return _serialize_order(self._admin_get_order(order_id))

    def admin_update_shipping_fee(self, admin_user: User, order_id: int, shipping_fee: Decimal) -> OrderRead:
        order = self._admin_get_order(order_id)
        if order.status == OrderStatus.CANCELLED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update shipping fee on cancelled order")

        old_fee = order.shipping_fee
        order.shipping_fee = Decimal(str(shipping_fee))
        order.shipping_fee_status = ShippingFeeStatus.AWAITING_CUSTOMER_CONFIRMATION.value
        order.total_amount = Decimal(str(order.subtotal_amount)) + order.shipping_fee

        self.db.add(
            AdminAuditLog(
                admin_user_id=admin_user.id,
                action="UPDATE_SHIPPING_FEE",
                entity_type="order",
                entity_id=order.id,
                metadata_json=json.dumps({
                    "old_shipping_fee": str(old_fee) if old_fee is not None else None,
                    "new_shipping_fee": str(order.shipping_fee),
                    "total_amount": str(order.total_amount),
                }),
            )
        )

        self.db.commit()
        return _serialize_order(self._admin_get_order(order_id))

    def customer_confirm_shipping_fee(self, current_user: User, order_id: int) -> OrderRead:
        order = self._get_owned_order(current_user, order_id)
        if order.status == OrderStatus.CANCELLED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Đơn hàng đã bị hủy")
        if order.shipping_fee_status != ShippingFeeStatus.AWAITING_CUSTOMER_CONFIRMATION.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Đơn hàng không ở trạng thái chờ khách hàng xác nhận phí vận chuyển",
            )
        order.shipping_fee_status = ShippingFeeStatus.CUSTOMER_CONFIRMED.value
        self.db.commit()
        return _serialize_order(self._get_owned_order(current_user, order_id))

    def _get_owned_order(self, current_user: User, order_id: int) -> Order:
        order = _order_query(self.db).filter(Order.id == order_id, Order.user_id == current_user.id).first()
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return order

    def _admin_get_order(self, order_id: int) -> Order:
        order = _order_query(self.db).filter(Order.id == order_id).first()
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return order
