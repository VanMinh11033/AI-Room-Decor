from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartRead
from app.services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["cart"])


def get_cart_service(db: Session = Depends(get_db)) -> CartService:
    return CartService(db)


@router.get("", response_model=CartRead)
def get_cart(
    current_user: User = Depends(get_current_user),
    service: CartService = Depends(get_cart_service),
):
    return service.get_cart(current_user)


@router.post("/items", response_model=CartRead, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    payload: CartItemCreate,
    current_user: User = Depends(get_current_user),
    service: CartService = Depends(get_cart_service),
):
    return service.add_item(current_user, payload.product_id, payload.quantity)


@router.patch("/items/{item_id}", response_model=CartRead)
def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    current_user: User = Depends(get_current_user),
    service: CartService = Depends(get_cart_service),
):
    return service.update_item(current_user, item_id, payload.quantity)


@router.delete("/items/{item_id}", response_model=CartRead)
def remove_cart_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    service: CartService = Depends(get_cart_service),
):
    return service.remove_item(current_user, item_id)


@router.delete("", response_model=CartRead)
def clear_cart(
    current_user: User = Depends(get_current_user),
    service: CartService = Depends(get_cart_service),
):
    return service.clear_cart(current_user)
