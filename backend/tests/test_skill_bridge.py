import io
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw
import pytest
from fastapi import HTTPException

from app.ai.image.base import GeneratedImage
from app.ai.image.factory import get_image_provider
from app.ai.skill_bridge import (
    parse_skill_metadata,
    serialize_skill_metadata,
)
from app.ai.skill_bridge.prompt_adapter import (
    CATALOG_TRAITS,
    MAX_SAFE_PROMPT_CHARS,
    build_skill_manifest,
    build_skill_prompt,
)
from app.ai.skill_bridge.quality_evaluator import (
    MAX_ACCEPTABLE_ARCHITECTURE_DRIFT,
    WEIGHTS,
    QualityEvaluator,
    estimate_cloudflare_neurons,
)
from app.core.config import settings
from app.main import app
from app.models.entities import Product, ProductImage, RoomDesignGeneration, RoomProject
from app.services.design_generation_service import DesignGenerationService
from app.services.storage_service import GeneratedDesignStorageService, ProductImageStorageService, RoomImageStorageService
from test_recommendations import create_product, setup_recommendation_case


def make_test_png(size=(400, 300), color=(220, 220, 220)):
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


def make_isolated_product_png():
    buf = io.BytesIO()
    img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 160, 160], fill=(160, 90, 60))
    img.save(buf, format="PNG")
    return buf.getvalue()


class MockCloudflareProvider:
    provider_name = "cloudflare"
    model_name = "@cf/black-forest-labs/flux-2-dev"
    MAX_INPUT_IMAGES = 4

    def __init__(self):
        self.call_count = 0
        self.last_source_path = None
        self.last_prompt = None
        self.last_reference_paths = None

    def generate_design(self, source_image_path: Path, prompt: str, reference_image_paths=None) -> GeneratedImage:
        self.call_count += 1
        self.last_source_path = source_image_path
        self.last_prompt = prompt
        self.last_reference_paths = reference_image_paths or []

        buf = io.BytesIO()
        Image.new("RGB", (1024, 1024), color=(210, 205, 195)).save(buf, format="JPEG")
        return GeneratedImage(data=buf.getvalue(), content_type="image/jpeg")


# =========================================================================
# 1. UNIT TESTS: MANIFEST & PROMPT ADAPTER
# =========================================================================

def test_skill_manifest_reference_order(tmp_path):
    room_file = tmp_path / "room.png"
    room_file.write_bytes(b"fake_room")

    prod1_file = tmp_path / "sofa.png"
    prod1_file.write_bytes(b"fake_sofa")
    prod2_file = tmp_path / "lamp.png"
    prod2_file.write_bytes(b"fake_lamp")

    p1 = Product(id=1, name="Ghế Sofa Văng")
    p2 = Product(id=9, name="Đèn Cây Đứng")

    manifest = build_skill_manifest(
        room_image_path=str(room_file),
        selected_products=[p1, p2],
        reference_image_paths=[prod1_file, prod2_file],
    )

    # Reference 0 MUST be room photo
    assert manifest[0]["index"] == 0
    assert manifest[0]["role"] == "room"
    assert manifest[0]["asset"] == str(room_file)

    # Reference 1..N MUST map to selected products
    assert len(manifest) == 3
    assert manifest[1]["index"] == 1
    assert manifest[1]["role"] == "product"
    assert manifest[1]["product_id"] == 1
    assert manifest[1]["asset"] == str(prod1_file)
    assert "sofa" in manifest[1]["distinctive_traits"].lower()

    assert manifest[2]["index"] == 2
    assert manifest[2]["product_id"] == 9
    assert manifest[2]["asset"] == str(prod2_file)
    assert "lamp" in manifest[2]["distinctive_traits"].lower() or "đèn" in manifest[2]["distinctive_traits"].lower()


def test_dynamic_prompt_builder_contains_invariants_and_traits(tmp_path):
    room_file = tmp_path / "room.png"
    p1_file = tmp_path / "sofa.png"
    p1 = Product(id=1, name="Ghế Sofa Văng Hiện Đại")

    manifest = build_skill_manifest(str(room_file), [p1], [p1_file])
    project = RoomProject(room_type="living-room")

    prompt = build_skill_prompt(
        project=project,
        selected_products=[p1],
        manifest=manifest,
        correction="Adjust lighting to warm amber.",
    )

    # 1. Architectural invariants check
    assert "Architecture Lock" in prompt
    assert "IMMUTABLE" in prompt
    assert "windows, doors, ceiling, and flooring" in prompt

    # 2. Circulation clearances
    assert "Circulation & Clearance" in prompt
    assert "unobstructed pathways" in prompt

    # 3. Product trait injection
    assert "Product #1" in prompt
    assert "low-profile floor sofa" in prompt

    # 4. Prior correction injection
    assert "PRIOR VALIDATION CORRECTIONS" in prompt
    assert "Adjust lighting to warm amber." in prompt

    # 5. Prompt length check (< 3580 chars)
    assert len(prompt) <= MAX_SAFE_PROMPT_CHARS


def test_prompt_distinctive_traits_dictionary():
    assert len(CATALOG_TRAITS) >= 30
    assert 1 in CATALOG_TRAITS
    assert "sofa" in CATALOG_TRAITS[1].lower()


# =========================================================================
# 2. UNIT TESTS: QUALITY EVALUATOR & HARD GATES
# =========================================================================

def test_quality_evaluator_weights_and_threshold(tmp_path):
    evaluator = QualityEvaluator(threshold=85.0)

    # Setup base room
    room_path = tmp_path / "room.png"
    room_path.write_bytes(make_test_png((400, 300), (220, 220, 220)))

    # Setup matching candidate
    candidate_bytes = make_test_png((400, 300), (218, 218, 218))

    # Setup product reference
    prod_path = tmp_path / "prod.png"
    prod_path.write_bytes(make_test_png((200, 200), (215, 215, 215)))

    result = evaluator.evaluate(
        source_room_path=room_path,
        candidate_image_bytes=candidate_bytes,
        selected_product_ids=[1],
        reference_image_paths=[prod_path],
        is_composite_mode=False,
    )

    # Verify component scores presence
    assert result.component_scores.catalog is not None
    assert result.component_scores.architecture is not None
    assert result.component_scores.proportion is not None
    assert result.component_scores.perspective is not None
    assert result.component_scores.lighting is not None
    assert result.component_scores.realism is not None

    # Weights match spec (35, 25, 15, 10, 10, 5)
    assert WEIGHTS["catalog"] == 35.0
    assert WEIGHTS["architecture"] == 25.0
    assert WEIGHTS["proportion"] == 15.0
    assert WEIGHTS["perspective"] == 10.0
    assert WEIGHTS["lighting"] == 10.0
    assert WEIGHTS["realism"] == 5.0

    # Overall score calculated correctly
    assert result.quality_score is not None
    assert 0 <= result.quality_score <= 100.0

    # AI preview must be NEEDS_REVIEW
    assert result.generation_status == "needs_review"
    assert result.neuron_estimate > 0


def test_quality_evaluator_hard_gate_architectural_drift(tmp_path):
    evaluator = QualityEvaluator()

    # Room is light grey
    room_path = tmp_path / "room.png"
    room_path.write_bytes(make_test_png((400, 300), (230, 230, 230)))

    # Candidate has upper 30% drastically changed (black)
    buf = io.BytesIO()
    cand_img = Image.new("RGB", (400, 300), color=(230, 230, 230))
    draw = ImageDraw.Draw(cand_img)
    draw.rectangle([0, 0, 400, 100], fill=(0, 0, 0))  # Upper 30% black
    cand_img.save(buf, format="PNG")
    candidate_bytes = buf.getvalue()

    result = evaluator.evaluate(
        source_room_path=room_path,
        candidate_image_bytes=candidate_bytes,
        selected_product_ids=[1],
        reference_image_paths=[],
    )

    assert result.hard_gates_passed is False
    assert result.generation_status == "rejected"
    assert "architecture" in result.failed_gates
    assert result.architecture.status == "fail"


def test_quality_evaluator_border_occlusion_warning(tmp_path):
    evaluator = QualityEvaluator()

    room_path = tmp_path / "room.png"
    room_path.write_bytes(make_test_png((400, 300), (230, 230, 230)))

    # Occlude left border heavily (doorway zone)
    buf = io.BytesIO()
    cand_img = Image.new("RGB", (400, 300), color=(230, 230, 230))
    draw = ImageDraw.Draw(cand_img)
    draw.rectangle([0, 120, 50, 300], fill=(10, 10, 10))  # Left border obstruction
    cand_img.save(buf, format="PNG")
    candidate_bytes = buf.getvalue()

    result = evaluator.evaluate(
        source_room_path=room_path,
        candidate_image_bytes=candidate_bytes,
        selected_product_ids=[1],
        reference_image_paths=[],
    )

    assert result.access.status == "unknown"
    assert any("lối đi" in w for w in result.warnings)


def test_estimate_cloudflare_neurons():
    # 1 room + 2 products = 3 images, 512x512, 8 steps
    neurons = estimate_cloudflare_neurons(
        model_name="@cf/black-forest-labs/flux-2-dev",
        input_image_count=3,
        target_width=512,
        target_height=512,
        inference_steps=8,
        vision_used=True,
    )
    assert neurons > 600
    assert 1050 <= neurons <= 1300


# =========================================================================
# 3. METADATA SERIALIZATION & DESERIALIZATION
# =========================================================================

def test_metadata_serialization_roundtrip():
    base_prompt = "Scandinavian living room with oak table and grey sofa."
    meta = {
        "version": "1.0",
        "generation_status": "needs_review",
        "quality_score": 87.5,
        "referenced_product_ids": [1, 2],
        "verified_product_ids": [1],
        "warnings": ["Pending human eye review"],
        "checks": {
            "catalog_fidelity": {"status": "pass", "score": 90.0},
        },
    }

    full_text = serialize_skill_metadata(base_prompt, meta)
    assert base_prompt in full_text
    assert "[SKILL_METADATA_V1]" in full_text

    cleaned_prompt, parsed_meta = parse_skill_metadata(full_text)
    assert cleaned_prompt.strip() == base_prompt.strip()
    assert parsed_meta is not None
    assert parsed_meta.generation_status == "needs_review"
    assert parsed_meta.quality_score == 87.5
    assert parsed_meta.referenced_product_ids == [1, 2]
    assert parsed_meta.verified_product_ids == [1]


def test_metadata_parsing_legacy_prompt():
    legacy_prompt = "Clean modern living room without any tags."
    cleaned, meta = parse_skill_metadata(legacy_prompt)
    assert cleaned == legacy_prompt
    assert meta is None


# =========================================================================
# 4. INTEGRATION TESTS: SERVICE & CAPABILITY MISMATCH
# =========================================================================

def test_capability_mismatch_when_exceeding_provider_limit(client, db_session):
    """When Skill Bridge is enabled, selecting > 3 products for Cloudflare
    FLUX.2 Dev MUST raise ConflictException (CAPABILITY_MISMATCH) instead
    of silently dropping items."""
    headers, project, catalog, _best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)

    # Create dummy room image
    room_storage = RoomImageStorageService()
    room_rel_path = Path(str(project["user_id"])) / str(project["id"]) / "test_room.png"
    room_abs_path = room_storage.storage_root / room_rel_path
    room_abs_path.parent.mkdir(parents=True, exist_ok=True)
    room_abs_path.write_bytes(make_test_png())

    room_proj = db_session.get(RoomProject, project["id"])
    room_proj.room_image_url = f"/storage/rooms/{project['user_id']}/{project['id']}/test_room.png"
    room_proj.room_image_path = str(room_rel_path).replace("\\", "/")
    room_proj.status = "COMPLETED"

    # Create 4 matching products
    p1 = create_product(db_session, "Sofa Alpha", "sofa-alpha", catalog["sofa"], "5000000", [catalog["japandi"]], [catalog["cream"]], [catalog["wood"]], [catalog["living"]])
    p2 = create_product(db_session, "Sofa Beta", "sofa-beta", catalog["sofa"], "6000000", [catalog["japandi"]], [catalog["cream"]], [catalog["wood"]], [catalog["living"]])
    p3 = create_product(db_session, "Lamp Alpha", "lamp-alpha", catalog["lighting"], "2000000", [catalog["japandi"]], [catalog["cream"]], [catalog["wood"]], [catalog["living"]])
    p4 = create_product(db_session, "Lamp Beta", "lamp-beta", catalog["lighting"], "3000000", [catalog["japandi"]], [catalog["cream"]], [catalog["wood"]], [catalog["living"]])

    prod_storage = ProductImageStorageService()
    for p in [p1, p2, p3, p4]:
        p_abs = prod_storage.storage_root / f"{p.slug}.png"
        p_abs.parent.mkdir(parents=True, exist_ok=True)
        p_abs.write_bytes(make_isolated_product_png())
        prod_img = db_session.query(ProductImage).filter(ProductImage.product_id == p.id).first()
        if prod_img:
            prod_img.image_url = f"/storage/products/{p.slug}.png"
        else:
            db_session.add(ProductImage(product_id=p.id, image_url=f"/storage/products/{p.slug}.png", is_primary=True, sort_order=0))

    db_session.commit()

    mock_cf = MockCloudflareProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    try:
        with patch.object(settings, "room_decor_skill_enabled", True), \
             patch.object(settings, "enable_cloud_ai", True):
            gen_res = client.post(
                f"/api/room-projects/{project['id']}/design-generations",
                json={
                    "product_ids": [p1.id, p2.id, p3.id, p4.id],
                    "generation_mode": "AI_PHOTOREALISTIC_PREVIEW",
                    "force": True,
                },
                headers=headers,
            )
            assert gen_res.status_code == 409
            assert "CAPABILITY_MISMATCH" in gen_res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_single_button_flow_with_skill_bridge_enabled(client, db_session):
    """End-to-end integration test with room_decor_skill_enabled = True:
    - Verifies manifest creation & prompt generation.
    - Cloudflare FLUX mock receives prompt with architectural invariants.
    - Database stores generation with [SKILL_METADATA_V1] metadata.
    - Read response exposes quality_score, verification_status, and referenced_product_ids."""
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)

    room_storage = RoomImageStorageService()
    room_rel_path = Path(str(project["user_id"])) / str(project["id"]) / "skill_room.png"
    room_abs_path = room_storage.storage_root / room_rel_path
    room_abs_path.parent.mkdir(parents=True, exist_ok=True)
    room_abs_path.write_bytes(make_test_png((800, 600), (230, 225, 215)))

    room_proj = db_session.get(RoomProject, project["id"])
    room_proj.room_image_url = f"/storage/rooms/{project['user_id']}/{project['id']}/skill_room.png"
    room_proj.room_image_path = str(room_rel_path).replace("\\", "/")
    room_proj.status = "COMPLETED"

    prod_storage = ProductImageStorageService()
    for prod in [best, lamp]:
        prod_fname = f"{prod.slug}.png"
        prod_abs = prod_storage.storage_root / prod_fname
        prod_abs.parent.mkdir(parents=True, exist_ok=True)
        prod_abs.write_bytes(make_isolated_product_png())

        prod_img = db_session.query(ProductImage).filter(ProductImage.product_id == prod.id).first()
        if prod_img:
            prod_img.image_url = f"/storage/products/{prod_fname}"
        else:
            db_session.add(ProductImage(product_id=prod.id, image_url=f"/storage/products/{prod_fname}", is_primary=True, sort_order=0))

    db_session.commit()

    mock_cf = MockCloudflareProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    try:
        with patch.object(settings, "room_decor_skill_enabled", True), \
             patch.object(settings, "enable_cloud_ai", True):
            gen_res = client.post(
                f"/api/room-projects/{project['id']}/design-generations",
                json={
                    "product_ids": [best.id, lamp.id],
                    "generation_mode": "AI_PHOTOREALISTIC_PREVIEW",
                    "force": True,
                },
                headers=headers,
            )
            assert gen_res.status_code == 201, gen_res.text
            gen_data = gen_res.json()

            # Verify prompt content sent to Cloudflare
            assert mock_cf.call_count == 1
            assert "Architecture Lock" in mock_cf.last_prompt
            assert f"Product #{best.id}" in mock_cf.last_prompt
            assert f"Product #{lamp.id}" in mock_cf.last_prompt

            # Verify response schema fields
            assert gen_data["verification_status"] == "NEEDS_REVIEW"
            assert "quality_score" in gen_data
            assert gen_data["quality_score"] is not None
            assert gen_data["quality_score"] >= 0.0

            # Verify database persistence & metadata
            db_session.rollback()
            db_gen = db_session.get(RoomDesignGeneration, gen_data["id"])
            assert db_gen is not None
            assert "[SKILL_METADATA_V1]" in db_gen.prompt
            details = db_gen.verification_details
            assert details is not None
            assert any(v in str(details.get("skill_version")) for v in ("1.5", "1.0"))
            assert best.id in details.get("referenced_product_ids", [])
            assert lamp.id in details.get("referenced_product_ids", [])
    finally:
        app.dependency_overrides.clear()


def test_offline_composite_fallback_metadata_and_label(client, db_session):
    """When Cloudflare is unavailable or disabled, offline composite fallback:
    - Labels generation as 'Bản ghép xem trước Offline – Không phải ảnh AI Photorealistic'.
    - Does NOT mark as VERIFIED.
    - Stores metadata safely without breaking."""
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)

    room_storage = RoomImageStorageService()
    room_rel_path = Path(str(project["user_id"])) / str(project["id"]) / "offline_room.png"
    room_abs_path = room_storage.storage_root / room_rel_path
    room_abs_path.parent.mkdir(parents=True, exist_ok=True)
    room_abs_path.write_bytes(make_test_png((800, 600), (230, 225, 215)))

    room_proj = db_session.get(RoomProject, project["id"])
    room_proj.room_image_url = f"/storage/rooms/{project['user_id']}/{project['id']}/offline_room.png"
    room_proj.room_image_path = str(room_rel_path).replace("\\", "/")
    room_proj.status = "COMPLETED"

    prod_storage = ProductImageStorageService()
    for prod in [best]:
        prod_fname = f"{prod.slug}.png"
        prod_abs = prod_storage.storage_root / prod_fname
        prod_abs.parent.mkdir(parents=True, exist_ok=True)
        prod_abs.write_bytes(make_isolated_product_png())

        prod_img = db_session.query(ProductImage).filter(ProductImage.product_id == prod.id).first()
        if prod_img:
            prod_img.image_url = f"/storage/products/{prod_fname}"
        else:
            db_session.add(ProductImage(product_id=prod.id, image_url=f"/storage/products/{prod_fname}", is_primary=True, sort_order=0))

    db_session.commit()

    mock_cf = MockCloudflareProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    try:
        with patch.object(settings, "room_decor_skill_enabled", True), \
             patch.object(settings, "enable_cloud_ai", False):  # Forces fallback
            gen_res = client.post(
                f"/api/room-projects/{project['id']}/design-generations",
                json={
                    "product_ids": [best.id],
                    "force": True,
                },
                headers=headers,
            )
            assert gen_res.status_code == 201, gen_res.text
            gen_data = gen_res.json()

            assert gen_data["verification_status"] != "VERIFIED"
            assert gen_data["is_ai_preview"] is False
            assert gen_data["generation_mode"] == "CATALOG_ACCURATE"

            # Check database record
            db_session.rollback()
            db_gen = db_session.get(RoomDesignGeneration, gen_data["id"])
            assert db_gen is not None
            assert "Bản ghép xem trước Offline" in db_gen.prompt
            details = db_gen.verification_details
            assert details is not None
            assert details.get("is_photorealistic") is False
    finally:
        app.dependency_overrides.clear()


def test_feature_flag_rollback_uses_legacy_behavior(client, db_session):
    """When room_decor_skill_enabled = False, system behaves exactly as legacy."""
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)

    room_storage = RoomImageStorageService()
    room_rel_path = Path(str(project["user_id"])) / str(project["id"]) / "legacy_room.png"
    room_abs_path = room_storage.storage_root / room_rel_path
    room_abs_path.parent.mkdir(parents=True, exist_ok=True)
    room_abs_path.write_bytes(make_test_png((800, 600), (230, 225, 215)))

    room_proj = db_session.get(RoomProject, project["id"])
    room_proj.room_image_url = f"/storage/rooms/{project['user_id']}/{project['id']}/legacy_room.png"
    room_proj.room_image_path = str(room_rel_path).replace("\\", "/")
    room_proj.status = "COMPLETED"

    prod_storage = ProductImageStorageService()
    for prod in [best]:
        prod_fname = f"{prod.slug}.png"
        prod_abs = prod_storage.storage_root / prod_fname
        prod_abs.parent.mkdir(parents=True, exist_ok=True)
        prod_abs.write_bytes(make_isolated_product_png())

        prod_img = db_session.query(ProductImage).filter(ProductImage.product_id == prod.id).first()
        if prod_img:
            prod_img.image_url = f"/storage/products/{prod_fname}"
        else:
            db_session.add(ProductImage(product_id=prod.id, image_url=f"/storage/products/{prod_fname}", is_primary=True, sort_order=0))

    db_session.commit()

    mock_cf = MockCloudflareProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    try:
        with patch.object(settings, "room_decor_skill_enabled", False), \
             patch.object(settings, "enable_cloud_ai", True):
            gen_res = client.post(
                f"/api/room-projects/{project['id']}/design-generations",
                json={
                    "product_ids": [best.id],
                    "generation_mode": "AI_PHOTOREALISTIC_PREVIEW",
                    "force": True,
                },
                headers=headers,
            )
            assert gen_res.status_code == 201, gen_res.text
            gen_data = gen_res.json()

            # When disabled, prompt shouldn't have [SKILL_METADATA_V1]
            db_session.rollback()
            db_gen = db_session.get(RoomDesignGeneration, gen_data["id"])
            assert db_gen is not None
            assert "[SKILL_METADATA_V1]" not in db_gen.prompt
    finally:
        app.dependency_overrides.clear()


def test_quality_evaluator_all_hard_gates(tmp_path):
    """Test all Skill V1.0 Hard Gates independently:
    1. Altered architecture (> 0.38 drift) -> REJECTED
    2. Missing product (< 15% color match) -> REJECTED
    3. Blocked doorway (occlusion > 0.50 at known door coordinates) -> REJECTED
    4. Diffusion mode never marks verified_product_ids without deterministic ground truth -> NEEDS_REVIEW
    """
    evaluator = QualityEvaluator()

    room_path = tmp_path / "room_gate.png"
    room_path.write_bytes(make_test_png((400, 300), (220, 220, 220)))

    # A. Test Blocked Doorway with door coordinates
    door_coords = [{"ymin": 0.4, "xmin": 0.0, "ymax": 1.0, "xmax": 0.2}]
    cand_blocked = Image.new("RGB", (400, 300), color=(220, 220, 220))
    draw = ImageDraw.Draw(cand_blocked)
    draw.rectangle([0, 120, 80, 300], fill=(20, 20, 20))  # Obstruct door
    buf = io.BytesIO()
    cand_blocked.save(buf, format="PNG")

    res_door = evaluator.evaluate(
        source_room_path=room_path,
        candidate_image_bytes=buf.getvalue(),
        selected_product_ids=[1],
        reference_image_paths=[],
        door_coordinates=door_coords,
    )
    assert res_door.generation_status == "rejected"
    assert "blocked_doorway" in res_door.failed_gates

    # B. Test Missing Product
    ref_path = tmp_path / "blue_ref.png"
    ref_img = Image.new("RGB", (100, 100), color=(0, 0, 240))  # Bright blue
    ref_img.save(ref_path)

    cand_no_blue = Image.new("RGB", (400, 300), color=(220, 220, 220))  # Light grey only
    buf2 = io.BytesIO()
    cand_no_blue.save(buf2, format="PNG")

    res_missing = evaluator.evaluate(
        source_room_path=room_path,
        candidate_image_bytes=buf2.getvalue(),
        selected_product_ids=[99],
        reference_image_paths=[ref_path],
    )
    assert res_missing.generation_status == "rejected"
    assert "missing_product_99" in res_missing.failed_gates

    # C. Test Diffusion Mode Lack of Proof -> NEEDS_REVIEW (verified_ids empty)
    cand_similar = Image.new("RGB", (400, 300), color=(220, 220, 220))
    draw = ImageDraw.Draw(cand_similar)
    draw.rectangle([100, 150, 300, 280], fill=(0, 0, 200))  # Placed blue object
    buf3 = io.BytesIO()
    cand_similar.save(buf3, format="PNG")

    res_diff = evaluator.evaluate(
        source_room_path=room_path,
        candidate_image_bytes=buf3.getvalue(),
        selected_product_ids=[99],
        reference_image_paths=[ref_path],
        is_composite_mode=False,
    )
    assert res_diff.generation_status == "needs_review"
    assert res_diff.verified_product_ids == []  # Not verified without deterministic proof


def test_cloudflare_neuron_breakdown_audit():
    """Verify Cloudflare FLUX.2 Dev Neuron Estimator matches official pricing geometry."""
    from app.ai.skill_bridge.quality_evaluator import get_cloudflare_neuron_breakdown

    breakdown = get_cloudflare_neuron_breakdown(
        model_name="@cf/black-forest-labs/flux-2-dev",
        room_dimensions=(1024, 768),
        reference_dimensions=[(512, 512), (400, 400)],
        output_dimensions=(1024, 1024),
        inference_steps=8,
        vision_used=True,
    )

    # 1024x768 = 2x2 = 4 tiles; 2 references of 512x512 = 1 tile each = 2 tiles. Total input = 6 tiles.
    assert breakdown["room_tiles"] == 4
    assert breakdown["reference_tiles"] == 2
    assert breakdown["total_input_tiles"] == 6
    assert breakdown["output_tiles"] == 4
    assert breakdown["vision_neurons"] == 250
    assert breakdown["estimated_neurons"] >= 2500


def test_design_cache_hit_and_miss_lifecycle(client, db_session, tmp_path):
    """Verify Design Cache:
    1. Reuses completed generation when all parameters, checksums, and skill version match.
    2. Misses when room image checksum changes.
    3. Misses when product reference image changes.
    4. Misses when skill version changes or candidate lacks skill metadata.
    5. Never caches REJECTED or FAILED candidates.
    """
    from app.services.design_generation_service import DesignGenerationService

    headers, project, catalog, best, lamp, mismatch, inactive = setup_recommendation_case(client, db_session)
    user_id = project["user_id"]

    room_file = tmp_path / "cache_room.png"
    room_file.write_bytes(make_test_png((600, 400), (220, 220, 220)))

    ref_file = tmp_path / "cache_ref.png"
    ref_file.write_bytes(make_test_png((300, 300), (120, 100, 80)))

    mock_prov = MockCloudflareProvider()
    svc = DesignGenerationService(db_session, mock_prov)
    prompt = "Base prompt test for cache"
    clean_prompt = prompt

    # 1. Create a successful cached generation with Skill Metadata V1
    meta = {
        "version": "1.0.0",
        "generation_status": "succeeded",
        "provenance": {
            "skill_version": "1.0.0",
            "room_image_checksum": svc._compute_checksum(room_file),
            "product_reference_checksums": [svc._compute_checksum(ref_file)],
        },
    }
    cand_prompt = f"[MODE: AI_PHOTOREALISTIC_PREVIEW] [STATUS: VERIFIED] {clean_prompt}\n\n[SKILL_METADATA_V1]\n"
    cand_prompt = serialize_skill_metadata(cand_prompt, meta)

    storage_service = GeneratedDesignStorageService()
    out_rel = f"test_cache_{project['id']}.png"
    out_file = storage_service.storage_root / out_rel
    out_file.write_bytes(make_test_png((600, 400), (200, 200, 200)))

    gen = RoomDesignGeneration(
        room_project_id=project["id"],
        user_id=user_id,
        status="COMPLETED",
        provider="cloudflare",
        model="@cf/black-forest-labs/flux-2-dev",
        prompt_version="v2",
        source_image_path=str(room_file),
        generated_image_path=out_rel,
        prompt=cand_prompt,
    )
    gen.products.append(best)
    db_session.add(gen)
    db_session.commit()

    # Case A: Cache Hit
    hit = svc._lookup_design_cache(
        user_id=user_id,
        project_id=project["id"],
        room_image_path=str(room_file),
        product_ids=[best.id],
        provider="cloudflare",
        model="@cf/black-forest-labs/flux-2-dev",
        prompt=cand_prompt,
        skill_version="1.0.0",
        reference_image_paths=[ref_file],
    )
    assert hit is not None
    assert hit.id == gen.id

    # Case B: Cache Miss on changed room image
    changed_room = tmp_path / "changed_room.png"
    changed_room.write_bytes(make_test_png((600, 400), (50, 50, 50)))
    miss_room = svc._lookup_design_cache(
        user_id=user_id,
        project_id=project["id"],
        room_image_path=str(changed_room),
        product_ids=[best.id],
        provider="cloudflare",
        model="@cf/black-forest-labs/flux-2-dev",
        prompt=cand_prompt,
        skill_version="1.0.0",
        reference_image_paths=[ref_file],
    )
    assert miss_room is None

    # Case C: Cache Miss on changed product reference
    changed_ref = tmp_path / "changed_ref.png"
    changed_ref.write_bytes(make_test_png((300, 300), (250, 250, 0)))
    miss_ref = svc._lookup_design_cache(
        user_id=user_id,
        project_id=project["id"],
        room_image_path=str(room_file),
        product_ids=[best.id],
        provider="cloudflare",
        model="@cf/black-forest-labs/flux-2-dev",
        prompt=cand_prompt,
        skill_version="1.0.0",
        reference_image_paths=[changed_ref],
    )
    assert miss_ref is None

    # Case D: Cache Miss on skill version change
    miss_ver = svc._lookup_design_cache(
        user_id=user_id,
        project_id=project["id"],
        room_image_path=str(room_file),
        product_ids=[best.id],
        provider="cloudflare",
        model="@cf/black-forest-labs/flux-2-dev",
        prompt=cand_prompt,
        skill_version="2.0.0",  # Different skill version
        reference_image_paths=[ref_file],
    )
    assert miss_ver is None

    # Case E: Never cache REJECTED candidate
    gen.prompt = f"[MODE: AI_PHOTOREALISTIC_PREVIEW] [STATUS: REJECTED] {clean_prompt}"
    db_session.commit()
    miss_rej = svc._lookup_design_cache(
        user_id=user_id,
        project_id=project["id"],
        room_image_path=str(room_file),
        product_ids=[best.id],
        provider="cloudflare",
        model="@cf/black-forest-labs/flux-2-dev",
        prompt=cand_prompt,
        skill_version="1.0.0",
        reference_image_paths=[ref_file],
    )
    assert miss_rej is None

