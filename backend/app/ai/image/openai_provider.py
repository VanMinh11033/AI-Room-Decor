import base64
import mimetypes
from pathlib import Path

import httpx

from app.ai.image.base import GeneratedImage, ImageGenerationUsage, ImageProviderError
from app.core.config import settings


class OpenAIImageProvider:
    provider_name = "openai"

    def __init__(self, api_key: str, model_name: str, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = (base_url or settings.image_api_base_url).rstrip("/")

    def generate_design(self, source_image_path: Path, prompt: str) -> GeneratedImage:
        try:
            with source_image_path.open("rb") as image_file:
                content_type = mimetypes.guess_type(source_image_path.name)[0] or "image/png"
                files = {"image": (source_image_path.name, image_file, content_type)}
                data = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "size": "1024x1024",
                    "response_format": "b64_json",
                }
                with httpx.Client(timeout=120) as client:
                    response = client.post(
                        f"{self.base_url}/images/edits",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        data=data,
                        files=files,
                    )
            response.raise_for_status()
            body = response.json()
            encoded = body["data"][0]["b64_json"]
            usage = body.get("usage") or {}
            return GeneratedImage(
                data=base64.b64decode(encoded),
                content_type="image/png",
                usage=ImageGenerationUsage(
                    input_tokens=int(usage.get("input_tokens") or 0),
                    output_tokens=int(usage.get("output_tokens") or 0),
                    total_tokens=int(usage.get("total_tokens") or 0),
                    estimated_cost=0,
                ),
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500] if exc.response is not None else str(exc)
            raise ImageProviderError("IMAGE_PROVIDER_HTTP_ERROR", detail) from exc
        except (httpx.HTTPError, OSError) as exc:
            raise ImageProviderError("IMAGE_PROVIDER_REQUEST_FAILED", str(exc)) from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ImageProviderError("IMAGE_PROVIDER_MALFORMED_RESPONSE", str(exc)) from exc
