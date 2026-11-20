import colorsys
import logging
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.ai.vision.base import VisionAnalysis, VisionUsage
from app.schemas.room_project import (
    DetectedObject,
    DominantColor,
    EmptyArea,
    LightingAnalysis,
    RoomAnalysisResult,
)

logger = logging.getLogger(__name__)

ROOM_TYPE_LABELS = {
    "living-room": "Phòng khách",
    "living room": "Phòng khách",
    "phòng khách": "Phòng khách",
    "phong khach": "Phòng khách",
    "bedroom": "Phòng ngủ",
    "phòng ngủ": "Phòng ngủ",
    "phong ngu": "Phòng ngủ",
    "workspace": "Góc làm việc",
    "office": "Phòng làm việc",
    "study-room": "Phòng học",
    "study room": "Phòng học",
    "phòng học": "Phòng học",
    "phong hoc": "Phòng học",
    "phòng làm việc": "Phòng làm việc",
    "góc làm việc": "Góc làm việc",
    "dining-room": "Phòng ăn",
    "dining room": "Phòng ăn",
    "phòng ăn": "Phòng ăn",
    "phong an": "Phòng ăn",
    "studio": "Studio",
    "phòng trống": "Phòng trống",
}


def normalize_room_type(value: str | None, floor_pct: int = 30) -> str:
    if value:
        cleaned = value.strip().lower()
        if cleaned in ROOM_TYPE_LABELS:
            return ROOM_TYPE_LABELS[cleaned]
        return value.strip()
    if floor_pct >= 20:
        return "Phòng khách"
    return "Phòng sinh hoạt"


class LocalFallbackProvider:
    provider_name = "local_fallback"
    model_name = "deterministic-v1"

    def __init__(self, room_type: str | None = None, fallback_reason: str = "LOCAL_MODE") -> None:
        self.room_type = room_type
        self.fallback_reason = fallback_reason

    def analyze_room(self, image_path: Path, content_type: str) -> VisionAnalysis:
        try:
            with Image.open(image_path) as im:
                rgb = im.convert("RGB")
                width, height = rgb.size
                arr = np.asarray(rgb, dtype=np.float32)
        except Exception as exc:
            logger.warning("LocalFallbackProvider failed to load image: %s", exc)
            return self._empty_analysis(None, None, "unknown")

        orientation = self._orientation(width, height)

        # Xử lý ảnh mẫu thử nghiệm / dummy test image (kích thước quá nhỏ < 32px)
        if min(width, height) < 32:
            colors = self._extract_dominant_colors(rgb)
            result = RoomAnalysisResult(
                room_type=self.room_type,
                dominant_colors=colors,
                existing_objects=[],
                empty_areas=[],
                lighting=None,
                design_characteristics=[],
                layout_summary=f"Ảnh mẫu kích thước nhỏ ({width}x{height}). Không thực hiện phân tích không gian.",
                confidence=0.0,
            )
            raw_response = {
                "fallback": True,
                "reason": self.fallback_reason,
                "engine": "local_computer_vision",
                "width": width,
                "height": height,
                "orientation": orientation,
            }
            return VisionAnalysis(result=result, raw_response=raw_response, usage=VisionUsage())

        dominant_colors = self._extract_dominant_colors(rgb)
        lighting, lighting_meta = self._extract_lighting(arr)
        empty_areas, is_floor_reliable, floor_ratio = self._extract_floor_and_areas(arr)
        floor_pct = round(floor_ratio * 100)
        room_type = normalize_room_type(self.room_type, floor_pct)

        existing_objects = self._detect_spatial_objects(is_floor_reliable, floor_ratio)

        # Generate rich Vietnamese layout summary
        orientation_vn = "ngang" if orientation == "landscape" else ("dọc" if orientation == "portrait" else "vuông")
        light_desc = lighting_meta.get("light_desc", "ánh sáng hài hòa")
        level_desc = lighting_meta.get("level_desc", "đầy đủ")
        color_names_str = ", ".join(c.name for c in dominant_colors[:3]) if dominant_colors else "trung tính"

        layout_summary = (
            f"Phòng có khung nhìn {orientation_vn} ({width}x{height}px). "
            f"Mặt sàn thông thoáng chiếm khoảng {floor_pct}% diện tích khung nhìn, bề mặt quang học thuận lợi bố trí nội thất. "
            f"Nguồn sáng chính {light_desc} với cường độ {level_desc}. "
            f"Gam màu chủ đạo bao gồm {color_names_str}."
        )

        design_characteristics = [
            f"Bố cục khung hình {orientation_vn}",
            f"Mặt sàn thông thoáng ~{floor_pct}%",
            f"Tông màu chính {dominant_colors[0].name if dominant_colors else 'Trung tính'}",
            f"Ánh sáng {level_desc}",
        ]

        result = RoomAnalysisResult(
            room_type=room_type,
            dominant_colors=dominant_colors,
            existing_objects=existing_objects,
            empty_areas=empty_areas,
            lighting=lighting,
            design_characteristics=design_characteristics,
            layout_summary=layout_summary,
            confidence=0.88 if is_floor_reliable else 0.55,
        )

        raw_response: dict[str, Any] = {
            "fallback": True,
            "reason": self.fallback_reason,
            "engine": "local_computer_vision",
            "width": width,
            "height": height,
            "orientation": orientation,
            "floor_reliable": bool(is_floor_reliable),
            "floor_ratio": round(float(floor_ratio), 3),
        }
        return VisionAnalysis(result=result, raw_response=raw_response, usage=VisionUsage())

    def _extract_dominant_colors(self, rgb: Image.Image) -> list[DominantColor]:
        w, h = rgb.size
        sample_w, sample_h = min(160, w), min(160, h)
        sample = rgb.resize((sample_w, sample_h))
        arr = np.asarray(sample, dtype=np.float32).reshape(-1, 3)

        if len(arr) < 5:
            r, g, b = np.mean(arr, axis=0) if len(arr) else (200, 200, 200)
            name, hex_code = self._classify_hsv(r, g, b)
            return [DominantColor(name=name, hex=hex_code, percentage=100)]

        try:
            from sklearn.cluster import MiniBatchKMeans

            kmeans = MiniBatchKMeans(n_clusters=5, random_state=42, n_init="auto").fit(arr)
            labels, counts = np.unique(kmeans.labels_, return_counts=True)
            total = len(arr)
            order = np.argsort(-counts)

            color_map: dict[str, dict[str, Any]] = {}
            for idx in order:
                R, G, B = [int(round(c)) for c in kmeans.cluster_centers_[idx]]
                pct = round(counts[idx] / total * 100)
                if pct <= 0:
                    continue
                name, hex_code = self._classify_hsv(R, G, B)
                if name in color_map:
                    color_map[name]["percentage"] += pct
                else:
                    color_map[name] = {"name": name, "hex": hex_code, "percentage": pct}

            colors = [
                DominantColor(name=v["name"], hex=v["hex"], percentage=v["percentage"])
                for v in color_map.values()
                if v["percentage"] >= 3
            ]
            colors.sort(key=lambda item: -(item.percentage or 0))
            return colors[:5]
        except Exception as exc:
            logger.warning("Dominant color clustering failed (%s); using mean color", exc)
            mean_rgb = np.mean(arr, axis=0)
            name, hex_code = self._classify_hsv(mean_rgb[0], mean_rgb[1], mean_rgb[2])
            return [DominantColor(name=name, hex=hex_code, percentage=100)]

    @staticmethod
    def _classify_hsv(r: float, g: float, b: float) -> tuple[str, str]:
        rn, gn, bn = r / 255.0, g / 255.0, b / 255.0
        h_val, s_val, v_val = colorsys.rgb_to_hsv(rn, gn, bn)
        h_deg = h_val * 360.0

        # Neutral / Achromatic (< 12% saturation)
        if s_val < 0.12:
            if v_val > 0.88:
                return "Trắng", "#FFFFFF"
            if v_val > 0.72:
                return ("Kem", "#F2EADC") if rn > bn + 0.02 else ("Xám", "#D3D3D3")
            if v_val > 0.35:
                return "Xám", "#808080"
            return "Đen", "#111111"

        # Low-to-moderate saturation (12% - 32%)
        if s_val < 0.32:
            if v_val > 0.80:
                return ("Be", "#F5F5DC") if 18 <= h_deg <= 60 else ("Trắng", "#FFFFFF")
            if v_val > 0.55:
                if 18 <= h_deg <= 55:
                    return "Be", "#E8D8C8"
                if 65 < h_deg <= 150:
                    return "Xanh sage", "#9CAF88"
                return "Xám", "#9E9E9E"
            if v_val > 0.28:
                if 15 <= h_deg <= 50:
                    return "Gỗ sồi", "#B8895B"
                return "Xám", "#616161"
            if 15 <= h_deg <= 45:
                return "Gỗ óc chó", "#6B4423"
            return "Đen", "#111111"

        # Moderate to high saturation (>= 32%)
        if 15 <= h_deg < 42:
            if v_val <= 0.55:
                return ("Gỗ sồi", "#B8895B") if v_val > 0.32 else ("Gỗ óc chó", "#6B4423")
            if s_val > 0.65:
                return "Cam", "#FFA500"
            return "Be", "#E8D8C8"
        if 42 <= h_deg < 68:
            return ("Đồng thau", "#B08D57") if v_val < 0.70 else ("Vàng", "#FFFF00")
        if 68 <= h_deg < 165:
            return ("Xanh sage", "#9CAF88") if s_val < 0.55 else ("Xanh lá", "#008000")
        if 165 <= h_deg < 260:
            return ("Xanh navy", "#1F3A5F") if v_val < 0.45 else ("Xanh dương", "#0000FF")
        if 260 <= h_deg < 320:
            return "Tím", "#800080"

        # Red / Pink / Terracotta region
        if v_val > 0.75 and s_val < 0.55:
            return "Hồng", "#FFC0CB"
        if v_val < 0.60 and s_val < 0.65:
            return "Đất nung", "#C66B4E"
        return "Đỏ", "#FF0000"

    def _extract_lighting(self, arr: np.ndarray) -> tuple[LightingAnalysis, dict[str, str]]:
        try:
            from app.services.design_compositor import detect_room_lighting

            lighting_meta = detect_room_lighting(arr)
            light_dx = lighting_meta["light_dir"][0]
            dir_str = (
                "chiếu từ bên trái"
                if light_dx > 0.15
                else ("chiếu từ bên phải" if light_dx < -0.15 else "chiếu từ trên cao / ánh sáng phòng")
            )
            level_str = (
                "sáng rõ"
                if lighting_meta["ambient_lum"] > 150
                else ("vừa phải" if lighting_meta["ambient_lum"] > 100 else "dịu nhẹ")
            )
            r, g, b = lighting_meta["ambient_rgb"]
            temp_str = (
                "ánh sáng ấm"
                if (r > b + 15)
                else ("ánh sáng lạnh" if (b > r + 15) else "ánh sáng tự nhiên")
            )
            lighting = LightingAnalysis(
                type=f"Tự nhiên ({dir_str}, {temp_str})",
                level=level_str.capitalize(),
            )
            return lighting, {"light_desc": dir_str, "level_desc": level_str, "temp_desc": temp_str}
        except Exception as exc:
            logger.warning("Lighting analysis failed (%s); using default", exc)
            return (
                LightingAnalysis(type="Ánh sáng tự nhiên", level="Vừa phải"),
                {"light_desc": "ánh sáng tự nhiên", "level_desc": "vừa phải", "temp_desc": "tự nhiên"},
            )

    def _extract_floor_and_areas(self, arr: np.ndarray) -> tuple[list[EmptyArea], bool, float]:
        try:
            from app.services.design_compositor import detect_floor_plane

            floor_mask, is_floor_reliable = detect_floor_plane(arr)
            floor_ratio = float(np.mean(floor_mask > 0.5)) if floor_mask.size else 0.30
        except Exception as exc:
            logger.warning("Floor plane detection failed (%s); using default ratio", exc)
            is_floor_reliable, floor_ratio = False, 0.25

        floor_pct = round(floor_ratio * 100)
        areas = [
            EmptyArea(
                location="Khu vực trung tâm sàn phòng",
                description=(
                    f"Mặt sàn thông thoáng (chiếm khoảng {floor_pct}% diện tích khung nhìn), "
                    "thích hợp bố trí sofa, bàn trà hoặc thảm decor."
                ),
                suitable_for_decor=True,
            ),
            EmptyArea(
                location="Khu vực chân tường & góc phòng",
                description="Khoảng không tiếp giáp mảng tường, thích hợp đặt tủ kệ, đèn cây hoặc cây cảnh nội thất.",
                suitable_for_decor=True,
            ),
        ]
        return areas, is_floor_reliable, floor_ratio

    @staticmethod
    def _detect_spatial_objects(is_floor_reliable: bool, floor_ratio: float) -> list[DetectedObject]:
        floor_conf = 0.88 if is_floor_reliable else 0.55
        objects = [
            DetectedObject(name="Mặt sàn nội thất", confidence=floor_conf),
            DetectedObject(name="Mảng tường & trần phòng", confidence=0.82),
            DetectedObject(name="Khu vực đón sáng tự nhiên", confidence=0.78),
        ]
        if floor_ratio < 0.20:
            objects.append(DetectedObject(name="Khối vật thể nội thất hiện hữu trên sàn", confidence=0.72))
        return objects

    @staticmethod
    def _orientation(width: int | None, height: int | None) -> str:
        if width is None or height is None:
            return "unknown"
        if height > width:
            return "portrait"
        if width > height:
            return "landscape"
        return "square"

    def _empty_analysis(self, width: int | None, height: int | None, orientation: str) -> VisionAnalysis:
        result = RoomAnalysisResult(
            room_type=self.room_type or "Phòng khách",
            dominant_colors=[DominantColor(name="Trắng", hex="#FFFFFF", percentage=100)],
            existing_objects=[DetectedObject(name="Không gian phòng", confidence=0.5)],
            empty_areas=[EmptyArea(location="Khu vực sàn", description="Không gian sẵn sàng decor", suitable_for_decor=True)],
            lighting=LightingAnalysis(type="Ánh sáng tự nhiên", level="Vừa phải"),
            design_characteristics=["Không gian phòng"],
            layout_summary="Phân tích thị giác cục bộ (Local CV).",
            confidence=0.5,
        )
        raw_response: dict[str, Any] = {
            "fallback": True,
            "reason": self.fallback_reason,
            "width": width,
            "height": height,
            "orientation": orientation,
        }
        return VisionAnalysis(result=result, raw_response=raw_response, usage=VisionUsage())
