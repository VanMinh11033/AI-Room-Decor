import io
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
import pytest
from app.ai.image.base import GeneratedImage
from app.ai.image.factory import get_image_provider
from app.core.config import settings
from app.main import app
from app.models.entities import ProductImage, RoomProject
from app.services.storage_service import ProductImageStorageService, RoomImageStorageService
from test_recommendations import setup_recommendation_case


def make_valid_png(size=(400, 300), color=(200, 220, 240)):
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


def setup_valid_room_and_product_images(db_session, project_id, user_id, best_product):
    # 1. Valid room image
    room_storage = RoomImageStorageService()
    room_rel_path = Path(str(user_id)) / str(project_id) / "valid_room.png"
    room_abs_path = room_storage.storage_root / room_rel_path
    room_abs_path.parent.mkdir(parents=True, exist_ok=True)
    room_abs_path.write_bytes(make_valid_png((600, 400), (240, 235, 225)))

    room_proj = db_session.get(RoomProject, project_id)
    room_proj.room_image_url = f"/storage/rooms/{user_id}/{project_id}/valid_room.png"
    room_proj.room_image_path = str(room_rel_path).replace("\\", "/")
    room_proj.status = "COMPLETED"

    # 2. Valid isolated product image for composite
    prod_storage = ProductImageStorageService()
    prod_fname = f"{best_product.slug}.png"
    prod_abs_path = prod_storage.storage_root / prod_fname
    prod_abs_path.parent.mkdir(parents=True, exist_ok=True)
    prod_abs_path.write_bytes(make_isolated_product_png())

    prod_img = db_session.query(ProductImage).filter(ProductImage.product_id == best_product.id).first()
    if prod_img:
        prod_img.image_url = f"/storage/products/{prod_fname}"
    else:
        db_session.add(ProductImage(product_id=best_product.id, image_url=f"/storage/products/{prod_fname}", is_primary=True, sort_order=0))

    db_session.commit()


class MockCloudflareImageProvider:
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
        Image.new("RGB", (1024, 1024), color=(220, 200, 180)).save(buf, format="JPEG")
        return GeneratedImage(data=buf.getvalue(), content_type="image/jpeg")


def test_project_end_to_end_mock_cloudflare_flow(client, db_session):
    """Kiểm tra end-to-end:
    1. Chọn mode AI_PHOTOREALISTIC_PREVIEW -> Gọi đúng Cloudflare mock, không chuyển sang Composite.
    2. Product IDs và catalog references được lấy động từ dự án (Product ID và reference images thật).
    3. Lưu đúng Generation ID mới, provider cloudflare, model @cf/black-forest-labs/flux-2-dev.
    4. Gán đúng is_ai_preview=True, generation_mode=AI_PHOTOREALISTIC_PREVIEW, verification_status=NEEDS_REVIEW.
    5. Chọn mode CATALOG_ACCURATE -> Gọi đúng Composite Engine, verification_status=VERIFIED.
    """
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    setup_valid_room_and_product_images(db_session, project["id"], project["user_id"], best)
    selected_ids = [best.id]

    mock_cf = MockCloudflareImageProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    try:
        # TEST 1: Cloudflare FLUX mode
        with patch.object(settings, "enable_cloud_ai", True):
            res = client.post(
                f"/api/room-projects/{project['id']}/design-generations",
                json={
                    "product_ids": selected_ids,
                    "generation_mode": "AI_PHOTOREALISTIC_PREVIEW",
                    "force": True,
                },
                headers=headers,
            )
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            data = res.json()

            # 1. Kiểm tra provider và model
            assert data["provider"] == "cloudflare", f"Expected cloudflare, got {data['provider']}"
            assert data["model"] == "@cf/black-forest-labs/flux-2-dev"
            assert data["generation_mode"] == "AI_PHOTOREALISTIC_PREVIEW"
            assert data["is_ai_preview"] is True
            assert data["verification_status"] == "NEEDS_REVIEW"
            assert data["status"] == "COMPLETED"
            assert data["generated_image_url"] is not None

            # 2. Kiểm tra Cloudflare mock được gọi đúng 1 lần
            assert mock_cf.call_count == 1
            assert mock_cf.last_source_path is not None
            assert len(mock_cf.last_reference_paths) == len(selected_ids)

            # 3. Kiểm tra sản phẩm tham chiếu là từ dự án thực tế, không hardcode
            prompt = mock_cf.last_prompt
            for pid in selected_ids:
                assert f"Product ID {pid}" in prompt

            gen_id_cloudflare = data["id"]
            print(f"\n[PASS] Cloudflare Generation ID: {gen_id_cloudflare}, status={data['status']}, verification={data['verification_status']}")

        # TEST 2: Composite Engine mode (Catalog Accurate)
        res_comp = client.post(
            f"/api/room-projects/{project['id']}/design-generations",
            json={
                "product_ids": selected_ids,
                "generation_mode": "CATALOG_ACCURATE",
                "force": True,
            },
            headers=headers,
        )
        assert res_comp.status_code == 201, f"Expected 201, got {res_comp.status_code}: {res_comp.text}"
        data_comp = res_comp.json()
        assert data_comp["provider"] == "composite"
        assert data_comp["generation_mode"] == "CATALOG_ACCURATE"
        assert data_comp["is_ai_preview"] is False
        assert data_comp["verification_status"] == "VERIFIED"
        gen_id_comp = data_comp["id"]
        print(f"[PASS] Composite Generation ID: {gen_id_comp}, provider={data_comp['provider']}, verification={data_comp['verification_status']}")

        # Đảm bảo 2 generation ID khác nhau
        assert gen_id_cloudflare != gen_id_comp

    finally:
        app.dependency_overrides.pop(get_image_provider, None)
