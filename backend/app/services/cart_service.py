from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.entities import Cart, CartItem, Product, ProductStatus, User
from app.schemas.cart import CartItemRead, CartRead
from app.schemas.product import ProductRead


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


def _get_or_create_cart(db: Session, user_id: int) -> Cart:
    cart = _cart_query(db, user_id).first()
    if cart is None:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.flush()
    return cart


def _serialize_cart(cart: Cart) -> CartRead:
    items: list[CartItemRead] = []
    subtotal = Decimal("0")
    total_items = 0
    for item in cart.items:
        unit_price = Decimal(str(item.product.price))
        line_subtotal = unit_price * item.quantity
        items.append(
            CartItemRead(
                id=item.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=unit_price,
                subtotal=line_subtotal,
                product=ProductRead.model_validate(item.product),
            )
        )
        subtotal += line_subtotal
        total_items += item.quantity
    return CartRead(id=cart.id, items=items, subtotal=subtotal, total_items=total_items)


def _get_available_product(db: Session, product_id: int) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not product.is_active or product.status != ProductStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product is not available")
    return product


class CartService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_cart(self, current_user: User) -> CartRead:
        cart = _cart_query(self.db, current_user.id).first()
        if cart is None:
            cart = Cart(user_id=current_user.id)
            self.db.add(cart)
            self.db.commit()
            self.db.refresh(cart)
            cart = _cart_query(self.db, current_user.id).first()
        return _serialize_cart(cart)

    def add_item(self, current_user: User, product_id: int, quantity: int) -> CartRead:
        product = _get_available_product(self.db, product_id)
        cart = _get_or_create_cart(self.db, current_user.id)

        existing = next((item for item in cart.items if item.product_id == product_id), None)
        new_quantity = (existing.quantity if existing else 0) + quantity
        if new_quantity > product.stock_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity exceeds available stock",
            )

        if existing:
            existing.quantity = new_quantity
        else:
            self.db.add(CartItem(cart_id=cart.id, product_id=product_id, quantity=quantity))

        self.db.commit()
        return self.get_cart(current_user)

    def update_item(self, current_user: User, item_id: int, quantity: int) -> CartRead:
        cart = _get_or_create_cart(self.db, current_user.id)
        item = next((item for item in cart.items if item.id == item_id), None)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")
        if quantity > item.product.stock_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity exceeds available stock",
            )
        item.quantity = quantity
        self.db.commit()
        return self.get_cart(current_user)

    def remove_item(self, current_user: User, item_id: int) -> CartRead:
        cart = _get_or_create_cart(self.db, current_user.id)
        item = next((item for item in cart.items if item.id == item_id), None)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")
        self.db.delete(item)
        self.db.commit()
        return self.get_cart(current_user)

    def clear_cart(self, current_user: User) -> CartRead:
        cart = _get_or_create_cart(self.db, current_user.id)
        for item in list(cart.items):
            self.db.delete(item)
        self.db.commit()
        return self.get_cart(current_user)
