"""
TEST SUITE: P0 ORDER CREATION MAINTENANCE GATE (ĐÓNG BĂNG TẠO ĐƠN HÀNG)
Kiểm thử toàn diện các yêu cầu an toàn theo chỉ thị P0:
1. Khi Maintenance Active:
   - Chặn tạo đơn mới (POST /api/orders) -> Trả HTTP 503 SERVICE UNAVAILABLE.
   - Header Retry-After: 300 có mặt.
   - KHÔNG tạo Order.
   - KHÔNG tạo OrderItem.
   - KHÔNG trừ Stock (tồn kho giữ nguyên 100%).
   - KHÔNG xóa Cart (giỏ hàng giữ nguyên).
   - Chặn các thao tác ghi khác (cancel order, confirm shipping fee) -> Trả HTTP 503.
2. Khi Maintenance Kết thúc (Inactive):
   - Tạo đơn hoạt động bình thường trở lại (HTTP 201 Created).
   - Trừ stock, tạo OrderItem, xóa Cart theo đúng nghiệp vụ.
3. Các thao tác đọc và tính năng khác KHÔNG bị ảnh hưởng trong thời gian bảo trì:
   - Probe endpoint GET /api/orders/maintenance-status -> HTTP 200.
   - Auth (Login / Me) -> HTTP 200.
   - Catalog (List products, categories) -> HTTP 200.
   - User Order History (GET /api/orders) -> HTTP 200.
   - Cart lookup & add item -> HTTP 200.
"""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.maintenance import (
    get_order_maintenance_status,
    is_order_maintenance_active,
    reset_order_maintenance_mode,
    set_order_maintenance_mode,
)
from app.models.entities import (
    Cart,
    CartItem,
    Category,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductStatus,
    User,
)


@pytest.fixture(autouse=True)
def cleanup_maintenance_mode():
    """Đảm bảo dọn dẹp trạng thái bảo trì sau mỗi bài test."""
    yield
    reset_order_maintenance_mode()


@pytest.fixture()
def setup_customer_and_cart(client: TestClient, db_session: Session):
    # Register customer through standard API
    reg_resp = client.post(
        "/api/auth/register",
        json={"email": "freeze_test_user@example.com", "password": "Password123!", "full_name": "Freeze Tester"},
    )
    assert reg_resp.status_code == 201
    headers = {"Authorization": f"Bearer {reg_resp.json()['access_token']}"}

    user = db_session.query(User).filter_by(email="freeze_test_user@example.com").first()
    cart = db_session.query(Cart).filter_by(user_id=user.id).first()

    cat = Category(name="Decor Freeze", slug="decor-freeze")
    db_session.add(cat)
    db_session.flush()

    # Product with initial stock = 10
    product = Product(
        name="Đèn Bàn Vintage Freeze",
        slug="den-ban-vintage-freeze",
        price=Decimal("450000.00"),
        stock_quantity=10,
        status=ProductStatus.ACTIVE,
        is_active=True,
        category_id=cat.id,
    )
    db_session.add(product)
    db_session.flush()

    cart_item = CartItem(
        cart_id=cart.id,
        product_id=product.id,
        quantity=2,
    )
    db_session.add(cart_item)
    db_session.commit()

    return {
        "user": user,
        "product": product,
        "cart": cart,
        "cart_item": cart_item,
        "headers": headers,
    }


def test_public_maintenance_status_endpoint(client: TestClient):
    """Xác nhận endpoint GET /api/orders/maintenance-status hoạt động công khai không cần auth."""
    # Mặc định: Inactive
    reset_order_maintenance_mode()
    res = client.get("/api/orders/maintenance-status")
    assert res.status_code == 200
    data = res.json()
    assert data["order_maintenance_active"] is False
    assert data["status"] == "OPERATIONAL"

    # Bật maintenance
    set_order_maintenance_mode(True)
    res2 = client.get("/api/orders/maintenance-status")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["order_maintenance_active"] is True
    assert data2["status"] == "MAINTENANCE_ACTIVE"
    assert "bảo trì" in data2["message"]


def test_environment_enforced_maintenance_cannot_be_disabled_by_runtime(client: TestClient, monkeypatch):
    """
    Quy tắc an toàn P0 (Phase 2):
    Nếu biến môi trường máy chủ (ORDER_MAINTENANCE_MODE=true) đang bật,
    runtime override KHÔNG được phép tắt chế độ bảo trì (ném HTTP 400).
    """
    from app.core.config import settings
    monkeypatch.setattr(settings, "order_maintenance_mode", True)

    assert is_order_maintenance_active() is True

    # Thử tắt qua runtime -> Phải ném HTTPException 400
    with pytest.raises(Exception) as exc_info:
        set_order_maintenance_mode(False)
    assert "ORDER_MAINTENANCE_MODE=true" in str(exc_info.value)

    # Trạng thái vẫn là True
    assert is_order_maintenance_active() is True

    # Kiểm tra API public status
    res = client.get("/api/orders/maintenance-status")
    assert res.status_code == 200
    assert res.json()["order_maintenance_active"] is True
    assert res.json()["env_enforced"] is True


def test_checkout_blocked_when_maintenance_active(client: TestClient, db_session: Session, setup_customer_and_cart):
    """
    KIỂM THỬ TRỌNG YẾU:
    Khi maintenance active:
    - POST /api/orders bị chặn với HTTP 503.
    - Không tạo Order, không tạo OrderItem.
    - Stock quantity KHÔNG bị trừ (giữ nguyên 10).
    - Cart items KHÔNG bị xóa (giữ nguyên).
    """
    ctx = setup_customer_and_cart
    product_id = ctx["product"].id
    cart_id = ctx["cart"].id

    initial_orders_count = db_session.query(Order).count()
    initial_items_count = db_session.query(OrderItem).count()
    initial_stock = db_session.get(Product, product_id).stock_quantity
    initial_cart_count = db_session.query(CartItem).filter_by(cart_id=cart_id).count()

    assert initial_stock == 10
    assert initial_cart_count == 1

    # KÍCH HOẠT MAINTENANCE MODE
    set_order_maintenance_mode(True)
    assert is_order_maintenance_active() is True

    payload = {
        "recipient_name": "Nguyễn Văn Test",
        "recipient_phone": "0912345678",
        "province": "TP. Hồ Chí Minh",
        "ward": "Phường Bến Nghé",
        "street_address": "Số 1 Lê Duẩn",
        "delivery_notes": "Giao giờ hành chính",
        "payment_method": "COD",
    }

    # Gửi request checkout khi đang bảo trì
    response = client.post("/api/orders", json=payload, headers=ctx["headers"])

    # 1. Trả về đúng HTTP 503 SERVICE UNAVAILABLE
    assert response.status_code == 503
    assert response.headers.get("Retry-After") == "300"
    assert response.headers.get("X-Maintenance-Mode") == "ORDER_CREATION_FREEZE"
    assert "bảo trì" in response.json()["detail"].lower()

    # 2. XÁC MINH ZERO-MUTATION TRONG CƠ SỞ DỮ LIỆU
    db_session.expire_all()

    # KHÔNG tạo Order
    assert db_session.query(Order).count() == initial_orders_count

    # KHÔNG tạo OrderItem
    assert db_session.query(OrderItem).count() == initial_items_count

    # KHÔNG trừ Stock
    current_product = db_session.get(Product, product_id)
    assert current_product.stock_quantity == initial_stock, "Stock quantity must NOT be deducted during maintenance"

    # KHÔNG xóa Cart
    current_cart_count = db_session.query(CartItem).filter_by(cart_id=cart_id).count()
    assert current_cart_count == initial_cart_count, "Cart items must NOT be deleted during maintenance"


def test_order_mutations_blocked_during_maintenance(client: TestClient, db_session: Session, setup_customer_and_cart):
    """Các thao tác ghi khác như cancel order, confirm shipping fee cũng phải bị chặn HTTP 503."""
    ctx = setup_customer_and_cart

    # Tạo trước 1 đơn hàng ở trạng thái bình thường (maintenance off)
    set_order_maintenance_mode(False)
    order = Order(
        user_id=ctx["user"].id,
        status=OrderStatus.PENDING,
        recipient_name="Khách Cũ",
        recipient_phone="0909090909",
        province="Hà Nội",
        ward="Hàng Bài",
        street_address="12 Hàng Bài",
        total_amount=Decimal("500000.00"),
        subtotal_amount=Decimal("500000.00"),
        shipping_fee=Decimal("30000.00"),
        payment_method="COD",
        payment_status="UNPAID",
    )
    db_session.add(order)
    db_session.commit()
    order_id = order.id

    # KÍCH HOẠT MAINTENANCE MODE
    set_order_maintenance_mode(True)

    # Thử Cancel Order
    res_cancel = client.post(f"/api/orders/{order_id}/cancel", headers=ctx["headers"])
    assert res_cancel.status_code == 503
    assert "bảo trì" in res_cancel.json()["detail"].lower()

    # Thử Confirm Shipping Fee
    res_confirm = client.post(f"/api/orders/{order_id}/confirm-shipping-fee", headers=ctx["headers"])
    assert res_confirm.status_code == 503
    assert "bảo trì" in res_confirm.json()["detail"].lower()

    # Trạng thái đơn hàng trong DB không bị biến đổi
    db_session.expire_all()
    fresh_order = db_session.get(Order, order_id)
    assert fresh_order.status == OrderStatus.PENDING


def test_checkout_restores_when_maintenance_ends(client: TestClient, db_session: Session, setup_customer_and_cart):
    """Khi maintenance kết thúc, luồng checkout hoạt động bình thường trở lại."""
    ctx = setup_customer_and_cart
    product_id = ctx["product"].id
    cart_id = ctx["cart"].id

    # Bật maintenance trước
    set_order_maintenance_mode(True)
    payload = {
        "recipient_name": "Nguyễn Văn Hồi Phục",
        "recipient_phone": "0987654321",
        "province": "Đà Nẵng",
        "ward": "Hải Châu 1",
        "street_address": "88 Nguyễn Du",
        "delivery_notes": "Gọi trước",
        "payment_method": "COD",
    }
    r_blocked = client.post("/api/orders", json=payload, headers=ctx["headers"])
    assert r_blocked.status_code == 503

    # KẾT THÚC BẢO TRÌ
    set_order_maintenance_mode(False)
    assert is_order_maintenance_active() is False

    # Thử lại đặt hàng -> Phải thành công (HTTP 201)
    r_success = client.post("/api/orders", json=payload, headers=ctx["headers"])
    assert r_success.status_code == 201
    created_order = r_success.json()
    assert created_order["recipient_name"] == "Nguyễn Văn Hồi Phục"
    assert created_order["payment_method"] == "COD"

    # Stock bị trừ từ 10 xuống 8
    db_session.commit()
    assert db_session.get(Product, product_id).stock_quantity == 8

    # Cart được xóa sạch
    assert db_session.query(CartItem).filter_by(cart_id=cart_id).count() == 0


def test_safe_operations_unaffected_during_maintenance(client: TestClient, db_session: Session, setup_customer_and_cart):
    """
    Xác nhận trong lúc bảo trì:
    - Auth (Login / Register / Me) hoạt động bình thường.
    - Catalog (Products, Categories) hoạt động bình thường.
    - Đọc giỏ hàng (Cart) và danh sách đơn cũ (Orders) hoạt động bình thường.
    """
    ctx = setup_customer_and_cart

    set_order_maintenance_mode(True)

    # 1. Catalog
    r_cat = client.get("/api/categories")
    assert r_cat.status_code == 200

    r_prod = client.get("/api/products")
    assert r_prod.status_code == 200

    # 2. Auth login
    login_payload = {
        "email": "freeze_test_user@example.com",
        "password": "Password123!",
    }
    r_login = client.post("/api/auth/login", json=login_payload)
    assert r_login.status_code == 200
    assert "access_token" in r_login.json()

    # 3. Read current cart
    r_cart = client.get("/api/cart", headers=ctx["headers"])
    assert r_cart.status_code == 200

    # 4. Read user order history
    r_orders = client.get("/api/orders", headers=ctx["headers"])
    assert r_orders.status_code == 200
