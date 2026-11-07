from decimal import Decimal

from app.core.security import get_password_hash
from app.models.entities import (
    AIUsageLog,
    Cart,
    Category,
    OrderStatus,
    Product,
    ProductImage,
    ProductStatus,
    Role,
    RoleName,
    RoomAnalysis,
    RoomDesignGeneration,
    RoomPreference,
    RoomProject,
    User,
    UserProfile,
)


def register_customer(client, email="admin-monitor-customer@example.com"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Customer Monitor"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_admin_headers(client, db_session, email="monitor-admin@example.com"):
    role = db_session.query(Role).filter(Role.name == RoleName.ADMIN).one()
    admin = User(
        email=email,
        full_name="Monitor Admin",
        hashed_password=get_password_hash("Password123!"),
        role_id=role.id,
    )
    db_session.add(admin)
    db_session.flush()
    db_session.add(UserProfile(user_id=admin.id))
    db_session.add(Cart(user_id=admin.id))
    db_session.commit()
    login = client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_product(db_session, name="Monitor Lamp", slug="monitor-lamp", price="100.00", stock=10):
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
        status=ProductStatus.ACTIVE,
        is_active=True,
    )
    db_session.add(product)
    db_session.flush()
    db_session.add(ProductImage(product_id=product.id, image_url="/storage/products/monitor.jpg", is_primary=True))
    db_session.commit()
    return product


def create_project_fixture(db_session, customer_email="project-owner@example.com"):
    slug_suffix = customer_email.split("@", 1)[0].replace(".", "-")
    role = db_session.query(Role).filter(Role.name == RoleName.CUSTOMER).one()
    user = User(
        email=customer_email,
        full_name="Project Owner",
        hashed_password=get_password_hash("Password123!"),
        role_id=role.id,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserProfile(user_id=user.id))
    db_session.add(Cart(user_id=user.id))
    project = RoomProject(
        user_id=user.id,
        title="Căn hộ demo",
        room_type="living room",
        room_image_url="/storage/rooms/demo.jpg",
        room_image_path="/storage/rooms/demo.jpg",
        image_checksum="abc123",
        status="COMPLETED",
    )
    db_session.add(project)
    db_session.flush()
    preference = RoomPreference(
        room_project_id=project.id,
        user_id=user.id,
        budget_min=Decimal("1000000"),
        budget_max=Decimal("5000000"),
        purpose="decor",
    )
    db_session.add(preference)
    analysis = RoomAnalysis(
        room_project_id=project.id,
        user_id=user.id,
        image_checksum="abc123",
        status="COMPLETED",
        provider="gemini",
        model="gemini-test",
        room_type="living room",
        dominant_colors=[{"name": "white", "hex": "#ffffff", "percentage": 60}],
        existing_objects=[{"name": "wall", "confidence": 0.9}],
        empty_areas=[{"location": "corner", "suitable_for_decor": True}],
        design_characteristics=["modern"],
        layout_summary="Open layout",
        confidence=Decimal("0.900"),
    )
    db_session.add(analysis)
    product = create_product(db_session, f"Project Lamp {slug_suffix}", f"project-lamp-{slug_suffix}")
    generation = RoomDesignGeneration(
        room_project_id=project.id,
        user_id=user.id,
        status="COMPLETED",
        provider="cloudflare",
        model="flux",
        source_image_path="/storage/rooms/demo.jpg",
        generated_image_url="/storage/generated-room-designs/demo.png",
        products=[product],
    )
    db_session.add(generation)
    db_session.add(
        AIUsageLog(
            user_id=user.id,
            room_project_id=project.id,
            provider="gemini",
            model="gemini-test",
            task_type="ROOM_IMAGE_ANALYSIS",
            status="SUCCESS",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            estimated_cost=Decimal("0.001000"),
        )
    )
    db_session.commit()
    return project


def test_admin_dashboard_stats_and_customer_blocked(client, db_session):
    customer_headers = register_customer(client, "dash-customer@example.com")
    admin_headers = create_admin_headers(client, db_session)
    product = create_product(db_session, "Dashboard Lamp", "dashboard-lamp")
    project_one = create_project_fixture(db_session, "dashboard-project-one@example.com")
    project_two = create_project_fixture(db_session, "dashboard-project-two@example.com")
    client.post("/api/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer_headers)
    order = client.post("/api/orders", json={"shipping_address": "Demo"}, headers=customer_headers).json()
    client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "COMPLETED"}, headers=admin_headers)

    assert client.get("/api/admin/dashboard", headers=customer_headers).status_code == 403
    response = client.get("/api/admin/dashboard", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["total_users"] >= 2
    assert payload["stats"]["total_products"] >= 1
    assert payload["stats"]["completed_orders"] == 1
    assert payload["stats"]["completed_order_revenue"] == "100.00"
    assert payload["recent_orders"][0]["customer"]["email"] == "dash-customer@example.com"
    recent_project_ids = {item["id"] for item in payload["recent_room_projects"]}
    assert {project_one.id, project_two.id}.issubset(recent_project_ids)
    assert "project" not in payload["recent_room_projects"][0]
    assert payload["recent_room_projects"][0]["customer"]["email"]
    assert payload["recent_room_projects"][0]["design_generation_count"] >= 1


def test_admin_users_list_detail_active_update_and_self_protection(client, db_session):
    customer_headers = register_customer(client, "users-customer@example.com")
    admin_headers = create_admin_headers(client, db_session, "users-admin@example.com")

    assert client.get("/api/admin/users", headers=customer_headers).status_code == 403
    users = client.get("/api/admin/users", headers=admin_headers)
    assert users.status_code == 200
    customer = next(item for item in users.json() if item["email"] == "users-customer@example.com")

    detail = client.get(f"/api/admin/users/{customer['id']}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["email"] == "users-customer@example.com"

    deactivated = client.patch(f"/api/admin/users/{customer['id']}/active", json={"is_active": False}, headers=admin_headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    admin = next(item for item in users.json() if item["email"] == "users-admin@example.com")
    blocked = client.patch(f"/api/admin/users/{admin['id']}/active", json={"is_active": False}, headers=admin_headers)
    assert blocked.status_code == 400


def test_admin_room_project_list_detail_and_customer_blocked(client, db_session):
    customer_headers = register_customer(client, "room-monitor-customer@example.com")
    admin_headers = create_admin_headers(client, db_session, "room-monitor-admin@example.com")
    project = create_project_fixture(db_session)

    assert client.get("/api/admin/room-projects", headers=customer_headers).status_code == 403
    listing = client.get("/api/admin/room-projects", headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    assert any(item["project"]["id"] == project.id for item in listing.json()["items"])

    detail = client.get(f"/api/admin/room-projects/{project.id}", headers=admin_headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["customer"]["email"] == "project-owner@example.com"
    assert payload["latest_analysis"]["status"] == "COMPLETED"
    assert payload["preference"]["budget_max"] == "5000000.00"
    assert len(payload["design_generations"]) == 1


def test_admin_ai_usage_list_summary_and_customer_blocked(client, db_session):
    customer_headers = register_customer(client, "ai-customer@example.com")
    admin_headers = create_admin_headers(client, db_session, "ai-admin@example.com")
    create_project_fixture(db_session, "ai-project-owner@example.com")

    assert client.get("/api/admin/ai-usage", headers=customer_headers).status_code == 403
    response = client.get("/api/admin/ai-usage", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_calls"] >= 1
    assert payload["summary"]["success_calls"] >= 1
    assert payload["summary"]["gemini_calls"] >= 1
    assert payload["summary"]["total_tokens"] >= 30
    assert payload["items"][0]["provider"]


def test_admin_order_customer_display_preserved(client, db_session):
    customer_headers = register_customer(client, "order-display@example.com")
    admin_headers = create_admin_headers(client, db_session, "order-display-admin@example.com")
    product = create_product(db_session, "Order Display Lamp", "order-display-lamp")
    client.post("/api/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer_headers)
    order = client.post("/api/orders", json={}, headers=customer_headers).json()

    response = client.get(f"/api/admin/orders/{order['id']}", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["customer"]["full_name"] == "Customer Monitor"
    assert payload["customer"]["email"] == "order-display@example.com"
    assert payload["items"][0]["product"]["name"] == "Order Display Lamp"
