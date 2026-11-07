import json

import pytest

from app.ai.vision.base import VisionProviderError
from app.ai.vision.factory import get_vision_provider, settings
from app.ai.vision.gemini_provider import GeminiVisionProvider

HIGH_DEMAND_MESSAGE = (
    "This model is currently experiencing high demand. Spikes in demand are usually temporary. "
    "Please try again later."
)


class FakeUsageMetadata:
    prompt_token_count = 12
    candidates_token_count = 8
    total_token_count = 20


class FakeResponse:
    text = json.dumps(
        {
            "room_type": "bedroom",
            "dominant_colors": [{"name": "Warm white", "hex": "#F7F1E8", "percentage": 70}],
            "existing_objects": [{"name": "bed", "confidence": 0.93}],
            "empty_areas": [{"location": "left wall", "description": "open wall", "suitable_for_decor": True}],
            "lighting": {"type": "natural", "level": "medium"},
            "design_characteristics": ["cozy", "minimal"],
            "layout_summary": "A compact bedroom with a clear wall for decor.",
            "confidence": 0.91,
        }
    )
    usage_metadata = FakeUsageMetadata()


class FakeGeminiError(Exception):
    def __init__(self, code: int, status: str, message: str) -> None:
        super().__init__(
            f"{code} {status}. {{'error': {{'code': {code}, 'message': '{message}', 'status': '{status}'}}}}"
        )
        self.code = code
        self.status = status
        self.message = message


class FakeModels:
    def __init__(self) -> None:
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return FakeResponse()


class FakeClient:
    def __init__(self) -> None:
        self.models = FakeModels()


class ScriptedModels:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        outcome = self.outcomes[min(self.calls - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class ScriptedClient:
    def __init__(self, outcomes) -> None:
        self.models = ScriptedModels(outcomes)


class FakePart:
    @classmethod
    def from_bytes(cls, data, mime_type):
        return {"bytes": data, "mime_type": mime_type}


class FakeGenerateContentConfig:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class FakeTypes:
    Part = FakePart
    GenerateContentConfig = FakeGenerateContentConfig


def make_image(tmp_path):
    image_path = tmp_path / "room.jpg"
    image_path.write_bytes(b"fake-image-bytes")
    return image_path


def make_scripted_provider(outcomes, **kwargs):
    client = ScriptedClient(outcomes)
    slept: list[float] = []
    provider = GeminiVisionProvider(
        api_key="test-key",
        model_name="gemini-3.6-flash",
        client_factory=lambda: (client, FakeTypes),
        sleep=slept.append,
        **kwargs,
    )
    return provider, client, slept


def test_gemini_provider_returns_structured_room_analysis(tmp_path):
    image_path = make_image(tmp_path)
    fake_client = FakeClient()
    provider = GeminiVisionProvider(
        api_key="test-key",
        model_name="gemini-2.5-flash",
        client_factory=lambda: (fake_client, FakeTypes),
    )

    result = provider.analyze_room(image_path, "image/jpeg")

    assert result.result.room_type == "bedroom"
    assert result.result.lighting.type == "natural"
    assert result.result.dominant_colors[0].hex == "#F7F1E8"
    assert result.usage.total_tokens == 20
    assert fake_client.models.calls[0]["model"] == "gemini-2.5-flash"
    assert fake_client.models.calls[0]["contents"][1]["mime_type"] == "image/jpeg"


def test_factory_can_select_gemini_provider(monkeypatch):
    monkeypatch.setattr(settings, "vision_provider", "gemini")
    monkeypatch.setattr(settings, "vision_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")

    provider = get_vision_provider()

    assert isinstance(provider, GeminiVisionProvider)
    assert provider.provider_name == "gemini"
    assert provider.model_name == "gemini-2.5-flash"


def test_transient_503_is_retried_then_succeeds(tmp_path):
    image_path = make_image(tmp_path)
    provider, client, slept = make_scripted_provider(
        [FakeGeminiError(503, "UNAVAILABLE", HIGH_DEMAND_MESSAGE), FakeResponse()]
    )

    result = provider.analyze_room(image_path, "image/jpeg")

    assert result.result.room_type == "bedroom"
    assert client.models.calls == 2
    assert slept == [2.0]


def test_transient_503_exhausts_retries_with_backoff(tmp_path):
    image_path = make_image(tmp_path)
    provider, client, slept = make_scripted_provider([FakeGeminiError(503, "UNAVAILABLE", HIGH_DEMAND_MESSAGE)])

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    error = exc_info.value
    assert error.code == "GEMINI_PROVIDER_UNAVAILABLE"
    assert error.transient is True
    assert error.status_code == 503
    assert client.models.calls == 4
    assert slept == [2.0, 4.0, 8.0]


def test_high_demand_mentioning_model_is_not_model_error(tmp_path):
    image_path = make_image(tmp_path)
    provider, _client, _slept = make_scripted_provider([FakeGeminiError(503, "UNAVAILABLE", HIGH_DEMAND_MESSAGE)])

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    assert "model" in exc_info.value.message.lower()
    assert exc_info.value.code != "GEMINI_PROVIDER_MODEL_ERROR"
    assert exc_info.value.code == "GEMINI_PROVIDER_UNAVAILABLE"


def test_429_is_quota_error_and_not_retried(tmp_path):
    image_path = make_image(tmp_path)
    provider, client, slept = make_scripted_provider(
        [FakeGeminiError(429, "RESOURCE_EXHAUSTED", "You exceeded your current quota, please check your plan")]
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    assert exc_info.value.code == "GEMINI_PROVIDER_QUOTA_ERROR"
    assert exc_info.value.code != "GEMINI_PROVIDER_UNAVAILABLE"
    assert exc_info.value.transient is False
    assert client.models.calls == 1
    assert slept == []


def test_404_model_not_found_is_classified_and_not_retried(tmp_path):
    image_path = make_image(tmp_path)
    provider, client, slept = make_scripted_provider(
        [FakeGeminiError(404, "NOT_FOUND", "models/gemini-9.9-flash is not found for API version v1beta")]
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    assert exc_info.value.code == "GEMINI_PROVIDER_MODEL_ERROR"
    assert exc_info.value.status_code == 404
    assert client.models.calls == 1
    assert slept == []


def test_auth_error_is_classified_and_not_retried(tmp_path):
    image_path = make_image(tmp_path)
    provider, client, slept = make_scripted_provider(
        [FakeGeminiError(401, "UNAUTHENTICATED", "API key not valid. Please pass a valid API key.")]
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    assert exc_info.value.code == "GEMINI_PROVIDER_AUTH_ERROR"
    assert exc_info.value.status_code == 401
    assert client.models.calls == 1
    assert slept == []


def test_400_is_request_failure_and_not_retried(tmp_path):
    image_path = make_image(tmp_path)
    provider, client, slept = make_scripted_provider(
        [FakeGeminiError(400, "INVALID_ARGUMENT", "Invalid image data provided")]
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    assert exc_info.value.code == "GEMINI_PROVIDER_REQUEST_FAILED"
    assert client.models.calls == 1
    assert slept == []


def test_malformed_response_is_not_retried(tmp_path):
    image_path = make_image(tmp_path)

    class EmptyResponse:
        text = ""

    provider, client, slept = make_scripted_provider([EmptyResponse()])

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    assert exc_info.value.code == "GEMINI_PROVIDER_MALFORMED_RESPONSE"
    assert client.models.calls == 1
    assert slept == []


def test_api_key_is_redacted_in_error_message(tmp_path):
    image_path = make_image(tmp_path)
    provider, _client, _slept = make_scripted_provider(
        [FakeGeminiError(401, "UNAUTHENTICATED", "API key not valid: test-key")]
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    assert "test-key" not in exc_info.value.message
    assert "[redacted]" in exc_info.value.message


def test_permission_403_is_classified_and_not_retried(tmp_path):
    image_path = make_image(tmp_path)
    provider, client, slept = make_scripted_provider(
        [FakeGeminiError(403, "PERMISSION_DENIED", "The caller does not have permission")]
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    assert exc_info.value.code == "GEMINI_PROVIDER_AUTH_ERROR"
    assert exc_info.value.status_code == 403
    assert client.models.calls == 1
    assert slept == []


def test_auth_401_with_access_token_type_unsupported_classified_and_not_retried(tmp_path):
    image_path = make_image(tmp_path)
    error_msg = (
        "Request had invalid authentication credentials. Expected OAuth 2 access token. "
        "details: [{'reason': 'ACCESS_TOKEN_TYPE_UNSUPPORTED'}]"
    )
    provider, client, slept = make_scripted_provider(
        [FakeGeminiError(401, "UNAUTHENTICATED", error_msg)]
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    assert exc_info.value.code == "GEMINI_PROVIDER_AUTH_ERROR"
    assert exc_info.value.status_code == 401
    assert exc_info.value.transient is False
    assert client.models.calls == 1
    assert slept == []


def test_high_demand_raw_text_without_status_code_is_unavailable_and_not_model_error(tmp_path):
    image_path = make_image(tmp_path)
    provider, client, slept = make_scripted_provider(
        [RuntimeError("This model is currently experiencing high demand. Please try again later.")]
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    assert exc_info.value.code == "GEMINI_PROVIDER_UNAVAILABLE"
    assert exc_info.value.code != "GEMINI_PROVIDER_MODEL_ERROR"
    assert exc_info.value.transient is True


def test_safe_error_message_redacts_tokens_and_secrets(tmp_path):
    image_path = make_image(tmp_path)
    provider, _client, _slept = make_scripted_provider(
        [FakeGeminiError(401, "UNAUTHENTICATED", "Bearer secret-token-12345 with AQ.fake_auth_token_123456789012345678")]
    )

    with pytest.raises(VisionProviderError) as exc_info:
        provider.analyze_room(image_path, "image/jpeg")

    assert "secret-token-12345" not in exc_info.value.message
    assert "fake_auth_token" not in exc_info.value.message
    assert "[REDACTED]" in exc_info.value.message
