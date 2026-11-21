from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.entities import User
from app.schemas.order import (
    AdminConfirmPayment,
    AdminUpdateShippingFee,
    OrderCreate,
    OrderListResponse,
    OrderRead,
    OrderStatusUpdate,
    ShippingPreviewResponse,
)
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])
admin_router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])


def get_order_service(db: Session = Depends(get_db)) -> OrderService:
    return OrderService(db)


@router.get("/shipping-preview", response_model=ShippingPreviewResponse)
def get_shipping_preview(
    current_user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    return service.get_shipping_preview(current_user)


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    return service.checkout(current_user, payload)


@router.get("", response_model=OrderListResponse)
def list_orders(
    current_user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    return service.list_orders(current_user)


@router.get("/{order_id}", response_model=OrderRead)
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    return service.get_order(current_user, order_id)


@router.post("/{order_id}/cancel", response_model=OrderRead)
def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    return service.cancel_order(current_user, order_id)


@router.post("/{order_id}/confirm-shipping-fee", response_model=OrderRead)
def customer_confirm_shipping_fee(
    order_id: int,
    current_user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    return service.customer_confirm_shipping_fee(current_user, order_id)


@admin_router.get("", response_model=OrderListResponse)
def admin_list_orders(
    _: User = Depends(require_admin),
    service: OrderService = Depends(get_order_service),
):
    return service.admin_list_orders()


@admin_router.get("/{order_id}", response_model=OrderRead)
def admin_get_order(
    order_id: int,
    _: User = Depends(require_admin),
    service: OrderService = Depends(get_order_service),
):
    return service.admin_get_order(order_id)


@admin_router.patch("/{order_id}/status", response_model=OrderRead)
def admin_update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    admin_user: User = Depends(require_admin),
    service: OrderService = Depends(get_order_service),
):
    return service.admin_update_status(admin_user, order_id, payload.status)


@admin_router.patch("/{order_id}/payment-status", response_model=OrderRead)
def admin_confirm_payment(
    order_id: int,
    payload: AdminConfirmPayment,
    admin_user: User = Depends(require_admin),
    service: OrderService = Depends(get_order_service),
):
    return service.admin_confirm_payment(admin_user, order_id, payload.payment_status, payload.note)


@admin_router.patch("/{order_id}/shipping-fee", response_model=OrderRead)
def admin_update_shipping_fee(
    order_id: int,
    payload: AdminUpdateShippingFee,
    admin_user: User = Depends(require_admin),
    service: OrderService = Depends(get_order_service),
):
    return service.admin_update_shipping_fee(admin_user, order_id, payload.shipping_fee)
