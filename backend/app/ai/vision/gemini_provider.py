import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from app.ai.vision.base import VisionAnalysis, VisionProviderError, VisionUsage
from app.schemas.room_project import RoomAnalysisResult

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_BACKOFF_SECONDS = 2.0

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


class GeminiVisionProvider:
    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        model_name: str,
        client_factory: Callable | None = None,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_backoff_seconds: float = DEFAULT_BASE_BACKOFF_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self._client_factory = client_factory
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self._sleep = sleep

    def analyze_room(self, image_path: Path, content_type: str) -> VisionAnalysis:
        try:
            image_bytes = image_path.read_bytes()
        except (OSError, TimeoutError, ConnectionError) as exc:
            raise VisionProviderError("GEMINI_PROVIDER_REQUEST_FAILED", str(exc)) from exc

        client, types = self._build_client()
        prompt = self._prompt()

        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                return self._generate(client, types, prompt, image_bytes, content_type)
            except VisionProviderError as exc:
                if not exc.transient or attempt >= attempts - 1:
                    raise
                self._sleep(self._backoff_delay(attempt))
        raise AssertionError("unreachable: retry loop exhausted without returning or raising")

    def _generate(self, client: Any, types: Any, prompt: str, image_bytes: bytes, content_type: str) -> VisionAnalysis:
        try:
            image_part = types.Part.from_bytes(data=image_bytes, mime_type=content_type)
            response = client.models.generate_content(
                model=self.model_name,
                contents=[prompt, image_part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            result = self._parse_result(response)
            return VisionAnalysis(
                result=result,
                raw_response=self._safe_raw_response(response),
                usage=self._usage(response),
            )
        except VisionProviderError:
            raise
        except (OSError, TimeoutError, ConnectionError) as exc:
            raise VisionProviderError("GEMINI_PROVIDER_REQUEST_FAILED", str(exc)) from exc
        except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            raise VisionProviderError("GEMINI_PROVIDER_MALFORMED_RESPONSE", str(exc)) from exc
        except Exception as exc:
            raise self._classify_provider_error(exc) from exc

    def _backoff_delay(self, attempt: int) -> float:
        return self.base_backoff_seconds * (2**attempt)

    def _build_client(self):
        if self._client_factory is not None:
            return self._client_factory()
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise VisionProviderError("GEMINI_SDK_NOT_INSTALLED", "google-genai package is not installed") from exc
        return genai.Client(api_key=self.api_key), types

    def _parse_result(self, response: Any) -> RoomAnalysisResult:
        text = getattr(response, "text", None)
        if not text:
            raise ValueError("Gemini response did not contain text")
        return RoomAnalysisResult.model_validate(json.loads(self._extract_json(text)))

    def _usage(self, response: Any) -> VisionUsage | None:
        metadata = getattr(response, "usage_metadata", None)
        if metadata is None:
            return None
        input_tokens = int(getattr(metadata, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(metadata, "candidates_token_count", 0) or 0)
        total_tokens = int(getattr(metadata, "total_token_count", input_tokens + output_tokens) or 0)
        return VisionUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens, estimated_cost=0)

    def _safe_raw_response(self, response: Any) -> dict[str, Any]:
        metadata = getattr(response, "usage_metadata", None)
        return {
            "usage_metadata": {
                "prompt_token_count": getattr(metadata, "prompt_token_count", None),
                "candidates_token_count": getattr(metadata, "candidates_token_count", None),
                "total_token_count": getattr(metadata, "total_token_count", None),
            }
            if metadata is not None
            else None
        }

    def _extract_json(self, text: str) -> str:
        value = text.strip()
        if value.startswith("```"):
            value = value.strip("`").strip()
            if value.lower().startswith("json"):
                value = value[4:].strip()
        start = value.find("{")
        end = value.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("Gemini response is not valid JSON")
        return value[start : end + 1]

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

    def _classify_provider_error(self, exc: Exception) -> VisionProviderError:
        status_code, status = self._extract_status(exc)
        message = self._safe_error_message(str(exc))
        haystack = f"{status or ''} {message}".lower()

        # Priority 1: Exact HTTP status code matching
        if status_code in (401, 403):
            return VisionProviderError("GEMINI_PROVIDER_AUTH_ERROR", message, status_code=status_code)
        if status_code == 404:
            return VisionProviderError("GEMINI_PROVIDER_MODEL_ERROR", message, status_code=status_code)
        if status_code == 429:
            return VisionProviderError("GEMINI_PROVIDER_QUOTA_ERROR", message, status_code=status_code)
        if status_code in (502, 503, 504):
            return VisionProviderError(
                "GEMINI_PROVIDER_UNAVAILABLE", message, transient=True, status_code=status_code
            )

        # Priority 2: Text markers (Auth -> Quota -> Transient -> Model)
        if any(marker in haystack for marker in _AUTH_MARKERS):
            return VisionProviderError("GEMINI_PROVIDER_AUTH_ERROR", message, status_code=status_code)
        if any(marker in haystack for marker in _QUOTA_MARKERS):
            return VisionProviderError("GEMINI_PROVIDER_QUOTA_ERROR", message, status_code=status_code)
        if any(marker in haystack for marker in _TRANSIENT_MARKERS):
            return VisionProviderError(
                "GEMINI_PROVIDER_UNAVAILABLE", message, transient=True, status_code=status_code
            )
        if any(marker in haystack for marker in _MODEL_MARKERS):
            return VisionProviderError("GEMINI_PROVIDER_MODEL_ERROR", message, status_code=status_code)

        return VisionProviderError("GEMINI_PROVIDER_REQUEST_FAILED", message, status_code=status_code)

    def _safe_error_message(self, message: str) -> str:
        if not message:
            return ""
        safe = message
        if self.api_key:
            safe = safe.replace(self.api_key, "[redacted]")
        safe = _SECRET_PATTERNS.sub("[REDACTED]", safe)
        return safe[:500]

    def _prompt(self) -> str:
        return (
            "Analyze this room image for an interior decor application. "
            "Return only JSON with these fields: room_type, dominant_colors, existing_objects, empty_areas, "
            "lighting, design_characteristics, layout_summary, confidence. "
            "dominant_colors must be an array of objects with name, optional hex, optional percentage 0-100. "
            "existing_objects must be an array of objects with name and confidence 0-1. "
            "empty_areas must be an array of objects with location, optional description, suitable_for_decor boolean. "
            "lighting must be an object with type and level. "
            "design_characteristics must be an array of strings. "
            "confidence must be a number from 0 to 1. "
            "Do not recommend products and do not generate decorated images."
        )
