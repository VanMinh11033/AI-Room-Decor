import base64

import pytest
from google import genai

from app.ai.image.base import ImageProviderError
from app.ai.image.factory import NotConfiguredImageProvider, get_image_provider, settings
from app.ai.image.gemini_provider import GeminiImageProvider
from app.ai.image.openai_provider import OpenAIImageProvider


PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


class FakeUsageMetadata:
    prompt_token_count = 17
    candidates_token_count = 29
    total_token_count = 46


class FakeInlineData:
    data = PNG_BYTES
    mime_type = "image/png"


class FakePartResponse:
    inline_data = FakeInlineData()


class FakeContent:
    parts = [FakePartResponse()]


class FakeCandidate:
    content = FakeContent()


class FakeResponse:
    candidates = [FakeCandidate()]
    usage_metadata = FakeUsageMetadata()


class FakeModels:
    def __init__(self, response=None, error=None) -> None:
        self.response = response or FakeResponse()
        self.error = error
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response=None, error=None) -> None:
        self.models = FakeModels(response=response, error=error)


class FakePart:
    @classmethod
    def from_bytes(cls, data, mime_type):
        return {"data": data, "mime_type": mime_type}


class FakeGenerateContentConfig:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class FakeTypes:
    Part = FakePart
    GenerateContentConfig = FakeGenerateContentConfig


def reset_image_settings(monkeypatch):
    monkeypatch.setattr(settings, "image_provider", None)
    monkeypatch.setattr(settings, "image_model", None)
    monkeypatch.setattr(settings, "image_api_key", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)


def test_image_factory_selects_openai_provider(monkeypatch):
    reset_image_settings(monkeypatch)
    monkeypatch.setattr(settings, "image_provider", "openai")
    monkeypatch.setattr(settings, "image_model", "gpt-image-1")
    monkeypatch.setattr(settings, "image_api_key", "image-key")

    provider = get_image_provider()

    assert isinstance(provider, OpenAIImageProvider)
    assert provider.model_name == "gpt-image-1"


def test_image_factory_selects_gemini_provider_with_image_key_priority(monkeypatch):
    reset_image_settings(monkeypatch)
    monkeypatch.setattr(settings, "image_provider", "gemini")
    monkeypatch.setattr(settings, "image_model", "gemini-image-test")
    monkeypatch.setattr(settings, "image_api_key", "image-key")
    monkeypatch.setattr(settings, "gemini_api_key", "gemini-key")

    provider = get_image_provider()

    assert isinstance(provider, GeminiImageProvider)
    assert provider.model_name == "gemini-image-test"
    assert provider.api_key == "image-key"


def test_image_factory_gemini_falls_back_to_gemini_key(monkeypatch):
    reset_image_settings(monkeypatch)
    monkeypatch.setattr(settings, "image_provider", "gemini")
    monkeypatch.setattr(settings, "image_model", "gemini-image-test")
    monkeypatch.setattr(settings, "image_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "gemini-key")

    provider = get_image_provider()

    assert isinstance(provider, GeminiImageProvider)
    assert provider.api_key == "gemini-key"


def test_image_factory_gemini_missing_keys_is_not_configured(monkeypatch):
    reset_image_settings(monkeypatch)
    monkeypatch.setattr(settings, "image_provider", "gemini")
    monkeypatch.setattr(settings, "image_model", "gemini-image-test")

    provider = get_image_provider()

    assert isinstance(provider, NotConfiguredImageProvider)


def test_gemini_image_provider_returns_generated_image(tmp_path):
    image_path = tmp_path / "room.png"
    image_path.write_bytes(PNG_BYTES)
    fake_client = FakeClient()
    provider = GeminiImageProvider(
        api_key="test-key",
        model_name="gemini-image-test",
        client_factory=lambda: (fake_client, FakeTypes),
    )

    result = provider.generate_design(image_path, "Decorate with selected product IDs 1 and 2.")

    assert result.data == PNG_BYTES
    assert result.content_type == "image/png"
    assert result.usage.total_tokens == 46
    assert fake_client.models.calls[0]["model"] == "gemini-image-test"
    assert fake_client.models.calls[0]["contents"][1]["mime_type"] == "image/png"
    assert "Do not invent product IDs" in fake_client.models.calls[0]["contents"][0]


def test_gemini_image_provider_sends_room_and_selected_products_in_order(tmp_path):
    room_path = tmp_path / "room.png"
    product_a = tmp_path / "sofa.webp"
    product_b = tmp_path / "lamp.jpg"
    room_path.write_bytes(b"room-image")
    product_a.write_bytes(b"sofa-image")
    product_b.write_bytes(b"lamp-image")
    fake_client = FakeClient()
    provider = GeminiImageProvider(
        api_key="test-key",
        model_name="gemini-nano-banana-2.1",
        client_factory=lambda: (fake_client, FakeTypes),
    )

    provider.generate_design(
        room_path,
        "REFERENCE 1: Product ID 10; sofa.\nREFERENCE 2: Product ID 11; lamp.",
        reference_image_paths=[product_a, product_b],
    )

    contents = fake_client.models.calls[0]["contents"]
    assert contents[1] == {"data": b"room-image", "mime_type": "image/png"}
    assert contents[2] == {"data": b"sofa-image", "mime_type": "image/webp"}
    assert contents[3] == {"data": b"lamp-image", "mime_type": "image/jpeg"}
    assert "2 selected product photo references" in contents[0]
    assert "Product ID 10" in contents[0]
    assert "Product ID 11" in contents[0]


def test_gemini_image_provider_rejects_reference_images_over_model_limit(tmp_path):
    image_path = tmp_path / "room.png"
    image_path.write_bytes(PNG_BYTES)
    fake_client = FakeClient()
    provider = GeminiImageProvider(
        api_key="test-key",
        model_name="gemini-nano-banana-2.1",
        client_factory=lambda: (fake_client, FakeTypes),
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.", reference_image_paths=[image_path] * 14)

    assert exc_info.value.code == "GEMINI_IMAGE_REFERENCE_LIMIT_EXCEEDED"
    assert "at most 14 images total" in exc_info.value.message
    assert fake_client.models.calls == []


def test_gemini_image_provider_rejects_inline_request_over_20_mib(tmp_path):
    image_path = tmp_path / "large-room.png"
    image_path.write_bytes(b"x" * (16 * 1024 * 1024))
    fake_client = FakeClient()
    provider = GeminiImageProvider(
        api_key="test-key",
        model_name="gemini-nano-banana-2.1",
        client_factory=lambda: (fake_client, FakeTypes),
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "GEMINI_IMAGE_REQUEST_TOO_LARGE"
    assert fake_client.models.calls == []


def test_gemini_sdk_client_is_configured_for_a_single_attempt(monkeypatch):
    captured = {}
    monkeypatch.setattr(genai, "Client", lambda **kwargs: captured.update(kwargs) or object())
    provider = GeminiImageProvider(api_key="test-key", model_name="gemini-nano-banana-2.1")

    _client, types = provider._build_client()

    assert isinstance(captured["http_options"], types.HttpOptions)
    assert captured["http_options"].retry_options.attempts == 1


def test_gemini_image_provider_decodes_base64_response(tmp_path):
    image_path = tmp_path / "room.jpg"
    image_path.write_bytes(PNG_BYTES)
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inline_data": {
                                "data": base64.b64encode(PNG_BYTES).decode("ascii"),
                                "mime_type": "image/png",
                            }
                        }
                    ]
                }
            }
        ]
    }
    fake_client = FakeClient(response=response)
    provider = GeminiImageProvider(
        api_key="test-key",
        model_name="gemini-image-test",
        client_factory=lambda: (fake_client, FakeTypes),
    )

    result = provider.generate_design(image_path, "Decorate this room.")

    assert result.data == PNG_BYTES


def test_gemini_image_provider_rejects_response_without_image(tmp_path):
    image_path = tmp_path / "room.png"
    image_path.write_bytes(PNG_BYTES)
    fake_client = FakeClient(response={"candidates": [{"content": {"parts": [{"text": "no image"}]}}]})
    provider = GeminiImageProvider(
        api_key="test-key",
        model_name="gemini-image-test",
        client_factory=lambda: (fake_client, FakeTypes),
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "GEMINI_IMAGE_RESPONSE_ERROR"


def test_gemini_image_provider_maps_provider_exceptions_safely(tmp_path):
    image_path = tmp_path / "room.png"
    image_path.write_bytes(PNG_BYTES)
    fake_client = FakeClient(error=RuntimeError("quota exhausted for secret-key"))
    provider = GeminiImageProvider(
        api_key="secret-key",
        model_name="gemini-image-test",
        client_factory=lambda: (fake_client, FakeTypes),
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "GEMINI_IMAGE_QUOTA_ERROR"
    assert "secret-key" not in exc_info.value.message
    assert "[redacted]" in exc_info.value.message


def test_gemini_image_provider_high_demand_with_model_word_maps_to_unavailable(tmp_path):
    image_path = tmp_path / "room.png"
    image_path.write_bytes(PNG_BYTES)
    msg = "503 UNAVAILABLE. This model is currently experiencing high demand. Please try again later."
    fake_client = FakeClient(error=RuntimeError(msg))
    provider = GeminiImageProvider(
        api_key="secret-key",
        model_name="gemini-image-test",
        client_factory=lambda: (fake_client, FakeTypes),
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "GEMINI_IMAGE_UNAVAILABLE"
    assert exc_info.value.code != "GEMINI_IMAGE_MODEL_ERROR"


def test_gemini_image_provider_auth_error_mapping(tmp_path):
    image_path = tmp_path / "room.png"
    image_path.write_bytes(PNG_BYTES)
    msg = "401 UNAUTHENTICATED. ACCESS_TOKEN_TYPE_UNSUPPORTED with secret-token-xyz"
    fake_client = FakeClient(error=RuntimeError(msg))
    provider = GeminiImageProvider(
        api_key="secret-key",
        model_name="gemini-image-test",
        client_factory=lambda: (fake_client, FakeTypes),
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "GEMINI_IMAGE_AUTH_ERROR"
    assert "secret-token-xyz" not in exc_info.value.message
    assert "[REDACTED]" in exc_info.value.message


def test_gemini_image_provider_model_not_found_mapping(tmp_path):
    image_path = tmp_path / "room.png"
    image_path.write_bytes(PNG_BYTES)
    msg = "404 NOT_FOUND. models/gemini-invalid is not found"
    fake_client = FakeClient(error=RuntimeError(msg))
    provider = GeminiImageProvider(
        api_key="secret-key",
        model_name="gemini-image-test",
        client_factory=lambda: (fake_client, FakeTypes),
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "GEMINI_IMAGE_MODEL_ERROR"
