from app.core.security import get_password_hash
from app.models.entities import Cart, Role, RoleName, User, UserProfile


def admin_headers(client, db_session, email="catalog-admin@example.com"):
    admin_role = db_session.query(Role).filter(Role.name == RoleName.ADMIN).one()
    admin = User(
        email=email,
        full_name="Catalog Admin",
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


def customer_headers(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "customer-catalog@example.com", "password": "Password123!", "full_name": "Customer"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_lookup(client, headers, path, name, slug, extra=None):
    payload = {"name": name, "slug": slug, "is_active": True, **(extra or {})}
    response = client.post(path, json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def seed_product_dependencies(client, headers):
    category = create_lookup(client, headers, "/api/admin/categories", "Lighting", "lighting")
    material = create_lookup(client, headers, "/api/admin/materials", "Wood", "wood")
    style = create_lookup(client, headers, "/api/admin/styles", "Japandi", "japandi")
    room_type = create_lookup(client, headers, "/api/admin/room-types", "Bedroom", "bedroom")
    color = create_lookup(client, headers, "/api/admin/colors", "Oak", "oak", {"hex_code": "#b8895b"})
    return category, material, style, room_type, color


def product_payload(category, material, style, room_type, color, slug="oak-floor-lamp"):
    return {
        "category_id": category["id"],
        "name": "Oak Floor Lamp",
        "slug": slug,
        "description": "Warm lamp for bedroom decor",
        "price": "129.99",
        "stock_quantity": 10,
        "width": "30.00",
        "height": "160.00",
        "depth": "30.00",
        "weight": "4.50",
        "tags": "lamp, oak, warm",
        "status": "ACTIVE",
        "is_active": True,
        "material_ids": [material["id"]],
        "style_ids": [style["id"]],
        "room_type_ids": [room_type["id"]],
        "color_ids": [color["id"]],
        "images": [{"image_url": "/storage/products/sample.jpg", "alt_text": "Lamp", "sort_order": 0, "is_primary": True}],
    }


def test_lookup_crud_for_material_style_room_type_color(client, db_session):
    headers = admin_headers(client, db_session)
    cases = [
        ("/api/materials", "/api/admin/materials", {"name": "Metal", "slug": "metal", "is_active": True}),
        ("/api/styles", "/api/admin/styles", {"name": "Modern", "slug": "modern", "is_active": True}),
        ("/api/room-types", "/api/admin/room-types", {"name": "Living Room", "slug": "living-room", "is_active": True}),
        ("/api/colors", "/api/admin/colors", {"name": "Black", "slug": "black", "hex_code": "#111111", "is_active": True}),
    ]
    for public_path, admin_path, payload in cases:
        created = client.post(admin_path, json=payload, headers=headers)
        assert created.status_code == 201
        updated = client.put(f"{admin_path}/{created.json()['id']}", json={"name": f"{payload['name']} Updated"}, headers=headers)
        assert updated.status_code == 200
        listed = client.get(public_path)
        assert listed.status_code == 200
        assert listed.json()["total"] == 1
        deleted = client.delete(f"{admin_path}/{created.json()['id']}", headers=headers)
        assert deleted.status_code == 200


def test_category_crud(client, db_session):
    headers = admin_headers(client, db_session)
    create = client.post(
        "/api/admin/categories",
        json={"name": "Sofa", "slug": "sofa", "description": "Sofa decor", "is_active": True},
        headers=headers,
    )
    assert create.status_code == 201
    category_id = create.json()["id"]
    admin_list = client.get("/api/admin/categories", headers=headers)
    assert admin_list.status_code == 200
    update = client.put(f"/api/admin/categories/{category_id}", json={"description": "Updated"}, headers=headers)
    assert update.status_code == 200
    assert update.json()["description"] == "Updated"
    delete = client.delete(f"/api/admin/categories/{category_id}", headers=headers)
    assert delete.status_code == 200


def test_product_crud_filtering_pagination_and_image_upload(client, db_session):
    headers = admin_headers(client, db_session)
    category, material, style, room_type, color = seed_product_dependencies(client, headers)

    create = client.post("/api/admin/products", json=product_payload(category, material, style, room_type, color), headers=headers)
    assert create.status_code == 201
    product_id = create.json()["id"]
    assert create.json()["materials"][0]["slug"] == "wood"

    second_payload = product_payload(category, material, style, room_type, color, "oak-table-lamp")
    second_payload["name"] = "Oak Table Lamp"
    client.post("/api/admin/products", json=second_payload, headers=headers)

    filtered = client.get("/api/products?style=japandi&material=wood&room_type=bedroom&color=oak&max_price=200&page=1&page_size=1&sort=price_asc")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 2
    assert len(filtered.json()["items"]) == 1

    image_response = client.post(
        f"/api/admin/products/{product_id}/images",
        headers=headers,
        files={"file": ("lamp.png", b"fakepng", "image/png")},
        data={"is_primary": "true", "alt_text": "Uploaded lamp"},
    )
    assert image_response.status_code == 200
    assert any(item["is_primary"] for item in image_response.json()["images"])

    update = client.put(f"/api/admin/products/{product_id}", json={"stock_quantity": 8, "price": "119.99", "status": "INACTIVE"}, headers=headers)
    assert update.status_code == 200
    assert update.json()["stock_quantity"] == 8
    assert update.json()["is_active"] is False

    delete = client.delete(f"/api/admin/products/{product_id}", headers=headers)
    assert delete.status_code == 200


def test_admin_authorization_and_invalid_input(client, db_session):
    customer = customer_headers(client)
    blocked = client.post("/api/admin/materials", json={"name": "Stone", "slug": "stone", "is_active": True}, headers=customer)
    assert blocked.status_code == 403

    headers = admin_headers(client, db_session, "invalid-admin@example.com")
    invalid = client.post(
        "/api/admin/products",
        json={"category_id": 999, "name": "Bad", "slug": "bad", "price": "-1", "stock_quantity": -2},
        headers=headers,
    )
    assert invalid.status_code in (400, 422)

