import base64
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image, UnidentifiedImageError

from app.ai.image.base import GeneratedImage, ImageGenerationUsage, ImageProviderError

MAX_INPUT_IMAGES = 10
MAX_REFERENCE_IMAGES = MAX_INPUT_IMAGES - 1
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_IMAGE_SIDE = 384
MAX_IMAGE_SIDE = 3072
MAX_ASPECT_RATIO = 10
MAX_OUTPUT_BYTES = 25 * 1024 * 1024
SUPPORTED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "BMP": "image/bmp", "TIFF": "image/tiff", "GIF": "image/gif"}
API_PATH = "/services/aigc/multimodal-generation/generation"
MODEL_NAME = "qwen-image-2.1-pro"


class QwenCloudImageProvider:
    provider_name = "qwencloud"
    model_name = MODEL_NAME
    MAX_INPUT_IMAGES = MAX_INPUT_IMAGES
    requires_all_product_references = True

    def __init__(
        self,
        api_key: str,
        model_name: str = MODEL_NAME,
        base_url: str = "https://maas.qwencloudapi.com/api/v1",
        timeout_seconds: int = 600,
        client_factory=None,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client_factory = client_factory

    def generate_design(
        self,
        source_image_path: Path,
        prompt: str,
        reference_image_paths: list[Path] | None = None,
    ) -> GeneratedImage:
        references = list(reference_image_paths or [])
        if len(references) > MAX_REFERENCE_IMAGES:
            raise ImageProviderError(
                "QWENCLOUD_IMAGE_REFERENCE_LIMIT_EXCEEDED",
                f"Qwen Image accepts at most {MAX_INPUT_IMAGES} images total: one room image and {MAX_REFERENCE_IMAGES} product references.",
            )
        try:
            paths = [source_image_path, *references]
            images = [self._encode_image(path) for path in paths]
            payload = {
                "model": self.model_name,
                "input": {
                    "messages": [{
                        "role": "user",
                        "content": [
                            *({"image": item} for item in images),
                            {"text": self._prompt(prompt, len(references))},
                        ],
                    }],
                },
                "parameters": {"n": 1, "prompt_extend": True, "watermark": False},
            }
            with self._client() as client:
                response = client.post(
                    f"{self.base_url}{API_PATH}",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
                image_url = self._extract_image_url(body)
                self._validate_result_url(image_url)
                with client.stream("GET", image_url, follow_redirects=False) as image_response:
                    image_response.raise_for_status()
                    image_bytes = self._read_limited(image_response)
                    content_type = self._validate_output_image(image_bytes)
            return GeneratedImage(data=image_bytes, content_type=content_type, usage=self._usage(body))
        except ImageProviderError:
            raise
        except httpx.HTTPStatusError as exc:
            response = exc.response
            status_code = response.status_code if response is not None else 0
            body_text = response.text if response is not None else str(exc)
            code = self._status_error_code(status_code)
            raise ImageProviderError(code, self._safe_error(body_text)) from exc
        except (httpx.HTTPError, OSError, TimeoutError) as exc:
            raise ImageProviderError("QWENCLOUD_IMAGE_REQUEST_FAILED", self._safe_error(str(exc))) from exc
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError, UnidentifiedImageError) as exc:
            raise ImageProviderError("QWENCLOUD_IMAGE_RESPONSE_ERROR", self._safe_error(str(exc))) from exc
        except Exception as exc:
            raise ImageProviderError("QWENCLOUD_IMAGE_REQUEST_FAILED", self._safe_error(str(exc))) from exc

    def _client(self):
        if self._client_factory is not None:
            return self._client_factory()
        return httpx.Client(timeout=httpx.Timeout(self.timeout_seconds, connect=20), follow_redirects=False)

    def _encode_image(self, path: Path) -> str:
        try:
            data = path.read_bytes()
            if len(data) > MAX_IMAGE_BYTES:
                raise ImageProviderError(
                    "QWENCLOUD_IMAGE_INPUT_TOO_LARGE",
                    f"Each Qwen input image must be no larger than 10 MiB; {path.name} exceeds the limit.",
                )
            with Image.open(path) as image:
                image_format = (image.format or "").upper()
                width, height = image.size
                if image_format not in SUPPORTED_FORMATS:
                    raise ImageProviderError("QWENCLOUD_IMAGE_INPUT_FORMAT_UNSUPPORTED", "Qwen input must be JPEG, PNG, WEBP, BMP, TIFF, or GIF.")
                if width < MIN_IMAGE_SIDE or height < MIN_IMAGE_SIDE or width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE:
                    raise ImageProviderError(
                        "QWENCLOUD_IMAGE_INPUT_DIMENSIONS_INVALID",
                        "Qwen input image sides must be between 384 and 3072 pixels.",
                    )
                if max(width, height) / min(width, height) > MAX_ASPECT_RATIO:
                    raise ImageProviderError("QWENCLOUD_IMAGE_INPUT_ASPECT_RATIO_INVALID", "Qwen input image aspect ratio must not exceed 10:1.")
                image.verify()
            return f"data:{SUPPORTED_FORMATS[image_format]};base64,{base64.b64encode(data).decode('ascii')}"
        except ImageProviderError:
            raise
        except (OSError, UnidentifiedImageError) as exc:
            raise ImageProviderError("QWENCLOUD_IMAGE_INPUT_INVALID", f"Input image {path.name} could not be read as a supported image.") from exc

    def _prompt(self, prompt: str, reference_count: int) -> str:
        image_map = ["Image 1 is the original room photograph and must remain the edited scene."]
        image_map.extend(
            f"Image {index + 2} is selected catalog product reference {index + 1}; use every reference in order."
            for index in range(reference_count)
        )
        return "\n".join([
            "Edit the original room photo into one photorealistic interior design image.",
            "Preserve the room geometry, camera angle, doors, windows, walls, floor, and fixed architecture as closely as possible.",
            "Place the selected real catalog products at a plausible scale and location. Keep each product's recognizable shape, colors, materials, and distinctive features; do not silently omit or replace any selected item.",
            "Follow the requested room type, style, color choices, and customer text instructions below. Visual similarity is best effort, not an exact reproduction guarantee.",
            *image_map,
            "The backend design brief follows; its REFERENCE 0 denotes the room and REFERENCE 1 onward denote catalog products in the same order as Images 2 onward.",
            prompt,
        ])

    def _extract_image_url(self, body: dict) -> str:
        choices = body.get("output", {}).get("choices", [])
        if not choices:
            raise ImageProviderError("QWENCLOUD_IMAGE_RESPONSE_ERROR", "Qwen response contained no generated image.")
        content = choices[0].get("message", {}).get("content", [])
        for item in content:
            image_url = item.get("image") if isinstance(item, dict) else None
            if image_url:
                return image_url
        raise ImageProviderError("QWENCLOUD_IMAGE_RESPONSE_ERROR", "Qwen response contained no generated image URL.")

    def _validate_result_url(self, image_url: str) -> None:
        try:
            parsed = urlsplit(image_url)
            host = (parsed.hostname or "").lower().rstrip(".")
            if parsed.scheme != "https" or not host or parsed.username or parsed.password:
                raise ValueError
            if host != "aliyuncs.com" and not host.endswith(".aliyuncs.com"):
                raise ValueError
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError
        except ValueError as exc:
            raise ImageProviderError("QWENCLOUD_IMAGE_RESPONSE_ERROR", "Qwen returned an invalid or unsupported image URL.") from exc

    def _read_limited(self, response: httpx.Response) -> bytes:
        length = response.headers.get("content-length")
        if length and int(length) > MAX_OUTPUT_BYTES:
            raise ImageProviderError("QWENCLOUD_IMAGE_OUTPUT_TOO_LARGE", "Generated image exceeds the 25 MiB download limit.")
        chunks = bytearray()
        for chunk in response.iter_bytes():
            chunks.extend(chunk)
            if len(chunks) > MAX_OUTPUT_BYTES:
                raise ImageProviderError("QWENCLOUD_IMAGE_OUTPUT_TOO_LARGE", "Generated image exceeds the 25 MiB download limit.")
        data = bytes(chunks)
        if not data:
            raise ImageProviderError("QWENCLOUD_IMAGE_RESPONSE_ERROR", "Qwen returned an empty image.")
        return data

    def _validate_output_image(self, data: bytes) -> str:
        try:
            with Image.open(__import__("io").BytesIO(data)) as image:
                content_type = SUPPORTED_FORMATS.get((image.format or "").upper())
                if content_type not in {"image/png", "image/jpeg", "image/webp"}:
                    raise ImageProviderError("QWENCLOUD_IMAGE_RESPONSE_ERROR", "Qwen returned an unsupported image format.")
                image.verify()
                return content_type
        except (OSError, UnidentifiedImageError) as exc:
            raise ImageProviderError("QWENCLOUD_IMAGE_RESPONSE_ERROR", "Qwen returned invalid image data.") from exc

    def _usage(self, body: dict) -> ImageGenerationUsage | None:
        usage = body.get("usage") or {}
        if not usage:
            return None
        count = int(usage.get("image_count") or usage.get("output_image_count") or 1)
        # QwenCloud's published list price is $0.04 per successfully generated image.
        return ImageGenerationUsage(estimated_cost=0.04 * count)

    def _status_error_code(self, status: int) -> str:
        if status in {401, 403}:
            return "QWENCLOUD_IMAGE_AUTH_ERROR"
        if status == 429:
            return "QWENCLOUD_IMAGE_QUOTA_ERROR"
        if status >= 500:
            return "QWENCLOUD_IMAGE_SERVER_ERROR"
        return "QWENCLOUD_IMAGE_API_ERROR"

    def _safe_error(self, message: str) -> str:
        safe = message.replace(self.api_key, "[redacted]") if self.api_key else message
        safe = re.sub(r"(?i)(bearer\s+)[^\s\"']+", r"\1[redacted]", safe)
        safe = re.sub(r"https?://[^\s\"']+", "[upstream URL redacted]", safe)
        return safe[:500]
