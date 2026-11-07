from app.ai.image.base import ImageProvider, ImageProviderNotConfiguredError
from app.ai.image.cloudflare_provider import CloudflareImageProvider
from app.ai.image.composite_provider import CompositeImageProvider
from app.ai.image.gemini_provider import GeminiImageProvider
from app.ai.image.openai_provider import OpenAIImageProvider
from app.ai.image.qwen_provider import QwenCloudImageProvider
from app.core.config import settings


class NotConfiguredImageProvider:
    provider_name = "not_configured"
    model_name = "not_configured"

    def generate_design(self, source_image_path, prompt):
        raise ImageProviderNotConfiguredError()


def get_image_provider() -> ImageProvider:
    provider = (settings.image_provider or "").strip().lower()
    if not provider:
        return NotConfiguredImageProvider()
    if provider == "composite":
        return CompositeImageProvider()
    if provider == "openai":
        if not settings.image_api_key:
            return NotConfiguredImageProvider()
        return OpenAIImageProvider(
            api_key=settings.image_api_key,
            model_name=settings.image_model or "gpt-image-1",
            base_url=settings.image_api_base_url,
        )
    if provider == "gemini":
        api_key = settings.image_api_key or settings.gemini_api_key
        if not api_key or not settings.image_model:
            return NotConfiguredImageProvider()
        return GeminiImageProvider(
            api_key=api_key,
            model_name=settings.image_model,
        )
    if provider == "cloudflare":
        if not settings.cloudflare_account_id or not settings.cloudflare_api_token or not settings.image_model:
            return NotConfiguredImageProvider()
        return CloudflareImageProvider(
            account_id=settings.cloudflare_account_id,
            api_token=settings.cloudflare_api_token,
            model_name=settings.image_model,
            timeout_seconds=settings.cloudflare_image_timeout_seconds,
            max_retries=settings.cloudflare_image_max_retries,
        )
    if provider == "qwencloud":
        if not settings.qwencloud_api_key or settings.image_model != "qwen-image-2.1-pro":
            return NotConfiguredImageProvider()
        return QwenCloudImageProvider(
            api_key=settings.qwencloud_api_key,
            model_name=settings.image_model,
            base_url=settings.qwencloud_api_base_url,
            timeout_seconds=settings.qwencloud_image_timeout_seconds,
        )
    return NotConfiguredImageProvider()
