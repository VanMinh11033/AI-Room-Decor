from pathlib import Path

from app.ai.vision.base import VisionAnalysis, VisionProviderError, VisionUsage
from app.ai.vision.factory import get_vision_provider
from app.main import app
from app.models.entities import AIUsageLog, RoomAnalysis, RoomProject
from app.schemas.room_project import RoomAnalysisResult


PNG_BYTES = b"\x89PNG\r\n\x1a\nvalid-test-image"


class FakeVisionProvider:
    provider_name = "fake_test"
    model_name = "fake-vision-model"

    def __init__(self) -> None:
        self.calls = 0

    def analyze_room(self, image_path: Path, content_type: str) -> VisionAnalysis:
        self.calls += 1
        assert image_path.exists()
        assert content_type == "image/png"
        result = RoomAnalysisResult(
            room_type="bedroom",
            dominant_colors=[{"name": "white", "hex": "#FFFFFF", "percentage": 60}],
            existing_objects=[{"name": "bed", "confidence": 0.95}],
            empty_areas=[{"location": "wall above bed", "description": "Open wall", "suitable_for_decor": True}],
            lighting={"type": "natural", "level": "medium"},
            design_characteristics=["minimal", "neutral"],
            layout_summary="A compact bedroom with a clear wall for decor.",
            confidence=0.9,
        )
        return VisionAnalysis(result=result, raw_response=result.model_dump(), usage=VisionUsage(input_tokens=10, output_tokens=20, total_tokens=30))


class FailingVisionProvider(FakeVisionProvider):
    provider_name = "failing_test"

    def analyze_room(self, image_path: Path, content_type: str) -> VisionAnalysis:
        raise VisionProviderError("VISION_PROVIDER_FAILED", "Provider failed")


def auth_headers(client, email="room-user@example.com"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Room User"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_project(client, headers, title="My Bedroom"):
    response = client.post("/api/room-projects", json={"title": title, "room_type": "bedroom"}, headers=headers)
    assert response.status_code == 201
    return response.json()


def upload_image(client, headers, project_id, filename="room.png", content=PNG_BYTES, content_type="image/png"):
    return client.post(
        f"/api/room-projects/{project_id}/image",
        headers=headers,
        files={"file": (filename, content, content_type)},
    )


def test_create_list_and_view_own_room_projects(client):
    headers = auth_headers(client)
    project = create_project(client, headers)

    listed = client.get("/api/room-projects", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == project["id"]

    detail = client.get(f"/api/room-projects/{project['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["title"] == "My Bedroom"


def test_room_project_ownership_is_enforced(client):
    owner_headers = auth_headers(client, "owner@example.com")
    other_headers = auth_headers(client, "other@example.com")
    project = create_project(client, owner_headers)

    detail = client.get(f"/api/room-projects/{project['id']}", headers=other_headers)
    upload = upload_image(client, other_headers, project["id"])
    analyze = client.post(f"/api/room-projects/{project['id']}/analyze", headers=other_headers)

    assert detail.status_code == 404
    assert upload.status_code == 404
    assert analyze.status_code == 404


def test_valid_room_image_upload_and_invalid_file_rejection(client):
    headers = auth_headers(client)
    project = create_project(client, headers)

    upload = upload_image(client, headers, project["id"])
    assert upload.status_code == 200
    payload = upload.json()
    assert payload["status"] == "UPLOADED"
    assert payload["room_image_url"].startswith("/storage/rooms/")
    assert payload["image_content_type"] == "image/png"
    assert payload["image_size_bytes"] == len(PNG_BYTES)

    invalid = upload_image(client, headers, project["id"], filename="bad.txt", content=b"not image", content_type="text/plain")
    assert invalid.status_code == 400


def test_analyze_saves_structured_result_and_uses_cache(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    assert upload_image(client, headers, project["id"]).status_code == 200
    provider = FakeVisionProvider()
    app.dependency_overrides[get_vision_provider] = lambda: provider

    first = client.post(f"/api/room-projects/{project['id']}/analyze", headers=headers)
    assert first.status_code == 200
    result = first.json()
    assert result["status"] == "COMPLETED"
    assert result["room_type"] == "bedroom"
    assert result["dominant_colors"][0]["hex"] == "#FFFFFF"
    assert result["existing_objects"][0]["name"] == "bed"
    assert result["lighting"]["level"] == "medium"

    second = client.post(f"/api/room-projects/{project['id']}/analyze", headers=headers)
    assert second.status_code == 200
    assert second.json()["id"] == result["id"]
    assert provider.calls == 1

    stored = db_session.query(RoomAnalysis).filter(RoomAnalysis.id == result["id"]).one()
    assert stored.status == "COMPLETED"
    usage = db_session.query(AIUsageLog).filter(AIUsageLog.room_project_id == project["id"]).one()
    assert usage.task_type == "ROOM_IMAGE_ANALYSIS"
    assert usage.total_tokens == 30


def test_ai_provider_not_configured_is_not_faked(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    assert upload_image(client, headers, project["id"]).status_code == 200

    response = client.post(f"/api/room-projects/{project['id']}/analyze", headers=headers)
    assert response.status_code == 503
    assert response.json()["detail"] == "AI_PROVIDER_NOT_CONFIGURED"

    usage = db_session.query(AIUsageLog).filter(AIUsageLog.room_project_id == project["id"]).one()
    assert usage.status == "FAILED"
    assert usage.error_code == "AI_PROVIDER_NOT_CONFIGURED"


def test_ai_provider_failure_is_saved(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    assert upload_image(client, headers, project["id"]).status_code == 200
    app.dependency_overrides[get_vision_provider] = lambda: FailingVisionProvider()

    response = client.post(f"/api/room-projects/{project['id']}/analyze", headers=headers)
    assert response.status_code == 503
    assert response.json()["detail"] == "VISION_PROVIDER_FAILED"

    failed = db_session.query(RoomAnalysis).filter(RoomAnalysis.room_project_id == project["id"]).one()
    assert failed.status == "FAILED"
    assert failed.user_id == project["user_id"]


def test_failed_room_analysis_with_null_result_lists_serializes(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    assert upload_image(client, headers, project["id"]).status_code == 200
    db_session.rollback()
    stored_project = db_session.get(RoomProject, project["id"])
    analysis = RoomAnalysis(
        room_project_id=project["id"],
        user_id=project["user_id"],
        image_checksum=stored_project.image_checksum,
        status="FAILED",
        provider="gemini",
        model="gemini-2.5-flash",
        error_code="GEMINI_PROVIDER_REQUEST_FAILED",
        error_message="safe test failure",
    )
    db_session.add(analysis)
    db_session.commit()

    response = client.get(f"/api/room-projects/{project['id']}/analysis", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["dominant_colors"] == []
    assert body["existing_objects"] == []
    assert body["empty_areas"] == []
    assert body["design_characteristics"] == []


def test_failed_room_analysis_can_retry_to_completed(client, db_session):
    headers = auth_headers(client)
    project = create_project(client, headers)
    assert upload_image(client, headers, project["id"]).status_code == 200
    app.dependency_overrides[get_vision_provider] = lambda: FailingVisionProvider()

    failed = client.post(f"/api/room-projects/{project['id']}/analyze", headers=headers)
    assert failed.status_code == 503

    provider = FakeVisionProvider()
    app.dependency_overrides[get_vision_provider] = lambda: provider
    retried = client.post(f"/api/room-projects/{project['id']}/analyze?force=true", headers=headers)

    assert retried.status_code == 200
    assert retried.json()["status"] == "COMPLETED"
    assert provider.calls == 1
    db_session.rollback()
    statuses = [row.status for row in db_session.query(RoomAnalysis).filter(RoomAnalysis.room_project_id == project["id"]).order_by(RoomAnalysis.id).all()]
    assert statuses == ["FAILED", "COMPLETED"]


def test_room_project_requires_authentication(client):
    response = client.get("/api/room-projects")
    assert response.status_code == 401
