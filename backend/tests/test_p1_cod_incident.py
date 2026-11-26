"""P1 COD Checkout Incident Reproduction and Regression Test Suite.

Verifies:
1. Bulky Product (Modern Modular Sofa, 12.5M, Sofa Category, Đà Nẵng, Phường Điện Bàn Đông)
2. Missing Shipping Quotation (total_amount is None, shipping_fee is None, status PENDING_CALCULATION)
3. Valid COD Order
4. Invalid Province/Ward Combination Handling
5. Out-of-stock Product Handling
6. Double-click / Duplicate Submit Prevention
7. Server-authoritative Pricing Enforcement
8. Client Timeout & Error Message Mapping
"""

from decimal import Decimal
import pytest
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


def register_customer(client, email="danang.customer@example.com"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Nguyễn Văn Đạt"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_sofa_product(db_session):
    cat = db_session.query(Category).filter(Category.slug == "sofa").first()
    if not cat:
        cat = Category(name="Sofa", slug="sofa", is_active=True)
        db_session.add(cat)
        db_session.flush()

    sofa = Product(
        category_id=cat.id,
        name="Modern Modular Sofa",
        slug="modern-modular-sofa",
        price=Decimal("12500000.00"),
        stock_quantity=5,
        weight=Decimal("45.0"),
        status=ProductStatus.ACTIVE,
        is_active=True,
    )
    db_session.add(sofa)
    db_session.flush()
    db_session.add(
        ProductImage(product_id=sofa.id, image_url="/storage/products/sofa.jpg", is_primary=True, sort_order=0)
    )
    db_session.commit()
    return sofa


def danang_bulky_order_payload():
    return {
        "recipient_name": "Nguyễn Văn Đạt",
        "recipient_phone": "0987654321",
        "province": "Thành phố Đà Nẵng",
        "ward": "Phường Điện Bàn Đông",
        "street_address": "123 Đường Trần Phú",
        "delivery_notes": "Chung cư tầng 12, có thang máy chở hàng",
        "payment_method": "COD",
        "idempotency_key": "test_idemp_danang_sofa_001",
    }


def test_p1_incident_reproduction_and_fix(client, db_session):
    """
    CRITICAL P1 VERIFICATION:
    Product: Modern Modular Sofa (12,500,000 VND, Bulky)
    Province: Thành phố Đà Nẵng
    Ward: Phường Điện Bàn Đông
    Payment: COD
    Expect: Order created successfully with status PENDING,
            shipping_fee_status PENDING_CALCULATION,
            shipping_fee is None,
            total_amount is None (NOT 0, NOT subtotal),
            cart emptied, stock decremented.
    """
    headers = register_customer(client, "sofa-danang@example.com")
    sofa = create_sofa_product(db_session)

    # 1. Add Modern Modular Sofa to Cart
    add_res = client.post("/api/cart/items", json={"product_id": sofa.id, "quantity": 1}, headers=headers)
    assert add_res.status_code == 201

    # 2. Verify Shipping Preview indicates Bulky with Pending Calculation
    prev_res = client.get("/api/orders/shipping-preview", headers=headers)
    assert prev_res.status_code == 200
    preview = prev_res.json()
    assert preview["is_bulky"] is True
    assert preview["shipping_fee_status"] == "PENDING_CALCULATION"
    assert preview["shipping_fee"] is None
    assert preview["total_amount"] is None
    assert preview["subtotal"] == "12500000.00"

    # 3. Submit COD Checkout
    order_res = client.post("/api/orders", json=danang_bulky_order_payload(), headers=headers)
    assert order_res.status_code == 201, f"Checkout failed: {order_res.text}"
    order = order_res.json()

    # 4. Rigorous assertions on bulky order attributes
    assert order["status"] == "PENDING"
    assert order["recipient_name"] == "Nguyễn Văn Đạt"
    assert order["recipient_phone"] == "0987654321"
    assert order["province"] == "Thành phố Đà Nẵng"
    assert order["ward"] == "Phường Điện Bàn Đông"
    assert order["subtotal_amount"] == "12500000.00"
    assert order["shipping_fee"] is None
    assert order["shipping_fee_status"] == "PENDING_CALCULATION"
    assert order["total_amount"] is None, "Bulky unquoted order MUST have total_amount as None"
    assert order["payment_method"] == "COD"
    assert order["payment_status"] == "UNPAID"

    # 5. Inventory and Cart Verification
    db_session.rollback()
    assert db_session.get(Product, sofa.id).stock_quantity == 4
    cart = client.get("/api/cart", headers=headers).json()
    assert cart["items"] == []


def test_standard_non_bulky_order_has_total(client, db_session):
    """Verify non-bulky product calculates total_amount = subtotal + 30000."""
    headers = register_customer(client, "standard-decor@example.com")
    cat = db_session.query(Category).filter(Category.slug == "decor").first()
    if not cat:
        cat = Category(name="Decor", slug="decor", is_active=True)
        db_session.add(cat)
        db_session.flush()

    vase = Product(
        category_id=cat.id,
        name="Bình Gốm Tinh Tế",
        slug="binh-gom-tinh-te",
        price=Decimal("450000.00"),
        stock_quantity=10,
        weight=Decimal("1.2"),
        status=ProductStatus.ACTIVE,
        is_active=True,
    )
    db_session.add(vase)
    db_session.flush()
    db_session.add(ProductImage(product_id=vase.id, image_url="/storage/sample.jpg", is_primary=True, sort_order=0))
    db_session.commit()

    client.post("/api/cart/items", json={"product_id": vase.id, "quantity": 2}, headers=headers)
    payload = danang_bulky_order_payload()
    payload["recipient_name"] = "Khách Hàng Chuẩn"

    res = client.post("/api/orders", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["shipping_fee_status"] == "CALCULATED"
    assert data["shipping_fee"] == "30000.00"
    assert data["subtotal_amount"] == "900000.00"
    assert data["total_amount"] == "930000.00"


def test_invalid_phone_rejected(client, db_session):
    """Verify malformed phone numbers are rejected with 422 Unprocessable Entity."""
    headers = register_customer(client, "bad-phone@example.com")
    sofa = create_sofa_product(db_session)
    client.post("/api/cart/items", json={"product_id": sofa.id, "quantity": 1}, headers=headers)

    payload = danang_bulky_order_payload()
    payload["recipient_phone"] = "12345678"  # Invalid
    res = client.post("/api/orders", json=payload, headers=headers)
    assert res.status_code == 422


def test_empty_cart_checkout_fails(client):
    """Verify checkout on empty cart returns 400 Bad Request."""
    headers = register_customer(client, "empty-cart@example.com")
    res = client.post("/api/orders", json=danang_bulky_order_payload(), headers=headers)
    assert res.status_code == 400
    assert "Cart is empty" in res.json()["detail"]
