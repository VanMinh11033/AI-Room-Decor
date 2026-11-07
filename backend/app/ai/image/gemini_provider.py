import base64
import re
from pathlib import Path
from typing import Any, Callable

from app.ai.image.base import GeneratedImage, ImageGenerationUsage, ImageProviderError

MAX_INPUT_IMAGES = 14
MAX_REFERENCE_IMAGES = MAX_INPUT_IMAGES - 1
MAX_INLINE_REQUEST_BYTES = 20 * 1024 * 1024
INLINE_REQUEST_OVERHEAD_BYTES = 64 * 1024

_ERROR_CODE_PATTERN = re.compile(r"^\s*(\d{3})\b")
_ERROR_STATUS_PATTERN = re.compile(r"^\s*\d{3}\s+([A-Z_]+)")

_SECRET_PATTERNS = re.compile(
    r"(?:Bearer\s+[^\s,;]+|sk-[a-zA-Z0-9_\-]{8,}|AIza[0-9A-Za-z\-_]{20,}|AQ\.[a-zA-Z0-9_\-\.]{20,}|(?:token|key|secret|password)=[^\s&,;]+|secret-[a-zA-Z0-9_\-]+)",
    re.IGNORECASE,
)

_AUTH_MARKERS = (
    "unauthenticated",
    "permission_denied",
    "permission denied",
    "api key not valid",
    "api_key_invalid",
    "invalid api key",
    "api key",
    "access_token_type_unsupported",
    "access token",
)
_QUOTA_MARKERS = (
    "resource_exhausted",
    "resource exhausted",
    "quota",
    "rate limit",
    "rate_limit",
    "too many requests",
)
_MODEL_MARKERS = (
    "not found",
    "not_found",
    "does not exist",
    "unsupported model",
    "is not supported",
    "unknown model",
)
_TRANSIENT_MARKERS = (
    "unavailable",
    "high demand",
    "overloaded",
    "try again later",
    "temporarily",
)


class GeminiImageProvider:
    provider_name = "gemini"
    MAX_INPUT_IMAGES = MAX_INPUT_IMAGES

    def __init__(self, api_key: str, model_name: str, client_factory: Callable | None = None) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self._client_factory = client_factory

    def generate_design(
        self,
        source_image_path: Path,
        prompt: str,
        reference_image_paths: list[Path] | None = None,
    ) -> GeneratedImage:
        reference_image_paths = list(reference_image_paths or [])
        if len(reference_image_paths) > MAX_REFERENCE_IMAGES:
            raise ImageProviderError(
                "GEMINI_IMAGE_REFERENCE_LIMIT_EXCEEDED",
                f"This Gemini model accepts at most {MAX_INPUT_IMAGES} images total: one room image and {MAX_REFERENCE_IMAGES} product references.",
            )
        try:
            image_paths = [source_image_path, *reference_image_paths]
            estimated_payload_bytes = len(self._prompt(prompt, len(reference_image_paths)).encode("utf-8"))
            estimated_payload_bytes += sum(((path.stat().st_size + 2) // 3) * 4 for path in image_paths)
            if estimated_payload_bytes > MAX_INLINE_REQUEST_BYTES - INLINE_REQUEST_OVERHEAD_BYTES:
                raise ImageProviderError(
                    "GEMINI_IMAGE_REQUEST_TOO_LARGE",
                    "Gemini inline image requests must stay below 20 MiB. Resize the room or product images, or select fewer products.",
                )
            client, types = self._build_client()
            image_parts = [
                types.Part.from_bytes(data=path.read_bytes(), mime_type=self._content_type(path))
                for path in image_paths
            ]
            response = client.models.generate_content(
                model=self.model_name,
                contents=[self._prompt(prompt, len(reference_image_paths)), *image_parts],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"], temperature=0.4),
            )
            data, content_type = self._extract_image(response)
            return GeneratedImage(data=data, content_type=content_type, usage=self._usage(response))
        except ImageProviderError:
            raise
        except (OSError, TimeoutError, ConnectionError) as exc:
            raise ImageProviderError("GEMINI_IMAGE_REQUEST_FAILED", self._safe_error_message(str(exc))) from exc
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ImageProviderError("GEMINI_IMAGE_RESPONSE_ERROR", self._safe_error_message(str(exc))) from exc
        except Exception as exc:
            raise self._map_provider_error(exc) from exc

    def _build_client(self):
        if self._client_factory is not None:
            return self._client_factory()
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ImageProviderError("GEMINI_IMAGE_SDK_NOT_INSTALLED", "google-genai package is not installed") from exc
        return genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
        ), types

    def _extract_image(self, response: Any) -> tuple[bytes, str]:
        for part in self._response_parts(response):
            inline_data = getattr(part, "inline_data", None)
            if inline_data is None and isinstance(part, dict):
                inline_data = part.get("inline_data")
            if inline_data is None:
                continue
            raw_data = self._field(inline_data, "data")
            if not raw_data:
                continue
            content_type = self._field(inline_data, "mime_type") or "image/png"
            if isinstance(raw_data, bytes):
                return raw_data, content_type
            if isinstance(raw_data, str):
                return base64.b64decode(raw_data), content_type
        raise ImageProviderError("GEMINI_IMAGE_RESPONSE_ERROR", "Gemini response did not contain generated image data")

    def _response_parts(self, response: Any) -> list[Any]:
        candidates = self._field(response, "candidates") or []
        parts: list[Any] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None and isinstance(candidate, dict):
                content = candidate.get("content")
            candidate_parts = self._field(content, "parts") or []
            parts.extend(candidate_parts)
        if not parts:
            direct_parts = self._field(response, "parts")
            if direct_parts:
                parts.extend(direct_parts)
        return parts

    def _usage(self, response: Any) -> ImageGenerationUsage | None:
        metadata = getattr(response, "usage_metadata", None)
        if metadata is None:
            return None
        input_tokens = int(getattr(metadata, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(metadata, "candidates_token_count", 0) or 0)
        total_tokens = int(getattr(metadata, "total_token_count", input_tokens + output_tokens) or 0)
        return ImageGenerationUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens, estimated_cost=0)

    def _prompt(self, prompt: str, reference_count: int = 0) -> str:
        reference_instructions = [
            "The first attached image is the user's original room; keep it as the scene to edit.",
            "Following attached images are product photos in the same order as their numbered references in the design brief.",
            "Place the selected products naturally in the room. Preserve their recognizable silhouette, color, materials, and distinctive details as closely as possible.",
            "Do not replace selected products with unrelated items when their reference photo is provided.",
        ]
        if reference_count:
            reference_instructions.append(f"There are {reference_count} selected product photo references after the room image.")
        return "\n".join(
            [
                "Create one photorealistic interior design image by editing the provided source room photo.",
                "Preserve the original room geometry, camera angle, windows, walls, floor, doors, and fixed architecture.",
                "Arrange furniture and decor at realistic scale for the detected room type and keep the room layout plausible.",
                *reference_instructions,
                "Decorate according to the user preferences and selected real catalog products in the prompt.",
                "Do not invent product IDs or add text. Product appearance is guided by references and is not guaranteed to match exactly.",
                prompt,
            ]
        )

    def _content_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"

    def _field(self, value: Any, name: str) -> Any:
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    def _extract_status(self, exc: Exception) -> tuple[int | None, str | None]:
        raw = str(exc)
        status_code = getattr(exc, "code", None)
        if not isinstance(status_code, int):
            response = getattr(exc, "response", None)
            resp_status = getattr(response, "status_code", None)
            if isinstance(resp_status, int):
                status_code = resp_status
            else:
                match = _ERROR_CODE_PATTERN.match(raw)
                status_code = int(match.group(1)) if match else None
        status = getattr(exc, "status", None)
        if not isinstance(status, str):
            match = _ERROR_STATUS_PATTERN.match(raw)
            status = match.group(1) if match else None
        return status_code, status

    def _map_provider_error(self, exc: Exception) -> ImageProviderError:
        status_code, status = self._extract_status(exc)
        message = self._safe_error_message(str(exc))
        haystack = f"{status or ''} {message}".lower()

        # Priority 1: Exact HTTP status code matching
        if status_code in (401, 403):
            return ImageProviderError("GEMINI_IMAGE_AUTH_ERROR", message)
        if status_code == 404:
            return ImageProviderError("GEMINI_IMAGE_MODEL_ERROR", message)
        if status_code == 429:
            return ImageProviderError("GEMINI_IMAGE_QUOTA_ERROR", message)
        if status_code in (502, 503, 504):
            return ImageProviderError("GEMINI_IMAGE_UNAVAILABLE", message)

        # Priority 2: Text markers (Auth -> Quota -> Transient -> Model)
        if any(marker in haystack for marker in _AUTH_MARKERS):
            return ImageProviderError("GEMINI_IMAGE_AUTH_ERROR", message)
        if any(marker in haystack for marker in _QUOTA_MARKERS):
            return ImageProviderError("GEMINI_IMAGE_QUOTA_ERROR", message)
        if any(marker in haystack for marker in _TRANSIENT_MARKERS):
            return ImageProviderError("GEMINI_IMAGE_UNAVAILABLE", message)
        if any(marker in haystack for marker in _MODEL_MARKERS):
            return ImageProviderError("GEMINI_IMAGE_MODEL_ERROR", message)
        if "http" in haystack or "status" in haystack:
            return ImageProviderError("GEMINI_IMAGE_HTTP_ERROR", message)
        return ImageProviderError("GEMINI_IMAGE_REQUEST_FAILED", message)

    def _safe_error_message(self, message: str) -> str:
        if not message:
            return ""
        safe = message
        if self.api_key:
            safe = safe.replace(self.api_key, "[redacted]")
        safe = _SECRET_PATTERNS.sub("[REDACTED]", safe)
        return safe[:500]
