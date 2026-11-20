"""Deterministic image provider that composites selected products onto the room.

Implements the :class:`ImageProvider` protocol but performs no generative
inference: it preserves the original room photo as the background and pastes the
exact product images (with background removal) at category-aware positions. Scene
images are rejected with a clear error instead of being pasted as rectangles.
"""

from pathlib import Path

from app.ai.image.base import GeneratedImage, ImageGenerationUsage, ImageProviderError
from app.services.design_compositor import ProductNotCompositibleError, composite_design


class CompositeImageProvider:
    provider_name = "composite"
    model_name = "deterministic-compositor-v2"
    # source room image + up to 4 product reference images.
    MAX_INPUT_IMAGES = 5
    supports_categories = True

    def generate_design(
        self,
        source_image_path: Path,
        prompt: str,
        reference_image_paths: list[Path] | None = None,
        reference_categories: list[str | None] | None = None,
        placements: list[dict] | None = None,
        light_direction: str | None = None,
        shadow_intensity: float | None = None,
        floor_horizon_ratio: float | None = None,
    ) -> GeneratedImage:
        try:
            data = composite_design(
                source_image_path,
                list(reference_image_paths or []),
                list(reference_categories or []),
                placements=placements,
                light_direction=light_direction,
                shadow_intensity=shadow_intensity,
                floor_horizon_ratio=floor_horizon_ratio,
            )
        except ProductNotCompositibleError as exc:
            raise ImageProviderError("PRODUCT_IMAGE_NOT_COMPOSITIBLE", str(exc)) from exc

        return GeneratedImage(
            data=data,
            content_type="image/png",
            usage=ImageGenerationUsage(),
        )
