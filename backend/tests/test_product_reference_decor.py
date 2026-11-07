from pathlib import Path
from uuid import uuid4

from PIL import Image

from app.models.entities import Product, ProductImage, RoomDesignGeneration
from app.services.storage_service import ProductImageStorageService
from test_design_generations import FakeImageProvider, add_room_image, override_image_provider
from test_recommendations import create_product, setup_recommendation_case


def write_product_image(storage: ProductImageStorageService, filename: str) -> Path:
    path = storage.storage_root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (96, 96), (180, 140, 110)).save(path, format="JPEG")
    return path


def replace_product_images(db_session, product, images):
    db_session.query(ProductImage).filter(ProductImage.product_id == product.id).delete()
    db_session.commit()
    for image in images:
        db_session.add(ProductImage(product_id=product.id, **image))
    db_session.commit()


def test_generation_sends_room_and_product_references_in_order(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)
    storage = ProductImageStorageService()
    write_product_image(storage, f"{best.slug}.jpg")
    write_product_image(storage, f"{lamp.slug}.jpg")

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id, lamp.id]},
        headers=headers,
    )

    assert response.status_code == 201
    assert len(provider.calls) == 1
    references = [Path(path) for path in provider.calls[0]["references"]]
    assert references == [storage.storage_root / f"{best.slug}.jpg", storage.storage_root / f"{lamp.slug}.jpg"]
    assert provider.calls[0]["source"].endswith("source.png")
    prompt = provider.calls[0]["prompt"]
    assert "REFERENCE 0: original room image." in prompt
    assert f"REFERENCE 1: Product ID {best.id}" in prompt
    assert f"REFERENCE 2: Product ID {lamp.id}" in prompt


def test_primary_product_image_is_preferred_over_non_primary(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    replace_product_images(
        db_session,
        best,
        [
            {"image_url": "/storage/products/best-secondary.jpg", "is_primary": False, "sort_order": 0},
            {"image_url": "/storage/products/best-primary.jpg", "is_primary": True, "sort_order": 1},
        ],
    )
    storage = ProductImageStorageService()
    write_product_image(storage, "best-secondary.jpg")
    write_product_image(storage, "best-primary.jpg")
    add_room_image(db_session, project)

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id]},
        headers=headers,
    )

    assert response.status_code == 201
    references = [Path(path).name for path in provider.calls[0]["references"]]
    assert references == ["best-primary.jpg"]


def test_falls_back_to_first_ordered_image_when_no_primary(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    replace_product_images(
        db_session,
        best,
        [
            {"image_url": "/storage/products/late.jpg", "is_primary": False, "sort_order": 10},
            {"image_url": "/storage/products/early.jpg", "is_primary": False, "sort_order": 1},
        ],
    )
    storage = ProductImageStorageService()
    write_product_image(storage, "late.jpg")
    write_product_image(storage, "early.jpg")
    add_room_image(db_session, project)

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id]},
        headers=headers,
    )

    assert response.status_code == 201
    references = [Path(path).name for path in provider.calls[0]["references"]]
    assert references == ["early.jpg"]


def test_product_images_are_read_through_existing_storage(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)
    storage = ProductImageStorageService()
    best_path = write_product_image(storage, f"{best.slug}.jpg")
    lamp_path = write_product_image(storage, f"{lamp.slug}.jpg")

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id, lamp.id]},
        headers=headers,
    )

    assert response.status_code == 201
    references = [Path(path) for path in provider.calls[0]["references"]]
    assert references == [best_path, lamp_path]
    for path in references:
        assert path.is_file()
        assert storage.storage_root in path.parents


def test_missing_product_image_keeps_id_linkage_without_fake_reference(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    for product in (best, lamp):
        replace_product_images(
            db_session,
            product,
            [{"image_url": f"/storage/products/{uuid4().hex}.jpg", "is_primary": True, "sort_order": 0}],
        )
    add_room_image(db_session, project)

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id, lamp.id]},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert [product["id"] for product in body["products"]] == [best.id, lamp.id]
    assert provider.calls[0]["references"] == []
    prompt = provider.calls[0]["prompt"]
    assert f"Product ID {best.id}" in prompt
    assert f"Product ID {lamp.id}" in prompt
    assert all(db_session.get(Product, product["id"]) is not None for product in body["products"])


def test_selected_products_are_real_and_linked_in_database(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id, lamp.id]},
        headers=headers,
    )

    assert response.status_code == 201
    db_session.rollback()
    generation = db_session.query(RoomDesignGeneration).one()
    assert {product.id for product in generation.products} == {best.id, lamp.id}
    assert response.json()["prompt_version"] == "v2"


def test_deterministic_reference_order_caps_at_provider_limit(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    armchair = create_product(
        db_session,
        "Japandi Wood Armchair",
        "japandi-wood-armchair",
        catalog["sofa"],
        "5000000",
        [catalog["japandi"]],
        [catalog["cream"]],
        [catalog["wood"]],
        [catalog["living"]],
    )
    table_lamp = create_product(
        db_session,
        "Japandi Table Lamp",
        "japandi-table-lamp",
        catalog["lighting"],
        "1200000",
        [catalog["japandi"]],
        [catalog["cream"]],
        [catalog["wood"]],
        [catalog["living"]],
    )
    storage = ProductImageStorageService()
    for product in (best, lamp, armchair, table_lamp):
        write_product_image(storage, f"{product.slug}.jpg")
    add_room_image(db_session, project)

    selected = [best.id, lamp.id, armchair.id, table_lamp.id]
    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": selected},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert [product["id"] for product in body["products"]] == selected
    references = [Path(path).name for path in provider.calls[0]["references"]]
    assert references == [f"{best.slug}.jpg", f"{armchair.slug}.jpg", f"{lamp.slug}.jpg"]
    prompt = provider.calls[0]["prompt"]
    assert f"Product ID {table_lamp.id}" in prompt


def test_cart_integration_from_generated_products_still_works(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    generation = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id, lamp.id]},
        headers=headers,
    )
    assert generation.status_code == 201

    for product in generation.json()["products"]:
        added = client.post("/api/cart/items", json={"product_id": product["id"], "quantity": 1}, headers=headers)
        assert added.status_code == 201

    cart = client.get("/api/cart", headers=headers)
    assert cart.status_code == 200
    assert {item["product_id"] for item in cart.json()["items"]} == {best.id, lamp.id}
