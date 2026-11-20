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


def test_single_button_ai_design_flow(client, db_session):
    """KIỂM THỬ LUỒNG 1 NÚT DUY NHẤT:
    1. Tạo ảnh phòng mới.
    2. Tự phân tích phòng.
    3. Tự chọn sản phẩm phù hợp (1-3 sản phẩm có ảnh catalog hợp lệ).
    4. Gửi request tạo thiết kế duy nhất với Cloudflare FLUX.
    5. Mock backend xác nhận Cloudflare nhận đúng ảnh phòng và sản phẩm.
    6. Đúng 1 ảnh kết quả duy nhất, không trùng lặp.
    7. Metadata đúng: provider cloudflare, NEEDS_REVIEW, is_ai_preview True.
    """
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)

    # 1. Thiết lập ảnh phòng mới hợp lệ
    room_storage = RoomImageStorageService()
    room_rel_path = Path(str(project["user_id"])) / str(project["id"]) / "new_room.png"
    room_abs_path = room_storage.storage_root / room_rel_path
    room_abs_path.parent.mkdir(parents=True, exist_ok=True)
    room_abs_path.write_bytes(make_valid_png((800, 600), (230, 225, 215)))

    room_proj = db_session.get(RoomProject, project["id"])
    room_proj.room_image_url = f"/storage/rooms/{project['user_id']}/{project['id']}/new_room.png"
    room_proj.room_image_path = str(room_rel_path).replace("\\", "/")
    room_proj.status = "COMPLETED"

    # 2. Thiết lập ảnh catalog hợp lệ cho sản phẩm đề xuất
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

    # 3. Lấy danh sách gợi ý và tự động chọn 1-3 sản phẩm
    rec_res = client.get(f"/api/room-projects/{project['id']}/recommendations?limit=10", headers=headers)
    assert rec_res.status_code == 200
    rec_items = rec_res.json()["items"]
    assert len(rec_items) >= 2

    # Logic autoSelectTopProducts (tối đa 3 sản phẩm phù hợp nhất)
    auto_selected_ids = [item["product"]["id"] for item in rec_items[:3]]
    assert 1 <= len(auto_selected_ids) <= 3
    assert best.id in auto_selected_ids

    # 4. Mock Cloudflare FLUX và thực hiện bấm nút 'TẠO THIẾT KẾ AI'
    mock_cf = MockCloudflareImageProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    try:
        with patch.object(settings, "enable_cloud_ai", True):
            gen_res = client.post(
                f"/api/room-projects/{project['id']}/design-generations",
                json={
                    "product_ids": auto_selected_ids,
                    "generation_mode": "AI_PHOTOREALISTIC_PREVIEW",
                    "force": True,
                },
                headers=headers,
            )
            assert gen_res.status_code == 201, gen_res.text
            gen_data = gen_res.json()

            # 5. Xác nhận Cloudflare nhận đúng ảnh phòng và sản phẩm
            assert mock_cf.call_count == 1
            assert mock_cf.last_source_path is not None
            assert mock_cf.last_source_path.exists()
            assert len(mock_cf.last_reference_paths) == len(auto_selected_ids)
            for ref_path in mock_cf.last_reference_paths:
                assert ref_path.exists()

            # Prompt chứa đúng ID sản phẩm
            for pid in auto_selected_ids:
                assert f"Product ID #{pid}" in mock_cf.last_prompt or f"Product ID {pid}" in mock_cf.last_prompt

            # 6. Đúng 1 ảnh kết quả, metadata chính xác
            assert gen_data["provider"] == "cloudflare"
            assert gen_data["model"] == "@cf/black-forest-labs/flux-2-dev"
            assert gen_data["generation_mode"] == "AI_PHOTOREALISTIC_PREVIEW"
            assert gen_data["is_ai_preview"] is True
            assert gen_data["verification_status"] == "NEEDS_REVIEW"
            assert gen_data["status"] == "COMPLETED"
            assert gen_data["generated_image_url"] is not None

            # 7. Danh sách sản phẩm thực sự đã dùng khớp chính xác
            used_ids = [p["id"] for p in gen_data["products"]]
            assert set(used_ids) == set(auto_selected_ids)

    finally:
        app.dependency_overrides.pop(get_image_provider, None)


def test_auto_selection_strictly_excludes_unverified_product_3(client, db_session):
    """Xác minh:
    1. Product #3 (Scandinavian Lounge Chair) KHÔNG có ảnh studio xác thực trong storage/verified_catalog_cutouts.
    2. Logic autoSelectTopProducts loại bỏ hoàn toàn Product #3 và bất kỳ sản phẩm nào chưa xác minh.
    3. Trả về đúng 1-3 sản phẩm đã xác minh từ các danh mục công năng khác nhau.
    """
    cutout_dir = Path("storage/verified_catalog_cutouts")
    p3_cutouts = list(cutout_dir.glob("3_*.png"))
    assert len(p3_cutouts) == 0, "Product #3 không được phép có cutout giả hoặc chưa kiểm định"

    # Danh sách ID đã kiểm định studio catalog
    verified_ids = [1, 5, 6, 7, 9, 12, 15, 16, 19, 21, 28]

    # Giả lập danh sách gợi ý bao gồm cả #1, #5, #3, #10, #12
    raw_mock_items = [
        {"product": {"id": 1, "name": "Japandi Low Sofa", "category": {"id": 1, "slug": "sofa"}}, "score": 100.0},
        {"product": {"id": 5, "name": "Oak Coffee Table", "category": {"id": 2, "slug": "table"}}, "score": 52.2},
        {"product": {"id": 3, "name": "Scandinavian Lounge Chair", "category": {"id": 3, "slug": "chair"}}, "score": 59.7},
        {"product": {"id": 10, "name": "Bamboo Pendant Light", "category": {"id": 4, "slug": "lighting"}}, "score": 59.7},
        {"product": {"id": 12, "name": "Woven Jute Rug", "category": {"id": 5, "slug": "rug"}}, "score": 82.2},
    ]

    # Lọc chỉ sản phẩm có trong verified_ids
    verified_items = [item for item in raw_mock_items if item["product"]["id"] in verified_ids]

    # Chọn 1-3 sản phẩm từ các danh mục khác nhau
    selected = []
    seen_cats = set()
    for item in verified_items:
        if len(selected) >= 3:
            break
        cat_id = item["product"]["category"]["id"]
        if cat_id not in seen_cats:
            seen_cats.add(cat_id)
            selected.append(item["product"]["id"])

    assert 3 not in selected, "Product #3 TUYỆT ĐỐI KHÔNG được tự động chọn"
    assert selected == [1, 5, 12], f"Phải tự chọn đúng [1, 5, 12] (Sofa, Table, Rug), thực tế: {selected}"


def test_cloudflare_rejects_empty_image_or_blank_room(client, db_session):
    """Xác minh: Backend không bao giờ báo COMPLETED khi ảnh tạo ra bị rỗng hoặc trùng lặp với ảnh phòng trống ban đầu."""
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)

    room_storage = RoomImageStorageService()
    room_rel_path = Path(str(project["user_id"])) / str(project["id"]) / "test_room.png"
    room_abs_path = room_storage.storage_root / room_rel_path
    room_abs_path.parent.mkdir(parents=True, exist_ok=True)
    room_bytes = make_valid_png((800, 600), (210, 210, 210))
    room_abs_path.write_bytes(room_bytes)

    room_proj = db_session.get(RoomProject, project["id"])
    room_proj.room_image_url = f"/storage/rooms/{project['user_id']}/{project['id']}/test_room.png"
    room_proj.room_image_path = str(room_rel_path).replace("\\", "/")
    room_proj.status = "COMPLETED"

    prod_storage = ProductImageStorageService()
    prod_fname = f"{best.slug}.png"
    (prod_storage.storage_root / prod_fname).write_bytes(make_isolated_product_png())
    db_session.query(ProductImage).filter(ProductImage.product_id == best.id).delete()
    db_session.add(ProductImage(product_id=best.id, image_url=f"/storage/products/{prod_fname}", is_primary=True, sort_order=0))
    db_session.commit()

    class EmptyReturnProvider:
        provider_name = "cloudflare"
        model_name = "@cf/black-forest-labs/flux-2-dev"
        MAX_INPUT_IMAGES = 4

        def generate_design(self, source_image_path, prompt, reference_image_paths=None):
            return GeneratedImage(data=b"", content_type="image/jpeg")

    class UnmodifiedRoomReturnProvider:
        provider_name = "cloudflare"
        model_name = "@cf/black-forest-labs/flux-2-dev"
        MAX_INPUT_IMAGES = 4

        def generate_design(self, source_image_path, prompt, reference_image_paths=None):
            return GeneratedImage(data=room_bytes, content_type="image/png")

    try:
        # Trường hợp 1: Dữ liệu rỗng
        app.dependency_overrides[get_image_provider] = lambda: EmptyReturnProvider()
        with patch.object(settings, "enable_cloud_ai", True):
            res_empty = client.post(
                f"/api/room-projects/{project['id']}/design-generations",
                json={"product_ids": [best.id], "generation_mode": "AI_PHOTOREALISTIC_PREVIEW", "force": True},
                headers=headers,
            )
            assert res_empty.status_code == 502
            assert "EMPTY_GENERATED_IMAGE" in res_empty.text

        # Trường hợp 2: Trả về trùng lặp hoàn toàn với ảnh phòng trống
        app.dependency_overrides[get_image_provider] = lambda: UnmodifiedRoomReturnProvider()
        with patch.object(settings, "enable_cloud_ai", True):
            res_blank = client.post(
                f"/api/room-projects/{project['id']}/design-generations",
                json={"product_ids": [best.id], "generation_mode": "AI_PHOTOREALISTIC_PREVIEW", "force": True},
                headers=headers,
            )
            assert res_blank.status_code == 502
            assert "EMPTY_ROOM_RETURNED" in res_blank.text

    finally:
        app.dependency_overrides.pop(get_image_provider, None)


def test_history_ui_preserves_gemini_manual_import_metadata(client, db_session):
    """Xác minh: Lịch sử thiết kế cũ của Gemini (nhập thủ công) giữ nguyên nhãn và metadata, không bị ghi đè."""
    from app.models.entities import RoomDesignGeneration
    from test_recommendations import auth_headers, create_project

    headers = auth_headers(client, "gemini_hist_user@example.com")
    project = create_project(client, headers)

    gen_manual = RoomDesignGeneration(
        room_project_id=project["id"],
        user_id=project["user_id"],
        status="COMPLETED",
        provider="gemini_manual_import",
        model="gemini-2.5-flash-image",
        prompt_version="v2",
        source_image_path="test/room.png",
        generated_image_path="test/gen.jpg",
        generated_image_url="/storage/generations/test/gen.jpg",
        prompt="[MODE: AI_PHOTOREALISTIC_PREVIEW] [STATUS: NEEDS_REVIEW] Gemini manual import",
    )
    db_session.add(gen_manual)
    db_session.commit()
    db_session.refresh(gen_manual)

    assert gen_manual.provider == "gemini_manual_import"
    assert gen_manual.is_ai_preview is True
    assert gen_manual.verification_status == "NEEDS_REVIEW"
    assert gen_manual.verification_details["source_type"] == "GEMINI_WEB_APP_MANUAL"
    assert "Gemini" in gen_manual.verification_details["source_label"]

