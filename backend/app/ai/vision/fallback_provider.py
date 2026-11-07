from pathlib import Path
from typing import Any

from app.ai.vision.base import VisionAnalysis, VisionUsage
from app.schemas.room_project import DominantColor, RoomAnalysisResult

# Deterministic, objective color names derived from nearest-RGB match against a
# fixed palette. These are labels for locally measured colors, not AI guesses.
_PALETTE: tuple[tuple[str, str, tuple[int, int, int]], ...] = (
    ("Đen", "#000000", (0, 0, 0)),
    ("Trắng", "#FFFFFF", (255, 255, 255)),
    ("Xám", "#808080", (128, 128, 128)),
    ("Đỏ", "#FF0000", (255, 0, 0)),
    ("Cam", "#FFA500", (255, 165, 0)),
    ("Vàng", "#FFFF00", (255, 255, 0)),
    ("Xanh lá", "#008000", (0, 128, 0)),
    ("Xanh dương", "#0000FF", (0, 0, 255)),
    ("Tím", "#800080", (128, 0, 128)),
    ("Hồng", "#FFC0CB", (255, 192, 203)),
    ("Nâu", "#A52A2A", (165, 42, 42)),
    ("Be", "#F5F5DC", (245, 245, 220)),
    ("Xanh ngọc", "#008080", (0, 128, 128)),
)


class LocalFallbackProvider:
    provider_name = "local_fallback"
    model_name = "deterministic-v1"

    def __init__(self, room_type: str | None = None) -> None:
        self.room_type = room_type

    def analyze_room(self, image_path: Path, content_type: str) -> VisionAnalysis:
        width, height, dominant_colors = self._inspect_image(image_path)
        orientation = self._orientation(width, height)
        if width is not None and height is not None:
            layout_summary = (
                f"Local fallback analysis ({width}x{height}, {orientation}). "
                "No AI inference performed; objects and style were not detected."
            )
        else:
            layout_summary = "Local fallback analysis. No AI inference performed."

        result = RoomAnalysisResult(
            room_type=self.room_type,
            dominant_colors=dominant_colors,
            existing_objects=[],
            empty_areas=[],
            lighting=None,
            design_characteristics=[],
            layout_summary=layout_summary,
            confidence=0.0,
        )
        raw_response: dict[str, Any] = {
            "fallback": True,
            "reason": "GEMINI_PROVIDER_UNAVAILABLE",
            "width": width,
            "height": height,
            "orientation": orientation,
        }
        return VisionAnalysis(result=result, raw_response=raw_response, usage=VisionUsage())

    def _inspect_image(self, image_path: Path) -> tuple[int | None, int | None, list[DominantColor]]:
        try:
            from PIL import Image
        except ImportError:
            return None, None, []

        try:
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                width, height = img.size
                sample = img.copy()
                sample.thumbnail((64, 64))
                quantized = sample.quantize(colors=5, method=Image.MEDIANCUT)
                palette = quantized.getpalette() or []
                total = quantized.width * quantized.height
                counts = sorted(quantized.getcolors(5) or [], key=lambda item: -item[0])
                colors: list[DominantColor] = []
                for count, index in counts:
                    rgb = tuple(palette[index * 3 : index * 3 + 3])
                    if len(rgb) != 3:
                        continue
                    percentage = round(count / total * 100) if total else 0
                    if percentage <= 0:
                        continue
                    name, hex_code = self._nearest_color(rgb)
                    colors.append(DominantColor(name=name, hex=hex_code, percentage=percentage))
                return width, height, colors
        except Exception:
            return None, None, []

    @staticmethod
    def _orientation(width: int | None, height: int | None) -> str:
        if width is None or height is None:
            return "unknown"
        if height > width:
            return "portrait"
        if width > height:
            return "landscape"
        return "square"

    @staticmethod
    def _nearest_color(rgb: tuple[int, int, int]) -> tuple[str, str]:
        best_name, best_hex = _PALETTE[0][0], _PALETTE[0][1]
        best_distance = float("inf")
        for name, hex_code, target in _PALETTE:
            distance = sum((a - b) ** 2 for a, b in zip(rgb, target))
            if distance < best_distance:
                best_name, best_hex, best_distance = name, hex_code, distance
        return best_name, best_hex
