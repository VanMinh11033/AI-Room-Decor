from io import BytesIO
import pytest
from PIL import Image
from app.core.config import settings

from app.ai.vision.base import VisionAnalysis, VisionProviderError, VisionUsage
from app.ai.vision.fallback_provider import LocalFallbackProvider
from app.ai.vision.factory import get_vision_provider
from app.main import app
from app.models.entities import AIUsageLog, RoomAnalysis
from app.schemas.room_project import RoomAnalysisResult


def make_png_bytes(size=(8, 8), color=(200, 30, 30)):
    buf = BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


class SuccessVisionProvider:
    provider_name = "gemini"
    model_name = "gemini-3.6-flash"

    def __init__(self) -> None:
        self.calls = 0

    def analyze_room(self, image_path, content_type):
        self.calls += 1
        result = RoomAnalysisResult(
            room_type="bedroom",
            dominant_colors=[{"name": "white", "hex": "#FFFFFF", "percentage": 60}],
            existing_objects=[{"name": "bed", "confidence": 0.95}],
            empty_areas=[],
            lighting={"type": "natural", "level": "medium"},
            design_characteristics=["minimal"],
            layout_summary="A bedroom.",
            confidence=0.9,
        )
        return VisionAnalysis(result=result, raw_response=result.model_dump(), usage=VisionUsage(input_tokens=10, output_tokens=20, total_tokens=30))


class ErrorVisionProvider:
    provider_name = "gemini"
    model_name = "gemini-3.6-flash"

    def __init__(self, code: str, message: str, **kwargs) -> None:
        self.code = code
        self.message = message
        self.kwargs = kwargs
        self.calls = 0

    def analyze_room(self, image_path, content_type):
        self.calls += 1
        raise VisionProviderError(self.code, self.message, **self.kwargs)


def auth_headers(client, email="fallback-user@example.com"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Fallback User"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_project(client, headers, title="Fallback Bedroom"):
    response = client.post("/api/room-projects", json={"title": title, "room_type": "bedroom"}, headers=headers)
    assert response.status_code == 201
    return response.json()


def upload_png(client, headers, project_id):
    response = client.post(
        f"/api/room-projects/{project_id}/image",
        headers=headers,
        files={"file": ("room.png", make_png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    return response


@pytest.mark.skipif(not settings.enable_cloud_ai, reason="Yêu cầu ENABLE_CLOUD_AI=true (chế độ Cloud AI Gemini)")
def test_gemini_success_does_not_fallback(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    upload_png(client, headers, project["id"])
    app.dependency_overrides[get_vision_provider] = lambda: SuccessVisionProvider()

    response = client.post(f"/api/room-projects/{project['id']}/analyze", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "gemini"
    assert body["model"] == "gemini-3.6-flash"
    fallback_logs = db_session.query(AIUsageLog).filter(AIUsageLog.provider == "local_fallback").count()
    assert fallback_logs == 0


@pytest.mark.skipif(not settings.enable_cloud_ai, reason="Yêu cầu ENABLE_CLOUD_AI=true (chế độ Cloud AI Gemini)")
def test_unavailable_falls_back_and_completes(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    upload_png(client, headers, project["id"])
    app.dependency_overrides[get_vision_provider] = lambda: ErrorVisionProvider(
        "GEMINI_PROVIDER_UNAVAILABLE", "503 UNAVAILABLE. This model is currently experiencing high demand.", transient=True, status_code=503
    )

    response = client.post(f"/api/room-projects/{project['id']}/analyze", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["provider"] == "local_fallback"
    assert body["model"] == "deterministic-v1"
    assert body["existing_objects"] == []
    assert body["error_code"] is None

    logs = db_session.query(AIUsageLog).filter(AIUsageLog.room_project_id == project["id"]).all()
    gemini_log = next(log for log in logs if log.provider == "gemini")
    fallback_log = next(log for log in logs if log.provider == "local_fallback")
    assert gemini_log.status == "FAILED"
    assert gemini_log.error_code == "GEMINI_PROVIDER_UNAVAILABLE"
    assert fallback_log.status == "SUCCESS"
    assert fallback_log.total_tokens == 0


@pytest.mark.skipif(not settings.enable_cloud_ai, reason="Yêu cầu ENABLE_CLOUD_AI=true (chế độ Cloud AI Gemini)")
def test_quota_error_falls_back(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    upload_png(client, headers, project["id"])
    app.dependency_overrides[get_vision_provider] = lambda: ErrorVisionProvider(
        "GEMINI_PROVIDER_QUOTA_ERROR", "429 RESOURCE_EXHAUSTED", status_code=429
    )

    response = client.post(f"/api/room-projects/{project['id']}/analyze", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["provider"] == "local_fallback"
    assert body["model"] == "deterministic-v1"
    assert body["existing_objects"] == []

    gemini_log = db_session.query(AIUsageLog).filter(AIUsageLog.provider == "gemini").one()
    fallback_log = db_session.query(AIUsageLog).filter(AIUsageLog.provider == "local_fallback").one()
    assert gemini_log.status == "FAILED"
    assert gemini_log.error_code == "GEMINI_PROVIDER_QUOTA_ERROR"
    assert fallback_log.status == "SUCCESS"
    assert fallback_log.total_tokens == 0


@pytest.mark.skipif(not settings.enable_cloud_ai, reason="Yêu cầu ENABLE_CLOUD_AI=true (chế độ Cloud AI Gemini)")
def test_auth_error_does_not_fallback(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    upload_png(client, headers, project["id"])
    app.dependency_overrides[get_vision_provider] = lambda: ErrorVisionProvider(
        "GEMINI_PROVIDER_AUTH_ERROR", "API key not valid.", status_code=401
    )

    response = client.post(f"/api/room-projects/{project['id']}/analyze", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"] == "GEMINI_PROVIDER_AUTH_ERROR"
    assert db_session.query(RoomAnalysis).filter(RoomAnalysis.provider == "local_fallback").count() == 0


@pytest.mark.skipif(not settings.enable_cloud_ai, reason="Yêu cầu ENABLE_CLOUD_AI=true (chế độ Cloud AI Gemini)")
def test_model_error_does_not_fallback(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    upload_png(client, headers, project["id"])
    app.dependency_overrides[get_vision_provider] = lambda: ErrorVisionProvider(
        "GEMINI_PROVIDER_MODEL_ERROR", "models/gemini-9.9-flash is not found.", status_code=404
    )

    response = client.post(f"/api/room-projects/{project['id']}/analyze", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"] == "GEMINI_PROVIDER_MODEL_ERROR"
    assert db_session.query(RoomAnalysis).filter(RoomAnalysis.provider == "local_fallback").count() == 0


def test_fallback_makes_no_external_call_and_invents_no_objects(tmp_path):
    image_path = tmp_path / "room.png"
    image_path.write_bytes(make_png_bytes())
    provider = LocalFallbackProvider(room_type="bedroom")

    analysis = provider.analyze_room(image_path, "image/png")

    assert provider.provider_name == "local_fallback"
    assert provider.model_name == "deterministic-v1"
    assert analysis.result.existing_objects == []
    assert analysis.result.empty_areas == []
    assert analysis.result.lighting is None
    assert analysis.result.design_characteristics == []
    assert analysis.usage.total_tokens == 0
    assert analysis.raw_response["fallback"] is True


@pytest.mark.skipif(not settings.enable_cloud_ai, reason="Yêu cầu ENABLE_CLOUD_AI=true (chế độ Cloud AI Gemini)")
def test_force_reattempts_gemini_after_fallback(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    upload_png(client, headers, project["id"])
    app.dependency_overrides[get_vision_provider] = lambda: ErrorVisionProvider(
        "GEMINI_PROVIDER_UNAVAILABLE", "503 UNAVAILABLE high demand", transient=True, status_code=503
    )

    first = client.post(f"/api/room-projects/{project['id']}/analyze", headers=headers)
    assert first.status_code == 200
    assert first.json()["provider"] == "local_fallback"

    success = SuccessVisionProvider()
    app.dependency_overrides[get_vision_provider] = lambda: success
    second = client.post(f"/api/room-projects/{project['id']}/analyze?force=true", headers=headers)

    assert second.status_code == 200
    assert second.json()["provider"] == "gemini"
    assert success.calls == 1

    db_session.rollback()
    newest = (
        db_session.query(RoomAnalysis)
        .filter(RoomAnalysis.room_project_id == project["id"])
        .order_by(RoomAnalysis.id.desc())
        .first()
    )
    assert newest.provider == "gemini"
    assert newest.status == "COMPLETED"


def test_fallback_real_room_image_full_analysis(tmp_path):
    # Test on a realistic sized image (128x128)
    image_path = tmp_path / "real_room.png"
    buf = BytesIO()
    # Create an image with top bright (light) and bottom floor (tan/wood)
    im = Image.new("RGB", (128, 128), color=(240, 238, 230))
    # Draw floor at the bottom
    for y in range(80, 128):
        for x in range(128):
            im.putpixel((x, y), (180, 140, 100))
    im.save(buf, format="PNG")
    image_path.write_bytes(buf.getvalue())

    provider = LocalFallbackProvider(room_type="living-room", fallback_reason="LOCAL_MODE")
    analysis = provider.analyze_room(image_path, "image/png")

    assert provider.provider_name == "local_fallback"
    assert analysis.result.room_type == "Phòng khách"
    assert len(analysis.result.dominant_colors) > 0
    assert analysis.result.lighting is not None
    assert analysis.result.lighting.type.startswith("Tự nhiên")
    assert len(analysis.result.empty_areas) >= 2
    assert len(analysis.result.existing_objects) >= 3
    assert "khung nhìn" in analysis.result.layout_summary
    assert analysis.raw_response["fallback"] is True
    assert analysis.raw_response["reason"] == "LOCAL_MODE"

