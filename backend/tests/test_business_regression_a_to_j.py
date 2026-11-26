"""Comprehensive Business Regression Test Suite (Scenarios A through J)
for P1 COD Checkout Migration Safety Check (INC-20261126-COD-500).

Scenarios covered:
- Scenario A: Standard product order (shipping calculated 30k, total = subtotal + 30k)
- Scenario B: Bulky product order with pending shipping quotation (Modern Modular Sofa, total None, shipping None, PENDING_CALCULATION)
- Scenario C: Existing order with non-null total (serialization preserves exact numeric total)
- Scenario D: New order with null total (serialization keeps total_amount None without error or coercing to 0)
- Scenario E: Order serialization & history (Customer API GET /api/orders & GET /api/orders/{id} handles both null and non-null)
- Scenario F: Admin order display with pending total (Admin API GET /api/admin/orders & GET /api/admin/orders/{id})
- Scenario G: Shipping quotation assignment & final total calculation (Admin updates fee -> AWAITING_CUSTOMER_CONFIRMATION -> Customer confirms -> CUSTOMER_CONFIRMED)
- Scenario H: Cart preservation on failed checkout (validation error leaves cart items completely intact)
- Scenario I: Stock deduction & rollback (stock decremented on success, left untouched on abort)
- Scenario J: Duplicate order submission protection (rapid duplicate submit rejected with 400 Cart is empty)
"""

from decimal import Decimal
import pytest
from app.core.security import get_password_hash
from app.models.entities import (
    Cart,
    Category,
    Order,
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


def get_or_create_category(db_session, name: str, slug: str) -> Category:
    cat = db_session.query(Category).filter((Category.slug == slug) | (Category.name == name)).first()
    if not cat:
        cat = Category(name=name, slug=slug, is_active=True)
        db_session.add(cat)
        db_session.flush()
    return cat


def create_customer(client, db_session, email: str, full_name: str = "Khách Hàng Kiểm Thử"):
    cust_role = db_session.query(Role).filter(Role.name == RoleName.CUSTOMER).one()
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash("Password123!"),
        role_id=cust_role.id,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserProfile(user_id=user.id))
    db_session.add(Cart(user_id=user.id))
    db_session.commit()

    login = client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return user, {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_admin(client, db_session, email: str = "admin-safety@example.com"):
    admin_role = db_session.query(Role).filter(Role.name == RoleName.ADMIN).one()
    user = User(
        email=email,
        full_name="Quản Trị Viên Hệ Thống",
        hashed_password=get_password_hash("Password123!"),
        role_id=admin_role.id,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserProfile(user_id=user.id))
    db_session.add(Cart(user_id=user.id))
    db_session.commit()

    login = client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return user, {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_product(
    db_session,
    name: str,
    slug: str,
    price: str,
    stock: int = 10,
    weight: float = 1.0,
    category_slug: str = "decor",
    category_name: str = "Trang Trí",
) -> Product:
    cat = get_or_create_category(db_session, category_name, category_slug)
    prod = Product(
        category_id=cat.id,
        name=name,
        slug=slug,
        price=Decimal(price),
        stock_quantity=stock,
        weight=Decimal(str(weight)),
        status=ProductStatus.ACTIVE,
        is_active=True,
    )
    db_session.add(prod)
    db_session.flush()
    db_session.add(ProductImage(product_id=prod.id, image_url="/storage/products/item.jpg", is_primary=True, sort_order=0))
    db_session.commit()
    return prod


def make_checkout_payload(
    name="Nguyễn Văn A",
    phone="0987654321",
    province="Thành phố Đà Nẵng",
    ward="Phường Điện Bàn Đông",
    street="123 Đường Trần Phú",
    notes="Giao giờ hành chính",
    idemp_key="idemp_key_001",
):
    return {
        "recipient_name": name,
        "recipient_phone": phone,
        "province": province,
        "ward": ward,
        "street_address": street,
        "delivery_notes": notes,
        "payment_method": "COD",
        "idempotency_key": idemp_key,
    }


def test_scenario_a_standard_product_order(client, db_session):
    """Scenario A: Standard product order -> shipping calculated 30k, total = subtotal + 30k."""
    user, headers = create_customer(client, db_session, "customer_a@example.com")
    vase = create_product(db_session, "Bình Hoa Gốm Sứ", "binh-hoa-gom-su", "450000.00", stock=10, weight=1.5, category_slug="decor", category_name="Trang Trí")

    # Add 2 items
    res_add = client.post("/api/cart/items", json={"product_id": vase.id, "quantity": 2}, headers=headers)
    assert res_add.status_code == 201

    payload = make_checkout_payload(idemp_key="idemp_a_001")
    res = client.post("/api/orders", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["status"] == "PENDING"
    assert data["subtotal_amount"] == "900000.00"
    assert data["shipping_fee"] == "30000.00"
    assert data["shipping_fee_status"] == "CALCULATED"
    assert data["total_amount"] == "930000.00"
    assert data["payment_method"] == "COD"
    assert data["payment_status"] == "UNPAID"


def test_scenario_b_bulky_product_order_pending_shipping(client, db_session):
    """Scenario B: Bulky product order with pending shipping quotation (Modern Modular Sofa)."""
    user, headers = create_customer(client, db_session, "customer_b@example.com")
    sofa = create_product(
        db_session,
        "Modern Modular Sofa",
        "modern-modular-sofa-b",
        "12500000.00",
        stock=5,
        weight=45.0,
        category_slug="sofa",
        category_name="Sofa",
    )

    client.post("/api/cart/items", json={"product_id": sofa.id, "quantity": 1}, headers=headers)

    # Shipping preview must show pending
    preview = client.get("/api/orders/shipping-preview", headers=headers).json()
    assert preview["is_bulky"] is True
    assert preview["shipping_fee_status"] == "PENDING_CALCULATION"
    assert preview["shipping_fee"] is None
    assert preview["total_amount"] is None

    # Checkout bulky order
    payload = make_checkout_payload(
        province="Thành phố Đà Nẵng",
        ward="Phường Điện Bàn Đông",
        idemp_key="idemp_b_001",
    )
    res = client.post("/api/orders", json=payload, headers=headers)
    assert res.status_code == 201
    order = res.json()

    assert order["status"] == "PENDING"
    assert order["subtotal_amount"] == "12500000.00"
    assert order["shipping_fee"] is None
    assert order["shipping_fee_status"] == "PENDING_CALCULATION"
    assert order["total_amount"] is None, "Bulky order with pending shipping MUST have total_amount as None"
    assert order["payment_method"] == "COD"


def test_scenario_c_and_d_order_serialization_and_null_preservation(client, db_session):
    """Scenario C & D: Existing order with non-null total and new order with null total."""
    user, headers = create_customer(client, db_session, "customer_cd@example.com")
    vase = create_product(db_session, "Tranh Treo Tường", "tranh-treo-tuong-cd", "600000.00", stock=10, weight=1.0, category_slug="decor", category_name="Trang Trí")
    sofa = create_product(db_session, "Sofa Băng Da", "sofa-bang-da-cd", "15000000.00", stock=5, weight=40.0, category_slug="sofa", category_name="Sofa")

    # Order 1: Non-bulky with total
    client.post("/api/cart/items", json={"product_id": vase.id, "quantity": 1}, headers=headers)
    res1 = client.post("/api/orders", json=make_checkout_payload(idemp_key="idemp_cd_1"), headers=headers)
    assert res1.status_code == 201
    order1 = res1.json()

    # Scenario C assertion: exact numeric total preserved
    assert order1["subtotal_amount"] == "600000.00"
    assert order1["shipping_fee"] == "30000.00"
    assert order1["total_amount"] == "630000.00"

    # Order 2: Bulky with null total
    client.post("/api/cart/items", json={"product_id": sofa.id, "quantity": 1}, headers=headers)
    res2 = client.post("/api/orders", json=make_checkout_payload(idemp_key="idemp_cd_2"), headers=headers)
    assert res2.status_code == 201
    order2 = res2.json()

    # Scenario D assertion: total_amount is strictly None, not '0' or '0.00'
    assert order2["subtotal_amount"] == "15000000.00"
    assert order2["shipping_fee"] is None
    assert order2["shipping_fee_status"] == "PENDING_CALCULATION"
    assert order2["total_amount"] is None


def test_scenario_e_customer_order_history_handles_both(client, db_session):
    """Scenario E: Customer API GET /api/orders and GET /api/orders/{id} serialize both correctly."""
    user, headers = create_customer(client, db_session, "customer_e@example.com")
    item = create_product(db_session, "Đèn Bàn Gỗ", "den-ban-go-e", "350000.00", stock=10, weight=1.0, category_slug="decor", category_name="Trang Trí")
    sofa = create_product(db_session, "Sofa L-Shape", "sofa-l-shape-e", "18000000.00", stock=5, weight=55.0, category_slug="sofa", category_name="Sofa")

    # Create Order 1 (standard)
    client.post("/api/cart/items", json={"product_id": item.id, "quantity": 1}, headers=headers)
    res1 = client.post("/api/orders", json=make_checkout_payload(idemp_key="idemp_e_1"), headers=headers)
    id1 = res1.json()["id"]

    # Create Order 2 (bulky)
    client.post("/api/cart/items", json={"product_id": sofa.id, "quantity": 1}, headers=headers)
    res2 = client.post("/api/orders", json=make_checkout_payload(idemp_key="idemp_e_2"), headers=headers)
    id2 = res2.json()["id"]

    # List orders for customer
    list_res = client.get("/api/orders", headers=headers)
    assert list_res.status_code == 200
    orders_list = list_res.json()["items"]
    assert len(orders_list) >= 2

    order1_found = next(o for o in orders_list if o["id"] == id1)
    order2_found = next(o for o in orders_list if o["id"] == id2)

    assert order1_found["total_amount"] == "380000.00"
    assert order2_found["total_amount"] is None

    # Detail GETs
    get1 = client.get(f"/api/orders/{id1}", headers=headers)
    assert get1.status_code == 200
    assert get1.json()["total_amount"] == "380000.00"

    get2 = client.get(f"/api/orders/{id2}", headers=headers)
    assert get2.status_code == 200
    assert get2.json()["total_amount"] is None


def test_scenario_f_admin_order_display_with_pending_total(client, db_session):
    """Scenario F: Admin API GET /api/admin/orders displays bulky order with pending total."""
    admin_user, admin_headers = create_admin(client, db_session, "admin_f@example.com")
    cust, cust_headers = create_customer(client, db_session, "customer_f@example.com")

    sofa = create_product(db_session, "Sofa Vải Nỉ", "sofa-vai-ni-f", "11000000.00", stock=5, weight=42.0, category_slug="sofa", category_name="Sofa")
    client.post("/api/cart/items", json={"product_id": sofa.id, "quantity": 1}, headers=cust_headers)
    res_order = client.post("/api/orders", json=make_checkout_payload(name="Khách Hàng F", idemp_key="idemp_f_1"), headers=cust_headers)
    order_id = res_order.json()["id"]

    # Admin list
    admin_list = client.get("/api/admin/orders", headers=admin_headers)
    assert admin_list.status_code == 200
    orders = admin_list.json()["items"]
    admin_order = next(o for o in orders if o["id"] == order_id)
    assert admin_order["recipient_name"] == "Khách Hàng F"
    assert admin_order["shipping_fee_status"] == "PENDING_CALCULATION"
    assert admin_order["total_amount"] is None

    # Admin detail
    admin_detail = client.get(f"/api/admin/orders/{order_id}", headers=admin_headers)
    assert admin_detail.status_code == 200
    assert admin_detail.json()["total_amount"] is None


def test_scenario_g_shipping_quotation_and_customer_confirmation(client, db_session):
    """Scenario G: Shipping quotation assignment & final total calculation lifecycle."""
    admin_user, admin_headers = create_admin(client, db_session, "admin_g@example.com")
    cust, cust_headers = create_customer(client, db_session, "customer_g@example.com")

    sofa = create_product(db_session, "Modern Modular Sofa G", "sofa-modular-g", "12500000.00", stock=5, weight=45.0, category_slug="sofa", category_name="Sofa")
    client.post("/api/cart/items", json={"product_id": sofa.id, "quantity": 1}, headers=cust_headers)
    res_order = client.post("/api/orders", json=make_checkout_payload(idemp_key="idemp_g_1"), headers=cust_headers)
    order_id = res_order.json()["id"]

    # 1. Admin assigns quotation: 250,000 VND via PATCH
    quote_res = client.patch(
        f"/api/admin/orders/{order_id}/shipping-fee",
        json={"shipping_fee": "250000.00"},
        headers=admin_headers,
    )
    assert quote_res.status_code == 200
    quoted_order = quote_res.json()
    assert quoted_order["shipping_fee_status"] == "AWAITING_CUSTOMER_CONFIRMATION"
    assert quoted_order["shipping_fee"] == "250000.00"
    assert quoted_order["subtotal_amount"] == "12500000.00"
    assert quoted_order["total_amount"] == "12750000.00"

    # 2. Customer confirms the quotation via POST
    confirm_res = client.post(
        f"/api/orders/{order_id}/confirm-shipping-fee",
        headers=cust_headers,
    )
    assert confirm_res.status_code == 200
    confirmed_order = confirm_res.json()
    assert confirmed_order["shipping_fee_status"] == "CUSTOMER_CONFIRMED"
    assert confirmed_order["shipping_fee"] == "250000.00"
    assert confirmed_order["total_amount"] == "12750000.00"


def test_scenario_h_cart_preservation_on_failed_checkout(client, db_session):
    """Scenario H: Cart preservation on failed checkout (invalid phone validation error)."""
    user, headers = create_customer(client, db_session, "customer_h@example.com")
    vase = create_product(db_session, "Đồng Hồ Cổ Điển", "dong-ho-co-dien-h", "750000.00", stock=10, category_slug="decor", category_name="Trang Trí")

    # Add 2 units to cart
    client.post("/api/cart/items", json={"product_id": vase.id, "quantity": 2}, headers=headers)
    cart_before = client.get("/api/cart", headers=headers).json()
    assert len(cart_before["items"]) == 1
    assert cart_before["items"][0]["quantity"] == 2

    # Attempt checkout with invalid phone
    bad_payload = make_checkout_payload(phone="0123", idemp_key="idemp_h_fail")
    res = client.post("/api/orders", json=bad_payload, headers=headers)
    assert res.status_code == 422

    # Assert cart is 100% preserved
    cart_after = client.get("/api/cart", headers=headers).json()
    assert len(cart_after["items"]) == 1
    assert cart_after["items"][0]["quantity"] == 2
    assert cart_after["items"][0]["product"]["id"] == vase.id


def test_scenario_i_stock_deduction_and_rollback(client, db_session):
    """Scenario I: Stock deduction on success and rollback on failure."""
    user, headers = create_customer(client, db_session, "customer_i@example.com")
    item = create_product(db_session, "Gối Tựa Sofa Cao Cấp", "goi-tua-sofa-i", "200000.00", stock=5, category_slug="decor", category_name="Trang Trí")

    # 1. Successful checkout for 2 units
    client.post("/api/cart/items", json={"product_id": item.id, "quantity": 2}, headers=headers)
    res_success = client.post("/api/orders", json=make_checkout_payload(idemp_key="idemp_i_1"), headers=headers)
    assert res_success.status_code == 201

    # Stock should be decremented from 5 to 3
    db_session.rollback()
    assert db_session.get(Product, item.id).stock_quantity == 3

    # 2. Attempt checkout for 4 units (only 3 in stock)
    # Add to cart directly through DB or cart endpoint
    res_add_exceed = client.post("/api/cart/items", json={"product_id": item.id, "quantity": 4}, headers=headers)
    assert res_add_exceed.status_code == 400
    assert "exceeds available stock" in res_add_exceed.json()["detail"].lower() or "stock" in res_add_exceed.json()["detail"].lower()

    # Stock must remain strictly 3
    db_session.rollback()
    assert db_session.get(Product, item.id).stock_quantity == 3


def test_scenario_j_duplicate_order_submission_protection(client, db_session):
    """Scenario J: Rapid duplicate submit protection (cart is emptied upon first success)."""
    user, headers = create_customer(client, db_session, "customer_j@example.com")
    item = create_product(db_session, "Thảm Lông Cừu", "tham-long-cuu-j", "1500000.00", stock=10, category_slug="decor", category_name="Trang Trí")

    # Add item
    client.post("/api/cart/items", json={"product_id": item.id, "quantity": 1}, headers=headers)

    payload = make_checkout_payload(idemp_key="idemp_j_duplicate")

    # Request 1: succeeds
    res1 = client.post("/api/orders", json=payload, headers=headers)
    assert res1.status_code == 201

    # Request 2: duplicate rapid submit immediately fails because cart has been emptied
    res2 = client.post("/api/orders", json=payload, headers=headers)
    assert res2.status_code == 400
    assert "Cart is empty" in res2.json()["detail"]
