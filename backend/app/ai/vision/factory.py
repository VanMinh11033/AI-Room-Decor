from app.ai.vision.base import VisionProvider, VisionProviderNotConfiguredError
from app.ai.vision.fallback_provider import LocalFallbackProvider
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
    if not provider or provider == "local_fallback":
        return LocalFallbackProvider(fallback_reason="LOCAL_MODE")
    if provider == "cloudflare":
        account_id = (settings.cloudflare_account_id or "").strip()
        api_token = (settings.cloudflare_api_token or "").strip()
        if not account_id or not api_token:
            return LocalFallbackProvider(fallback_reason="MISSING_API_KEY")
        from app.ai.vision.cloudflare_provider import CloudflareVisionProvider

        return CloudflareVisionProvider(
            account_id=account_id,
            api_token=api_token,
            model_name=settings.vision_model or "@cf/meta/llama-3.2-11b-vision-instruct",
        )
    if provider == "openai":
        if not settings.vision_api_key:
            return LocalFallbackProvider(fallback_reason="MISSING_API_KEY")
        return OpenAIVisionProvider(
            api_key=settings.vision_api_key,
            model_name=settings.vision_model or "gpt-4o-mini",
            base_url=settings.vision_api_base_url,
        )
    if provider == "gemini":
        api_key = (settings.gemini_api_key or "").strip()
        if not api_key:
            return LocalFallbackProvider(fallback_reason="MISSING_API_KEY")
        return GeminiVisionProvider(
            api_key=api_key,
            model_name=settings.vision_model or "gemini-2.5-flash",
        )
    return LocalFallbackProvider(fallback_reason="LOCAL_MODE")
