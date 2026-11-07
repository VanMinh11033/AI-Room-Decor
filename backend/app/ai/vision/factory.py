from app.ai.vision.base import VisionProvider, VisionProviderNotConfiguredError
from app.ai.vision.gemini_provider import GeminiVisionProvider
from app.ai.vision.openai_provider import OpenAIVisionProvider
from app.core.config import settings


class NotConfiguredVisionProvider:
    provider_name = "not_configured"
    model_name = "not_configured"

    def analyze_room(self, image_path, content_type):
        raise VisionProviderNotConfiguredError()


def get_vision_provider() -> VisionProvider:
    provider = (settings.vision_provider or "").strip().lower()
    if not provider:
        return NotConfiguredVisionProvider()
    if provider == "openai":
        if not settings.vision_api_key:
            return NotConfiguredVisionProvider()
        return OpenAIVisionProvider(
            api_key=settings.vision_api_key,
            model_name=settings.vision_model or "gpt-4o-mini",
            base_url=settings.vision_api_base_url,
        )
    if provider == "gemini":
        if not settings.gemini_api_key:
            return NotConfiguredVisionProvider()
        return GeminiVisionProvider(
            api_key=settings.gemini_api_key,
            model_name=settings.vision_model or "gemini-2.5-flash",
        )
    raise VisionProviderNotConfiguredError()
