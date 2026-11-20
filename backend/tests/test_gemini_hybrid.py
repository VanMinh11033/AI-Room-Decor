from io import BytesIO
import json
from pathlib import Path
from typing import Any
import pytest
from PIL import Image

from app.ai.gemini_hybrid.catalog_validator import CatalogIdentityValidator
from app.ai.gemini_hybrid.fallback_manager import CompositeFallbackManager
from app.ai.gemini_hybrid.image_renderer import GeminiImageRenderer
from app.ai.gemini_hybrid.layout_planner import GeminiLayoutPlanner
from app.ai.gemini_hybrid.room_analyzer import GeminiRoomAnalyzer
from app.ai.gemini_hybrid.schemas import (
    FloorAreaSchema,
    GeminiLayoutPlan,
    GeminiRoomAnalysisSchema,
    LightingAnalysisSchema,
    PlannedPlacement,
    VerificationResult,
)
from app.ai.image.base import GeneratedImage, ImageGenerationUsage, ImageProviderError
from app.ai.image.composite_provider import CompositeImageProvider
from app.schemas.design_generation import DesignGenerationCreate, DesignGenerationRead


PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00\x1f\xf3\xffa"


class MockGeminiTypes:
    class Part:
        @classmethod
        def from_bytes(cls, data, mime_type):
            return {"data": data, "mime_type": mime_type}

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


class MockGeminiModels:
    def __init__(self, response_text: str | None = None, response_image: bytes | None = None, error: Exception | None = None):
        self.response_text = response_text
        self.response_image = response_image
        self.error = error
        self.calls = []

    def generate_content(self, model: str, contents: list, config: Any = None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.error:
            raise self.error

        class FakeCandidate:
            def __init__(self, text, image_bytes):
                self.text = text
                if image_bytes:
                    class FakePart:
                        inline_data = {"data": image_bytes, "mime_type": "image/png"}
                    self.content = type("FakeContent", (), {"parts": [FakePart()]})()
                else:
                    self.content = type("FakeContent", (), {"parts": []})()

        class FakeResponse:
            def __init__(self, text, image_bytes):
                self.text = text
                self.candidates = [FakeCandidate(text, image_bytes)]
                self.usage_metadata = type("Usage", (), {"prompt_token_count": 10, "candidates_token_count": 20, "total_token_count": 30})()

        return FakeResponse(self.response_text, self.response_image)


class MockGeminiClient:
    def __init__(self, response_text: str | None = None, response_image: bytes | None = None, error: Exception | None = None):
        self.models = MockGeminiModels(response_text, response_image, error)


# =====================================================================
# 1. Mock Gemini API & Schema Validation for Room Analyzer
# =====================================================================

def test_gemini_room_analyzer_with_valid_mock(tmp_path):
    img_path = tmp_path / "room.png"
    Image.new("RGB", (300, 200), color=(220, 210, 200)).save(img_path)

    mock_json = json.dumps({
        "room_type": "living room",
        "layout_summary": "Phòng khách thoáng đãng có cửa sổ lấy sáng bên trái",
        "floor_area": {"visible": True, "horizon_ratio": 0.60, "floor_material": "wood"},
        "lighting": {"type": "natural daylight", "direction": "left", "level": "bright", "color_temp": "warm"},
        "dominant_colors": ["White", "Oak Wood", "Beige"],
        "decor_spots": [{"location": "center floor", "description": "Khu vực đặt sofa", "suitable_categories": ["sofa"]}],
        "confidence": 0.95,
    })

    client = MockGeminiClient(response_text=mock_json)
    analyzer = GeminiRoomAnalyzer(
        api_key="test_key",
        client_factory=lambda: (client, MockGeminiTypes),
    )

    result = analyzer.analyze(img_path)
    assert isinstance(result, GeminiRoomAnalysisSchema)
    assert result.room_type == "living room"
    assert result.lighting.direction == "left"
    assert result.floor_area.visible is True
    assert result.confidence == 0.95
    assert len(client.models.calls) == 1


def test_gemini_room_analyzer_local_fallback_when_api_fails(tmp_path):
    img_path = tmp_path / "room_fail.png"
    Image.new("RGB", (200, 150), color=(200, 200, 200)).save(img_path)

    client = MockGeminiClient(error=RuntimeError("Google API 503 Unavailable"))
    analyzer = GeminiRoomAnalyzer(
        api_key="test_key",
        client_factory=lambda: (client, MockGeminiTypes),
    )

    result = analyzer.analyze(img_path)
    # Should safely fallback to local CV analysis without throwing
    assert isinstance(result, GeminiRoomAnalysisSchema)
    assert result.confidence > 0.0


# =====================================================================
# 2. Schema Validation (Rejects invalid schemas)
# =====================================================================

def test_schema_rejects_invalid_lighting_or_confidence():
    with pytest.raises(Exception):
        # Confidence must be between 0.0 and 1.0
        GeminiRoomAnalysisSchema(
            room_type="living room",
            layout_summary="Test",
            confidence=1.5,
        )


# =====================================================================
# 3. Product ID Mapping & Constraint Integrity (Layout Planner)
# =====================================================================

def test_layout_planner_rejects_hallucinated_product_ids():
    # Gemini returns an extra product ID not requested
    mock_plan_json = json.dumps({
        "placements": [
            {"product_id": 1, "category": "sofa", "x_ratio": 0.44, "y_ratio": 0.72, "width_ratio": 0.44, "z_index": 4, "reasoning": "center"},
            {"product_id": 9999, "category": "hallucinated_table", "x_ratio": 0.60, "y_ratio": 0.84, "width_ratio": 0.22, "z_index": 6, "reasoning": "invented"},
        ],
        "light_direction": "left",
        "shadow_intensity": 0.72,
        "floor_horizon_ratio": 0.65,
    })

    client = MockGeminiClient(response_text=mock_plan_json)
    planner = GeminiLayoutPlanner(api_key="test_key", client_factory=lambda: (client, MockGeminiTypes))

    # Request only Product ID 1 and Product ID 7
    plan = planner.plan_layout(
        product_ids=[1, 7],
        product_metadata={1: {"category": "sofa"}, 7: {"category": "table"}},
    )

    # Must reject the hallucinated plan and fallback to deterministic layout for [1, 7]
    planned_ids = {p.product_id for p in plan.placements}
    assert planned_ids == {1, 7}
    assert 9999 not in planned_ids


def test_layout_planner_deterministic_z_ordering():
    planner = GeminiLayoutPlanner()
    plan = planner.plan_layout(
        product_ids=[1, 7, 9],
        product_metadata={1: {"category": "sofa"}, 7: {"category": "table"}, 9: {"category": "lighting"}},
        floor_area=FloorAreaSchema(horizon_ratio=0.60),
    )

    placements_by_id = {p.product_id: p for p in plan.placements}
    # Rug/Lighting in back (z < 3), Sofa in middle (z=4), Table in front (z=6)
    assert placements_by_id[9].z_index < placements_by_id[1].z_index
    assert placements_by_id[1].z_index < placements_by_id[7].z_index


# =====================================================================
# 4. Catalog Product Identity & Architecture Drift Validation
# =====================================================================

def test_catalog_validator_marks_composite_as_verified(tmp_path):
    room_path = tmp_path / "room.png"
    Image.new("RGB", (200, 200), color=(240, 240, 240)).save(room_path)

    validator = CatalogIdentityValidator()
    result = validator.validate(
        source_room_path=room_path,
        output_image_data=room_path.read_bytes(),
        selected_product_ids=[1, 7],
        is_composite_mode=True,
    )

    assert result.status == "VERIFIED"
    assert result.is_catalog_exact is True
    assert result.is_ai_preview is False
    assert result.architecture_drift_score == 0.0


def test_catalog_validator_marks_ai_preview_as_needs_review(tmp_path):
    room_path = tmp_path / "room.png"
    out_path = tmp_path / "out_preview.png"
    Image.new("RGB", (200, 200), color=(240, 240, 240)).save(room_path)
    # Slight color difference representing AI inpainting
    Image.new("RGB", (200, 200), color=(235, 230, 225)).save(out_path)

    validator = CatalogIdentityValidator()
    result = validator.validate(
        source_room_path=room_path,
        output_image_data=out_path.read_bytes(),
        selected_product_ids=[1],
        is_composite_mode=False,
    )

    # Under AI Preview mode, it must NEVER auto-mark VERIFIED
    assert result.status == "NEEDS_REVIEW"
    assert result.is_catalog_exact is False
    assert result.is_ai_preview is True


def test_catalog_validator_rejects_severe_architecture_drift(tmp_path):
    room_path = tmp_path / "room.png"
    out_path = tmp_path / "drifted.png"
    Image.new("RGB", (200, 200), color=(255, 255, 255)).save(room_path)
    # Drastically changed ceiling/walls (e.g. black room instead of white)
    Image.new("RGB", (200, 200), color=(10, 10, 10)).save(out_path)

    validator = CatalogIdentityValidator()
    result = validator.validate(
        source_room_path=room_path,
        output_image_data=out_path.read_bytes(),
        selected_product_ids=[1],
        is_composite_mode=False,
    )

    assert result.status == "REJECTED"
    assert result.architecture_drift_score > 0.38


# =====================================================================
# 5 & 6. Composite Fallback Manager (429, Timeout, API Error, Rejected)
# =====================================================================

def test_fallback_manager_triggers_on_429():
    manager = CompositeFallbackManager()
    quota_err = ImageProviderError("GEMINI_IMAGE_QUOTA_ERROR", "429 Resource Exhausted")
    needed, reason = manager.should_fallback(cloud_ai_enabled=True, api_key_configured=True, error=quota_err)
    assert needed is True
    assert "QUOTA" in reason


def test_fallback_manager_triggers_on_timeout():
    manager = CompositeFallbackManager()
    timeout_err = ImageProviderError("TIMEOUT", "Request deadline exceeded")
    needed, reason = manager.should_fallback(cloud_ai_enabled=True, api_key_configured=True, error=timeout_err)
    assert needed is True
    assert "TIMEOUT" in reason


def test_fallback_manager_triggers_on_validation_rejection():
    manager = CompositeFallbackManager()
    needed, reason = manager.should_fallback(
        cloud_ai_enabled=True,
        api_key_configured=True,
        verification_status="REJECTED",
    )
    assert needed is True
    assert reason == "CATALOG_VALIDATION_REJECTED"


# =====================================================================
# 7 & 8. Design Generation Schemas & Mode Contract
# =====================================================================

def test_design_generation_schema_defaults_and_validation():
    req = DesignGenerationCreate(product_ids=[1, 7])
    assert req.generation_mode == "CATALOG_ACCURATE" or req.generation_mode is None

    # Duplicate IDs rejected
    with pytest.raises(ValueError):
        DesignGenerationCreate(product_ids=[1, 1])

    # AI Photorealistic Preview mode explicit configuration
    req_ai = DesignGenerationCreate(product_ids=[1, 7], generation_mode="AI_PHOTOREALISTIC_PREVIEW")
    assert req_ai.generation_mode == "AI_PHOTOREALISTIC_PREVIEW"


# =====================================================================
# 9. Local Composite Engine Still Operational
# =====================================================================

def test_local_composite_engine_functional(tmp_path):
    room_path = tmp_path / "room.png"
    sofa_path = tmp_path / "sofa.png"

    Image.new("RGB", (400, 300), color=(230, 225, 220)).save(room_path)
    # Create isolated sofa cutout with transparent border
    im = Image.new("RGBA", (100, 60), color=(0, 0, 0, 0))
    for y in range(10, 50):
        for x in range(10, 90):
            im.putpixel((x, y), (180, 150, 120, 255))
    im.save(sofa_path)

    provider = CompositeImageProvider()
    result = provider.generate_design(
        source_image_path=room_path,
        prompt="Test local composite",
        reference_image_paths=[sofa_path],
        reference_categories=["sofa"],
    )

    assert isinstance(result, GeneratedImage)
    assert result.content_type == "image/png"
    assert len(result.data) > 0


# =====================================================================
# 10. Persistence & Reload Stability (Mode & Verification Invariance)
# =====================================================================

def test_generation_persistence_and_reload_maintains_ai_preview():
    from datetime import UTC, datetime
    from app.models.entities import RoomDesignGeneration

    gen = RoomDesignGeneration(
        id=101,
        room_project_id=1,
        user_id=1,
        status="COMPLETED",
        provider="gemini",
        model="gemini-3.1-flash-image",
        prompt_version="v2",
        source_image_path="test_room.jpg",
        generated_image_url="/storage/gen101.jpg",
        prompt="[MODE: AI_PHOTOREALISTIC_PREVIEW] [STATUS: NEEDS_REVIEW] Photorealistic living room preview with verified references",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Initial serialization
    read_initial = DesignGenerationRead.model_validate(gen)
    assert read_initial.generation_mode == "AI_PHOTOREALISTIC_PREVIEW"
    assert read_initial.is_ai_preview is True
    assert read_initial.verification_status == "NEEDS_REVIEW"

    # Reload simulation (subsequent GET /api/room-projects/{id}/design-generations/{gen_id})
    read_reloaded = DesignGenerationRead.model_validate(gen)
    assert read_reloaded.generation_mode == "AI_PHOTOREALISTIC_PREVIEW"
    assert read_reloaded.is_ai_preview is True
    assert read_reloaded.verification_status == "NEEDS_REVIEW"
    # CRITICAL: An AI Preview MUST NEVER flip to VERIFIED after reload
    assert read_reloaded.verification_status != "VERIFIED"


def test_generation_persistence_and_reload_maintains_catalog_accurate():
    from datetime import UTC, datetime
    from app.models.entities import RoomDesignGeneration

    gen = RoomDesignGeneration(
        id=102,
        room_project_id=1,
        user_id=1,
        status="COMPLETED",
        provider="composite",
        model="deterministic-compositor-v2",
        prompt_version="v2",
        source_image_path="test_room.jpg",
        generated_image_url="/storage/gen102.png",
        prompt="[MODE: CATALOG_ACCURATE] [STATUS: VERIFIED] Deterministic composite with exact catalog cutouts",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    read_reloaded = DesignGenerationRead.model_validate(gen)
    assert read_reloaded.generation_mode == "CATALOG_ACCURATE"
    assert read_reloaded.is_ai_preview is False
    assert read_reloaded.verification_status == "VERIFIED"
