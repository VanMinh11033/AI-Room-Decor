import json
import logging
from pathlib import Path
from typing import Any, Callable

from PIL import Image
import numpy as np

from app.ai.gemini_hybrid.schemas import (
    DecorSpot,
    FloorAreaSchema,
    GeminiRoomAnalysisSchema,
    LightingAnalysisSchema,
)
from app.ai.vision.base import VisionProviderError
from app.services.design_compositor import detect_floor_plane, detect_room_lighting

logger = logging.getLogger(__name__)


class GeminiRoomAnalyzer:
    """Multimodal room analyzer leveraging Gemini Vision with structured schema validation

    and local deterministic computer-vision fallback.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-3-flash-preview",
        client_factory: Callable | None = None,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self._client_factory = client_factory

    def analyze(self, image_path: Path) -> GeminiRoomAnalysisSchema:
        """Analyze a room photo and return a verified GeminiRoomAnalysisSchema.

        If Gemini API key is missing or calls fail, falls back to deterministic local CV analysis.
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Room image not found at {image_path}")

        if self.api_key:
            try:
                return self._analyze_with_gemini(image_path)
            except Exception as exc:
                logger.warning("GeminiRoomAnalyzer remote call failed (%s); falling back to local CV", exc)

        return self._analyze_locally(image_path)

    def _analyze_with_gemini(self, image_path: Path) -> GeminiRoomAnalysisSchema:
        client, types = self._build_client()
        image_bytes = image_path.read_bytes()
        suffix = image_path.suffix.lower()
        mime_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

        prompt = (
            "You are a professional interior architectural vision analyst. "
            "Analyze this room photo strictly based on visible image evidence. Do not guess or hallucinate.\n"
            "Return a strictly valid JSON object matching the following schema:\n"
            "{\n"
            '  "room_type": "living room | bedroom | empty room | dining room",\n'
            '  "layout_summary": "Factual description of the room layout, visible walls, floor and windows.",\n'
            '  "floor_area": {\n'
            '    "visible": true,\n'
            '    "horizon_ratio": 0.65,\n'
            '    "floor_material": "wood | tile | concrete | carpet"\n'
            "  },\n"
            '  "lighting": {\n'
            '    "type": "natural daylight | artificial | mixed",\n'
            '    "direction": "left | right | overhead | ambient",\n'
            '    "level": "bright | medium | dim",\n'
            '    "color_temp": "warm | neutral | cool"\n'
            "  },\n"
            '  "dominant_colors": ["White", "Oak Wood", "Beige"],\n'
            '  "decor_spots": [\n'
            '    {"location": "center floor", "description": "Open floor area in center of room", "suitable_categories": ["sofa", "table", "rug"]},\n'
            '    {"location": "right wall", "description": "Empty wall space", "suitable_categories": ["lighting", "plant-decor"]}\n'
            "  ],\n"
            '  "confidence": 0.95\n'
            "}\n"
            "If the floor plane is not clearly visible or is cut off, set floor_area.visible to false and confidence below 0.5."
        )

        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        response = client.models.generate_content(
            model=self.model_name,
            contents=[prompt, image_part],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        text = getattr(response, "text", None)
        if not text:
            raise VisionProviderError("GEMINI_ANALYSIS_EMPTY", "Gemini returned empty response text")

        data = json.loads(text)
        return GeminiRoomAnalysisSchema.model_validate(data)

    def _analyze_locally(self, image_path: Path) -> GeminiRoomAnalysisSchema:
        """Deterministic Computer Vision analysis using Pillow, NumPy and gradient filtering."""
        with Image.open(image_path) as im:
            rgb = im.convert("RGB")
            w, h = rgb.size
            arr = np.asarray(rgb, dtype=np.float32)

        floor_mask, is_floor_reliable = detect_floor_plane(arr)
        horizon_indices = np.where(floor_mask > 0.5)[0]
        floor_horizon_ratio = (float(horizon_indices[0]) / float(h)) if len(horizon_indices) else 0.65

        lighting_meta = detect_room_lighting(arr)
        light_dx = lighting_meta["light_dir"][0]
        direction = "left" if light_dx > 0.15 else ("right" if light_dx < -0.15 else "overhead")

        # Color temperature estimation from ambient RGB
        amb_rgb = lighting_meta["ambient_rgb"]
        r, g, b = amb_rgb
        color_temp = "warm" if (r > b + 15) else ("cool" if (b > r + 15) else "neutral")

        return GeminiRoomAnalysisSchema(
            room_type="empty room" if is_floor_reliable else "living room",
            layout_summary=f"Phòng có kích thước {w}x{h} pixel, độ cao chân trời sàn ~{floor_horizon_ratio:.2f}.",
            floor_area=FloorAreaSchema(
                visible=bool(is_floor_reliable),
                horizon_ratio=round(floor_horizon_ratio, 3),
                floor_material="wood" if (r > 120 and g > 90 and b < 100) else "tile",
            ),
            lighting=LightingAnalysisSchema(
                type="natural daylight",
                direction=direction,
                level="bright" if lighting_meta["ambient_lum"] > 140 else "medium",
                color_temp=color_temp,
            ),
            dominant_colors=["Warm White", "Wood Neutral"],
            decor_spots=[
                DecorSpot(
                    location="center floor",
                    description="Khu vực trung tâm sàn phòng khách",
                    suitable_categories=["sofa", "table", "rug"],
                ),
                DecorSpot(
                    location="corner",
                    description="Góc phòng bên cạnh cửa sổ / tường",
                    suitable_categories=["lighting", "plant-decor"],
                ),
            ],
            confidence=0.92 if is_floor_reliable else 0.45,
        )

    def _build_client(self):
        if self._client_factory is not None:
            return self._client_factory()
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise VisionProviderError("GEMINI_SDK_NOT_INSTALLED", "google-genai package is not installed") from exc

        return genai.Client(api_key=self.api_key), types
