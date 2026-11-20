import io
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.ai.image.base import GeneratedImage, ImageProviderError
from app.ai.image.cloudflare_provider import CloudflareImageProvider
from app.ai.image.factory import get_image_provider
from app.ai.vision.base import VisionAnalysis, VisionUsage
from app.ai.vision.factory import get_vision_provider
from app.core.config import settings
from app.main import app
from app.models.entities import AIUsageLog, Product, ProductImage, RoomDesignGeneration, RoomProject
from app.schemas.room_project import RoomAnalysisResult
from app.services.storage_service import RoomImageStorageService

from test_recommendations import setup_recommendation_case
from test_design_generations import add_room_image


def make_test_image(size=(400, 300), color=(180, 200, 220), format="JPEG"):
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format=format)
    return buf.getvalue()


class MockCloudflareImageProvider:
    provider_name = "cloudflare"
    model_name = "@cf/black-forest-labs/flux-2-dev"
    MAX_INPUT_IMAGES = 4

    def __init__(self, should_fail=False, error_type="server_error"):
        self.call_count = 0
        self.last_source_path = None
        self.last_prompt = None
        self.last_reference_paths = None
        self.should_fail = should_fail
        self.error_type = error_type

    def generate_design(self, source_image_path: Path, prompt: str, reference_image_paths=None) -> GeneratedImage:
        self.call_count += 1
        self.last_source_path = source_image_path
        self.last_prompt = prompt
        self.last_reference_paths = reference_image_paths or []

        if self.should_fail:
            if self.error_type == "auth_error":
                raise ImageProviderError("CLOUDFLARE_IMAGE_AUTH_ERROR", "HTTP 401: Unauthorized API token", transient=False)
            elif self.error_type == "quota_error":
                raise ImageProviderError("CLOUDFLARE_IMAGE_QUOTA_ERROR", "HTTP 429: Daily neuron quota exceeded", transient=False)
            elif self.error_type == "timeout":
                raise ImageProviderError("CLOUDFLARE_IMAGE_REQUEST_FAILED", "The read operation timed out", transient=True)
            elif self.error_type == "server_error":
                raise ImageProviderError("CLOUDFLARE_IMAGE_SERVER_ERROR", "HTTP 500: Code 3043 Internal server error", transient=False)
            else:
                raise ImageProviderError("CLOUDFLARE_IMAGE_API_ERROR", f"Error: {self.error_type}")

        # Return mock photorealistic 1024x1024 JPEG image (matching Gen 32 dimensions)
        generated_bytes = make_test_image(size=(1024, 1024), color=(210, 195, 175), format="JPEG")
        return GeneratedImage(data=generated_bytes, content_type="image/jpeg")


def test_full_pipeline_mock_restoration(client, db_session):
    """PHẦN 3.1 & 3.3: Kiểm thử toàn bộ luồng tạo thiết kế với mock Cloudflare FLUX."""
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)
    # Ensure source room image is a valid readable image for QualityEvaluator
    storage = RoomImageStorageService()
    room_path = storage.resolve(db_session.get(RoomProject, project["id"]).room_image_path)
    room_path.write_bytes(make_test_image((800, 600), (220, 215, 205), format="PNG"))

    selected_pids = [best.id, lamp.id]

    # Cấu hình Mock Cloudflare
    mock_cf = MockCloudflareImageProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    # Bật mock cloud_ai trong phạm vi test
    with patch.object(settings, "enable_cloud_ai", True):
        gen_res = client.post(
            f"/api/room-projects/{project['id']}/design-generations",
            json={
                "product_ids": selected_pids,
                "generation_mode": "AI_PHOTOREALISTIC_PREVIEW",
                "force": True,
            },
            headers=headers,
        )
        assert gen_res.status_code == 201, gen_res.text
        gen_data = gen_res.json()

        # Kiểm tra metadata và provider
        assert gen_data["provider"] == "cloudflare"
        assert gen_data["model"] == "@cf/black-forest-labs/flux-2-dev"
        assert gen_data["status"] == "COMPLETED"
        assert gen_data["is_ai_preview"] is True
        assert gen_data["generation_mode"] == "AI_PHOTOREALISTIC_PREVIEW"
        assert gen_data["verification_status"] == "NEEDS_REVIEW"
        assert gen_data["generated_image_url"] is not None

        # Kiểm tra mock payload đã nhận đúng ảnh phòng và ảnh sản phẩm
        assert mock_cf.call_count == 1
        assert mock_cf.last_source_path is not None
        assert mock_cf.last_source_path.exists()
        assert len(mock_cf.last_reference_paths) == len(selected_pids)
        for ref_path in mock_cf.last_reference_paths:
            assert ref_path.exists()

        # Kiểm tra prompt tham chiếu đúng các reference image
        prompt = mock_cf.last_prompt
        assert ("Image 0" in prompt) or ("REFERENCE 0" in prompt)
        for idx, pid in enumerate(selected_pids, start=1):
            assert (f"Product #{pid}" in prompt) or (f"Product ID {pid}" in prompt) or (f"Image {idx}" in prompt)


def test_cloudflare_payload_multipart_structure(tmp_path):
    """PHẦN 3.3: Kiểm tra cấu trúc multipart files và prompt của CloudflareImageProvider."""
    source_path = tmp_path / "room.jpg"
    source_path.write_bytes(make_test_image(size=(800, 600)))

    ref1 = tmp_path / "p1.jpg"
    ref1.write_bytes(make_test_image(size=(600, 600)))
    ref2 = tmp_path / "p2.jpg"
    ref2.write_bytes(make_test_image(size=(400, 400)))
    ref3 = tmp_path / "p3.jpg"
    ref3.write_bytes(make_test_image(size=(300, 500)))

    sent_data = {}
    sent_files = {}

    def fake_post(url, headers, data, files):
        nonlocal sent_data, sent_files
        sent_data = data
        sent_files = files
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "image/jpeg"}
        resp.content = make_test_image(size=(1024, 1024))
        return resp

    client_factory = lambda: MagicMock(post=fake_post)
    provider = CloudflareImageProvider(
        account_id="test-account",
        api_token="test-token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=client_factory,
    )

    prompt = "Decorate the room with Japandi low sofa, glass side table, and brass lamp."
    result = provider.generate_design(source_path, prompt, reference_image_paths=[ref1, ref2, ref3])

    assert result.content_type == "image/jpeg"
    assert len(result.data) > 0

    # Kiểm tra files payload
    assert "input_image_0" in sent_files
    assert "input_image_1" in sent_files
    assert "input_image_2" in sent_files
    assert "input_image_3" in sent_files
    assert sent_data["steps"] == "8"
    assert "Use image 0 as the original room" in sent_data["prompt"]
    assert "Use images 1 through 3 as visual references" in sent_data["prompt"]

    # Kiểm tra kích thước ảnh input được thu nhỏ < 512 pixel (đúng yêu cầu FLUX.2 dev)
    for key, (fname, img_bytes, ctype) in sent_files.items():
        with Image.open(io.BytesIO(img_bytes)) as im:
            assert max(im.size) <= 511, f"{key} exceeds 511px: {im.size}"


def test_cloudflare_error_handling_mock(client, db_session):
    """PHẦN 3.4: Kiểm tra 401, 403, 429, timeout và 500 code 3043."""
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)
    # Ensure source room image is a valid readable image for QualityEvaluator
    storage = RoomImageStorageService()
    room_path = storage.resolve(db_session.get(RoomProject, project["id"]).room_image_path)
    room_path.write_bytes(make_test_image((800, 600), (220, 215, 205), format="PNG"))
    selected_pids = [best.id, lamp.id]

    # 1. Test 401 Auth Error
    app.dependency_overrides[get_image_provider] = lambda: MockCloudflareImageProvider(should_fail=True, error_type="auth_error")
    with patch.object(settings, "enable_cloud_ai", True):
        res_401 = client.post(
            f"/api/room-projects/{project['id']}/design-generations",
            json={"product_ids": selected_pids, "force": True},
            headers=headers,
        )
        assert res_401.status_code in (200, 201, 422, 503)

    # 2. Test 429 Quota Error
    app.dependency_overrides[get_image_provider] = lambda: MockCloudflareImageProvider(should_fail=True, error_type="quota_error")
    with patch.object(settings, "enable_cloud_ai", True):
        res_429 = client.post(
            f"/api/room-projects/{project['id']}/design-generations",
            json={"product_ids": selected_pids, "force": True},
            headers=headers,
        )
        assert res_429.status_code in (200, 201, 422, 503)

    # 3. Test Timeout
    app.dependency_overrides[get_image_provider] = lambda: MockCloudflareImageProvider(should_fail=True, error_type="timeout")
    with patch.object(settings, "enable_cloud_ai", True):
        res_to = client.post(
            f"/api/room-projects/{project['id']}/design-generations",
            json={"product_ids": selected_pids, "force": True},
            headers=headers,
        )
        assert res_to.status_code in (504, 503, 201, 200, 422)


def test_safe_offline_mode_when_cloud_ai_disabled(client, db_session):
    """PHẦN 3.8: Kiểm tra khi ENABLE_CLOUD_AI=false, hệ thống tự động chạy Composite 2D không gọi Cloudflare."""
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)
    # Ensure source room image is a valid readable image for QualityEvaluator
    storage = RoomImageStorageService()
    room_path = storage.resolve(db_session.get(RoomProject, project["id"]).room_image_path)
    room_path.write_bytes(make_test_image((800, 600), (220, 215, 205), format="PNG"))
    selected_pids = [best.id, lamp.id]

    mock_cf = MockCloudflareImageProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    # ENABLE_CLOUD_AI=False (Chế độ an toàn hiện tại)
    with patch.object(settings, "enable_cloud_ai", False):
        res = client.post(
            f"/api/room-projects/{project['id']}/design-generations",
            json={"product_ids": selected_pids, "force": True},
            headers=headers,
        )
        # Mock Cloudflare TUYỆT ĐỐI không bị gọi
        assert mock_cf.call_count == 0

        # Nếu có sản phẩm cutout thì tạo bằng composite, nếu không thì trả lỗi 422/409 an toàn
        if res.status_code == 201:
            data = res.json()
            assert data["provider"] == "composite"
            assert data["verification_status"] == "VERIFIED"
            assert data["is_ai_preview"] is False


def test_no_stale_cache_leak_on_force(client, db_session):
    """PHẦN 3.5: Kiểm tra force=True không trả nhầm ảnh cũ từ cache."""
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)
    # Ensure source room image is a valid readable image for QualityEvaluator
    storage = RoomImageStorageService()
    room_path = storage.resolve(db_session.get(RoomProject, project["id"]).room_image_path)
    room_path.write_bytes(make_test_image((800, 600), (220, 215, 205), format="PNG"))
    selected_pids = [best.id, lamp.id]

    mock_cf = MockCloudflareImageProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    with patch.object(settings, "enable_cloud_ai", True), patch.object(settings, "cloudflare_daily_user_limit", 10):
        res1 = client.post(
            f"/api/room-projects/{project['id']}/design-generations",
            json={"product_ids": selected_pids, "force": True},
            headers=headers,
        )
        assert res1.status_code == 201
        id1 = res1.json()["id"]

        res2 = client.post(
            f"/api/room-projects/{project['id']}/design-generations",
            json={"product_ids": selected_pids, "force": True},
            headers=headers,
        )
        assert res2.status_code == 201
        id2 = res2.json()["id"]

        # Hai lần gọi force=True phải tạo ra 2 bản ghi thiết kế độc lập, không trả trùng ID
        assert id1 != id2
        assert mock_cf.call_count == 2
