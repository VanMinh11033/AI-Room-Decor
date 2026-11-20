import base64
import json
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

import httpx
from PIL import Image

from app.ai.vision.base import VisionAnalysis, VisionProviderError, VisionUsage
from app.ai.vision.fallback_provider import LocalFallbackProvider, normalize_room_type
from app.schemas.room_project import (
    DetectedObject,
    EmptyArea,
    RoomAnalysisResult,
)

logger = logging.getLogger(__name__)

DEFAULT_VISION_MODEL = "@cf/meta/llama-3.2-11b-vision-instruct"
DEFAULT_TIMEOUT_SECONDS = 60
MAX_IMAGE_DIMENSION = 1024

_JSON_EXTRACT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


class CloudflareVisionProvider:
    provider_name = "cloudflare"

    def __init__(
        self,
        account_id: str,
        api_token: str,
        model_name: str = DEFAULT_VISION_MODEL,
        base_url: str = "https://api.cloudflare.com/client/v4",
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        client_factory: Callable | None = None,
        local_fallback: LocalFallbackProvider | None = None,
    ) -> None:
        self.account_id = account_id.strip()
        self.api_token = api_token.strip()
        self.model_name = model_name.strip() or DEFAULT_VISION_MODEL
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client_factory = client_factory
        self._local_cv = local_fallback or LocalFallbackProvider()

    def analyze_room(self, image_path: Path, content_type: str) -> VisionAnalysis:
        if not image_path.exists():
            raise VisionProviderError("CLOUDFLARE_VISION_SOURCE_NOT_FOUND", "Source room image was not found")

        # 1. Run Local CV optical analysis on the ground-truth pixels
        local_analysis = self._local_cv.analyze_room(image_path, content_type)
        local_res = local_analysis.result

        try:
            with Image.open(image_path) as im:
                rgb = im.convert("RGB")
                w, h = rgb.size
        except VisionProviderError:
            raise
        except Exception as exc:
            logger.warning("Failed to open image for Cloudflare Vision: %s", exc)
            return local_analysis

        # Synthetic/tiny test images bypass remote call
        if min(w, h) < 32:
            return local_analysis

        # 2. Prepare optimized base64 data URL for Cloudflare Workers AI
        image_data_url = self._prepare_data_url(rgb, w, h)

        # 3. Call Cloudflare Llama 3.2 11B Vision Instruct
        prompt = self._build_prompt(local_res.room_type)
        try:
            response_json = self._call_cloudflare_api(prompt, image_data_url)
        except VisionProviderError:
            raise
        except Exception as exc:
            raise self._classify_error(exc) from exc

        # 4. Parse Vision response and merge with Local CV ground truth
        try:
            parsed = self._extract_json_response(response_json)
            merged_result = self._merge_results(parsed, local_res, w, h)
            raw_response = {
                "engine": "hybrid_cloudflare_local_cv",
                "vision_model": self.model_name,
                "parsed_vision": parsed,
                "local_cv": local_analysis.raw_response,
            }
            return VisionAnalysis(result=merged_result, raw_response=raw_response, usage=VisionUsage(total_tokens=250))
        except VisionProviderError:
            raise
        except Exception as exc:
            logger.warning("Error parsing/merging Cloudflare Vision response (%s); falling back to Local CV", exc)
            return local_analysis

    def _prepare_data_url(self, rgb: Image.Image, w: int, h: int) -> str:
        if max(w, h) > MAX_IMAGE_DIMENSION:
            scale = MAX_IMAGE_DIMENSION / max(w, h)
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
            rgb = rgb.resize((nw, nh), Image.LANCZOS)

        buf = BytesIO()
        rgb.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    def _build_prompt(self, fallback_room_type: str | None) -> str:
        return (
            "You are a professional interior architectural vision analyst. "
            "Analyze this room photo strictly based on visible image evidence. Do not hallucinate or guess items not present.\n"
            "Return ONLY a valid JSON object matching this exact schema (no markdown formatting, no prose):\n"
            "{\n"
            '  "room_type": "Phòng khách | Phòng ngủ | Góc làm việc | Phòng ăn | Studio",\n'
            '  "style": "Hiện đại | Bắc Âu | Tối giản | Japandi | Công nghiệp | Cổ điển",\n'
            '  "existing_objects": [\n'
            '    {"name": "Tên đồ vật (tiếng Việt, ví dụ: Sofa văng, Bàn trà, Đèn cây, Cửa sổ, Tủ kệ)", "confidence": 0.9}\n'
            "  ],\n"
            '  "empty_areas": [\n'
            '    {"location": "Khu vực giữa sàn", "description": "Mặt sàn trống thích hợp bố trí sofa và bàn trà", "suitable_for_decor": true}\n'
            "  ],\n"
            '  "layout_summary": "Mô tả chi tiết bằng tiếng Việt về bố cục không gian, mặt sàn, tường và vị trí tiềm năng để trang trí nội thất.",\n'
            '  "confidence": 0.92\n'
            "}"
        )

    def _call_cloudflare_api(self, prompt: str, image_data_url: str) -> dict[str, Any]:
        url = f"{self.base_url}/accounts/{self.account_id}/ai/run/{self.model_name}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "image": image_data_url,
            "max_tokens": 1024,
        }

        if self._client_factory is not None:
            client = self._client_factory()
            res = client.post(url, headers=headers, json=payload)
        else:
            with httpx.Client(timeout=httpx.Timeout(self.timeout_seconds, connect=10)) as client:
                res = client.post(url, headers=headers, json=payload)

        if res.status_code in (401, 403):
            raise VisionProviderError("CLOUDFLARE_VISION_AUTH_ERROR", "Lỗi xác thực Cloudflare API Token.", status_code=res.status_code)
        if res.status_code == 429:
            codes: set[int] = set()
            try:
                cf_json = res.json()
                if isinstance(cf_json, dict):
                    for err in cf_json.get("errors", []):
                        if isinstance(err, dict) and isinstance(err.get("code"), int):
                            codes.add(err["code"])
            except Exception:
                pass
            lowered = res.text.lower()
            if 4006 in codes or 3036 in codes or "10,000 neurons" in lowered or "daily free allocation" in lowered:
                raise VisionProviderError(
                    "CLOUDFLARE_VISION_DAILY_QUOTA_EXCEEDED",
                    "Hạn mức 10.000 Neurons miễn phí hôm nay của Cloudflare đã chạm trần (Mã lỗi 4006). Tự động chuyển Local CV.",
                    status_code=429,
                )
            if 3040 in codes:
                raise VisionProviderError(
                    "CLOUDFLARE_VISION_RATE_LIMIT",
                    "Máy chủ Cloudflare AI đang quá tải đồng thời (Mã lỗi 3040). Tự động chuyển Local CV.",
                    transient=True,
                    status_code=429,
                )
            raise VisionProviderError("CLOUDFLARE_VISION_QUOTA_ERROR", "Đã đạt giới hạn quota Cloudflare Workers AI.", status_code=429)
        if res.status_code in (502, 503, 504):
            raise VisionProviderError("CLOUDFLARE_VISION_UNAVAILABLE", "Dịch vụ Cloudflare AI đang tạm thời bận.", transient=True, status_code=res.status_code)
        if res.status_code >= 400:
            raise VisionProviderError("CLOUDFLARE_VISION_API_ERROR", f"Cloudflare API returned HTTP {res.status_code}: {res.text[:200]}", status_code=res.status_code)

        data = res.json()
        return data

    def _extract_json_response(self, data: dict[str, Any]) -> dict[str, Any]:
        result = data.get("result") or {}
        text = result.get("response") or ""

        # Check for Meta License Agreement requirement
        text_lower = text.lower()
        if "agree" in text_lower and ("license" in text_lower or "terms" in text_lower or "prompt" in text_lower):
            raise VisionProviderError(
                "CLOUDFLARE_VISION_AGREEMENT_REQUIRED",
                "Cần chấp nhận điều khoản Meta Llama trước khi sử dụng model này trên tài khoản Cloudflare.",
            )

        match = _JSON_EXTRACT_PATTERN.search(text)
        if not match:
            raise ValueError(f"No valid JSON object found in Cloudflare response: {text[:150]}")
        return json.loads(match.group(0))

    def _merge_results(self, vision_data: dict[str, Any], local_res: RoomAnalysisResult, w: int, h: int) -> RoomAnalysisResult:
        # Room type: prioritize vision if reasonable, fallback to local
        v_room = str(vision_data.get("room_type") or "").strip()
        room_type = normalize_room_type(v_room) if v_room else (local_res.room_type or "Phòng khách")

        # Existing objects: parse from Vision
        existing_objects: list[DetectedObject] = []
        raw_objs = vision_data.get("existing_objects") or []
        for item in raw_objs:
            if isinstance(item, dict) and item.get("name"):
                name = str(item["name"]).strip()
                conf = float(item.get("confidence", 0.85))
                existing_objects.append(DetectedObject(name=name, confidence=min(1.0, max(0.1, conf))))

        # If vision detected no specific objects, supplement with local structural objects
        if not existing_objects:
            existing_objects = list(local_res.existing_objects)

        # Empty areas: merge vision empty areas with local floor areas
        empty_areas: list[EmptyArea] = []
        raw_areas = vision_data.get("empty_areas") or []
        for item in raw_areas:
            if isinstance(item, dict) and item.get("location"):
                empty_areas.append(
                    EmptyArea(
                        location=str(item["location"]).strip(),
                        description=str(item.get("description") or "").strip() or None,
                        suitable_for_decor=bool(item.get("suitable_for_decor", True)),
                    )
                )
        if not empty_areas:
            empty_areas = list(local_res.empty_areas)

        # Style & Characteristics
        style = str(vision_data.get("style") or "").strip()
        design_chars = list(local_res.design_characteristics)
        if style and style not in design_chars:
            design_chars.insert(0, f"Phong cách {style}")

        # Layout summary: use vision summary if high quality, else combine
        v_summary = str(vision_data.get("layout_summary") or "").strip()
        layout_summary = v_summary if len(v_summary) >= 30 else local_res.layout_summary

        conf = float(vision_data.get("confidence", 0.90))

        return RoomAnalysisResult(
            room_type=room_type,
            dominant_colors=local_res.dominant_colors,  # Ground truth optical measurement (0% pink)
            existing_objects=existing_objects,
            empty_areas=empty_areas,
            lighting=local_res.lighting,  # Ground truth optical lighting
            design_characteristics=design_chars,
            layout_summary=layout_summary,
            confidence=min(0.98, max(0.70, conf)),
        )

    def _classify_error(self, exc: Exception) -> VisionProviderError:
        msg = str(exc)
        if isinstance(exc, httpx.TimeoutException):
            return VisionProviderError("CLOUDFLARE_VISION_UNAVAILABLE", "Request to Cloudflare Vision timed out.", transient=True)
        if isinstance(exc, httpx.NetworkError):
            return VisionProviderError("CLOUDFLARE_VISION_UNAVAILABLE", "Network error connecting to Cloudflare.", transient=True)
        return VisionProviderError("CLOUDFLARE_VISION_REQUEST_FAILED", f"Cloudflare Vision failed: {msg[:200]}")
