from app.models.entities import Category, Color, Material, RoomPreference, RoomProject, Style


def auth_headers(client, email="preference-user@example.com"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Preference User"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_project(client, headers, title="Preference Bedroom"):
    response = client.post("/api/room-projects", json={"title": title, "room_type": "bedroom"}, headers=headers)
    assert response.status_code == 201
    return response.json()


def create_preference_lookups(db_session):
    style = Style(name="Japandi", slug="japandi", is_active=True)
    color = Color(name="Cream", slug="cream", hex_code="#f2eadc", is_active=True)
    material = Material(name="Wood", slug="wood", is_active=True)
    category = Category(name="Lighting", slug="lighting", is_active=True)
    db_session.add_all([style, color, material, category])
    db_session.commit()
    return style, color, material, category


def preference_payload(style, color, material, category):
    return {
        "budget_min": "5000000",
        "budget_max": "15000000",
        "currency": "VND",
        "purpose": "relaxation",
        "notes": "Bright, tidy, easy to clean.",
        "style_ids": [style.id, style.id],
        "color_ids": [color.id],
        "material_ids": [material.id],
        "category_ids": [category.id],
    }


def test_save_and_get_room_preferences(client, db_session):
    style, color, material, category = create_preference_lookups(db_session)
    headers = auth_headers(client)
    project = create_project(client, headers)

    save = client.put(f"/api/room-projects/{project['id']}/preferences", json=preference_payload(style, color, material, category), headers=headers)
    assert save.status_code == 200
    saved = save.json()
    assert saved["budget_min"] == "5000000.00"
    assert saved["budget_max"] == "15000000.00"
    assert saved["styles"][0]["id"] == style.id
    assert len(saved["styles"]) == 1
    assert saved["colors"][0]["hex_code"] == "#f2eadc"

    get = client.get(f"/api/room-projects/{project['id']}/preferences", headers=headers)
    assert get.status_code == 200
    assert get.json()["id"] == saved["id"]


def test_update_preferences_does_not_duplicate_record(client, db_session):
    style, color, material, category = create_preference_lookups(db_session)
    second_style = Style(name="Modern", slug="modern", is_active=True)
    db_session.add(second_style)
    db_session.commit()
    headers = auth_headers(client)
    project = create_project(client, headers)

    first = client.put(f"/api/room-projects/{project['id']}/preferences", json=preference_payload(style, color, material, category), headers=headers)
    assert first.status_code == 200
    preference_id = first.json()["id"]

    updated_payload = preference_payload(second_style, color, material, category)
    updated_payload["budget_min"] = "10000000"
    updated_payload["budget_max"] = "20000000"
    updated_payload["purpose"] = "work"
    update = client.put(f"/api/room-projects/{project['id']}/preferences", json=updated_payload, headers=headers)
    assert update.status_code == 200
    assert update.json()["id"] == preference_id
    assert update.json()["styles"][0]["id"] == second_style.id

    db_session.rollback()
    count = db_session.query(RoomPreference).filter(RoomPreference.room_project_id == project["id"]).count()
    assert count == 1


def test_preference_budget_validation(client, db_session):
    style, color, material, category = create_preference_lookups(db_session)
    headers = auth_headers(client)
    project = create_project(client, headers)
    payload = preference_payload(style, color, material, category)

    payload["budget_min"] = "-1"
    negative = client.put(f"/api/room-projects/{project['id']}/preferences", json=payload, headers=headers)
    assert negative.status_code == 422

    payload["budget_min"] = "20000000"
    payload["budget_max"] = "10000000"
    invalid_range = client.put(f"/api/room-projects/{project['id']}/preferences", json=payload, headers=headers)
    assert invalid_range.status_code == 422


def test_preference_invalid_lookup_ids_are_rejected(client, db_session):
    style, color, material, category = create_preference_lookups(db_session)
    headers = auth_headers(client)
    project = create_project(client, headers)
    base_payload = preference_payload(style, color, material, category)

    for key in ["style_ids", "color_ids", "material_ids", "category_ids"]:
        payload = {**base_payload, key: [999999]}
        response = client.put(f"/api/room-projects/{project['id']}/preferences", json=payload, headers=headers)
        assert response.status_code == 400


def test_preference_authentication_and_ownership(client, db_session):
    style, color, material, category = create_preference_lookups(db_session)
    owner_headers = auth_headers(client, "preference-owner@example.com")
    other_headers = auth_headers(client, "preference-other@example.com")
    project = create_project(client, owner_headers)
    payload = preference_payload(style, color, material, category)

    unauthenticated = client.get(f"/api/room-projects/{project['id']}/preferences")
    assert unauthenticated.status_code == 401

    blocked_get = client.get(f"/api/room-projects/{project['id']}/preferences", headers=other_headers)
    blocked_put = client.put(f"/api/room-projects/{project['id']}/preferences", json=payload, headers=other_headers)
    assert blocked_get.status_code == 404
    assert blocked_put.status_code == 404

    owner_save = client.put(f"/api/room-projects/{project['id']}/preferences", json=payload, headers=owner_headers)
    assert owner_save.status_code == 200
    stored_project = db_session.query(RoomProject).filter(RoomProject.id == project["id"]).one()
    assert stored_project.user_id == project["user_id"]
