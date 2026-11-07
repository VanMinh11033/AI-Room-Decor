import base64
from contextlib import contextmanager
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.ai.image.base import ImageProviderError
from app.ai.image.factory import NotConfiguredImageProvider, get_image_provider, settings
from app.ai.image.qwen_provider import MODEL_NAME, QwenCloudImageProvider


def make_image(path, size=(384, 384), color=(20, 110, 180)):
    Image.new("RGB", size, color).save(path, format="JPEG")
    return path


def png_bytes():
    output = BytesIO()
    Image.new("RGB", (384, 384), (190, 140, 90)).save(output, format="PNG")
    return output.getvalue()


class FakeClient:
    def __init__(self, generation_response=None, image_response=None):
        self.generation_response = generation_response or httpx.Response(200, json={
            "output": {"choices": [{"message": {"content": [{"image": "https://dashscope-result.oss-cn-beijing.aliyuncs.com/result.png"}]}}]},
            "usage": {"image_count": 1, "width": 1024, "height": 1024},
        })
        self.image_response = image_response or httpx.Response(200, content=png_bytes(), headers={"content-type": "image/png"})
        self.generation_response._request = httpx.Request("POST", "https://maas.qwencloudapi.com/api/v1/generation")
        self.image_response._request = httpx.Request("GET", "https://dashscope-result.oss-cn-beijing.aliyuncs.com/result.png")
        self.posts = []
        self.gets = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return self.generation_response

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return self.image_response

    @contextmanager
    def stream(self, method, url, **kwargs):
        assert method == "GET"
        self.gets.append((url, kwargs))
        yield self.image_response


def test_qwen_provider_posts_room_and_product_refs_as_base64_then_downloads_output(tmp_path):
    room = make_image(tmp_path / "room.jpg")
    sofa = make_image(tmp_path / "sofa.jpg", color=(10, 20, 30))
    table = make_image(tmp_path / "table.jpg", color=(40, 50, 60))
    lamp = make_image(tmp_path / "lamp.jpg", color=(70, 80, 90))
    client = FakeClient()
    provider = QwenCloudImageProvider("private-test-key", client_factory=lambda: client)

    result = provider.generate_design(room, "Use warm Japandi style.", [sofa, table, lamp])

    assert result.data == png_bytes()
    assert result.content_type == "image/png"
    assert result.usage.estimated_cost == 0.04
    url, request = client.posts[0]
    assert url.endswith("/services/aigc/multimodal-generation/generation")
    assert request["headers"]["Authorization"] == "Bearer private-test-key"
    body = request["json"]
    assert body["model"] == MODEL_NAME
    assert body["parameters"]["n"] == 1
    content = body["input"]["messages"][0]["content"]
    assert len(content) == 5
    assert base64.b64decode(content[0]["image"].split(",", 1)[1]).startswith(b"\xff\xd8")
    assert "Image 1 is the original room" in content[-1]["text"]
    assert "Image 4 is selected catalog product reference 3" in content[-1]["text"]
    assert client.gets[0][1]["follow_redirects"] is False


def test_qwen_provider_rejects_more_than_nine_product_images_without_request(tmp_path):
    room = make_image(tmp_path / "room.jpg")
    client = FakeClient()
    provider = QwenCloudImageProvider("test", client_factory=lambda: client)

    with pytest.raises(ImageProviderError) as error:
        provider.generate_design(room, "room", [room] * 10)

    assert error.value.code == "QWENCLOUD_IMAGE_REFERENCE_LIMIT_EXCEEDED"
    assert not client.posts


def test_qwen_provider_validates_input_dimensions_and_file_size(tmp_path, monkeypatch):
    small = make_image(tmp_path / "small.jpg", size=(200, 200))
    provider = QwenCloudImageProvider("test", client_factory=FakeClient)
    with pytest.raises(ImageProviderError, match="384") as error:
        provider.generate_design(small, "room")
    assert error.value.code == "QWENCLOUD_IMAGE_INPUT_DIMENSIONS_INVALID"

    room = make_image(tmp_path / "room.jpg")
    monkeypatch.setattr("app.ai.image.qwen_provider.MAX_IMAGE_BYTES", 10)
    with pytest.raises(ImageProviderError) as error:
        provider.generate_design(room, "room")
    assert error.value.code == "QWENCLOUD_IMAGE_INPUT_TOO_LARGE"


def test_qwen_provider_rejects_non_qwen_result_hosts(tmp_path):
    room = make_image(tmp_path / "room.jpg")
    client = FakeClient(generation_response=httpx.Response(200, json={
        "output": {"choices": [{"message": {"content": [{"image": "https://127.0.0.1/private.png"}]}}]},
    }))
    provider = QwenCloudImageProvider("test", client_factory=lambda: client)

    with pytest.raises(ImageProviderError) as error:
        provider.generate_design(room, "room")

    assert error.value.code == "QWENCLOUD_IMAGE_RESPONSE_ERROR"
    assert not client.gets


def test_qwen_factory_requires_key_and_explicit_supported_model(monkeypatch):
    monkeypatch.setattr(settings, "image_provider", "qwencloud")
    monkeypatch.setattr(settings, "image_model", MODEL_NAME)
    monkeypatch.setattr(settings, "qwencloud_api_key", None)
    assert isinstance(get_image_provider(), NotConfiguredImageProvider)

    monkeypatch.setattr(settings, "qwencloud_api_key", "test-key")
    assert isinstance(get_image_provider(), QwenCloudImageProvider)

    monkeypatch.setattr(settings, "image_model", "some-other-model")
    assert isinstance(get_image_provider(), NotConfiguredImageProvider)
