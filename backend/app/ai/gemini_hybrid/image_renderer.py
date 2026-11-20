from io import BytesIO
import logging
from pathlib import Path
from typing import Any, Callable

from PIL import Image
import numpy as np

from app.ai.image.base import GeneratedImage, ImageGenerationUsage, ImageProviderError
from app.ai.image.gemini_provider import GeminiImageProvider
from app.services.design_compositor import composite_design, defringe_cutout

logger = logging.getLogger(__name__)


class GeminiImageRenderer:
    """Manages Gemini-based interior rendering with strict prompt engineering

    and optional Sandwich Compositing (Alpha Re-Blit) to safeguard product identity.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-3.1-flash-image",
        gemini_provider: GeminiImageProvider | None = None,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.provider = gemini_provider or (
            GeminiImageProvider(api_key=api_key, model_name=model_name) if api_key else None
        )

    def render_photorealistic_preview(
        self,
        source_room_path: Path,
        prompt: str,
        reference_image_paths: list[Path] | None = None,
    ) -> GeneratedImage:
        """Call Gemini Image generation with strict anti-hallucination and architecture preservation prompts."""
        if not self.provider:
            raise ImageProviderError(
                "GEMINI_NOT_CONFIGURED",
                "Gemini Image Provider is not configured with a valid API key.",
            )

        strict_prompt = self._build_strict_prompt(prompt)
        return self.provider.generate_design(
            source_image_path=source_room_path,
            prompt=strict_prompt,
            reference_image_paths=reference_image_paths,
        )

    def render_hybrid_sandwich(
        self,
        source_room_path: Path,
        ai_background_image_data: bytes,
        catalog_cutout_paths: list[Path],
        categories: list[str | None],
        placements: list[dict[str, Any]] | None = None,
        light_direction: str = "auto",
        shadow_intensity: float = 0.72,
        floor_horizon_ratio: float | None = None,
    ) -> GeneratedImage:
        """Kỹ thuật Ghép 3 Lớp (Sandwich Compositing):

        Lấy ánh sáng và không gian chân thực từ AI background, sau đó
        'Hard-Pin' (dán đè) các pixel chuẩn bóc nền của sản phẩm Catalog lên trên cùng,
        loại bỏ hoàn toàn nguy cơ méo mó, biến dạng hay vẽ sai họa tiết sản phẩm.
        """
        # Save temporary AI background in memory and composite the real cutouts onto it
        ai_bg = Image.open(BytesIO(ai_background_image_data)).convert("RGB")
        temp_bg_bytes = BytesIO()
        ai_bg.save(temp_bg_bytes, format="PNG")
        temp_bg_bytes.seek(0)

        # Composite real cutouts on top of AI generated harmonized room
        # Use composite_design by passing a mock path or memory
        final_png_data = composite_design(
            room_image_path=temp_bg_bytes,
            product_image_paths=catalog_cutout_paths,
            product_categories=categories,
            placements=placements,
            light_direction=light_direction,
            shadow_intensity=shadow_intensity,
            floor_horizon_ratio=floor_horizon_ratio,
        )

        return GeneratedImage(
            data=final_png_data,
            content_type="image/png",
            usage=ImageGenerationUsage(total_tokens=0, estimated_cost=0),
        )

    def _build_strict_prompt(self, base_prompt: str) -> str:
        return (
            "SYSTEM INSTRUCTIONS FOR INTERIOR DESIGN PHOTOREALISM:\n"
            "1. Architectural Preservation: Keep the original room walls, windows, ceiling, flooring material, "
            "and camera perspective unchanged. Do not remove or mutate fixed doors or window frames.\n"
            "2. Catalog Integrity: Decorate using ONLY the items provided in the reference images. "
            "DO NOT replace the sofa, table, chair, or lamp with different models. "
            "Maintain their distinctive shape, proportions, fabric texture, and authentic colors as closely as possible.\n"
            "3. Clean Commercial Output: DO NOT generate any text, watermarks, brand logos, or UI placeholder boxes.\n"
            "4. Lighting & Physics: Cast soft, physically plausible contact shadows on the floor adhering to the primary window light source.\n\n"
            f"User Brief & Preferences:\n{base_prompt}"
        )
