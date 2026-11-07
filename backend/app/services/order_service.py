from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.entities import Cart, CartItem, Order, OrderItem, OrderStatus, Product, ProductStatus, User
from app.schemas.order import OrderItemRead, OrderListResponse, OrderRead
from app.schemas.product import ProductRead
from app.schemas.user import UserRead


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
        joinedload(Order.items).joinedload(OrderItem.product).options(*_product_load_options())
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
        status=order.status.value,
        total_amount=Decimal(str(order.total_amount)),
        shipping_address=order.shipping_address,
        customer=UserRead.model_validate(order.user) if order.user else None,
        items=items,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


class OrderService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def checkout(self, current_user: User, shipping_address: str | None) -> OrderRead:
        cart = _cart_query(self.db, current_user.id).first()
        if cart is None or not cart.items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

        product_ids = [item.product_id for item in cart.items]
        products = {p.id: p for p in self.db.query(Product).filter(Product.id.in_(product_ids)).all()}

        for item in cart.items:
            product = products.get(item.product_id)
            if product is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A product is no longer available")
            if not product.is_active or product.status != ProductStatus.ACTIVE:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product '{product.name}' is not available")
            if item.quantity < 1:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid quantity")
            if item.quantity > product.stock_quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for '{product.name}'",
                )

        order = Order(
            user_id=current_user.id,
            status=OrderStatus.PENDING,
            total_amount=Decimal("0"),
            shipping_address=shipping_address,
        )
        self.db.add(order)
        self.db.flush()

        total = Decimal("0")
        for item in cart.items:
            product = products[item.product_id]
            unit_price = Decimal(str(product.price))
            total += unit_price * item.quantity
            self.db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=item.quantity,
                    unit_price=unit_price,
                )
            )
            product.stock_quantity -= item.quantity

        order.total_amount = total
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

        for item in order.items:
            product = self.db.get(Product, item.product_id)
            if product is not None:
                product.stock_quantity += item.quantity
        order.status = OrderStatus.CANCELLED
        self.db.commit()
        return _serialize_order(self._get_owned_order(current_user, order_id))

    def admin_list_orders(self) -> OrderListResponse:
        orders = _order_query(self.db).order_by(Order.created_at.desc(), Order.id.desc()).all()
        return OrderListResponse(total=len(orders), items=[_serialize_order(order) for order in orders])

    def admin_get_order(self, order_id: int) -> OrderRead:
        return _serialize_order(self._admin_get_order(order_id))

    def admin_update_status(self, order_id: int, status_value: str) -> OrderRead:
        try:
            new_status = OrderStatus(status_value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid order status") from exc
        order = self._admin_get_order(order_id)
        order.status = new_status
        self.db.commit()
        return _serialize_order(self._admin_get_order(order_id))

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
