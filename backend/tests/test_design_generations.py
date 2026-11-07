import logging
from pathlib import Path

from app.ai.image.base import GeneratedImage, ImageProviderError, ImageGenerationUsage
from app.ai.image.factory import get_image_provider
from app.models.entities import AIUsageLog, RoomDesignGeneration, RoomProject
from app.services.storage_service import GeneratedDesignStorageService, RoomImageStorageService
from test_recommendations import auth_headers, create_project, setup_recommendation_case

PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


class FakeImageProvider:
    provider_name = "fake_image"
    model_name = "fake-image-model"
    MAX_INPUT_IMAGES = 4

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_design(self, source_image_path: Path, prompt: str, reference_image_paths=None) -> GeneratedImage:
        self.calls.append({"source": str(source_image_path), "prompt": prompt, "references": list(reference_image_paths or [])})
        return GeneratedImage(
            data=PNG_BYTES,
            content_type="image/png",
            usage=ImageGenerationUsage(input_tokens=11, output_tokens=22, total_tokens=33, estimated_cost=0),
        )


class FailingImageProvider(FakeImageProvider):
    def generate_design(self, source_image_path: Path, prompt: str, reference_image_paths=None) -> GeneratedImage:
        self.calls.append({"source": str(source_image_path), "prompt": prompt, "references": list(reference_image_paths or [])})
        raise ImageProviderError("IMAGE_PROVIDER_TEST_FAILURE", "Test provider failed")


class CrashingImageProvider(FakeImageProvider):
    def generate_design(self, source_image_path: Path, prompt: str, reference_image_paths=None) -> GeneratedImage:
        self.calls.append({"source": str(source_image_path), "prompt": prompt, "references": list(reference_image_paths or [])})
        raise RuntimeError("Simulated unexpected crash during image generation with secret Bearer secret-token-12345")


class LeakingTokenImageProvider(FakeImageProvider):
    def generate_design(self, source_image_path: Path, prompt: str, reference_image_paths=None) -> GeneratedImage:
        self.calls.append({"source": str(source_image_path), "prompt": prompt, "references": list(reference_image_paths or [])})
        raise ImageProviderError(
            "IMAGE_PROVIDER_LEAKY_FAILURE",
            "Provider failed with Bearer secret-provider-token-999 and key=AIzaSyFakeKey1234567890",
        )


def add_room_image(db_session, project: dict) -> None:
    storage = RoomImageStorageService()
    relative_path = Path(str(project["user_id"])) / str(project["id"]) / "source.png"
    absolute_path = storage.storage_root / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(PNG_BYTES)

    room_project = db_session.get(RoomProject, project["id"])
    room_project.room_image_url = f"/storage/rooms/{project['user_id']}/{project['id']}/source.png"
    room_project.room_image_path = str(relative_path).replace("\\", "/")
    room_project.image_original_filename = "source.png"
    room_project.image_content_type = "image/png"
    room_project.image_size_bytes = len(PNG_BYTES)
    room_project.image_checksum = "phase6checksum"
    room_project.status = "COMPLETED"
    db_session.commit()


def override_image_provider(app, provider):
    app.dependency_overrides[get_image_provider] = lambda: provider


def test_create_design_generation_uses_recommended_real_products(client, db_session):
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
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["provider"] == "fake_image"
    assert body["generated_image_url"].startswith("/storage/generated-room-designs/")
    assert [product["id"] for product in body["products"]] == [best.id, lamp.id]
    assert len(provider.calls) == 1
    assert str(best.id) in provider.calls[0]["prompt"]
    db_session.rollback()
    assert db_session.query(RoomDesignGeneration).count() == 1


def test_design_generation_history_and_latest_are_persistent(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    first = client.post(f"/api/room-projects/{project['id']}/design-generations", json={"product_ids": [best.id]}, headers=headers)
    second = client.post(f"/api/room-projects/{project['id']}/design-generations", json={"product_ids": [lamp.id]}, headers=headers)
    history = client.get(f"/api/room-projects/{project['id']}/design-generations", headers=headers)
    latest = client.get(f"/api/room-projects/{project['id']}/design-generations/latest", headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert history.status_code == 200
    assert history.json()["total"] == 2
    assert latest.status_code == 200
    assert latest.json()["id"] == second.json()["id"]


def test_design_generation_get_requires_owner(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)
    created = client.post(f"/api/room-projects/{project['id']}/design-generations", json={"product_ids": [best.id]}, headers=headers)
    other_headers = auth_headers(client, "design-other@example.com")

    response = client.get(
        f"/api/room-projects/{project['id']}/design-generations/{created.json()['id']}",
        headers=other_headers,
    )

    assert created.status_code == 201
    assert response.status_code == 404


def test_design_generation_rejects_invalid_and_not_recommended_products(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    invalid = client.post(f"/api/room-projects/{project['id']}/design-generations", json={"product_ids": [999999]}, headers=headers)
    not_recommended = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id, mismatch.id]},
        headers=headers,
    )
    duplicate = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id, best.id]},
        headers=headers,
    )

    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "INVALID_PRODUCT_IDS"
    assert not_recommended.status_code == 400
    assert not_recommended.json()["detail"] == "PRODUCT_NOT_RECOMMENDED"
    assert duplicate.status_code == 422
    assert len(provider.calls) == 0


def test_design_generation_requires_source_image(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)

    response = client.post(f"/api/room-projects/{project['id']}/design-generations", json={"product_ids": [best.id]}, headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "ROOM_IMAGE_REQUIRED"
    assert len(provider.calls) == 0


def test_gemini_design_generation_rejects_selected_product_without_readable_reference(client, db_session):
    provider = FakeImageProvider()
    provider.provider_name = "gemini"
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)
    best.images[0].image_url = "/storage/products/not-present.png"
    db_session.commit()

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id]},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"].startswith("GEMINI_PRODUCT_REFERENCE_IMAGE_MISSING")
    assert provider.calls == []
    assert db_session.query(RoomDesignGeneration).count() == 0


def test_qwen_design_generation_rejects_selected_product_without_readable_reference(client, db_session):
    provider = FakeImageProvider()
    provider.provider_name = "qwencloud"
    provider.requires_all_product_references = True
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)
    best.images[0].image_url = "/storage/products/not-present.png"
    db_session.commit()

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id]},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"].startswith("QWENCLOUD_PRODUCT_REFERENCES_UNAVAILABLE")
    assert provider.calls == []
    assert db_session.query(RoomDesignGeneration).count() == 0


def test_design_generation_requires_preferences_and_analysis(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers = auth_headers(client, "design-missing@example.com")
    project = create_project(client, headers)
    add_room_image(db_session, project)

    response = client.post(f"/api/room-projects/{project['id']}/design-generations", json={"product_ids": [1]}, headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "ROOM_PREFERENCES_REQUIRED"


def test_design_generation_provider_failure_is_logged(client, db_session):
    provider = FailingImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    response = client.post(f"/api/room-projects/{project['id']}/design-generations", json={"product_ids": [best.id]}, headers=headers)

    db_session.rollback()
    generation = db_session.query(RoomDesignGeneration).one()
    usage_log = db_session.query(AIUsageLog).filter(AIUsageLog.task_type == "ROOM_DESIGN_GENERATION").one()
    assert response.status_code == 503
    assert response.json()["detail"] == "IMAGE_PROVIDER_TEST_FAILURE: Test provider failed"
    assert generation.status == "FAILED"
    assert generation.error_code == "IMAGE_PROVIDER_TEST_FAILURE"
    assert usage_log.status == "FAILED"
    assert usage_log.error_code == "IMAGE_PROVIDER_TEST_FAILURE"


def test_design_generation_without_configured_provider_does_not_fake_success(client, db_session):
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    response = client.post(f"/api/room-projects/{project['id']}/design-generations", json={"product_ids": [best.id]}, headers=headers)

    db_session.rollback()
    generation = db_session.query(RoomDesignGeneration).one()
    assert response.status_code == 503
    assert response.json()["detail"] == "IMAGE_PROVIDER_NOT_CONFIGURED: Image generation provider is not configured"
    assert generation.status == "FAILED"
    assert generation.error_code == "IMAGE_PROVIDER_NOT_CONFIGURED"


def test_design_generation_success_logs_ai_usage_and_file_metadata(client, db_session):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    response = client.post(f"/api/room-projects/{project['id']}/design-generations", json={"product_ids": [best.id]}, headers=headers)

    db_session.rollback()
    generation = db_session.query(RoomDesignGeneration).one()
    usage_log = db_session.query(AIUsageLog).filter(AIUsageLog.task_type == "ROOM_DESIGN_GENERATION").one()
    assert response.status_code == 201
    assert generation.generated_image_path is not None
    assert generation.generated_image_url is not None
    assert (GeneratedDesignStorageService().storage_root / generation.generated_image_path).exists()
    assert usage_log.status == "SUCCESS"
    assert usage_log.input_tokens == 11


def test_design_generation_unexpected_exception_is_marked_failed(client, db_session, caplog):
    provider = CrashingImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    with caplog.at_level(logging.DEBUG):
        response = client.post(
            f"/api/room-projects/{project['id']}/design-generations",
            json={"product_ids": [best.id]},
            headers=headers,
        )

    db_session.rollback()
    generation = db_session.query(RoomDesignGeneration).one()
    usage_log = db_session.query(AIUsageLog).filter(AIUsageLog.task_type == "ROOM_DESIGN_GENERATION").one()
    assert response.status_code == 500
    assert response.json()["detail"] == "INTERNAL_GENERATION_ERROR"
    assert generation.status == "FAILED"
    assert generation.error_code == "INTERNAL_GENERATION_ERROR"
    assert "secret-token" not in (generation.error_message or "")
    assert "[REDACTED]" in (generation.error_message or "")
    assert usage_log.status == "FAILED"
    assert usage_log.error_code == "INTERNAL_GENERATION_ERROR"
    assert "secret-token" not in (usage_log.error_message or "")
    assert "secret-token-12345" not in caplog.text


def test_design_generation_provider_error_with_fake_token_is_sanitized(client, db_session, caplog):
    provider = LeakingTokenImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    with caplog.at_level(logging.DEBUG):
        response = client.post(
            f"/api/room-projects/{project['id']}/design-generations",
            json={"product_ids": [best.id]},
            headers=headers,
        )

    db_session.rollback()
    generation = db_session.query(RoomDesignGeneration).one()
    usage_log = db_session.query(AIUsageLog).filter(AIUsageLog.task_type == "ROOM_DESIGN_GENERATION").one()
    assert response.status_code == 503
    assert "secret-provider-token-999" not in response.json()["detail"]
    assert "AIzaSyFakeKey1234567890" not in response.json()["detail"]
    assert "[REDACTED]" in response.json()["detail"]
    assert generation.status == "FAILED"
    assert generation.error_code == "IMAGE_PROVIDER_LEAKY_FAILURE"
    assert "secret-provider-token-999" not in (generation.error_message or "")
    assert "AIzaSyFakeKey1234567890" not in (generation.error_message or "")
    assert "[REDACTED]" in (generation.error_message or "")
    assert usage_log.status == "FAILED"
    assert usage_log.error_code == "IMAGE_PROVIDER_LEAKY_FAILURE"
    assert "secret-provider-token-999" not in (usage_log.error_message or "")
    assert "secret-provider-token-999" not in caplog.text
    assert "AIzaSyFakeKey1234567890" not in caplog.text


def test_design_generation_commit_failure_in_persist_failure_rolls_back_safely(client, db_session, monkeypatch, caplog):
    provider = CrashingImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    from sqlalchemy.orm import Session
    orig_commit = Session.commit
    orig_rollback = Session.rollback
    commit_calls = 0
    rollback_called = False

    def tracking_rollback(self, *args, **kwargs):
        nonlocal rollback_called
        rollback_called = True
        return orig_rollback(self, *args, **kwargs)

    def failing_commit(self, *args, **kwargs):
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls > 1:
            raise RuntimeError("Simulated DB commit failure with secret-token-db-fail")
        return orig_commit(self, *args, **kwargs)

    monkeypatch.setattr(Session, "commit", failing_commit)
    monkeypatch.setattr(Session, "rollback", tracking_rollback)

    with caplog.at_level(logging.ERROR):
        response = client.post(
            f"/api/room-projects/{project['id']}/design-generations",
            json={"product_ids": [best.id]},
            headers=headers,
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "INTERNAL_GENERATION_ERROR"
    assert rollback_called is True
    assert "PERSIST_FAILURE_STATE_FAILED" in caplog.text
    assert "secret-token-db-fail" not in caplog.text


def test_design_generation_refresh_failure_recovers_and_marks_failed(client, db_session, monkeypatch):
    provider = FakeImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    from sqlalchemy.orm import Session
    orig_refresh = Session.refresh

    def failing_refresh(self, instance, *args, **kwargs):
        if isinstance(instance, RoomDesignGeneration):
            raise RuntimeError("Simulated DB connection drop on refresh")
        return orig_refresh(self, instance, *args, **kwargs)

    monkeypatch.setattr(Session, "refresh", failing_refresh)

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id]},
        headers=headers,
    )

    db_session.rollback()
    generation = db_session.query(RoomDesignGeneration).one()
    usage_log = db_session.query(AIUsageLog).filter(AIUsageLog.task_type == "ROOM_DESIGN_GENERATION").one()
    assert response.status_code == 500
    assert response.json()["detail"] == "INTERNAL_GENERATION_ERROR"
    assert generation.status == "FAILED"
    assert generation.error_code == "INTERNAL_GENERATION_ERROR"
    assert usage_log.status == "FAILED"


def test_design_generation_logging_failure_does_not_mask_original_error(client, db_session, monkeypatch):
    provider = CrashingImageProvider()
    override_image_provider(client.app, provider)
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    from app.services.design_generation_service import DesignGenerationService

    def buggy_persist(self, *args, **kwargs):
        raise RuntimeError("Simulated failure inside persistence helper")

    monkeypatch.setattr(DesignGenerationService, "_persist_failure", buggy_persist)

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations",
        json={"product_ids": [best.id]},
        headers=headers,
    )
    # The original error should still result in 500 without crashing unhandled
    assert response.status_code == 500
    assert response.json()["detail"] == "INTERNAL_GENERATION_ERROR"

