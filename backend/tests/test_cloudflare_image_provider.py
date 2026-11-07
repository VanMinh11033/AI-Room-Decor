import base64
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.ai.image.base import ImageProviderError
from app.ai.image.cloudflare_provider import CloudflareImageProvider
from app.ai.image.factory import NotConfiguredImageProvider, get_image_provider, settings


_jpeg_buffer = BytesIO()
Image.new("RGB", (4, 3), (120, 140, 160)).save(_jpeg_buffer, format="JPEG")
JPEG_BYTES = _jpeg_buffer.getvalue()


class FakeClient:
    def __init__(self, response: httpx.Response | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls = []

    def post(self, url, headers, data=None, files=None, json=None):
        self.calls.append({"url": url, "headers": headers, "data": data, "files": files, "json": json})
        if self.error:
            raise self.error
        return self.response


def response(status_code=200, json_body=None, content=b"", content_type="application/json") -> httpx.Response:
    if json_body is not None:
        return httpx.Response(status_code=status_code, json=json_body, headers={"content-type": content_type})
    return httpx.Response(status_code=status_code, content=content, headers={"content-type": content_type})


def write_image(path, size=(1024, 512), color=(160, 130, 110)):
    image = Image.new("RGB", size, color)
    image.save(path, format="JPEG")
    return path.read_bytes()


def image_size(data: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(data)) as image:
        return image.size


def reset_image_settings(monkeypatch):
    monkeypatch.setattr(settings, "image_provider", None)
    monkeypatch.setattr(settings, "image_model", None)
    monkeypatch.setattr(settings, "image_api_key", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "cloudflare_account_id", None)
    monkeypatch.setattr(settings, "cloudflare_api_token", None)
    monkeypatch.setattr(settings, "cloudflare_image_timeout_seconds", 300)
    monkeypatch.setattr(settings, "qwencloud_api_key", None)
    monkeypatch.setattr(settings, "qwencloud_api_base_url", "https://maas.qwencloudapi.com/api/v1")
    monkeypatch.setattr(settings, "qwencloud_image_timeout_seconds", 600)


def test_image_factory_selects_cloudflare_provider(monkeypatch):
    reset_image_settings(monkeypatch)
    monkeypatch.setattr(settings, "image_provider", "cloudflare")
    monkeypatch.setattr(settings, "image_model", "@cf/black-forest-labs/flux-2-dev")
    monkeypatch.setattr(settings, "cloudflare_account_id", "account-id")
    monkeypatch.setattr(settings, "cloudflare_api_token", "token")
    monkeypatch.setattr(settings, "cloudflare_image_timeout_seconds", 345)

    provider = get_image_provider()

    assert isinstance(provider, CloudflareImageProvider)
    assert provider.provider_name == "cloudflare"
    assert provider.model_name == "@cf/black-forest-labs/flux-2-dev"
    assert provider.timeout_seconds == 345


def test_image_factory_cloudflare_missing_config_is_not_configured(monkeypatch):
    reset_image_settings(monkeypatch)
    monkeypatch.setattr(settings, "image_provider", "cloudflare")
    monkeypatch.setattr(settings, "image_model", "@cf/black-forest-labs/flux-2-dev")
    monkeypatch.setattr(settings, "cloudflare_account_id", "account-id")

    provider = get_image_provider()

    assert isinstance(provider, NotConfiguredImageProvider)


def test_cloudflare_provider_sends_original_room_image_as_multipart(tmp_path):
    image_path = tmp_path / "room.jpg"
    original_bytes = write_image(image_path, size=(1024, 512))
    encoded = base64.b64encode(JPEG_BYTES).decode("ascii")
    fake_client = FakeClient(response=response(json_body={"success": True, "result": {"image": encoded}}))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    result = provider.generate_design(image_path, "Decorate using Product ID 1.")

    assert result.data == JPEG_BYTES
    assert result.content_type == "image/jpeg"
    call = fake_client.calls[0]
    assert call["url"].endswith("/ai/run/@cf/black-forest-labs/flux-2-dev")
    assert call["json"] is None
    assert "Content-Type" not in call["headers"]
    assert call["headers"]["Authorization"] == "Bearer token"
    assert "input_image_0" in call["files"]
    filename, sent_bytes, content_type = call["files"]["input_image_0"]
    assert filename == "input_image_0.jpg"
    assert content_type == "image/jpeg"
    assert sent_bytes
    assert image_path.read_bytes() == original_bytes


def test_cloudflare_provider_preprocesses_image_preserving_aspect_ratio(tmp_path):
    image_path = tmp_path / "wide-room.jpg"
    write_image(image_path, size=(1200, 600))
    encoded = base64.b64encode(JPEG_BYTES).decode("ascii")
    fake_client = FakeClient(response=response(json_body={"success": True, "result": {"image": encoded}}))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    provider.generate_design(image_path, "Decorate this room.")

    _filename, sent_bytes, _content_type = fake_client.calls[0]["files"]["input_image_0"]
    width, height = image_size(sent_bytes)
    assert width < 512
    assert height < 512
    assert width == 511
    assert height == 256


def test_cloudflare_provider_prompt_references_image_0(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    encoded = base64.b64encode(JPEG_BYTES).decode("ascii")
    fake_client = FakeClient(response=response(json_body={"success": True, "result": {"image": encoded}}))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    provider.generate_design(image_path, "Decorate using Product ID 3.")

    prompt = fake_client.calls[0]["data"]["prompt"]
    assert prompt.startswith("Use image 0 as the original room.")
    assert "Preserve the original room geometry" in prompt
    assert "Product ID 3" in prompt


def test_cloudflare_provider_returns_generated_image_from_binary_response(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    fake_client = FakeClient(response=response(content=JPEG_BYTES, content_type="image/jpeg"))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    result = provider.generate_design(image_path, "Decorate this room.")

    assert result.data == JPEG_BYTES
    assert result.content_type == "image/jpeg"


def test_cloudflare_provider_rejects_empty_or_missing_image(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    fake_client = FakeClient(response=response(json_body={"success": True, "result": {}}))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "CLOUDFLARE_IMAGE_RESPONSE_ERROR"


def test_cloudflare_provider_rejects_non_image_output(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    encoded = base64.b64encode(b"not an image").decode("ascii")
    fake_client = FakeClient(response=response(json_body={"success": True, "result": {"image": encoded}}))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "CLOUDFLARE_IMAGE_RESPONSE_ERROR"
    assert "not a valid image" in exc_info.value.message


def test_cloudflare_provider_classifies_non_json_error_response(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    fake_client = FakeClient(response=response(content=b"upstream proxy failure", content_type="text/plain"))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "CLOUDFLARE_IMAGE_RESPONSE_ERROR"
    assert "not valid JSON" in exc_info.value.message


def test_cloudflare_provider_classifies_invalid_base64_response(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    fake_client = FakeClient(response=response(json_body={"success": True, "result": {"image": "%%%"}}))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "CLOUDFLARE_IMAGE_RESPONSE_ERROR"
    assert "invalid base64" in exc_info.value.message


@pytest.mark.parametrize(
    ("status_code", "body", "expected_code"),
    [
        (400, "invalid image input", "CLOUDFLARE_IMAGE_INPUT_ERROR"),
        (401, "unauthorized token", "CLOUDFLARE_IMAGE_AUTH_ERROR"),
        (429, "rate limit exceeded", "CLOUDFLARE_IMAGE_QUOTA_ERROR"),
        (404, "model not found", "CLOUDFLARE_IMAGE_MODEL_ERROR"),
        (500, "upstream error", "CLOUDFLARE_IMAGE_SERVER_ERROR"),
    ],
)
def test_cloudflare_provider_maps_http_errors_safely(tmp_path, status_code, body, expected_code):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    fake_client = FakeClient(response=response(status_code=status_code, content=body.encode(), content_type="text/plain"))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="secret-token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
        sleep=lambda _: None,
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == expected_code
    assert "secret-token" not in exc_info.value.message


def test_cloudflare_provider_maps_network_errors(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    fake_client = FakeClient(error=httpx.ConnectError("connection failed"))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
        sleep=lambda _: None,
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "CLOUDFLARE_IMAGE_REQUEST_FAILED"


def test_cloudflare_provider_uses_configured_read_timeout():
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        timeout_seconds=300,
    )

    timeout = provider._timeout()

    assert timeout.connect == 10
    assert timeout.read == 300
    assert timeout.write == 30
    assert timeout.pool == 10


def test_cloudflare_provider_maps_read_timeout_safely(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    fake_client = FakeClient(error=httpx.ReadTimeout("read timed out"))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
        sleep=lambda _: None,
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "CLOUDFLARE_IMAGE_REQUEST_FAILED"
    assert "timed out" in exc_info.value.message


def test_cloudflare_provider_truncates_prompt_to_model_limit(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    encoded = base64.b64encode(JPEG_BYTES).decode("ascii")
    fake_client = FakeClient(response=response(json_body={"success": True, "result": {"image": encoded}}))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    provider.generate_design(image_path, "x" * 5000)

    assert len(fake_client.calls[0]["data"]["prompt"]) <= 4096


def test_cloudflare_provider_sends_product_reference_images_as_multipart(tmp_path):
    room_path = tmp_path / "room.jpg"
    product_a = tmp_path / "product-a.jpg"
    product_b = tmp_path / "product-b.jpg"
    write_image(room_path, size=(1024, 512))
    write_image(product_a, size=(800, 800))
    write_image(product_b, size=(600, 900))
    encoded = base64.b64encode(JPEG_BYTES).decode("ascii")
    fake_client = FakeClient(response=response(json_body={"success": True, "result": {"image": encoded}}))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    provider.generate_design(room_path, "Decorate with selected products.", reference_image_paths=[product_a, product_b])

    files = fake_client.calls[0]["files"]
    assert set(files) == {"input_image_0", "input_image_1", "input_image_2"}
    assert files["input_image_0"][0] == "input_image_0.jpg"
    assert files["input_image_1"][0] == "input_image_1.jpg"
    assert files["input_image_2"][0] == "input_image_2.jpg"
    assert files["input_image_1"][2] == "image/jpeg"
    assert files["input_image_2"][2] == "image/jpeg"


def test_cloudflare_provider_caps_references_at_three(tmp_path):
    room_path = tmp_path / "room.jpg"
    write_image(room_path)
    product_images = []
    for index in range(5):
        path = tmp_path / f"product-{index}.jpg"
        write_image(path)
        product_images.append(path)
    encoded = base64.b64encode(JPEG_BYTES).decode("ascii")
    fake_client = FakeClient(response=response(json_body={"success": True, "result": {"image": encoded}}))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    provider.generate_design(room_path, "Decorate with selected products.", reference_image_paths=product_images)

    files = fake_client.calls[0]["files"]
    assert set(files) == {"input_image_0", "input_image_1", "input_image_2", "input_image_3"}
    assert "input_image_4" not in files


def test_cloudflare_provider_prompt_describes_reference_images(tmp_path):
    room_path = tmp_path / "room.jpg"
    write_image(room_path)
    encoded = base64.b64encode(JPEG_BYTES).decode("ascii")
    fake_client = FakeClient(response=response(json_body={"success": True, "result": {"image": encoded}}))
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: fake_client,
    )

    provider.generate_design(room_path, "Decorate this room.", reference_image_paths=[room_path, room_path])

    prompt = fake_client.calls[0]["data"]["prompt"]
    assert prompt.startswith("Use image 0 as the original room.")
    assert "Use images 1 through 2 as visual references" in prompt


class ScriptedClient:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = []

    def post(self, url, headers, data=None, files=None, json=None):
        self.calls.append({"url": url, "headers": headers, "data": data, "files": files, "json": json})
        outcome = self.outcomes[min(len(self.calls) - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_scripted_provider(outcomes):
    client = ScriptedClient(outcomes)
    slept: list[float] = []
    provider = CloudflareImageProvider(
        account_id="account-id",
        api_token="token",
        model_name="@cf/black-forest-labs/flux-2-dev",
        client_factory=lambda: client,
        sleep=slept.append,
    )
    return provider, client, slept


def test_cloudflare_provider_retries_transient_server_error_then_succeeds(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    encoded = base64.b64encode(JPEG_BYTES).decode("ascii")
    provider, client, slept = make_scripted_provider(
        [
            response(status_code=500, content=b"internal server error", content_type="text/plain"),
            response(json_body={"success": True, "result": {"image": encoded}}),
        ]
    )

    result = provider.generate_design(image_path, "Decorate this room.")

    assert result.data == JPEG_BYTES
    assert len(client.calls) == 2
    assert slept == [2.0]


def test_cloudflare_provider_does_not_retry_internal_error_envelope(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    internal_error = httpx.Response(
        status_code=200,
        json={"success": False, "errors": [{"code": 3043, "message": "AiError: Internal server error"}], "result": {}},
        headers={"cf-ray": "test-ray-id"},
    )
    provider, client, slept = make_scripted_provider([internal_error])

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "CLOUDFLARE_IMAGE_SERVER_ERROR"
    assert "test-ray-id" in exc_info.value.message
    assert len(client.calls) == 1
    assert slept == []


def test_cloudflare_provider_includes_http_status_and_request_id_in_failure(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    failed_response = httpx.Response(
        status_code=500,
        text='{"errors":[{"code":3043,"message":"Internal server error"}]}',
        headers={"cf-ray": "test-ray-id"},
    )
    provider, client, slept = make_scripted_provider([failed_response])

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "CLOUDFLARE_IMAGE_SERVER_ERROR"
    assert "HTTP 500" in exc_info.value.message
    assert "test-ray-id" in exc_info.value.message
    assert len(client.calls) == 1
    assert slept == []


def test_cloudflare_provider_does_not_retry_http_500_code_3043(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    failed_response = httpx.Response(
        status_code=500,
        json={"success": False, "errors": [{"code": 3043, "message": "AiError: Internal server error"}]},
        headers={"cf-ray": "test-ray-id"},
    )
    provider, client, slept = make_scripted_provider([failed_response])

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "CLOUDFLARE_IMAGE_SERVER_ERROR"
    assert "test-ray-id" in exc_info.value.message
    assert len(client.calls) == 1
    assert slept == []


def test_cloudflare_provider_exhausts_retries_on_server_error(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    provider, client, slept = make_scripted_provider(
        [response(status_code=500, content=b"internal server error", content_type="text/plain")]
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "CLOUDFLARE_IMAGE_SERVER_ERROR"
    assert exc_info.value.transient is True
    assert len(client.calls) == 4
    assert slept == [2.0, 4.0, 8.0]


def test_cloudflare_provider_retries_read_timeout_then_succeeds(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    encoded = base64.b64encode(JPEG_BYTES).decode("ascii")
    provider, client, slept = make_scripted_provider(
        [
            httpx.ReadTimeout("read timed out"),
            response(json_body={"success": True, "result": {"image": encoded}}),
        ]
    )

    result = provider.generate_design(image_path, "Decorate this room.")

    assert result.data == JPEG_BYTES
    assert len(client.calls) == 2
    assert slept == [2.0]


def test_cloudflare_provider_does_not_retry_auth_error(tmp_path):
    image_path = tmp_path / "room.jpg"
    write_image(image_path)
    provider, client, slept = make_scripted_provider(
        [response(status_code=401, content=b"unauthorized token", content_type="text/plain")]
    )

    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(image_path, "Decorate this room.")

    assert exc_info.value.code == "CLOUDFLARE_IMAGE_AUTH_ERROR"
    assert len(client.calls) == 1
    assert slept == []
