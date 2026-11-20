import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.ai.vision.base import VisionProviderError
from app.ai.vision.cloudflare_provider import CloudflareVisionProvider, DEFAULT_VISION_MODEL
from app.ai.vision.factory import get_vision_provider
from app.ai.vision.fallback_provider import LocalFallbackProvider
from app.core.config import settings


class FakeClient:
    def __init__(self, response: httpx.Response | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def post(self, url, headers=None, json=None, **kwargs):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if self.error:
            raise self.error
        return self.response


def mock_response(status_code: int = 200, json_body: dict | None = None, text: str = "") -> httpx.Response:
    if json_body is not None:
        return httpx.Response(status_code=status_code, json=json_body, headers={"content-type": "application/json"})
    return httpx.Response(status_code=status_code, text=text, headers={"content-type": "text/plain"})


def create_test_image(path: Path, size: tuple[int, int] = (120, 100), color: tuple[int, int, int] = (220, 215, 200)) -> Path:
    img = Image.new("RGB", size, color)
    img.save(path, format="JPEG")
    return path


def test_cloudflare_vision_success(tmp_path: Path):
    test_img = create_test_image(tmp_path / "room.jpg")

    mock_llm_json = {
        "room_type": "Phòng khách",
        "style": "Bắc Âu",
        "existing_objects": [
            {"name": "Sofa văng 3 chỗ màu be", "confidence": 0.95},
            {"name": "Bàn trà tròn gỗ sồi", "confidence": 0.92},
            {"name": "Cửa sổ kính lớn lấy sáng", "confidence": 0.88},
        ],
        "empty_areas": [
            {"location": "Khu vực trung tâm sàn", "description": "Sàn gỗ trống phía trước sofa", "suitable_for_decor": True},
            {"location": "Góc tường bên phải", "description": "Góc trống gần cửa sổ", "suitable_for_decor": True},
        ],
        "layout_summary": "Phòng khách phong cách Bắc Âu đón ánh sáng tự nhiên chan hòa, sàn gỗ sáng màu và tường trắng tạo cảm giác rộng rãi.",
        "confidence": 0.94,
    }

    fake_resp = mock_response(
        200,
        {
            "success": True,
            "result": {
                "response": json.dumps(mock_llm_json, ensure_ascii=False)
            },
        },
    )
    fake_client = FakeClient(response=fake_resp)

    provider = CloudflareVisionProvider(
        account_id="test_acc_123",
        api_token="test_token_456",
        client_factory=lambda: fake_client,
    )

    analysis = provider.analyze_room(test_img, "image/jpeg")

    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    assert "test_acc_123/ai/run/@cf/meta/llama-3.2-11b-vision-instruct" in call["url"]
    assert call["headers"]["Authorization"] == "Bearer test_token_456"
    assert call["json"]["image"].startswith("data:image/jpeg;base64,")

    res = analysis.result
    assert res.room_type == "Phòng khách"
    assert len(res.existing_objects) == 3
    assert res.existing_objects[0].name == "Sofa văng 3 chỗ màu be"
    assert len(res.empty_areas) >= 2
    assert "Bắc Âu" in " ".join(res.design_characteristics)
    assert len(res.layout_summary) > 20
    assert analysis.raw_response["engine"] == "hybrid_cloudflare_local_cv"
    assert analysis.raw_response["vision_model"] == DEFAULT_VISION_MODEL
    assert len(res.dominant_colors) > 0


def test_cloudflare_vision_auth_error(tmp_path: Path):
    test_img = create_test_image(tmp_path / "room.jpg")
    fake_resp = mock_response(401, {"success": False, "errors": [{"message": "Invalid token"}]})
    fake_client = FakeClient(response=fake_resp)

    provider = CloudflareVisionProvider(
        account_id="test_acc",
        api_token="bad_token",
        client_factory=lambda: fake_client,
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(test_img, "image/jpeg")

    assert exc_info.value.code == "CLOUDFLARE_VISION_AUTH_ERROR"


def test_cloudflare_vision_quota_error(tmp_path: Path):
    test_img = create_test_image(tmp_path / "room.jpg")
    fake_resp = mock_response(429, {"success": False, "errors": [{"message": "Rate limit exceeded"}]})
    fake_client = FakeClient(response=fake_resp)

    provider = CloudflareVisionProvider(
        account_id="test_acc",
        api_token="test_token",
        client_factory=lambda: fake_client,
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(test_img, "image/jpeg")

    assert exc_info.value.code == "CLOUDFLARE_VISION_QUOTA_ERROR"


def test_cloudflare_vision_service_unavailable(tmp_path: Path):
    test_img = create_test_image(tmp_path / "room.jpg")
    fake_resp = mock_response(503, text="Service Unavailable")
    fake_client = FakeClient(response=fake_resp)

    provider = CloudflareVisionProvider(
        account_id="test_acc",
        api_token="test_token",
        client_factory=lambda: fake_client,
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(test_img, "image/jpeg")

    assert exc_info.value.code == "CLOUDFLARE_VISION_UNAVAILABLE"
    assert exc_info.value.transient is True


def test_cloudflare_vision_agreement_required(tmp_path: Path):
    test_img = create_test_image(tmp_path / "room.jpg")
    fake_resp = mock_response(
        200,
        {
            "success": True,
            "result": {
                "response": "To use this model you must agree to the Meta Llama 3.2 license agreement. Re-run with prompt: agree"
            },
        },
    )
    fake_client = FakeClient(response=fake_resp)

    provider = CloudflareVisionProvider(
        account_id="test_acc",
        api_token="test_token",
        client_factory=lambda: fake_client,
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(test_img, "image/jpeg")

    assert exc_info.value.code == "CLOUDFLARE_VISION_AGREEMENT_REQUIRED"


def test_cloudflare_vision_malformed_json_falls_back(tmp_path: Path):
    test_img = create_test_image(tmp_path / "room.jpg")
    fake_resp = mock_response(
        200,
        {
            "success": True,
            "result": {
                "response": "Here is a room with furniture, but I am not returning valid JSON."
            },
        },
    )
    fake_client = FakeClient(response=fake_resp)

    provider = CloudflareVisionProvider(
        account_id="test_acc",
        api_token="test_token",
        client_factory=lambda: fake_client,
    )

    analysis = provider.analyze_room(test_img, "image/jpeg")
    # Graceful fallback: returns optical analysis from local CV
    assert analysis is not None
    assert analysis.result is not None
    assert len(analysis.result.dominant_colors) > 0


def test_cloudflare_vision_tiny_image_bypasses_remote_call(tmp_path: Path):
    # Images < 32px are considered synthetic/test thumbnails and bypass network call
    tiny_img = create_test_image(tmp_path / "tiny.jpg", size=(16, 16))
    fake_client = FakeClient(response=mock_response(200, {"success": True}))

    provider = CloudflareVisionProvider(
        account_id="test_acc",
        api_token="test_token",
        client_factory=lambda: fake_client,
    )

    analysis = provider.analyze_room(tiny_img, "image/jpeg")
    assert len(fake_client.calls) == 0
    assert analysis is not None


def test_factory_selects_cloudflare_provider(monkeypatch):
    monkeypatch.setattr(settings, "vision_provider", "cloudflare")
    monkeypatch.setattr(settings, "cloudflare_account_id", "my_account_id")
    monkeypatch.setattr(settings, "cloudflare_api_token", "my_api_token")
    monkeypatch.setattr(settings, "vision_model", "@cf/meta/llama-3.2-11b-vision-instruct")

    provider = get_vision_provider()
    assert isinstance(provider, CloudflareVisionProvider)
    assert provider.account_id == "my_account_id"
    assert provider.api_token == "my_api_token"
    assert provider.model_name == "@cf/meta/llama-3.2-11b-vision-instruct"


def test_factory_missing_keys_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(settings, "vision_provider", "cloudflare")
    monkeypatch.setattr(settings, "cloudflare_account_id", "")
    monkeypatch.setattr(settings, "cloudflare_api_token", "")

    provider = get_vision_provider()
    assert isinstance(provider, LocalFallbackProvider)
    assert provider.fallback_reason == "MISSING_API_KEY"
