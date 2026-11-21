from decimal import Decimal

import pytest
from app.core.security import get_password_hash
from app.models.entities import (
    Cart,
    Category,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    Product,
    ProductImage,
    ProductStatus,
    Role,
    RoleName,
    ShippingFeeStatus,
    User,
    UserProfile,
)


def register_user(client, email="customer@example.com"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Nguyễn Văn A"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def get_admin_headers(client, db_session, email="admin-cod@example.com"):
    admin_role = db_session.query(Role).filter(Role.name == RoleName.ADMIN).one()
    admin = User(
        email=email,
        full_name="Quản Trị Viên",
        hashed_password=get_password_hash("Password123!"),
        role_id=admin_role.id,
    )
    db_session.add(admin)
    db_session.flush()
    db_session.add(UserProfile(user_id=admin.id))
    db_session.add(Cart(user_id=admin.id))
    db_session.commit()
    login = client.post("/api/auth/login", json={"email": admin.email, "password": "Password123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_product(
    db_session,
    name="Đèn Gỗ Japandi",
    slug="den-go-japandi",
    price="250000.00",
    stock=10,
    category_slug="lighting",
    category_name="Lighting",
    weight=2.5,
    active=True,
):
    category = db_session.query(Category).filter(Category.slug == category_slug).first()
    if category is None:
        category = Category(name=category_name, slug=category_slug, is_active=True)
        db_session.add(category)
        db_session.flush()

    product = Product(
        category_id=category.id,
        name=name,
        slug=slug,
        price=Decimal(price),
        stock_quantity=stock,
        weight=Decimal(str(weight)),
        status=ProductStatus.ACTIVE if active else ProductStatus.INACTIVE,
        is_active=active,
    )
    db_session.add(product)
    db_session.flush()
    db_session.add(
        ProductImage(product_id=product.id, image_url="/storage/products/sample.jpg", is_primary=True, sort_order=0)
    )
    db_session.commit()
    return product


def valid_order_payload():
    return {
        "recipient_name": "Nguyễn Văn A",
        "recipient_phone": "0912345678",
        "province": "Hà Nội",
        "ward": "Phường Cống Vị",
        "street_address": "Số 123 Đường Liễu Giai",
        "delivery_notes": "Giao giờ hành chính, gọi trước 15 phút",
        "payment_method": "COD",
    }


def test_cod_checkout_success(client, db_session):
    """TC01: COD thành công - Order PENDING, Payment UNPAID, trừ kho, dọn cart."""
    headers = register_user(client, "cod-success@example.com")
    lamp = create_product(db_session, "Đèn Gỗ Nhỏ", "den-go-nho", price="200000.00", stock=5)

    client.post("/api/cart/items", json={"product_id": lamp.id, "quantity": 2}, headers=headers)

    response = client.post("/api/orders", json=valid_order_payload(), headers=headers)
    assert response.status_code == 201
    order = response.json()

    assert order["status"] == "PENDING"
    assert order["payment_method"] == "COD"
    assert order["payment_status"] == "UNPAID"
    assert order["recipient_name"] == "Nguyễn Văn A"
    assert order["recipient_phone"] == "0912345678"
    assert order["province"] == "Hà Nội"
    assert order["ward"] == "Phường Cống Vị"
    assert order["street_address"] == "Số 123 Đường Liễu Giai"
    assert order["subtotal_amount"] == "400000.00"
    assert order["shipping_fee"] == "30000.00"
    assert order["shipping_fee_status"] == "CALCULATED"
    assert order["total_amount"] == "430000.00"
    assert len(order["items"]) == 1

    # Verify inventory was decremented
    db_session.rollback()
    assert db_session.get(Product, lamp.id).stock_quantity == 3

    # Verify cart was emptied
    cart = client.get("/api/cart", headers=headers).json()
    assert cart["items"] == []


def test_missing_or_invalid_phone(client, db_session):
    """TC02 & TC03: Thiếu số điện thoại hoặc sai định dạng số điện thoại Việt Nam."""
    headers = register_user(client, "phone-validate@example.com")
    lamp = create_product(db_session, "Đèn Phone", "den-phone", price="150000.00", stock=5)
    client.post("/api/cart/items", json={"product_id": lamp.id, "quantity": 1}, headers=headers)

    # Missing phone
    payload = valid_order_payload()
    del payload["recipient_phone"]
    res_missing = client.post("/api/orders", json=payload, headers=headers)
    assert res_missing.status_code == 422

    # Invalid phone (letters, wrong length, bad prefix)
    for bad_phone in ["0123456789", "091234", "abcdefghij", "1234567890"]:
        payload["recipient_phone"] = bad_phone
        res_bad = client.post("/api/orders", json=payload, headers=headers)
        assert res_bad.status_code == 422


def test_missing_address_fields(client, db_session):
    """TC04: Thiếu địa chỉ (province, ward, street_address)."""
    headers = register_user(client, "address-validate@example.com")
    lamp = create_product(db_session, "Đèn Addr", "den-addr", price="150000.00", stock=5)
    client.post("/api/cart/items", json={"product_id": lamp.id, "quantity": 1}, headers=headers)

    for field in ["province", "ward", "street_address", "recipient_name"]:
        payload = valid_order_payload()
        del payload[field]
        res = client.post("/api/orders", json=payload, headers=headers)
        assert res.status_code == 422


def test_out_of_stock_rejected(client, db_session):
    """TC05 & TC06: Hết hàng hoặc số lượng không hợp lệ."""
    headers = register_user(client, "out-of-stock@example.com")
    lamp = create_product(db_session, "Đèn Stock", "den-stock", price="150000.00", stock=1)
    client.post("/api/cart/items", json={"product_id": lamp.id, "quantity": 1}, headers=headers)

    # Manually drop stock to 0
    db_session.query(Product).filter(Product.id == lamp.id).update({"stock_quantity": 0})
    db_session.commit()

    res = client.post("/api/orders", json=valid_order_payload(), headers=headers)
    assert res.status_code == 400
    assert "Insufficient stock" in res.json()["detail"]


def test_frontend_price_tampering_ignored(client, db_session):
    """TC07: Giá frontend bị sửa -> Backend bỏ qua, tự tính theo DB."""
    headers = register_user(client, "tamper-price@example.com")
    lamp = create_product(db_session, "Đèn Tamper", "den-tamper", price="500000.00", stock=5)
    client.post("/api/cart/items", json={"product_id": lamp.id, "quantity": 1}, headers=headers)

    # Hacker tries to send total_amount=1000 or unit_price=1000
    payload = valid_order_payload()
    payload["total_amount"] = "1000.00"
    payload["unit_price"] = "1000.00"
    payload["shipping_fee"] = "0.00"

    res = client.post("/api/orders", json=payload, headers=headers)
    assert res.status_code == 201
    order = res.json()
    assert order["subtotal_amount"] == "500000.00"
    assert order["shipping_fee"] == "30000.00"
    assert order["total_amount"] == "530000.00"


def test_double_submit_protection(client, db_session):
    """TC08: Bấm đặt hàng hai lần -> Lần 2 giỏ hàng đã dọn, báo lỗi 400, không tạo đơn trùng."""
    headers = register_user(client, "double-submit@example.com")
    lamp = create_product(db_session, "Đèn Double", "den-double", price="200000.00", stock=5)
    client.post("/api/cart/items", json={"product_id": lamp.id, "quantity": 1}, headers=headers)

    res1 = client.post("/api/orders", json=valid_order_payload(), headers=headers)
    assert res1.status_code == 201

    res2 = client.post("/api/orders", json=valid_order_payload(), headers=headers)
    assert res2.status_code == 400
    assert "Cart is empty" in res2.json()["detail"]


def test_cross_user_order_isolation(client, db_session):
    """TC10: Người dùng khác không thể xem đơn của người khác."""
    user_a = register_user(client, "user-a@example.com")
    user_b = register_user(client, "user-b@example.com")
    lamp = create_product(db_session, "Đèn Iso", "den-iso", price="100000.00", stock=5)

    client.post("/api/cart/items", json={"product_id": lamp.id, "quantity": 1}, headers=user_a)
    created = client.post("/api/orders", json=valid_order_payload(), headers=user_a).json()
    order_id = created["id"]

    # User B cannot access User A's order
    assert client.get(f"/api/orders/{order_id}", headers=user_b).status_code == 404


def test_admin_order_lifecycle_and_confirm_payment(client, db_session):
    """TC11 & TC12: Admin xác nhận đơn (Payment vẫn UNPAID) -> Sau đó xác nhận thu tiền (Payment PAID)."""
    customer = register_user(client, "lifecycle-cust@example.com")
    admin = get_admin_headers(client, db_session, "lifecycle-admin@example.com")
    lamp = create_product(db_session, "Đèn Life", "den-life", price="300000.00", stock=5)

    client.post("/api/cart/items", json={"product_id": lamp.id, "quantity": 1}, headers=customer)
    created = client.post("/api/orders", json=valid_order_payload(), headers=customer).json()
    order_id = created["id"]

    # 1. Admin confirms order -> OrderStatus CONFIRMED, PaymentStatus remains UNPAID!
    conf = client.patch(f"/api/admin/orders/{order_id}/status", json={"status": "CONFIRMED"}, headers=admin)
    assert conf.status_code == 200
    assert conf.json()["status"] == "CONFIRMED"
    assert conf.json()["payment_status"] == "UNPAID"

    # 2. Admin advances to SHIPPED
    ship = client.patch(f"/api/admin/orders/{order_id}/status", json={"status": "SHIPPED"}, headers=admin)
    assert ship.status_code == 200
    assert ship.json()["status"] == "SHIPPED"
    assert ship.json()["payment_status"] == "UNPAID"

    # 3. Shipper collected cash -> Admin confirms COD payment
    pay = client.patch(
        f"/api/admin/orders/{order_id}/payment-status",
        json={"payment_status": "PAID", "note": "Đã thu 330.000 đ tiền mặt từ shipper"},
        headers=admin,
    )
    assert pay.status_code == 200
    assert pay.json()["payment_status"] == "PAID"
    # Auto-advanced to COMPLETED since it was SHIPPED
    assert pay.json()["status"] == "COMPLETED"


def test_cancel_order_and_prevent_double_restoration(client, db_session):
    """TC13: Hủy đơn hoàn kho -> Ngăn hoàn kho 2 lần và không cho đánh dấu PAID."""
    customer = register_user(client, "cancel-stock@example.com")
    admin = get_admin_headers(client, db_session, "cancel-admin@example.com")
    lamp = create_product(db_session, "Đèn Cancel", "den-cancel", price="100000.00", stock=5)

    client.post("/api/cart/items", json={"product_id": lamp.id, "quantity": 2}, headers=customer)
    order = client.post("/api/orders", json=valid_order_payload(), headers=customer).json()

    db_session.rollback()
    assert db_session.get(Product, lamp.id).stock_quantity == 3

    # Cancel order
    cancelled = client.post(f"/api/orders/{order['id']}/cancel", headers=customer)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["payment_status"] == "UNPAID"

    db_session.rollback()
    assert db_session.get(Product, lamp.id).stock_quantity == 5

    # Attempt cancel again -> 400
    again = client.post(f"/api/orders/{order['id']}/cancel", headers=customer)
    assert again.status_code == 400

    # Attempt to confirm payment on cancelled order -> blocked
    pay_blocked = client.patch(
        f"/api/admin/orders/{order['id']}/payment-status",
        json={"payment_status": "PAID"},
        headers=admin,
    )
    assert pay_blocked.status_code == 400


def test_bulky_item_shipping_quote_and_admin_update(client, db_session):
    """TC14 & TC16: Hàng cồng kềnh (sofa, table, storage, bed) có phí chờ xác nhận."""
    customer = register_user(client, "bulky-cust@example.com")
    admin = get_admin_headers(client, db_session, "bulky-admin@example.com")

    sofa = create_product(
        db_session,
        name="Sofa Da Sang Trọng",
        slug="sofa-da-sang-trong",
        price="12000000.00",
        stock=2,
        category_slug="sofa",
        category_name="Sofa",
        weight=45.0,
    )

    client.post("/api/cart/items", json={"product_id": sofa.id, "quantity": 1}, headers=customer)

    # 1. Preview shipping
    preview = client.get("/api/orders/shipping-preview", headers=customer)
    assert preview.status_code == 200
    prev_data = preview.json()
    assert prev_data["is_bulky"] is True
    assert prev_data["shipping_fee_status"] == "PENDING_CALCULATION"
    assert prev_data["shipping_fee"] is None
    assert prev_data["total_amount"] is None
    assert "Sofa Da Sang Trọng" in prev_data["bulky_items"]

    # 2. Place COD order
    order = client.post("/api/orders", json=valid_order_payload(), headers=customer).json()
    order_id = order["id"]
    assert order["shipping_fee_status"] == "PENDING_CALCULATION"
    assert order["shipping_fee"] is None
    assert order["total_amount"] is None
    assert order["subtotal_amount"] == "12000000.00"

    # 3. Admin attempts to mark SHIPPED while pending calculation -> blocked!
    ship_blocked_1 = client.patch(f"/api/admin/orders/{order_id}/status", json={"status": "SHIPPED"}, headers=admin)
    assert ship_blocked_1.status_code == 400

    # 4. Admin surveys address and quotes shipping fee
    quote = client.patch(
        f"/api/admin/orders/{order_id}/shipping-fee",
        json={"shipping_fee": "250000.00"},
        headers=admin,
    )
    assert quote.status_code == 200
    updated = quote.json()
    assert updated["shipping_fee"] == "250000.00"
    assert updated["shipping_fee_status"] == "AWAITING_CUSTOMER_CONFIRMATION"
    assert updated["total_amount"] == "12250000.00"

    # 5. Admin attempts to mark SHIPPED before customer confirms -> blocked!
    ship_blocked_2 = client.patch(f"/api/admin/orders/{order_id}/status", json={"status": "SHIPPED"}, headers=admin)
    assert ship_blocked_2.status_code == 400

    # 6. Customer confirms the shipping fee quote
    conf_fee = client.post(f"/api/orders/{order_id}/confirm-shipping-fee", headers=customer)
    assert conf_fee.status_code == 200
    conf_data = conf_fee.json()
    assert conf_data["shipping_fee_status"] == "CUSTOMER_CONFIRMED"
    assert conf_data["shipping_fee"] == "250000.00"
    assert conf_data["total_amount"] == "12250000.00"

    # 7. Now Admin can advance to SHIPPED
    ship_ok = client.patch(f"/api/admin/orders/{order_id}/status", json={"status": "SHIPPED"}, headers=admin)
    assert ship_ok.status_code == 200
    assert ship_ok.json()["status"] == "SHIPPED"


def test_backend_rejects_online_and_vnpay(client, db_session):
    """TC15: Backend từ chối phương thức thanh toán VNPAY / ONLINE."""
    customer = register_user(client, "reject-vnpay@example.com")
    lamp = create_product(db_session, "Đèn Test VNPAY", "den-test-vnpay", price="200000.00", stock=5)
    client.post("/api/cart/items", json={"product_id": lamp.id, "quantity": 1}, headers=customer)

    for method in ["VNPAY", "ONLINE", "MOMO", "ZALOPAY"]:
        payload = valid_order_payload()
        payload["payment_method"] = method
        res = client.post("/api/orders", json=payload, headers=customer)
        # Validation error from schema or service
        assert res.status_code in (400, 422)


def test_concurrent_checkout_requests(client, db_session):
    """TC09: Hai request đặt hàng đồng thời -> Chỉ 1 request thành công, 1 request bị từ chối, không trừ trùng kho."""
    import concurrent.futures

    customer = register_user(client, "concurrent-user@example.com")
    lamp = create_product(db_session, "Đèn Concurrent", "den-concurrent", price="100000.00", stock=1)
    client.post("/api/cart/items", json={"product_id": lamp.id, "quantity": 1}, headers=customer)

    def do_checkout():
        return client.post("/api/orders", json=valid_order_payload(), headers=customer)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(do_checkout)
        f2 = executor.submit(do_checkout)
        res1 = f1.result()
        res2 = f2.result()

    statuses = [res1.status_code, res2.status_code]
    assert 201 in statuses
    assert 400 in statuses

    # Refresh snapshot from separate connection
    db_session.rollback()

    # Verify only 1 order exists in database for this user
    user = db_session.query(User).filter(User.email == "concurrent-user@example.com").one()
    orders = db_session.query(Order).filter(Order.user_id == user.id).all()
    assert len(orders) == 1

    # Stock is 0, not negative!
    assert db_session.get(Product, lamp.id).stock_quantity == 0

