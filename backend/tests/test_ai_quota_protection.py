import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from PIL import Image

from app.ai.image.base import GeneratedImage, ImageProvider
from app.ai.image.factory import get_image_provider
from app.ai.vision.base import VisionAnalysis, VisionUsage
from app.ai.vision.factory import get_vision_provider
from app.core.config import settings
from app.core.security import get_password_hash
from app.main import app
from app.models.entities import (
    AIUsageLog,
    Cart,
    Category,
    Product,
    ProductStatus,
    Role,
    RoleName,
    RoomAnalysis,
    RoomDesignGeneration,
    RoomPreference,
    RoomProject,
    User,
    UserProfile,
)
from app.schemas.room_project import RoomAnalysisResult
from app.services.ai_quota_service import AIQuotaService


def make_png_bytes(size=(8, 8), color=(100, 150, 200)):
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


class MockGeminiVisionProvider:
    provider_name = "gemini"
    model_name = "gemini-3.6-flash"

    def __init__(self) -> None:
        self.calls = 0

    def analyze_room(self, image_path, content_type):
        self.calls += 1
        result = RoomAnalysisResult(
            room_type="bedroom",
            dominant_colors=[{"name": "blue", "hex": "#6496C8", "percentage": 80}],
            existing_objects=[{"name": "bed", "confidence": 0.95}],
            empty_areas=[],
            lighting={"type": "natural", "level": "high"},
            design_characteristics=["modern"],
            layout_summary="Modern blue bedroom.",
            confidence=0.92,
        )
        return VisionAnalysis(
            result=result,
            raw_response=result.model_dump(),
            usage=VisionUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.0001),
        )


class MockCloudflareImageProvider(ImageProvider):
    provider_name = "cloudflare"
    model_name = "flux-1-schnell"
    MAX_INPUT_IMAGES = 4

    def __init__(self) -> None:
        self.calls = 0

    def generate_design(self, source_image_path, prompt, reference_image_paths=None):
        self.calls += 1
        return GeneratedImage(
            data=make_png_bytes(size=(16, 16), color=(20, 180, 50)),
            content_type="image/png",
        )


def register_user(client, email="quota-user@example.com", name="Quota User"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": name},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_admin_token(client, db_session, email="quota-admin@example.com"):
    role = db_session.query(Role).filter(Role.name == RoleName.ADMIN).one()
    admin = User(
        email=email,
        full_name="Quota Admin",
        hashed_password=get_password_hash("Password123!"),
        role_id=role.id,
    )
    db_session.add(admin)
    db_session.flush()
    db_session.add(UserProfile(user_id=admin.id))
    db_session.add(Cart(user_id=admin.id))
    db_session.commit()
    login = client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def setup_sample_project(client, headers, title="Quota Test Room"):
    proj_resp = client.post("/api/room-projects", json={"title": title, "room_type": "bedroom"}, headers=headers)
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    upload_resp = client.post(
        f"/api/room-projects/{proj_id}/image",
        headers=headers,
        files={"file": ("room.png", make_png_bytes(), "image/png")},
    )
    assert upload_resp.status_code == 200
    return proj_id


def setup_catalog_product(db_session, name="Modern Bed", slug="modern-bed"):
    category = db_session.query(Category).filter(Category.slug == "bedding").first()
    if not category:
        category = Category(name="Bedding", slug="bedding", is_active=True)
        db_session.add(category)
        db_session.flush()

    product = Product(
        name=name,
        slug=slug,
        category_id=category.id,
        price=Decimal("500.00"),
        stock_quantity=10,
        status=ProductStatus.ACTIVE,
    )
    db_session.add(product)
    db_session.flush()

    # Create an isolated catalog image on disk for composite fallback tests
    from PIL import Image, ImageDraw
    from app.models.entities import ProductImage
    from app.services.storage_service import ProductImageStorageService
    storage = ProductImageStorageService()
    img_filename = f"{slug}.png"
    img_path = storage.storage_root / img_filename
    if not img_path.exists():
        im = Image.new("RGB", (200, 200), (255, 255, 255))
        d = ImageDraw.Draw(im)
        d.rectangle([60, 60, 140, 140], fill=(50, 100, 150))
        im.save(img_path, format="PNG")

    img = ProductImage(
        product_id=product.id,
        image_url=f"/storage/products/{img_filename}",
        is_primary=True,
        sort_order=0,
    )
    db_session.add(img)
    db_session.commit()
    return product


# -----------------------------------------------------------------------------
# Unit Tests
# -----------------------------------------------------------------------------


def test_ai_quota_service_direct_reservation_and_limits(db_session):
    """Kiểm tra trực tiếp các hàm nghiệp vụ của AIQuotaService."""
    quota_svc = AIQuotaService(db_session)
    role = db_session.query(Role).filter(Role.name == RoleName.CUSTOMER).first()
    user = User(email="direct-quota@example.com", full_name="Direct", hashed_password="pw", role_id=role.id if role else 1)
    db_session.add(user)
    db_session.flush()

    project = RoomProject(user_id=user.id, title="Direct Project", room_type="bedroom")
    db_session.add(project)
    db_session.flush()

    # 1. get_quota_limits
    gemini_u, gemini_s = quota_svc.get_quota_limits("gemini")
    assert gemini_u == settings.gemini_daily_user_limit
    assert gemini_s == settings.gemini_daily_system_limit

    # 2. get_daily_usage ban đầu là 0
    u_count, s_count = quota_svc.get_daily_usage(user.id, "gemini")
    assert u_count == 0
    assert s_count == 0

    # 3. reserve_quota thành công khi còn quota
    res1 = quota_svc.reserve_quota(user.id, project.id, "gemini", "gemini-3.6-flash", "ROOM_IMAGE_ANALYSIS")
    assert res1 is not None
    assert res1.status == "RESERVED"

    # Usage đếm cả RESERVED
    u_count, s_count = quota_svc.get_daily_usage(user.id, "gemini")
    assert u_count == 1
    assert s_count == 1

    # 4. finalize_success chuyển thành SUCCESS
    quota_svc.finalize_success(res1, latency_ms=120, total_tokens=150, estimated_cost=0.0001)
    assert res1.status == "SUCCESS"
    assert res1.latency_ms == 120

    # 5. release_reservation chuyển thành FAILED và giải phóng quota
    res2 = quota_svc.reserve_quota(user.id, project.id, "gemini", "gemini-3.6-flash", "ROOM_IMAGE_ANALYSIS")
    assert res2 is not None
    quota_svc.release_reservation(res2, error_code="MOCK_FAIL", error_message="Mock failure")
    assert res2.status == "FAILED"

    # Usage chỉ còn 1 (res1 đã SUCCESS, res2 đã FAILED)
    u_count, s_count = quota_svc.get_daily_usage(user.id, "gemini")
    assert u_count == 1


def test_ai_quota_service_concurrency_lock_and_stale_recovery(db_session):
    """Kiểm tra chống spam/gọi đồng thời và tự động dọn bản ghi treo quá hạn."""
    quota_svc = AIQuotaService(db_session)
    role = db_session.query(Role).filter(Role.name == RoleName.CUSTOMER).first()
    user = User(email="concurrency-user@example.com", full_name="Concurrency", hashed_password="pw", role_id=role.id if role else 1)
    db_session.add(user)
    db_session.flush()

    project = RoomProject(user_id=user.id, title="Concurrency Room", room_type="bedroom", status="DRAFT")
    db_session.add(project)
    db_session.flush()

    # Tạo bản ghi đang chạy ANALYZING
    analysis = RoomAnalysis(
        room_project_id=project.id,
        user_id=user.id,
        image_checksum="chk_concurrency",
        status="ANALYZING",
        provider="gemini",
        model="gemini-3.6-flash",
    )
    db_session.add(analysis)
    db_session.commit()

    # Request đồng thời bị chặn với HTTP 409 Conflict
    with pytest.raises(HTTPException) as exc_info:
        quota_svc.check_in_flight_concurrency(project.id, "ROOM_IMAGE_ANALYSIS")
    assert exc_info.value.status_code == 409
    assert "AI_ANALYSIS_IN_PROGRESS" in exc_info.value.detail

    # Giả lập bản ghi đã treo quá 300s (stale)
    analysis.created_at = datetime.now(UTC) - timedelta(seconds=350)
    db_session.commit()

    # Bản ghi cũ tự động bị thu hồi và cho phép request mới tiếp tục
    quota_svc.check_in_flight_concurrency(project.id, "ROOM_IMAGE_ANALYSIS")
    db_session.refresh(analysis)
    assert analysis.status == "FAILED"
    assert analysis.error_code == "STALE_ANALYSIS_TIMEOUT"


def test_gemini_user_daily_quota_limit_and_auto_fallback(client, db_session, monkeypatch):
    """Kiểm tra giới hạn 3 lượt/người/ngày của Gemini Vision: 3 lượt đầu qua Gemini, lượt thứ 4 tự chuyển Pillow Vision."""
    monkeypatch.setattr(settings, "gemini_daily_user_limit", 3)
    monkeypatch.setattr(settings, "enable_cloud_ai", True)

    mock_gemini = MockGeminiVisionProvider()
    app.dependency_overrides[get_vision_provider] = lambda: mock_gemini

    headers = register_user(client, email="gemini-quota-user@example.com")
    project_id = setup_sample_project(client, headers, "Gemini Quota Test")

    # Lượt 1, 2, 3: Gọi Gemini Cloud thành công
    for i in range(1, 4):
        p = db_session.query(RoomProject).filter(RoomProject.id == project_id).first()
        p.status = "READY"
        db_session.commit()

        resp = client.post(f"/api/room-projects/{project_id}/analyze?force=true", headers=headers)
        assert resp.status_code == 200, f"Lượt {i} thất bại: {resp.text}"
        body = resp.json()
        assert body["provider"] == "gemini", f"Lượt {i} phải dùng gemini"
        assert body["status"] == "COMPLETED"

    assert mock_gemini.calls == 3

    # Lượt 4: Vượt quá quota 3 lượt/ngày -> Tự động Fallback sang Pillow Vision offline
    p = db_session.query(RoomProject).filter(RoomProject.id == project_id).first()
    p.status = "READY"
    db_session.commit()

    resp4 = client.post(f"/api/room-projects/{project_id}/analyze?force=true", headers=headers)
    assert resp4.status_code == 200, f"Lượt 4 phải tự fallback thành công, status: {resp4.status_code}"
    body4 = resp4.json()
    assert body4["provider"] == "local_fallback"
    assert body4["model"] == "deterministic-v1"
    assert "[Chế độ Offline - QUOTA_EXCEEDED]" in body4["layout_summary"]
    # Mock Gemini không bị gọi thêm lần nào nữa (vẫn là 3)
    assert mock_gemini.calls == 3


def test_kill_switch_gemini_vision(client, db_session, monkeypatch):
    """Kiểm tra Emergency Kill Switch: ENABLE_CLOUD_AI=false ngăn gọi Gemini và chuyển ngay sang Pillow Vision."""
    monkeypatch.setattr(settings, "enable_cloud_ai", False)

    mock_gemini = MockGeminiVisionProvider()
    app.dependency_overrides[get_vision_provider] = lambda: mock_gemini

    headers = register_user(client, email="killswitch-vision-user@example.com")
    project_id = setup_sample_project(client, headers, "Kill Switch Vision Test")

    resp = client.post(f"/api/room-projects/{project_id}/analyze", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "local_fallback"
    assert "[Chế độ Offline - CLOUD_AI_DISABLED]" in body["layout_summary"]
    # Không gọi Gemini API
    assert mock_gemini.calls == 0


def test_kill_switch_design_generation(client, db_session, monkeypatch):
    """Kiểm tra Emergency Kill Switch: ENABLE_CLOUD_AI=false ngăn gọi Cloudflare và chuyển ngay sang Composite 2D."""
    monkeypatch.setattr(settings, "enable_cloud_ai", False)

    mock_cf = MockCloudflareImageProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    headers = register_user(client, email="killswitch-gen-user@example.com")
    project_id = setup_sample_project(client, headers, "Kill Switch Design Gen Test")

    project = db_session.query(RoomProject).filter(RoomProject.id == project_id).one()
    product = setup_catalog_product(db_session, name="KS Bed", slug="ks-bed")

    analysis = RoomAnalysis(
        room_project_id=project_id,
        user_id=project.user_id,
        image_checksum=project.image_checksum or "chk_ks",
        status="COMPLETED",
        provider="local_fallback",
        model="deterministic-v1",
        room_type="bedroom",
        confidence=Decimal("0.9"),
        dominant_colors=[{"name": "white", "hex": "#fff", "percentage": 100}],
        existing_objects=[],
    )
    pref = RoomPreference(
        room_project_id=project_id,
        user_id=project.user_id,
        budget_min=Decimal("100"),
        budget_max=Decimal("2000"),
    )
    db_session.add(analysis)
    db_session.add(pref)
    db_session.commit()

    resp = client.post(
        f"/api/room-projects/{project_id}/design-generations",
        json={"product_ids": [product.id]},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["provider"] == "composite"
    db_session.rollback()
    gen = db_session.get(RoomDesignGeneration, body["id"])
    assert gen is not None
    assert "[Chế độ Offline 2D - CLOUD_AI_DISABLED]" in gen.prompt
    assert mock_cf.calls == 0


def test_cloudflare_daily_quota_and_auto_fallback(client, db_session, monkeypatch):
    """Kiểm tra giới hạn 1 lượt/người/ngày tạo ảnh: Lượt 1 qua Cloudflare, lượt 2 tự chuyển Composite 2D."""
    monkeypatch.setattr(settings, "cloudflare_daily_user_limit", 1)
    monkeypatch.setattr(settings, "enable_cloud_ai", True)

    mock_cf = MockCloudflareImageProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    headers = register_user(client, email="cf-quota-user@example.com")
    project_id = setup_sample_project(client, headers, "CF Quota Test")

    project = db_session.query(RoomProject).filter(RoomProject.id == project_id).one()
    product = setup_catalog_product(db_session, name="CF Bed", slug="cf-bed")
    analysis = RoomAnalysis(
        room_project_id=project_id,
        user_id=project.user_id,
        image_checksum=project.image_checksum or "chk_cf",
        status="COMPLETED",
        provider="local_fallback",
        model="deterministic-v1",
        room_type="bedroom",
        confidence=Decimal("0.9"),
        dominant_colors=[{"name": "white", "hex": "#fff", "percentage": 100}],
        existing_objects=[],
    )
    pref = RoomPreference(
        room_project_id=project_id,
        user_id=project.user_id,
        budget_min=Decimal("100"),
        budget_max=Decimal("2000"),
    )
    db_session.add(analysis)
    db_session.add(pref)
    db_session.commit()

    # Lượt 1: Qua Cloudflare thành công
    resp1 = client.post(
        f"/api/room-projects/{project_id}/design-generations",
        json={"product_ids": [product.id], "force": True},
        headers=headers,
    )
    assert resp1.status_code == 201
    body1 = resp1.json()
    assert body1["provider"] == "cloudflare"
    assert mock_cf.calls == 1

    # Lượt 2: Vượt quá quota 1 lượt/ngày -> Tự động Fallback sang Composite 2D offline
    resp2 = client.post(
        f"/api/room-projects/{project_id}/design-generations",
        json={"product_ids": [product.id], "force": True},
        headers=headers,
    )
    assert resp2.status_code == 201
    body2 = resp2.json()
    assert body2["provider"] == "composite"
    db_session.rollback()
    gen2 = db_session.get(RoomDesignGeneration, body2["id"])
    assert gen2 is not None
    assert "[Chế độ Offline 2D - QUOTA_EXCEEDED]" in gen2.prompt
    # Mock Cloudflare không bị gọi thêm lần nữa
    assert mock_cf.calls == 1


def test_design_cache_reuse_and_bypass(client, db_session, monkeypatch):
    """Kiểm tra cache thiết kế: cùng ảnh phòng và danh sách sản phẩm thì tái sử dụng kết quả, không tiêu tốn quota."""
    monkeypatch.setattr(settings, "cloudflare_daily_user_limit", 10)
    monkeypatch.setattr(settings, "enable_cloud_ai", True)

    mock_cf = MockCloudflareImageProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    headers = register_user(client, email="cache-user@example.com")
    project_id = setup_sample_project(client, headers, "Cache Test Project")

    project = db_session.query(RoomProject).filter(RoomProject.id == project_id).one()
    product = setup_catalog_product(db_session, name="Cache Bed", slug="cache-bed")
    analysis = RoomAnalysis(
        room_project_id=project_id,
        user_id=project.user_id,
        image_checksum=project.image_checksum or "chk_cache",
        status="COMPLETED",
        provider="local_fallback",
        model="deterministic-v1",
        room_type="bedroom",
        confidence=Decimal("0.9"),
        dominant_colors=[{"name": "white", "hex": "#fff", "percentage": 100}],
        existing_objects=[],
    )
    pref = RoomPreference(
        room_project_id=project_id,
        user_id=project.user_id,
        budget_min=Decimal("100"),
        budget_max=Decimal("2000"),
    )
    db_session.add(analysis)
    db_session.add(pref)
    db_session.commit()

    # Lần 1: Tạo thiết kế mới (Cache Miss)
    resp1 = client.post(
        f"/api/room-projects/{project_id}/design-generations",
        json={"product_ids": [product.id]},
        headers=headers,
    )
    assert resp1.status_code == 201
    gen1 = resp1.json()
    assert mock_cf.calls == 1

    # Lần 2: Cùng ảnh, cùng sản phẩm -> Trả về kết quả Cache Hit, Cloudflare calls vẫn là 1
    resp2 = client.post(
        f"/api/room-projects/{project_id}/design-generations",
        json={"product_ids": [product.id]},
        headers=headers,
    )
    assert resp2.status_code == 201
    gen2 = resp2.json()
    assert gen2["id"] == gen1["id"]
    assert mock_cf.calls == 1

    # Lần 3: Dùng cờ force=True -> Bỏ qua Cache, Cloudflare calls tăng lên 2
    resp3 = client.post(
        f"/api/room-projects/{project_id}/design-generations",
        json={"product_ids": [product.id], "force": True},
        headers=headers,
    )
    assert resp3.status_code == 201
    gen3 = resp3.json()
    assert gen3["id"] != gen1["id"]
    assert mock_cf.calls == 2


def test_design_cache_isolated_between_users(client, db_session, monkeypatch):
    """Kiểm tra cách ly cache giữa các user: User B không thể truy cập hoặc dùng lén cache của User A."""
    monkeypatch.setattr(settings, "cloudflare_daily_user_limit", 10)
    monkeypatch.setattr(settings, "enable_cloud_ai", True)

    mock_cf = MockCloudflareImageProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    headers_a = register_user(client, email="user-a@example.com")
    headers_b = register_user(client, email="user-b@example.com")

    proj_a = setup_sample_project(client, headers_a, "Room A")
    proj_b = setup_sample_project(client, headers_b, "Room B")

    product = setup_catalog_product(db_session, name="Shared Catalog Bed", slug="shared-catalog-bed")

    for pid in (proj_a, proj_b):
        p = db_session.query(RoomProject).filter(RoomProject.id == pid).one()
        db_session.add(
            RoomAnalysis(
                room_project_id=pid,
                user_id=p.user_id,
                image_checksum=p.image_checksum or "chk_shared",
                status="COMPLETED",
                provider="local_fallback",
                model="deterministic-v1",
                room_type="bedroom",
                confidence=Decimal("0.9"),
                dominant_colors=[],
                existing_objects=[],
            )
        )
        db_session.add(
            RoomPreference(
                room_project_id=pid,
                user_id=p.user_id,
                budget_min=Decimal("100"),
                budget_max=Decimal("2000"),
            )
        )
    db_session.commit()

    # User A tạo thiết kế
    resp_a = client.post(f"/api/room-projects/{proj_a}/design-generations", json={"product_ids": [product.id]}, headers=headers_a)
    assert resp_a.status_code == 201
    gen_a = resp_a.json()
    assert mock_cf.calls == 1

    # User B tạo thiết kế với cùng sản phẩm -> KHÔNG được dùng cache của User A (mock_cf phải được gọi tiếp cho User B)
    resp_b = client.post(f"/api/room-projects/{proj_b}/design-generations", json={"product_ids": [product.id]}, headers=headers_b)
    assert resp_b.status_code == 201
    gen_b = resp_b.json()
    assert gen_b["id"] != gen_a["id"]
    assert mock_cf.calls == 2


def test_admin_ai_usage_endpoint_with_quota_metrics(client, db_session):
    """Kiểm tra API Admin /api/admin/ai-usage trả về đầy đủ các trường quota, status, fallback, và cost_disclaimer."""
    admin_headers = create_admin_token(client, db_session)

    resp = client.get("/api/admin/ai-usage", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    summary = data["summary"]
    assert summary["cloud_ai_enabled"] is True
    assert summary["gemini_daily_system_limit"] == settings.gemini_daily_system_limit
    assert summary["cloudflare_daily_system_limit"] == settings.cloudflare_daily_system_limit
    assert "gemini_system_quota_remaining" in summary
    assert "cloudflare_system_quota_remaining" in summary
    assert "today_gemini_calls" in summary
    assert "today_cloudflare_calls" in summary
    assert "local_fallback_calls" in summary
    assert "composite_fallback_calls" in summary
    assert "cost_disclaimer" in summary
    assert "chưa có dữ liệu billing thực tế" in summary["cost_disclaimer"]


# -----------------------------------------------------------------------------
# P0 / P1 / P2 Regression & Concurrency Tests
# -----------------------------------------------------------------------------


def test_concurrent_20_requests_race_condition(db_session, monkeypatch):
    """
    P0 Test: 20 request đồng thời tranh chấp đúng 1 quota còn lại.
    Sử dụng 20 DB connection/session thực tế qua ThreadPoolExecutor.
    Bảo đảm: Đúng 1 request đặt chỗ thành công, 19 request bị từ chối (None).
    """
    from concurrent.futures import ThreadPoolExecutor
    from tests.conftest import TestingSessionLocal

    monkeypatch.setattr(settings, "gemini_daily_user_limit", 1)
    monkeypatch.setattr(settings, "gemini_daily_system_limit", 50)
    monkeypatch.setattr(settings, "enable_cloud_ai", True)

    role = db_session.query(Role).filter(Role.name == RoleName.CUSTOMER).first()
    user = User(email="race-user@example.com", full_name="Race User", hashed_password="pw", role_id=role.id if role else 1)
    db_session.add(user)
    db_session.commit()

    project = RoomProject(user_id=user.id, title="Race Room", room_type="bedroom")
    db_session.add(project)
    db_session.commit()

    target_user_id = user.id
    target_project_id = project.id

    def attempt_reservation(thread_idx: int):
        thread_db = TestingSessionLocal()
        try:
            svc = AIQuotaService(thread_db)
            res = svc.reserve_quota(
                user_id=target_user_id,
                project_id=target_project_id,
                provider="gemini",
                model="gemini-3.6-flash",
                task_type="ROOM_IMAGE_ANALYSIS",
            )
            return res is not None
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(attempt_reservation, i) for i in range(20)]
        results = [f.result() for f in futures]

    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)

    assert successes == 1, f"Bắt buộc đúng 1 request thành công, thực tế có {successes} thành công!"
    assert failures == 19, f"Bắt buộc 19 request thất bại, thực tế có {failures} thất bại!"

    # Refresh snapshot của db_session để nhìn thấy commit từ các connection khác
    db_session.rollback()

    # Kiểm tra DB chỉ có đúng 1 bản ghi RESERVED
    count = db_session.query(AIUsageLog).filter(
        AIUsageLog.user_id == target_user_id,
        AIUsageLog.provider == "gemini",
        AIUsageLog.status == "RESERVED",
    ).count()
    assert count == 1


def test_concurrent_system_quota_across_multiple_users(db_session, monkeypatch):
    """
    P0 Test: 20 user khác nhau cùng gửi request khi Quota hệ thống chỉ còn 1 lượt.
    Bảo đảm: Đúng 1 user đặt chỗ thành công, 19 user khác bị từ chối do chạm trần system limit.
    """
    from concurrent.futures import ThreadPoolExecutor
    from tests.conftest import TestingSessionLocal

    monkeypatch.setattr(settings, "cloudflare_daily_user_limit", 10)
    monkeypatch.setattr(settings, "cloudflare_daily_system_limit", 1)
    monkeypatch.setattr(settings, "enable_cloud_ai", True)

    role = db_session.query(Role).filter(Role.name == RoleName.CUSTOMER).first()
    users = []
    projects = []
    for i in range(20):
        u = User(email=f"multi-user-{i}@example.com", full_name=f"User {i}", hashed_password="pw", role_id=role.id if role else 1)
        db_session.add(u)
        db_session.flush()
        p = RoomProject(user_id=u.id, title=f"Project {i}", room_type="bedroom")
        db_session.add(p)
        db_session.flush()
        users.append(u.id)
        projects.append(p.id)
    db_session.commit()

    target_users = list(users)
    target_projects = list(projects)

    def attempt_user_reservation(idx: int):
        thread_db = TestingSessionLocal()
        try:
            svc = AIQuotaService(thread_db)
            res = svc.reserve_quota(
                user_id=target_users[idx],
                project_id=target_projects[idx],
                provider="cloudflare",
                model="flux-1-schnell",
                task_type="ROOM_DESIGN_GENERATION",
            )
            return res is not None
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(attempt_user_reservation, i) for i in range(20)]
        results = [f.result() for f in futures]

    successes = sum(1 for r in results if r is True)
    assert successes == 1, f"Quota hệ thống là 1, nhưng có {successes} request vượt qua!"

    total_reserved = db_session.query(AIUsageLog).filter(
        AIUsageLog.provider == "cloudflare",
        AIUsageLog.status == "RESERVED",
    ).count()
    assert total_reserved == 1


def test_stale_recovery_and_fencing_token(client, db_session, monkeypatch):
    """
    P1 Test: Stale recovery thu hồi bản ghi treo quá 300s.
    Fencing token ngăn chặn request cũ khi chạy xong ghi đè trạng thái COMPLETED lên DB.
    """
    monkeypatch.setattr(settings, "enable_cloud_ai", True)
    headers = register_user(client, email="fencing-user@example.com")
    project_id = setup_sample_project(client, headers, "Fencing Room")
    project = db_session.query(RoomProject).filter(RoomProject.id == project_id).one()
    product = setup_catalog_product(db_session, name="Fencing Bed", slug="fencing-bed")

    # Tạo generation 1 đang chạy nhưng bị treo quá 350s (stale)
    gen1 = RoomDesignGeneration(
        room_project_id=project_id,
        user_id=project.user_id,
        status="GENERATING",
        provider="cloudflare",
        model="flux-1-schnell",
        prompt_version="v2",
        source_image_path=project.room_image_path,
        prompt="Initial prompt",
        products=[product],
    )
    gen1.created_at = datetime.now(UTC) - timedelta(seconds=350)
    db_session.add(gen1)
    db_session.commit()
    gen1_id = gen1.id

    # Request mới bay vào -> check_in_flight_concurrency thu hồi gen1 thành FAILED
    quota_svc = AIQuotaService(db_session)
    quota_svc.check_in_flight_concurrency(project_id, "ROOM_DESIGN_GENERATION")

    db_session.refresh(gen1)
    assert gen1.status == "FAILED"
    assert gen1.error_code == "STALE_GENERATION_TIMEOUT"

    # Bây giờ giả lập worker cũ của gen1 cuối cùng cũng nhận được ảnh từ Cloud AI (giây thứ 360)
    # Fencing token check: UPDATE ... WHERE id=gen1_id AND status='GENERATING'
    affected = (
        db_session.query(RoomDesignGeneration)
        .filter(
            RoomDesignGeneration.id == gen1_id,
            RoomDesignGeneration.status == "GENERATING",
        )
        .update({"status": "COMPLETED"})
    )
    db_session.commit()

    # Worker cũ bị chặn bởi fencing token check (0 rows affected)
    assert affected == 0
    db_session.refresh(gen1)
    # gen1 vẫn giữ nguyên trạng thái FAILED, tuyệt đối không bị ghi đè thành COMPLETED
    assert gen1.status == "FAILED"


def test_design_cache_miss_on_preference_change(client, db_session, monkeypatch):
    """
    P1 Test: Cache thiết kế phải phản ánh RoomPreference (Style/Color/Notes/Budget).
    Thay đổi sở thích phòng làm prompt thay đổi -> CACHE MISS và tạo ảnh mới.
    """
    monkeypatch.setattr(settings, "cloudflare_daily_user_limit", 10)
    monkeypatch.setattr(settings, "enable_cloud_ai", True)

    mock_cf = MockCloudflareImageProvider()
    app.dependency_overrides[get_image_provider] = lambda: mock_cf

    headers = register_user(client, email="pref-cache-user@example.com")
    project_id = setup_sample_project(client, headers, "Pref Cache Project")
    project = db_session.query(RoomProject).filter(RoomProject.id == project_id).one()
    product = setup_catalog_product(db_session, name="Pref Bed", slug="pref-bed")

    analysis = RoomAnalysis(
        room_project_id=project_id,
        user_id=project.user_id,
        image_checksum=project.image_checksum or "chk_pref",
        status="COMPLETED",
        provider="local_fallback",
        model="deterministic-v1",
        room_type="bedroom",
        confidence=Decimal("0.9"),
        dominant_colors=[],
        existing_objects=[],
    )
    pref = RoomPreference(
        room_project_id=project_id,
        user_id=project.user_id,
        notes="Phong cách tối giản minimalist",
        budget_min=Decimal("100"),
        budget_max=Decimal("2000"),
    )
    db_session.add(analysis)
    db_session.add(pref)
    db_session.commit()

    # Lần 1: Tạo thiết kế với phong cách "minimalist" (Cache Miss)
    resp1 = client.post(f"/api/room-projects/{project_id}/design-generations", json={"product_ids": [product.id]}, headers=headers)
    assert resp1.status_code == 201
    gen1 = resp1.json()
    assert mock_cf.calls == 1

    # Lần 2: Giữ nguyên preference -> Cache Hit (mock_cf vẫn là 1)
    resp2 = client.post(f"/api/room-projects/{project_id}/design-generations", json={"product_ids": [product.id]}, headers=headers)
    assert resp2.status_code == 201
    gen2 = resp2.json()
    assert gen2["id"] == gen1["id"]
    assert mock_cf.calls == 1

    # Lần 3: Người dùng thay đổi sở thích sang "vintage cổ điển"
    pref.notes = "Phong cách cổ điển vintage hoài niệm"
    db_session.commit()

    # Gọi tạo thiết kế với cùng sản phẩm -> Prompt thay đổi -> Cache MISS -> Gọi Cloudflare lần 2
    resp3 = client.post(f"/api/room-projects/{project_id}/design-generations", json={"product_ids": [product.id]}, headers=headers)
    assert resp3.status_code == 201
    gen3 = resp3.json()
    assert gen3["id"] != gen1["id"]
    assert mock_cf.calls == 2


def test_timeout_suspected_quota_accounting(client, db_session, monkeypatch):
    """
    P2 Test: Khi nhà cung cấp AI bị timeout không xác định:
    1. Đánh dấu reservation là TIMEOUT_SUSPECTED.
    2. Tính vào hạn mức an toàn của hệ thống (system_limit) để bảo vệ ngân sách.
    3. Không phạt người dùng (user_limit không bị trừ).
    4. Không tự động retry tạo ảnh trùng lặp.
    """
    monkeypatch.setattr(settings, "cloudflare_daily_user_limit", 5)
    monkeypatch.setattr(settings, "cloudflare_daily_system_limit", 10)
    monkeypatch.setattr(settings, "enable_cloud_ai", True)

    class TimeoutCloudflareProvider(ImageProvider):
        provider_name = "cloudflare"
        model_name = "flux-1-schnell"

        def generate_design(self, source_image_path, prompt, reference_image_paths=None):
            from app.ai.image.base import ImageProviderError
            raise ImageProviderError("CLOUDFLARE_IMAGE_REQUEST_FAILED", "Gateway timeout after 60 seconds")

    app.dependency_overrides[get_image_provider] = lambda: TimeoutCloudflareProvider()

    headers = register_user(client, email="timeout-user@example.com")
    project_id = setup_sample_project(client, headers, "Timeout Project")
    project = db_session.query(RoomProject).filter(RoomProject.id == project_id).one()
    product = setup_catalog_product(db_session, name="Timeout Bed", slug="timeout-bed")

    analysis = RoomAnalysis(
        room_project_id=project_id,
        user_id=project.user_id,
        image_checksum=project.image_checksum or "chk_timeout",
        status="COMPLETED",
        provider="local_fallback",
        model="deterministic-v1",
        room_type="bedroom",
        confidence=Decimal("0.9"),
        dominant_colors=[],
        existing_objects=[],
    )
    pref = RoomPreference(
        room_project_id=project_id,
        user_id=project.user_id,
        budget_min=Decimal("100"),
        budget_max=Decimal("2000"),
    )
    db_session.add(analysis)
    db_session.add(pref)
    db_session.commit()

    resp = client.post(f"/api/room-projects/{project_id}/design-generations", json={"product_ids": [product.id]}, headers=headers)
    assert resp.status_code == 504

    # Refresh snapshot của db_session để đọc dữ liệu mới commit từ client
    db_session.rollback()

    # Kiểm tra log usage có status TIMEOUT_SUSPECTED
    quota_svc = AIQuotaService(db_session)
    u_count, s_count = quota_svc.get_daily_usage(project.user_id, "cloudflare")
    # System limit tính lượt timeout này để bảo vệ ngân sách
    assert s_count == 1
    # User limit không bị phạt
    assert u_count == 0

    log = db_session.query(AIUsageLog).filter(
        AIUsageLog.user_id == project.user_id,
        AIUsageLog.provider == "cloudflare",
    ).first()
    assert log is not None
    assert log.status == "TIMEOUT_SUSPECTED"
