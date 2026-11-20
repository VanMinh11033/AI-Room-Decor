"""Unit and Integration Test Suite for Customer-Controlled Furniture Selection V1.5 PRO.

Tests all 15 required verification scenarios:
1. Customer selects only 1 lamp.
2. Customer selects desk and chair.
3. Customer selects bed and wardrobe.
4. Customer selects rug, wall art, and plant.
5. Customer replaces sofa with another product.
6. Customer removes all recommended products and picks different ones.
7. Customer selects product outside top recommendation in MANUAL mode.
8. Customer selects exceeding provider limit (> 3 products).
9. Customer selects products exceeding budget (allowed with warning).
10. Customer selects non-existent Product ID.
11. Changing selection changes prompt and cache key.
12. Check exact Product IDs sent to provider mock transport.
13. Auto Mode still works and enforces recommendation bounds.
14. Manual Mode is not overwritten by AI recommendation.
15. Single-button AI design flow preserved.
"""

from decimal import Decimal
import io
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import pytest

from app.ai.image.base import GeneratedImage
from app.ai.image.factory import get_image_provider
from app.core.config import settings
from app.main import app
from app.models.entities import (
    Category,
    Color,
    Material,
    Product,
    ProductImage,
    ProductStatus,
    RoomAnalysis,
    RoomDesignGeneration,
    RoomPreference,
    RoomProject,
    RoomType,
    Style,
    User,
)
from app.services.storage_service import ProductImageStorageService, RoomImageStorageService
from tests.test_room_preferences import auth_headers


class MockCloudflareProvider:
    provider_name = "cloudflare"
    model_name = "@cf/black-forest-labs/flux-2-dev"
    MAX_INPUT_IMAGES = 4

    def __init__(self):
        self.call_count = 0
        self.last_source_path = None
        self.last_prompt = None
        self.last_reference_paths = None

    def generate_design(self, source_image_path: Path, prompt: str, reference_image_paths=None, **kwargs) -> GeneratedImage:
        self.call_count += 1
        self.last_source_path = source_image_path
        self.last_prompt = prompt
        self.last_reference_paths = reference_image_paths or []

        buf = io.BytesIO()
        Image.new("RGB", (1024, 576), color=(220, 215, 205)).save(buf, format="JPEG")
        return GeneratedImage(data=buf.getvalue(), content_type="image/jpeg")


def make_test_png(size=(800, 600), color=(235, 230, 220)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def catalog_fixture(db_session):
    """Seed comprehensive test catalog with various furniture categories."""
    db_session.query(ProductImage).delete()
    db_session.query(Product).delete()
    db_session.query(Category).delete()
    db_session.query(Style).delete()
    db_session.query(Color).delete()
    db_session.query(Material).delete()
    db_session.query(RoomType).delete()
    db_session.commit()

    # Lookups
    cat_sofa = Category(name="Sofa", slug="sofa")
    cat_lamp = Category(name="Lighting", slug="lighting")
    cat_desk = Category(name="Desk", slug="desk")
    cat_chair = Category(name="Chair", slug="chair")
    cat_bed = Category(name="Bedding", slug="bedding")
    cat_storage = Category(name="Storage", slug="storage")
    cat_rug = Category(name="Rug", slug="rug")
    cat_art = Category(name="Wall Decor", slug="wall-decor")
    cat_plant = Category(name="Plant Decor", slug="plant-decor")
    db_session.add_all([cat_sofa, cat_lamp, cat_desk, cat_chair, cat_bed, cat_storage, cat_rug, cat_art, cat_plant])

    style_mod = Style(name="Modern", slug="modern")
    style_jap = Style(name="Japandi", slug="japandi")
    style_ind = Style(name="Industrial", slug="industrial")
    db_session.add_all([style_mod, style_jap, style_ind])

    color_beige = Color(name="Beige", slug="beige")
    color_black = Color(name="Black", slug="black")
    color_gold = Color(name="Gold", slug="gold")
    db_session.add_all([color_beige, color_black, color_gold])

    mat_wood = Material(name="Wood", slug="wood")
    mat_metal = Material(name="Metal", slug="metal")
    mat_fabric = Material(name="Fabric", slug="fabric")
    db_session.add_all([mat_wood, mat_metal, mat_fabric])

    room_lr = RoomType(name="Living Room", slug="living-room")
    room_br = RoomType(name="Bedroom", slug="bedroom")
    room_st = RoomType(name="Study", slug="study")
    db_session.add_all([room_lr, room_br, room_st])
    db_session.commit()

    storage = ProductImageStorageService()

    def make_prod(pid, name, slug, cat, price, styles, colors, materials, room_types, is_active=True):
        p = Product(
            id=pid,
            name=name,
            slug=slug,
            category_id=cat.id,
            price=Decimal(str(price)),
            stock_quantity=10,
            is_active=is_active,
            status=ProductStatus.ACTIVE if is_active else ProductStatus.INACTIVE,
            styles=styles,
            colors=colors,
            materials=materials,
            room_types=room_types,
        )
        db_session.add(p)
        db_session.commit()

        # Create clean image file
        img_name = f"test_{slug}.png"
        img_path = storage.storage_root / img_name
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img_path.write_bytes(make_test_png((400, 400), (200, 200, 200)))

        # Also create reference clean file for skill bridge
        proj_root = Path(__file__).resolve().parents[2]
        clean_dir = proj_root / "storage" / "product_references_clean"
        clean_dir.mkdir(parents=True, exist_ok=True)
        (clean_dir / f"product_{pid}_clean.png").write_bytes(make_test_png((400, 400), (200, 200, 200)))

        pi = ProductImage(
            product_id=p.id,
            image_url=f"/storage/products/{img_name}",
            is_primary=True,
            sort_order=0,
        )
        db_session.add(pi)
        db_session.commit()
        return p

    p1_sofa = make_prod(1, "Japandi Low Sofa", "japandi-sofa", cat_sofa, 9500000, [style_jap, style_mod], [color_beige], [mat_wood, mat_fabric], [room_lr])
    p2_sofa2 = make_prod(2, "Modern Modular Sofa", "modern-modular-sofa", cat_sofa, 12500000, [style_mod], [color_beige], [mat_fabric], [room_lr])
    p8_desk = make_prod(8, "Minimal Desk", "minimal-desk", cat_desk, 4500000, [style_mod], [color_black], [mat_wood, mat_metal], [room_st])
    p9_lamp = make_prod(9, "Brass Floor Lamp", "brass-floor-lamp", cat_lamp, 2800000, [style_mod], [color_gold], [mat_metal], [room_lr, room_st])
    p11_chair = make_prod(11, "Ergonomic Desk Chair", "ergo-desk-chair", cat_chair, 3200000, [style_mod], [color_black], [mat_metal], [room_st])
    p13_rug = make_prod(13, "Geometric Gray Rug", "geom-rug", cat_rug, 2600000, [style_mod], [color_beige], [mat_fabric], [room_lr])
    p15_art = make_prod(15, "Abstract Wall Art", "abstract-art", cat_art, 950000, [style_mod], [color_beige], [mat_wood], [room_lr, room_br])
    p20_bed = make_prod(20, "Platform Wooden Bed", "platform-bed", cat_bed, 14000000, [style_jap], [color_beige], [mat_wood], [room_br])
    p22_wardrobe = make_prod(22, "White Storage Cabinet", "white-cabinet", cat_storage, 3500000, [style_mod], [color_beige], [mat_wood], [room_br, room_st])
    p24_plant = make_prod(24, "Tall Faux Plant", "faux-plant", cat_plant, 1250000, [style_jap, style_mod], [color_beige], [mat_fabric], [room_lr, room_st])
    p99_mismatch = make_prod(99, "Industrial Steel Cage", "steel-cage", cat_storage, 25000000, [style_ind], [color_black], [mat_metal], [room_st])

    return {
        "sofa1": p1_sofa,
        "sofa2": p2_sofa2,
        "desk": p8_desk,
        "lamp": p9_lamp,
        "chair": p11_chair,
        "rug": p13_rug,
        "art": p15_art,
        "bed": p20_bed,
        "wardrobe": p22_wardrobe,
        "plant": p24_plant,
        "mismatch": p99_mismatch,
    }


@pytest.fixture
def test_setup(client, db_session, catalog_fixture):
    headers = auth_headers(client, email="customer_choice@example.com")
    user = db_session.query(User).filter(User.email == "customer_choice@example.com").first()

    # Create RoomProject
    room_storage = RoomImageStorageService()
    room_rel = Path(str(user.id)) / "99" / "test_room.jpg"
    room_abs = room_storage.storage_root / room_rel
    room_abs.parent.mkdir(parents=True, exist_ok=True)
    room_abs.write_bytes(make_test_png((1024, 576), (230, 225, 215)))

    project = RoomProject(
        id=99,
        user_id=user.id,
        title="Phòng khách thử nghiệm",
        room_type="Living Room",
        room_image_path=str(room_rel).replace("\\", "/"),
        room_image_url=f"/storage/rooms/{user.id}/99/test_room.jpg",
        status="ANALYZED",
    )
    db_session.add(project)

    analysis = RoomAnalysis(
        room_project_id=project.id,
        user_id=user.id,
        image_checksum="test_checksum_12345",
        status="COMPLETED",
        provider="gemini",
        model="gemini-2.5-flash",
        room_type="Living Room",
        lighting={"quality": "good", "direction": "left"},
        dominant_colors=["Beige", "White"],
    )
    db_session.add(analysis)

    pref = RoomPreference(
        room_project_id=project.id,
        user_id=user.id,
        budget_min=Decimal("5000000"),
        budget_max=Decimal("20000000"),
        currency="VND",
        purpose="tiếp khách thư giãn",
        styles=[db_session.query(Style).filter(Style.slug == "modern").first()],
    )
    db_session.add(pref)
    db_session.commit()

    mock_cf = MockCloudflareProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    return {
        "user": user,
        "headers": headers,
        "project": project,
        "catalog": catalog_fixture,
        "mock_cf": mock_cf,
    }


# =============================================================================
# SCENARIO 1: Customer selects only 1 lamp
# =============================================================================
def test_customer_selects_single_lamp(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    lamp = test_setup["catalog"]["lamp"]
    mock_cf = test_setup["mock_cf"]

    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [lamp.id], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()

    assert len(data["products"]) == 1
    assert data["products"][0]["id"] == lamp.id
    assert mock_cf.call_count == 1
    assert len(mock_cf.last_reference_paths) == 1
    assert f"Product #{lamp.id}" in mock_cf.last_prompt
    assert "Position lighting 'Brass Floor Lamp' on the right or left room corner" in mock_cf.last_prompt


# =============================================================================
# SCENARIO 2: Customer selects desk and chair
# =============================================================================
def test_customer_selects_desk_and_chair(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    desk = test_setup["catalog"]["desk"]
    chair = test_setup["catalog"]["chair"]
    mock_cf = test_setup["mock_cf"]

    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [desk.id, chair.id], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()

    assert len(data["products"]) == 2
    assert [p["id"] for p in data["products"]] == [desk.id, chair.id]
    assert len(mock_cf.last_reference_paths) == 2
    assert f"Product #{desk.id}" in mock_cf.last_prompt
    assert f"Product #{chair.id}" in mock_cf.last_prompt


# =============================================================================
# SCENARIO 3: Customer selects bed and wardrobe
# =============================================================================
def test_customer_selects_bed_and_wardrobe(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    bed = test_setup["catalog"]["bed"]
    wardrobe = test_setup["catalog"]["wardrobe"]
    mock_cf = test_setup["mock_cf"]

    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [bed.id, wardrobe.id], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()

    assert len(data["products"]) == 2
    assert [p["id"] for p in data["products"]] == [bed.id, wardrobe.id]
    assert len(mock_cf.last_reference_paths) == 2


# =============================================================================
# SCENARIO 4: Customer selects rug, wall art, and plant
# =============================================================================
def test_customer_selects_rug_wall_art_plant(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    rug = test_setup["catalog"]["rug"]
    art = test_setup["catalog"]["art"]
    plant = test_setup["catalog"]["plant"]
    mock_cf = test_setup["mock_cf"]

    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [rug.id, art.id, plant.id], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()

    assert len(data["products"]) == 3
    assert [p["id"] for p in data["products"]] == [rug.id, art.id, plant.id]
    assert len(mock_cf.last_reference_paths) == 3


# =============================================================================
# SCENARIO 5: Customer replaces sofa with another product
# =============================================================================
def test_customer_replaces_sofa_with_another_product(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    sofa2 = test_setup["catalog"]["sofa2"]
    lamp = test_setup["catalog"]["lamp"]
    mock_cf = test_setup["mock_cf"]

    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [sofa2.id, lamp.id], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()

    assert len(data["products"]) == 2
    assert data["products"][0]["id"] == sofa2.id
    assert "Modern Modular Sofa" in mock_cf.last_prompt
    assert "Japandi Low Sofa" not in mock_cf.last_prompt


# =============================================================================
# SCENARIO 6: Customer removes all recommended and picks different product
# =============================================================================
def test_customer_removes_all_recommended_and_picks_different(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    art = test_setup["catalog"]["art"]
    mock_cf = test_setup["mock_cf"]

    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [art.id], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()

    assert len(data["products"]) == 1
    assert data["products"][0]["id"] == art.id
    assert f"Product #{art.id}" in mock_cf.last_prompt


# =============================================================================
# SCENARIO 7: Customer selects product outside top recommendation in MANUAL mode
# =============================================================================
def test_customer_selects_product_outside_top_recommendation_in_manual_mode(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    mismatch = test_setup["catalog"]["mismatch"]

    # In MANUAL mode, even a mismatch / unrecommended active product is permitted!
    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [mismatch.id], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["products"][0]["id"] == mismatch.id


# =============================================================================
# SCENARIO 8: Customer selects exceeding provider limit (> 3 products)
# =============================================================================
def test_customer_selects_exceeding_provider_limit(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    sofa = test_setup["catalog"]["sofa1"]
    lamp = test_setup["catalog"]["lamp"]
    rug = test_setup["catalog"]["rug"]
    art = test_setup["catalog"]["art"]

    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [sofa.id, lamp.id, rug.id, art.id], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 409
    assert "CAPABILITY_MISMATCH" in res.json()["detail"]


# =============================================================================
# SCENARIO 9: Customer selects products exceeding budget (allowed with warning)
# =============================================================================
def test_customer_selects_products_exceeding_budget(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    bed = test_setup["catalog"]["bed"]          # 14M
    sofa2 = test_setup["catalog"]["sofa2"]      # 12.5M -> Total 26.5M > budget_max (20M)

    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [bed.id, sofa2.id], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert len(data["products"]) == 2
    # Check that over-budget warning is recorded in warnings
    assert any("vượt ngân sách dự kiến" in w for w in data["warnings"])


# =============================================================================
# SCENARIO 10: Customer selects non-existent Product ID
# =============================================================================
def test_customer_selects_nonexistent_product_id(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]

    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [999999], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 400
    assert "INVALID_PRODUCT_IDS" in res.json()["detail"]


# =============================================================================
# SCENARIO 11: Changing selection changes prompt and cache key
# =============================================================================
def test_changing_selection_changes_prompt_and_cache(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    lamp = test_setup["catalog"]["lamp"]
    desk = test_setup["catalog"]["desk"]
    chair = test_setup["catalog"]["chair"]
    mock_cf = test_setup["mock_cf"]

    # First generation: Lamp + Desk
    res1 = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [lamp.id, desk.id], "selection_mode": "MANUAL"},
        headers=headers,
    )
    assert res1.status_code == 201
    gen1 = res1.json()
    prompt1 = mock_cf.last_prompt

    # Second generation: Lamp + Chair (different set)
    res2 = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [lamp.id, chair.id], "selection_mode": "MANUAL"},
        headers=headers,
    )
    assert res2.status_code == 201
    gen2 = res2.json()
    prompt2 = mock_cf.last_prompt

    # Generations must be different records
    assert gen1["id"] != gen2["id"]
    assert prompt1 != prompt2
    assert "Minimal Desk" in prompt1
    assert "Minimal Desk" not in prompt2
    assert "Ergonomic Desk Chair" in prompt2


# =============================================================================
# SCENARIO 12: Check exact Product IDs sent to provider mock transport
# =============================================================================
def test_exact_product_ids_sent_to_provider_mock_transport(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    lamp = test_setup["catalog"]["lamp"]
    art = test_setup["catalog"]["art"]
    mock_cf = test_setup["mock_cf"]

    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [lamp.id, art.id], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 201

    # Exact reference paths in order
    assert len(mock_cf.last_reference_paths) == 2
    path_str_0 = str(mock_cf.last_reference_paths[0])
    path_str_1 = str(mock_cf.last_reference_paths[1])
    assert f"product_{lamp.id}_clean.png" in path_str_0 or lamp.slug in path_str_0
    assert f"product_{art.id}_clean.png" in path_str_1 or art.slug in path_str_1


# =============================================================================
# SCENARIO 13: Auto Mode still works and enforces recommendation bounds
# =============================================================================
def test_auto_mode_still_works_and_enforces_recommendations(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    mismatch = test_setup["catalog"]["mismatch"]

    # In AUTO mode (without MANUAL selection), unrecommended products raise PRODUCT_NOT_RECOMMENDED
    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [mismatch.id], "selection_mode": "AUTO", "force": True},
        headers=headers,
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "PRODUCT_NOT_RECOMMENDED"


# =============================================================================
# SCENARIO 14: Manual Mode is not overwritten by AI recommendation
# =============================================================================
def test_manual_mode_not_overwritten_by_ai_recommendation(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    chair = test_setup["catalog"]["chair"]
    plant = test_setup["catalog"]["plant"]

    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [chair.id, plant.id], "selection_mode": "MANUAL", "force": True},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()

    # The AI bundle recommended Sofa #1 and Lamp #9, but manual mode must retain chair & plant
    returned_ids = [p["id"] for p in data["products"]]
    assert returned_ids == [chair.id, plant.id]


# =============================================================================
# SCENARIO 15: Single-button AI design flow preserved
# =============================================================================
def test_single_button_ai_design_flow_preserved(client, test_setup):
    headers = test_setup["headers"]
    project = test_setup["project"]
    sofa = test_setup["catalog"]["sofa1"]
    lamp = test_setup["catalog"]["lamp"]

    # Verify recommendations contain the bundle items
    rec_res = client.get(f"/api/room-projects/{project.id}/recommendations", headers=headers)
    assert rec_res.status_code == 200
    bundle = rec_res.json().get("bundle", {})
    recommended_ids = bundle.get("product_ids", [])
    assert sofa.id in recommended_ids or lamp.id in recommended_ids

    # Emulating single-button AI flow using recommended items
    res = client.post(
        f"/api/room-projects/{project.id}/design-generations",
        json={"product_ids": [sofa.id, lamp.id], "generation_mode": "AI_PHOTOREALISTIC_PREVIEW", "force": True},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["generation_mode"] == "AI_PHOTOREALISTIC_PREVIEW"
    assert len(data["products"]) == 2
