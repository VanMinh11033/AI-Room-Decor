import json
import logging
from pathlib import Path
from typing import Any, Callable

from app.ai.gemini_hybrid.schemas import (
    FloorAreaSchema,
    GeminiLayoutPlan,
    LightingAnalysisSchema,
    PlannedPlacement,
)

logger = logging.getLogger(__name__)


# Category layout heuristics: (base_x_ratio, base_y_ratio, base_width_ratio, z_index)
_CATEGORY_DEFAULTS = {
    "sofa": (0.44, 0.72, 0.44, 4),
    "table": (0.60, 0.84, 0.22, 6),
    "chair": (0.78, 0.74, 0.22, 5),
    "lighting": (0.84, 0.65, 0.14, 2),
    "lamp": (0.84, 0.65, 0.14, 2),
    "rug": (0.50, 0.88, 0.52, 1),
    "wall-decor": (0.50, 0.38, 0.24, 0),
    "mirror": (0.50, 0.38, 0.22, 0),
    "art": (0.50, 0.38, 0.24, 0),
    "plant-decor": (0.16, 0.70, 0.16, 7),
    "plant": (0.16, 0.70, 0.16, 7),
    "divider": (0.86, 0.62, 0.25, 3),
}


class GeminiLayoutPlanner:
    """Coordinates spatial positioning and depth ordering for selected catalog products.

    Enforces strict identity constraints: Gemini cannot add, remove, or substitute Product IDs.
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

    def plan_layout(
        self,
        product_ids: list[int],
        product_metadata: dict[int, dict[str, Any]],
        floor_area: FloorAreaSchema | None = None,
        lighting: LightingAnalysisSchema | None = None,
    ) -> GeminiLayoutPlan:
        """Create a coordinated layout plan for the requested product IDs.

        Guarantees that 100% of the returned placements match the input product_ids.
        """
        if not product_ids:
            return GeminiLayoutPlan(placements=[])

        target_ids = set(product_ids)
        floor = floor_area or FloorAreaSchema()
        light = lighting or LightingAnalysisSchema(type="natural daylight", direction="ambient", level="bright", color_temp="neutral")

        # Try Gemini intelligent layout if API key is provided
        if self.api_key:
            try:
                plan = self._plan_with_gemini(product_ids, product_metadata, floor, light)
                # Strict Product ID Integrity Validation
                plan_ids = {p.product_id for p in plan.placements}
                if plan_ids == target_ids and len(plan.placements) == len(product_ids):
                    logger.info("GeminiLayoutPlanner successfully planned layout for product IDs: %s", product_ids)
                    return plan
                logger.warning(
                    "GeminiLayoutPlanner returned invalid product IDs (expected: %s, got: %s). Falling back to deterministic layout.",
                    target_ids,
                    plan_ids,
                )
            except Exception as exc:
                logger.warning("GeminiLayoutPlanner call failed (%s); using deterministic layout", exc)

        # Deterministic Physical Layout
        return self._plan_deterministically(product_ids, product_metadata, floor, light)

    def _plan_deterministically(
        self,
        product_ids: list[int],
        product_metadata: dict[int, dict[str, Any]],
        floor: FloorAreaSchema,
        light: LightingAnalysisSchema,
    ) -> GeminiLayoutPlan:
        horizon_y = floor.horizon_ratio
        light_from_left = light.direction == "left"
        has_sofa = any("sofa" in str(product_metadata.get(pid, {}).get("category", "")).lower() for pid in product_ids)

        placements: list[PlannedPlacement] = []
        for pid in product_ids:
            meta = product_metadata.get(pid, {})
            cat = str(meta.get("category", "accessories")).lower().strip()
            matched_key = next((k for k in _CATEGORY_DEFAULTS if k in cat), None)
            base_x, base_y, base_w, z_idx = _CATEGORY_DEFAULTS.get(matched_key, (0.50, 0.75, 0.20, 5))

            # Adjust lamp placement according to light direction
            if "lighting" in cat or "lamp" in cat:
                base_x = 0.86 if (light_from_left or has_sofa) else 0.16

            # Scale Y position relative to floor horizon
            if "wall" not in cat and "mirror" not in cat and "art" not in cat:
                effective_y = horizon_y + (1.0 - horizon_y) * (base_y - 0.5) / 0.5
                effective_y = max(horizon_y + 0.05, min(0.96, effective_y))
            else:
                effective_y = base_y

            placements.append(
                PlannedPlacement(
                    product_id=pid,
                    category=cat,
                    x_ratio=round(base_x, 3),
                    y_ratio=round(effective_y, 3),
                    width_ratio=round(base_w, 3),
                    z_index=z_idx,
                    reasoning=f"Bố trí chuẩn tỷ lệ cho {cat} dựa trên đường chân trời sàn ({horizon_y:.2f}).",
                )
            )

        return GeminiLayoutPlan(
            placements=placements,
            light_direction=light.direction,
            shadow_intensity=0.72,
            floor_horizon_ratio=horizon_y,
            plan_notes="Bố trí hình học vật lý xác định (Deterministic Layout).",
        )

    def _plan_with_gemini(
        self,
        product_ids: list[int],
        product_metadata: dict[int, dict[str, Any]],
        floor: FloorAreaSchema,
        light: LightingAnalysisSchema,
    ) -> GeminiLayoutPlan:
        client, types = self._build_client()

        items_desc = []
        for pid in product_ids:
            meta = product_metadata.get(pid, {})
            items_desc.append(
                f"- Product ID: {pid}, Name: {meta.get('name', 'Product')}, Category: {meta.get('category', 'Furniture')}"
            )

        prompt = (
            "You are an interior design spatial layout planner.\n"
            f"Room floor horizon ratio: {floor.horizon_ratio:.2f} (0.0 is top, 1.0 is bottom).\n"
            f"Primary light direction: {light.direction}.\n"
            "Selected products to place:\n"
            + "\n".join(items_desc)
            + "\n\n"
            "RULES:\n"
            "1. You MUST return EXACTLY ONE placement for each of the selected Product IDs above.\n"
            "2. DO NOT ADD ANY NEW PRODUCT IDs.\n"
            "3. DO NOT OMIT ANY PRODUCT IDs.\n"
            "4. Output strictly valid JSON matching this schema:\n"
            "{\n"
            '  "placements": [\n'
            '    {\n'
            '      "product_id": <int>,\n'
            '      "category": "<category>",\n'
            '      "x_ratio": <float 0.05 to 0.95>,\n'
            '      "y_ratio": <float floor_horizon to 0.95>,\n'
            '      "width_ratio": <float 0.10 to 0.85>,\n'
            '      "z_index": <int 0 to 10, higher is closer to camera>,\n'
            '      "reasoning": "<why this spot was chosen>"\n'
            "    }\n"
            "  ],\n"
            '  "light_direction": "auto | left | right | overhead",\n'
            '  "shadow_intensity": 0.72,\n'
            '  "floor_horizon_ratio": 0.65\n'
            "}\n"
        )

        response = client.models.generate_content(
            model=self.model_name,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        text = getattr(response, "text", None)
        if not text:
            raise ValueError("Gemini layout planner returned empty response")

        data = json.loads(text)
        return GeminiLayoutPlan.model_validate(data)

    def _build_client(self):
        if self._client_factory is not None:
            return self._client_factory()
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("google-genai package is not installed") from exc

        return genai.Client(api_key=self.api_key), types
