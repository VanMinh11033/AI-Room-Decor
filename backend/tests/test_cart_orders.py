from decimal import Decimal

from app.core.security import get_password_hash
from app.models.entities import (
    Cart,
    Category,
    Order,
    OrderItem,
    Product,
    ProductImage,
    ProductStatus,
    Role,
    RoleName,
    RoomDesignGeneration,
    RoomProject,
    User,
    UserProfile,
)


def register(client, email):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Test Customer"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def admin_headers(client, db_session, email="orders-admin@example.com"):
    admin_role = db_session.query(Role).filter(Role.name == RoleName.ADMIN).one()
    admin = User(
        email=email,
        full_name="Orders Admin",
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


def make_product(db_session, name="Oak Lamp", slug="oak-lamp", price="129.99", stock=10, active=True):
    category = db_session.query(Category).first()
    if category is None:
        category = Category(name="Lighting", slug="lighting", is_active=True)
        db_session.add(category)
        db_session.flush()
    product = Product(
        category_id=category.id,
        name=name,
        slug=slug,
        price=Decimal(price),
        stock_quantity=stock,
        status=ProductStatus.ACTIVE if active else ProductStatus.INACTIVE,
        is_active=active,
    )
    db_session.add(product)
    db_session.flush()
    db_session.add(ProductImage(product_id=product.id, image_url="/storage/products/sample.jpg", is_primary=True, sort_order=0))
    db_session.commit()
    return product


def test_add_item_and_duplicate_increments_quantity(client, db_session):
    headers = register(client, "cart-user@example.com")
    product = make_product(db_session, "Oak Lamp", "cart-lamp", "100.00", stock=10)

    first = client.post("/api/cart/items", json={"product_id": product.id, "quantity": 2}, headers=headers)
    assert first.status_code == 201
    assert first.json()["total_items"] == 2
    assert len(first.json()["items"]) == 1
    assert first.json()["items"][0]["quantity"] == 2
    assert first.json()["items"][0]["unit_price"] == "100.00"

    second = client.post("/api/cart/items", json={"product_id": product.id, "quantity": 3}, headers=headers)
    assert second.status_code == 201
    assert second.json()["items"][0]["quantity"] == 5
    assert second.json()["total_items"] == 5


def test_add_item_respects_stock_limit(client, db_session):
    headers = register(client, "stock-user@example.com")
    product = make_product(db_session, "Sofa", "stock-sofa", "500.00", stock=3)

    over = client.post("/api/cart/items", json={"product_id": product.id, "quantity": 4}, headers=headers)
    assert over.status_code == 400

    ok = client.post("/api/cart/items", json={"product_id": product.id, "quantity": 2}, headers=headers)
    assert ok.status_code == 201

    exceeded = client.post("/api/cart/items", json={"product_id": product.id, "quantity": 2}, headers=headers)
    assert exceeded.status_code == 400


def test_inactive_product_rejected(client, db_session):
    headers = register(client, "inactive-cart@example.com")
    product = make_product(db_session, "Hidden Lamp", "inactive-lamp", "10.00", stock=10, active=False)
    response = client.post("/api/cart/items", json={"product_id": product.id, "quantity": 1}, headers=headers)
    assert response.status_code == 400


def test_cart_update_remove_clear_and_ownership(client, db_session):
    owner = register(client, "owner-cart@example.com")
    other = register(client, "other-cart@example.com")
    product = make_product(db_session, "Chair", "owner-chair", "50.00", stock=10)

    added = client.post("/api/cart/items", json={"product_id": product.id, "quantity": 2}, headers=owner)
    item_id = added.json()["items"][0]["id"]

    blocked_update = client.patch(f"/api/cart/items/{item_id}", json={"quantity": 5}, headers=other)
    assert blocked_update.status_code == 404
    blocked_remove = client.delete(f"/api/cart/items/{item_id}", headers=other)
    assert blocked_remove.status_code == 404

    updated = client.patch(f"/api/cart/items/{item_id}", json={"quantity": 4}, headers=owner)
    assert updated.status_code == 200
    assert updated.json()["items"][0]["quantity"] == 4

    removed = client.delete(f"/api/cart/items/{item_id}", headers=owner)
    assert removed.status_code == 200
    assert removed.json()["items"] == []

    client.post("/api/cart/items", json={"product_id": product.id, "quantity": 1}, headers=owner)
    cleared = client.delete("/api/cart", headers=owner)
    assert cleared.status_code == 200
    assert cleared.json()["items"] == []
    assert cleared.json()["total_items"] == 0


def test_checkout_uses_db_price_decrements_stock_clears_cart(client, db_session):
    headers = register(client, "checkout-user@example.com")
    product = make_product(db_session, "Oak Lamp", "checkout-lamp", "200.00", stock=5)
    client.post("/api/cart/items", json={"product_id": product.id, "quantity": 2}, headers=headers)

    db_session.query(Product).filter(Product.id == product.id).update({"price": Decimal("250.00")})
    db_session.commit()

    response = client.post("/api/orders", json={"shipping_address": "123 Main St"}, headers=headers)
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "PENDING"
    assert order["total_amount"] == "500.00"
    assert order["items"][0]["unit_price"] == "250.00"
    assert order["items"][0]["quantity"] == 2

    db_session.rollback()
    assert db_session.get(Product, product.id).stock_quantity == 3

    cart = client.get("/api/cart", headers=headers)
    assert cart.json()["items"] == []


def test_checkout_insufficient_stock_rolls_back(client, db_session):
    headers = register(client, "insufficient@example.com")
    product = make_product(db_session, "Oak Lamp", "insufficient-lamp", "100.00", stock=2)
    client.post("/api/cart/items", json={"product_id": product.id, "quantity": 2}, headers=headers)

    db_session.query(Product).filter(Product.id == product.id).update({"stock_quantity": 1})
    db_session.commit()

    response = client.post("/api/orders", json={}, headers=headers)
    assert response.status_code == 400

    db_session.rollback()
    assert db_session.query(Order).count() == 0
    assert db_session.query(OrderItem).count() == 0
    assert db_session.get(Product, product.id).stock_quantity == 1

    cart = client.get("/api/cart", headers=headers)
    assert cart.json()["items"][0]["quantity"] == 2


def test_checkout_empty_cart_rejected(client, db_session):
    headers = register(client, "empty-cart@example.com")
    response = client.post("/api/orders", json={}, headers=headers)
    assert response.status_code == 400


def test_own_order_history_detail_and_cross_user_protection(client, db_session):
    owner = register(client, "order-owner@example.com")
    other = register(client, "order-other@example.com")
    product = make_product(db_session, "Oak Lamp", "history-lamp", "100.00", stock=10)

    client.post("/api/cart/items", json={"product_id": product.id, "quantity": 1}, headers=owner)
    created = client.post("/api/orders", json={}, headers=owner)
    assert created.status_code == 201
    order_id = created.json()["id"]

    history = client.get("/api/orders", headers=owner)
    assert history.status_code == 200
    assert history.json()["total"] == 1

    detail = client.get(f"/api/orders/{order_id}", headers=owner)
    assert detail.status_code == 200
    assert detail.json()["id"] == order_id

    assert client.get("/api/orders", headers=other).json()["total"] == 0
    assert client.get(f"/api/orders/{order_id}", headers=other).status_code == 404


def test_cancel_order_restores_stock(client, db_session):
    headers = register(client, "cancel-user@example.com")
    product = make_product(db_session, "Oak Lamp", "cancel-lamp", "100.00", stock=5)
    client.post("/api/cart/items", json={"product_id": product.id, "quantity": 2}, headers=headers)
    order = client.post("/api/orders", json={}, headers=headers).json()

    db_session.rollback()
    assert db_session.get(Product, product.id).stock_quantity == 3

    cancelled = client.post(f"/api/orders/{order['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    db_session.rollback()
    assert db_session.get(Product, product.id).stock_quantity == 5

    again = client.post(f"/api/orders/{order['id']}/cancel", headers=headers)
    assert again.status_code == 400


def test_admin_orders_and_customer_blocked(client, db_session):
    customer = register(client, "blocked-customer@example.com")
    admin = admin_headers(client, db_session)
    product = make_product(db_session, "Oak Lamp", "admin-lamp", "100.00", stock=10)

    client.post("/api/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
    order = client.post("/api/orders", json={}, headers=customer).json()

    assert client.get("/api/admin/orders", headers=customer).status_code == 403
    assert client.get(f"/api/admin/orders/{order['id']}", headers=customer).status_code == 403
    assert client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "CONFIRMED"}, headers=customer).status_code == 403

    listing = client.get("/api/admin/orders", headers=admin)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    detail = client.get(f"/api/admin/orders/{order['id']}", headers=admin)
    assert detail.status_code == 200
    assert detail.json()["id"] == order["id"]

    updated = client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "CONFIRMED"}, headers=admin)
    assert updated.status_code == 200
    assert updated.json()["status"] == "CONFIRMED"

    invalid = client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "BOGUS"}, headers=admin)
    assert invalid.status_code == 422


def test_design_generation_real_product_ids_add_to_cart(client, db_session):
    headers = register(client, "design-cart@example.com")
    user = db_session.query(User).filter(User.email == "design-cart@example.com").one()
    lamp = make_product(db_session, "Japandi Lamp", "design-lamp", "250.00", stock=10)
    sofa = make_product(db_session, "Japandi Sofa", "design-sofa", "900.00", stock=10)

    project = RoomProject(user_id=user.id, title="Test Room", status="COMPLETED")
    db_session.add(project)
    db_session.flush()
    generation = RoomDesignGeneration(
        room_project_id=project.id,
        user_id=user.id,
        status="COMPLETED",
        provider="fake",
        model="fake",
        source_image_path="/storage/rooms/source.png",
        products=[lamp, sofa],
    )
    db_session.add(generation)
    db_session.commit()

    db_session.refresh(generation)
    product_ids = [product.id for product in generation.products]
    assert lamp.id in product_ids
    assert sofa.id in product_ids

    for product_id in product_ids:
        response = client.post("/api/cart/items", json={"product_id": product_id, "quantity": 1}, headers=headers)
        assert response.status_code == 201

    cart = client.get("/api/cart", headers=headers)
    assert cart.json()["total_items"] == 2
    assert {item["product_id"] for item in cart.json()["items"]} == {lamp.id, sofa.id}
