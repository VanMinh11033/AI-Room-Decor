from decimal import Decimal

from app.models.entities import Category, Color, Material, Product, ProductImage, ProductStatus, RoomAnalysis, RoomPreference, RoomProject, RoomType, Style


def auth_headers(client, email="recommendation-user@example.com"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Recommendation User"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_project(client, headers):
    response = client.post("/api/room-projects", json={"title": "Recommendation Room", "room_type": "living-room"}, headers=headers)
    assert response.status_code == 201
    return response.json()


def create_catalog(db_session):
    living = RoomType(name="Living Room", slug="living-room", is_active=True)
    bedroom = RoomType(name="Bedroom", slug="bedroom", is_active=True)
    japandi = Style(name="Japandi", slug="japandi", is_active=True)
    industrial = Style(name="Industrial", slug="industrial", is_active=True)
    cream = Color(name="Cream", slug="cream", hex_code="#f2eadc", is_active=True)
    black = Color(name="Black", slug="black", hex_code="#111111", is_active=True)
    wood = Material(name="Wood", slug="wood", is_active=True)
    metal = Material(name="Metal", slug="metal", is_active=True)
    sofa = Category(name="Sofa", slug="sofa", is_active=True)
    lighting = Category(name="Lighting", slug="lighting", is_active=True)
    bedding = Category(name="Bedding", slug="bedding", is_active=True)
    db_session.add_all([living, bedroom, japandi, industrial, cream, black, wood, metal, sofa, lighting, bedding])
    db_session.commit()
    return {
        "living": living,
        "bedroom": bedroom,
        "japandi": japandi,
        "industrial": industrial,
        "cream": cream,
        "black": black,
        "wood": wood,
        "metal": metal,
        "sofa": sofa,
        "lighting": lighting,
        "bedding": bedding,
    }


def create_product(db_session, name, slug, category, price, styles, colors, materials, room_types, active=True, stock=10):
    product = Product(
        category_id=category.id,
        name=name,
        slug=slug,
        description=f"{name} real catalog product",
        price=Decimal(price),
        stock_quantity=stock,
        status=ProductStatus.ACTIVE if active else ProductStatus.INACTIVE,
        is_active=active,
        tags="decor, recommendation",
    )
    product.styles = styles
    product.colors = colors
    product.materials = materials
    product.room_types = room_types
    db_session.add(product)
    db_session.flush()
    db_session.add(ProductImage(product_id=product.id, image_url=f"/storage/products/{slug}.jpg", is_primary=True, sort_order=0))
    db_session.commit()
    return product


def create_analysis_and_preference(db_session, project, catalog, category_ids=None, budget_max="15000000"):
    analysis = RoomAnalysis(
        room_project_id=project["id"],
        user_id=project["user_id"],
        image_checksum="abc123",
        status="COMPLETED",
        provider="fake_test",
        model="fake-model",
        room_type="living-room",
        dominant_colors=[{"name": "Cream", "hex": "#f2eadc", "percentage": 60}],
        existing_objects=[],
        empty_areas=[],
        lighting={"type": "natural", "level": "medium"},
        design_characteristics=["minimal"],
        layout_summary="Living room analysis",
        confidence=Decimal("0.900"),
    )
    preference = RoomPreference(
        room_project_id=project["id"],
        user_id=project["user_id"],
        budget_min=Decimal("0"),
        budget_max=Decimal(budget_max) if budget_max is not None else None,
        currency="VND",
        purpose="relaxation",
        notes="Prefer warm minimal decor",
    )
    preference.styles = [catalog["japandi"]]
    preference.colors = [catalog["cream"]]
    preference.materials = [catalog["wood"]]
    preference.categories = [catalog["sofa"], catalog["lighting"]] if category_ids is None else [
        db_session.get(Category, category_id) for category_id in category_ids
    ]
    db_session.add_all([analysis, preference])
    db_session.commit()
    return analysis, preference


def setup_recommendation_case(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    catalog = create_catalog(db_session)
    best = create_product(
        db_session,
        "Japandi Cream Sofa",
        "japandi-cream-sofa",
        catalog["sofa"],
        "9000000",
        [catalog["japandi"]],
        [catalog["cream"]],
        [catalog["wood"]],
        [catalog["living"]],
    )
    lamp = create_product(
        db_session,
        "Japandi Floor Lamp",
        "japandi-floor-lamp",
        catalog["lighting"],
        "2500000",
        [catalog["japandi"]],
        [catalog["cream"]],
        [catalog["wood"]],
        [catalog["living"]],
    )
    mismatch = create_product(
        db_session,
        "Industrial Black Bed",
        "industrial-black-bed",
        catalog["bedding"],
        "7000000",
        [catalog["industrial"]],
        [catalog["black"]],
        [catalog["metal"]],
        [catalog["bedroom"]],
    )
    inactive = create_product(
        db_session,
        "Inactive Japandi Sofa",
        "inactive-japandi-sofa",
        catalog["sofa"],
        "8000000",
        [catalog["japandi"]],
        [catalog["cream"]],
        [catalog["wood"]],
        [catalog["living"]],
        active=False,
    )
    create_analysis_and_preference(db_session, project, catalog)
    return headers, project, catalog, best, lamp, mismatch, inactive


def test_recommendations_return_real_product_ids_and_score_range(client, db_session):
    headers, _project, _catalog, best, lamp, _mismatch, inactive = setup_recommendation_case(client, db_session)
    response = client.get(f"/api/room-projects/{_project['id']}/recommendations", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    product_ids = [item["product"]["id"] for item in items]
    assert best.id in product_ids
    assert lamp.id in product_ids
    assert inactive.id not in product_ids
    assert len(product_ids) == len(set(product_ids))
    assert all(0 <= item["score"] <= 100 for item in items)
    assert all(db_session.get(Product, product_id) is not None for product_id in product_ids)


def test_style_and_desired_category_increase_ranking(client, db_session):
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    response = client.get(f"/api/room-projects/{project['id']}/recommendations", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["product"]["id"] in {best.id, lamp.id}
    assert "style" in items[0]["breakdown"]
    assert any("phong cách" in reason.lower() for reason in items[0]["reasons"])


def test_budget_affects_ranking_and_filters_unaffordable_items(client, db_session):
    headers, project, catalog, _best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    expensive = create_product(
        db_session,
        "Expensive Japandi Sofa",
        "expensive-japandi-sofa",
        catalog["sofa"],
        "99000000",
        [catalog["japandi"]],
        [catalog["cream"]],
        [catalog["wood"]],
        [catalog["living"]],
    )
    response = client.get(f"/api/room-projects/{project['id']}/recommendations", headers=headers)
    assert response.status_code == 200
    product_ids = [item["product"]["id"] for item in response.json()["items"]]
    assert expensive.id not in product_ids


def test_deterministic_ordering_and_limit(client, db_session):
    headers, project, _catalog, _best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    first = client.get(f"/api/room-projects/{project['id']}/recommendations?limit=1", headers=headers)
    second = client.get(f"/api/room-projects/{project['id']}/recommendations?limit=1", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["items"] == second.json()["items"]
    assert len(first.json()["items"]) == 1


def test_recommendation_ownership_protection(client, db_session):
    owner_headers, project, _catalog, _best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    other_headers = auth_headers(client, "recommendation-other@example.com")
    response = client.get(f"/api/room-projects/{project['id']}/recommendations", headers=other_headers)
    assert response.status_code == 404
    assert owner_headers["Authorization"]


def test_recommendation_requires_authentication(client, db_session):
    headers, project, _catalog, _best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    response = client.get(f"/api/room-projects/{project['id']}/recommendations")
    assert response.status_code == 401
    assert headers["Authorization"]


def test_missing_preferences_and_analysis_are_handled(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    response = client.get(f"/api/room-projects/{project['id']}/recommendations", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "ROOM_PREFERENCES_REQUIRED"

    catalog = create_catalog(db_session)
    _, preference = create_analysis_and_preference(db_session, project, catalog)
    db_session.query(RoomAnalysis).filter(RoomAnalysis.room_project_id == project["id"]).delete()
    db_session.commit()
    response = client.get(f"/api/room-projects/{project['id']}/recommendations", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "ROOM_ANALYSIS_REQUIRED"
    assert preference.id
