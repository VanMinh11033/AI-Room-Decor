import io
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw
import pytest

from app.ai.image.base import GeneratedImage
from app.ai.image.factory import get_image_provider
from app.ai.skill_bridge import (
    QualityEvaluator,
    build_skill_manifest,
    build_skill_prompt,
    parse_skill_metadata,
)
from app.core.config import settings
from app.main import app
from app.models.entities import Category, Product, ProductImage, RoomDesignGeneration, RoomProject
from app.services.storage_service import ProductImageStorageService, RoomImageStorageService
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


class TrackingMockCloudflareProvider:
    provider_name = "cloudflare"
    model_name = "@cf/black-forest-labs/flux-2-dev"
    MAX_INPUT_IMAGES = 4

    def __init__(self):
        self.call_count = 0
        self.last_source_path = None
        self.last_prompt = None
        self.last_reference_paths = None
        self.last_categories = None

    def generate_design(
        self,
        source_image_path: Path,
        prompt: str,
        reference_image_paths=None,
        reference_categories=None,
    ) -> GeneratedImage:
        self.call_count += 1
        self.last_source_path = source_image_path
        self.last_prompt = prompt
        self.last_reference_paths = reference_image_paths
        self.last_categories = reference_categories
        return GeneratedImage(
            data=make_test_png((800, 600), (200, 210, 220)),
            content_type="image/png",
        )


def _setup_products_for_ordering(client, db_session):
    headers, project, _catalog, _p1, _p2, _mismatch, _inactive = setup_recommendation_case(client, db_session)

    def ensure_category(slug, name):
        cat = db_session.query(Category).filter(Category.slug == slug).first()
        if not cat:
            cat = Category(name=name, slug=slug, is_active=True)
            db_session.add(cat)
            db_session.commit()
            db_session.refresh(cat)
        return cat

    cat_sofa = ensure_category("sofa", "Sofa")
    cat_chair = ensure_category("chair", "Chair")
    cat_table = ensure_category("table", "Table")
    cat_lighting = ensure_category("lighting", "Lighting")
    cat_accessories = ensure_category("accessories", "Accessories")

    def ensure_product(prod_id, name, slug, category):
        prod = db_session.get(Product, prod_id)
        if prod is None:
            prod = Product(
                id=prod_id,
                name=name,
                slug=slug,
                category_id=category.id,
                price=1_500_000,
                is_active=True,
            )
            db_session.add(prod)
            db_session.commit()
            db_session.refresh(prod)
        else:
            prod.category_id = category.id
            db_session.commit()
        return prod

    p1 = ensure_product(1, "Japandi Low Sofa", "japandi-low-sofa", cat_sofa)
    p3 = ensure_product(3, "Minimalist Lounge Chair", "minimalist-lounge-chair", cat_chair)
    p5 = ensure_product(5, "Round Oak Coffee Table", "round-oak-coffee-table", cat_table)
    p9 = ensure_product(9, "Brass Floor Lamp", "brass-floor-lamp", cat_lighting)
    p21 = ensure_product(21, "Potted Monstera Deliciosa", "monstera-deliciosa-ceramic-pot", cat_accessories)

    # Set up room storage
    room_storage = RoomImageStorageService()
    room_rel_path = Path(str(project["user_id"])) / str(project["id"]) / "manifest_test_room.png"
    room_abs_path = room_storage.storage_root / room_rel_path
    room_abs_path.parent.mkdir(parents=True, exist_ok=True)
    room_abs_path.write_bytes(make_test_png((800, 600), (230, 225, 215)))

    room_proj = db_session.get(RoomProject, project["id"])
    room_proj.room_image_url = f"/storage/rooms/{project['user_id']}/{project['id']}/manifest_test_room.png"
    room_proj.room_image_path = str(room_rel_path).replace("\\", "/")
    room_proj.status = "COMPLETED"

    prod_storage = ProductImageStorageService()
    for prod in [p1, p3, p5, p9, p21]:
        prod_fname = f"{prod.id}_{prod.slug}.png"
        prod_abs = prod_storage.storage_root / prod_fname
        prod_abs.parent.mkdir(parents=True, exist_ok=True)
        prod_abs.write_bytes(make_isolated_product_png())

        prod_img = db_session.query(ProductImage).filter(ProductImage.product_id == prod.id).first()
        if prod_img:
            prod_img.image_url = f"/storage/products/{prod_fname}"
        else:
            db_session.add(ProductImage(product_id=prod.id, image_url=f"/storage/products/{prod_fname}", is_primary=True, sort_order=0))

    db_session.commit()
    return headers, project, {1: p1, 3: p3, 5: p5, 9: p9, 21: p21}


@pytest.mark.parametrize(
    "input_ids",
    [
        [3, 5, 21],
        [5, 3, 21],
        [21, 3, 5],
        [1, 9],
        [9, 1],
    ],
)
def test_reference_manifest_synchronization_across_permutations(client, db_session, input_ids):
    """Verify that for ANY product selection order:
    1. An ordered reference manifest is the single source of truth.
    2. In the prompt sent to Cloudflare, Image N strictly corresponds to Provider payload Image N.
    3. Product ID in Image N prompt matches the actual image file path in provider payload.
    4. Database generation record references products in the exact manifest order.
    5. Prompt contains strict inventory, scene lock, and realistic scale rules.
    """
    headers, project, prods = _setup_products_for_ordering(client, db_session)

    mock_cf = TrackingMockCloudflareProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    try:
        with patch.object(settings, "room_decor_skill_enabled", True), \
             patch.object(settings, "enable_cloud_ai", True):
            res = client.post(
                f"/api/room-projects/{project['id']}/design-generations",
                json={
                    "product_ids": input_ids,
                    "selection_mode": "MANUAL",
                    "generation_mode": "AI_PHOTOREALISTIC_PREVIEW",
                    "force": True,
                },
                headers=headers,
            )
            assert res.status_code == 201, res.text
            data = res.json()

            assert mock_cf.call_count == 1
            sent_prompt = mock_cf.last_prompt
            sent_refs = mock_cf.last_reference_paths
            assert sent_refs is not None
            assert len(sent_refs) == len(input_ids)

            # Check that prompt contains the strict inventory & scene lock rules
            assert "Architecture Lock" in sent_prompt
            assert "Strict Catalog Inventory (Zero Hallucination)" in sent_prompt
            assert "Physical Proportion & Realistic Scale" in sent_prompt
            assert "existing background elements" in sent_prompt
            assert "vases, flowers, tabletop decor" in sent_prompt

            # Extract Image N lines from prompt: e.g. "- Image 1 (Product #5 / Product ID 5): ..."
            image_lines = re.findall(r"Image (\d+) \(Product #(\d+)", sent_prompt)
            assert len(image_lines) == len(input_ids), f"Expected {len(input_ids)} Image references in prompt, found {image_lines}"

            for idx_str, pid_str in image_lines:
                idx = int(idx_str)
                pid = int(pid_str)

                # Reference index idx in prompt corresponds to sent_refs[idx - 1]
                ref_path = sent_refs[idx - 1]
                ref_filename = Path(ref_path).name

                # The file sent as reference image [idx - 1] MUST belong to product pid!
                # Our files are named e.g. "5_round-oak-coffee-table.png" or "{slug}.png"
                expected_prod = prods[pid]
                assert str(pid) in ref_filename or expected_prod.slug in ref_filename, (
                    f"Desynchronization bug detected! Prompt claims Image {idx} is Product #{pid}, "
                    f"but provider reference file at position {idx-1} is '{ref_filename}'"
                )

            # Verify database record metadata and product IDs order
            db_session.rollback()
            db_gen = db_session.get(RoomDesignGeneration, data["id"])
            assert db_gen is not None
            _cleaned, meta = parse_skill_metadata(db_gen.prompt)
            assert meta is not None

            # Manifest product IDs in meta.referenced_product_ids must match the ordered prompt
            prompt_pids = [int(p[1]) for p in image_lines]
            assert meta.referenced_product_ids == prompt_pids
            assert set(p.id for p in db_gen.products) == set(prompt_pids)

    finally:
        app.dependency_overrides.clear()


def test_quality_evaluation_needs_review_contract():
    """Verify that high Quality Score does NOT auto-verify or bypass human review for diffusion output."""
    evaluator = QualityEvaluator(threshold=85.0)

    # Even with an 8-step evaluation on mock bytes, diffusion mode must yield NEEDS_REVIEW
    # and not be equated to 100% SKU precision
    buf = io.BytesIO()
    img = Image.new("RGB", (400, 300), color=(200, 200, 200))
    img.save(buf, format="PNG")
    dummy_bytes = buf.getvalue()

    result = evaluator.evaluate(
        source_room_path=Path("dummy_room.png"),
        candidate_image_bytes=dummy_bytes,
        selected_product_ids=[1, 9],
        reference_image_paths=[],
        is_composite_mode=False,
    )

    # In diffusion preview mode (not composite), status must remain NEEDS_REVIEW
    # (or rejected if hard gates fail), NEVER auto-pass to VERIFIED
    assert result.generation_status in ("needs_review", "rejected")
    assert result.generation_status != "verified"
