import logging
from pathlib import Path
from typing import Any

from app.ai.image.base import GeneratedImage, ImageGenerationUsage
from app.ai.image.composite_provider import CompositeImageProvider

logger = logging.getLogger(__name__)


class CompositeFallbackManager:
    """Safely manages automatic fallback from Gemini to local Composite Engine

    whenever Cloud AI is disabled, rate-limited, timed out, or fails validation.
    """

    def __init__(self, composite_provider: CompositeImageProvider | None = None) -> None:
        self.composite_provider = composite_provider or CompositeImageProvider()

    def should_fallback(
        self,
        cloud_ai_enabled: bool,
        api_key_configured: bool,
        error: Exception | None = None,
        verification_status: str | None = None,
    ) -> tuple[bool, str]:
        """Check if fallback to local composite engine is required."""
        if not cloud_ai_enabled:
            return True, "CLOUD_AI_DISABLED"

        if not api_key_configured:
            return True, "API_KEY_NOT_CONFIGURED"

        if error is not None:
            err_str = str(error).lower()
            code = getattr(error, "code", "") or ""
            if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str or code == "GEMINI_IMAGE_QUOTA_ERROR":
                return True, "GEMINI_QUOTA_EXHAUSTED_429"
            if "timeout" in err_str or code in ("TIMEOUT", "GATEWAY_TIMEOUT"):
                return True, "GEMINI_TIMEOUT"
            return True, f"GEMINI_ERROR_{code or type(error).__name__}"

        if verification_status == "REJECTED":
            return True, "CATALOG_VALIDATION_REJECTED"

        return False, "NO_FALLBACK"

    def execute_fallback(
        self,
        source_image_path: Path,
        reference_image_paths: list[Path],
        reference_categories: list[str | None],
        placements: list[dict[str, Any]] | None = None,
        light_direction: str | None = "auto",
        shadow_intensity: float | None = 0.72,
        floor_horizon_ratio: float | None = None,
        reason: str = "AUTO_FALLBACK",
    ) -> tuple[GeneratedImage, str]:
        """Execute deterministic local composite generation as a safe fallback."""
        logger.info("CompositeFallbackManager executing fallback (reason: %s)", reason)

        prompt = f"[Local Composite Fallback - {reason}] Tự động chuyển sang Composite Engine chuẩn Catalog."
        result = self.composite_provider.generate_design(
            source_image_path=source_image_path,
            prompt=prompt,
            reference_image_paths=reference_image_paths,
            reference_categories=reference_categories,
            placements=placements,
            light_direction=light_direction,
            shadow_intensity=shadow_intensity,
            floor_horizon_ratio=floor_horizon_ratio,
        )

        return result, reason
