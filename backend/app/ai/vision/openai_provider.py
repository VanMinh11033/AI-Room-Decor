import base64
import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from app.ai.vision.base import VisionAnalysis, VisionProviderError, VisionUsage
from app.core.config import settings
from app.schemas.room_project import RoomAnalysisResult


class OpenAIVisionProvider:
    provider_name = "openai"

    def __init__(self, api_key: str, model_name: str, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = (base_url or settings.vision_api_base_url).rstrip("/")

    def analyze_room(self, image_path: Path, content_type: str) -> VisionAnalysis:
        image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        schema = RoomAnalysisResult.model_json_schema()
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You analyze room photos for an interior decor application. "
                        "Return only valid JSON that matches the provided schema. "
                        "Do not recommend products or generate decorated images."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze this room image. Identify room type, dominant colors, "
                                "existing objects, empty decor areas, lighting, design characteristics, "
                                "layout summary, and confidence."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{image_data}",
                                "detail": "auto",
                            },
                        },
                    ],
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "room_analysis",
                    "schema": schema,
                    "strict": False,
                },
            },
        }
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            response.raise_for_status()
            body = response.json()
            result = self._parse_result(body)
            usage = body.get("usage") or {}
            return VisionAnalysis(
                result=result,
                raw_response={"id": body.get("id"), "usage": usage},
                usage=VisionUsage(
                    input_tokens=int(usage.get("prompt_tokens") or 0),
                    output_tokens=int(usage.get("completion_tokens") or 0),
                    total_tokens=int(usage.get("total_tokens") or 0),
                    estimated_cost=0,
                ),
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500] if exc.response is not None else str(exc)
            raise VisionProviderError("VISION_PROVIDER_HTTP_ERROR", detail) from exc
        except (httpx.HTTPError, OSError) as exc:
            raise VisionProviderError("VISION_PROVIDER_REQUEST_FAILED", str(exc)) from exc
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise VisionProviderError("VISION_PROVIDER_MALFORMED_RESPONSE", str(exc)) from exc

    def _parse_result(self, body: dict[str, Any]) -> RoomAnalysisResult:
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content) if isinstance(content, str) else content
        return RoomAnalysisResult.model_validate(parsed)
