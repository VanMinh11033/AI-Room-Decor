import base64
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

import httpx
from PIL import Image, UnidentifiedImageError

from app.ai.image.base import GeneratedImage, ImageProviderError

# FLUX.2 [dev] requires each image dimension to be strictly below 512 pixels.
MAX_INPUT_IMAGE_SIDE = 511
MAX_INPUT_IMAGES = 4
MAX_REFERENCE_IMAGES = MAX_INPUT_IMAGES - 1

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_BACKOFF_SECONDS = 2.0


class CloudflareImageProvider:
    provider_name = "cloudflare"
    MAX_INPUT_IMAGES = MAX_INPUT_IMAGES

    def __init__(
        self,
        account_id: str,
        api_token: str,
        model_name: str,
        base_url: str = "https://api.cloudflare.com/client/v4",
        timeout_seconds: int = 300,
        client_factory: Callable | None = None,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_backoff_seconds: float = DEFAULT_BASE_BACKOFF_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.account_id = account_id
        self.api_token = api_token
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client_factory = client_factory
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self._sleep = sleep

    def generate_design(
        self,
        source_image_path: Path,
        prompt: str,
        reference_image_paths: list[Path] | None = None,
    ) -> GeneratedImage:
        if not source_image_path.exists():
            raise ImageProviderError("CLOUDFLARE_IMAGE_SOURCE_NOT_FOUND", "Source room image was not found")

        reference_image_paths = reference_image_paths or []
        try:
            image_bytes, content_type, filename = self._prepare_input_image(source_image_path)
            data = {"prompt": self._fit_prompt(self._editing_prompt(prompt, len(reference_image_paths))), "steps": "8"}
            files = {"input_image_0": (filename, image_bytes, content_type)}
            for index, reference_path in enumerate(reference_image_paths[:MAX_REFERENCE_IMAGES], start=1):
                reference_bytes, reference_content_type, reference_filename = self._prepare_reference_image(reference_path, index)
                files[f"input_image_{index}"] = (reference_filename, reference_bytes, reference_content_type)
        except (OSError, UnidentifiedImageError) as exc:
            raise ImageProviderError("CLOUDFLARE_IMAGE_INPUT_ERROR", self._safe_error_message(str(exc))) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ImageProviderError("CLOUDFLARE_IMAGE_RESPONSE_ERROR", self._safe_error_message(str(exc))) from exc

        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                response = self._post(data=data, files=files)
                return self._parse_response(response)
            except ImageProviderError as exc:
                if not exc.transient or attempt >= attempts - 1:
                    raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= attempts - 1:
                    raise ImageProviderError("CLOUDFLARE_IMAGE_REQUEST_FAILED", self._safe_error_message(str(exc))) from exc
            except httpx.HTTPError as exc:
                raise ImageProviderError("CLOUDFLARE_IMAGE_API_ERROR", self._safe_error_message(str(exc))) from exc
            self._sleep(self._backoff_delay(attempt))
        raise ImageProviderError("CLOUDFLARE_IMAGE_REQUEST_FAILED", "Cloudflare request failed after retries")

    def _post(self, data: dict[str, Any], files: dict[str, tuple[str, bytes, str]]) -> httpx.Response:
        url = f"{self.base_url}/accounts/{self.account_id}/ai/run/{self.model_name}"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        if self._client_factory is not None:
            client = self._client_factory()
            return client.post(url, headers=headers, data=data, files=files)
        with httpx.Client(timeout=self._timeout()) as client:
            return client.post(url, headers=headers, data=data, files=files)

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=10,
            read=self.timeout_seconds,
            write=30,
            pool=10,
        )

    def _backoff_delay(self, attempt: int) -> float:
        return self.base_backoff_seconds * (2**attempt)

    def _parse_response(self, response: httpx.Response) -> GeneratedImage:
        if response.status_code >= 400:
            raise self._map_http_error(response)
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("image/"):
            if not response.content:
                raise ImageProviderError("CLOUDFLARE_IMAGE_RESPONSE_ERROR", "Cloudflare returned an empty image response")
            return self._validated_generated_image(response.content, content_type.split(";")[0])
        try:
            body = response.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise ImageProviderError(
                "CLOUDFLARE_IMAGE_RESPONSE_ERROR",
                "Cloudflare returned a non-image response that was not valid JSON",
            ) from exc
        if body.get("success") is False:
            error_body = body.get("errors") or body
            message = self._safe_error_message(str(error_body))
            error_codes = self._extract_cloudflare_error_codes(error_body)
            if 3043 in error_codes or "internal server error" in message.lower():
                raise ImageProviderError(
                    "CLOUDFLARE_IMAGE_SERVER_ERROR",
                    self._response_diagnostic(message, response),
                    # Cloudflare's 3043 is an opaque model-side failure. Retrying
                    # image inference automatically can duplicate billable work
                    # without correcting the request that triggered it.
                    transient=False,
                )
            raise ImageProviderError(
                "CLOUDFLARE_IMAGE_API_ERROR",
                self._response_diagnostic(message, response),
            )
        encoded = self._extract_encoded_image(body)
        image_content_type = self._extract_content_type(encoded) or "image/jpeg"
        if encoded.startswith("data:"):
            encoded = encoded.split(",", 1)[1]
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ImageProviderError("CLOUDFLARE_IMAGE_RESPONSE_ERROR", "Cloudflare returned invalid base64 image data") from exc
        if not data:
            raise ImageProviderError("CLOUDFLARE_IMAGE_RESPONSE_ERROR", "Cloudflare returned empty image data")
        return self._validated_generated_image(data, image_content_type)

    def _validated_generated_image(self, data: bytes, declared_content_type: str) -> GeneratedImage:
        try:
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageProviderError(
                "CLOUDFLARE_IMAGE_RESPONSE_ERROR",
                "Cloudflare response data is not a valid image",
            ) from exc

        content_types = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
        detected_content_type = content_types.get(image_format or "")
        if detected_content_type is None:
            raise ImageProviderError(
                "CLOUDFLARE_IMAGE_RESPONSE_ERROR",
                "Cloudflare returned an unsupported image format",
            )
        if declared_content_type.startswith("image/") and declared_content_type not in content_types.values():
            raise ImageProviderError(
                "CLOUDFLARE_IMAGE_RESPONSE_ERROR",
                "Cloudflare returned an unsupported image content type",
            )
        return GeneratedImage(data=data, content_type=detected_content_type)

    def _extract_encoded_image(self, body: dict[str, Any]) -> str:
        result = body.get("result", body)
        if isinstance(result, dict):
            image = result.get("image") or result.get("data")
        else:
            image = result
        if not isinstance(image, str) or not image:
            raise ImageProviderError("CLOUDFLARE_IMAGE_RESPONSE_ERROR", "Cloudflare response did not contain generated image data")
        return image

    def _extract_content_type(self, encoded: str) -> str | None:
        if encoded.startswith("data:") and "," in encoded:
            return encoded.split(";", 1)[0].removeprefix("data:")
        return None

    def _map_http_error(self, response: httpx.Response) -> ImageProviderError:
        message = self._response_diagnostic(self._safe_error_message(response.text[:500]), response)
        status_code = response.status_code
        lowered = message.lower()
        if status_code in {401, 403}:
            return ImageProviderError("CLOUDFLARE_IMAGE_AUTH_ERROR", message)
        if status_code == 400:
            return ImageProviderError("CLOUDFLARE_IMAGE_INPUT_ERROR", message)
        if status_code == 429 or "quota" in lowered or "rate" in lowered:
            return ImageProviderError("CLOUDFLARE_IMAGE_QUOTA_ERROR", message)
        if status_code == 404 or "not found" in lowered or "unsupported" in lowered:
            return ImageProviderError("CLOUDFLARE_IMAGE_MODEL_ERROR", message)
        if status_code >= 500:
            try:
                error_codes = self._extract_cloudflare_error_codes(response.json())
            except (ValueError, UnicodeDecodeError):
                error_codes = set()
            if 3043 in error_codes:
                return ImageProviderError("CLOUDFLARE_IMAGE_SERVER_ERROR", message)
            return ImageProviderError("CLOUDFLARE_IMAGE_SERVER_ERROR", message, transient=True)
        return ImageProviderError("CLOUDFLARE_IMAGE_API_ERROR", message)

    def _extract_cloudflare_error_codes(self, value: Any) -> set[int]:
        codes: set[int] = set()
        if isinstance(value, dict):
            code = value.get("code")
            if isinstance(code, int):
                codes.add(code)
            for nested in value.values():
                codes.update(self._extract_cloudflare_error_codes(nested))
        elif isinstance(value, list):
            for nested in value:
                codes.update(self._extract_cloudflare_error_codes(nested))
        return codes

    def _response_diagnostic(self, message: str, response: httpx.Response) -> str:
        request_id = response.headers.get("cf-ray") or response.headers.get("cf-request-id") or response.headers.get("x-request-id")
        diagnostic = f"HTTP {response.status_code}: {message}"
        if request_id:
            diagnostic += f" (Cloudflare request ID: {request_id})"
        return diagnostic[:500]

    def _prepare_input_image(self, source_image_path: Path) -> tuple[bytes, str, str]:
        return self._prepare_image(source_image_path, "input_image_0.jpg")

    def _prepare_reference_image(self, source_image_path: Path, index: int) -> tuple[bytes, str, str]:
        return self._prepare_image(source_image_path, f"input_image_{index}.jpg")

    def _prepare_image(self, source_image_path: Path, filename: str) -> tuple[bytes, str, str]:
        with Image.open(source_image_path) as image:
            image.load()
            image = image.convert("RGB")
            image.thumbnail((MAX_INPUT_IMAGE_SIDE, MAX_INPUT_IMAGE_SIDE), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=92, optimize=True)
        return buffer.getvalue(), "image/jpeg", filename

    def _editing_prompt(self, prompt: str, reference_count: int = 0) -> str:
        lines = [
            "Use image 0 as the original room.",
            "Preserve the original room geometry, camera viewpoint, walls, floor, ceiling, windows, doors, and permanent architectural elements as much as possible.",
            "Only add or modify furniture and decor requested by the system prompt. Do not invent database product IDs.",
        ]
        if reference_count > 0:
            lines.append(
                f"Use images 1 through {reference_count} as visual references for the selected catalog products, "
                "preserving their recognizable shape, main color, material appearance, and distinctive design features as closely as possible."
            )
        lines.append(prompt)
        return "\n".join(lines)

    def _fit_prompt(self, prompt: str) -> str:
        value = prompt.strip()
        if len(value) <= 4096:
            return value
        suffix = "\n[Prompt truncated to fit Cloudflare model input limit.]"
        return value[: 4096 - len(suffix)].rstrip() + suffix

    def _safe_error_message(self, message: str) -> str:
        safe = message
        for secret in (self.api_token, self.account_id):
            if secret:
                safe = safe.replace(secret, "[redacted]")
        return safe[:500]
