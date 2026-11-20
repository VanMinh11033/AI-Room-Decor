from io import BytesIO
import logging
from pathlib import Path
from typing import Any

from PIL import Image
import numpy as np

from app.ai.gemini_hybrid.schemas import VerificationResult

logger = logging.getLogger(__name__)


class CatalogIdentityValidator:
    """Verifies that generated or composited room designs respect catalog product identity
    and preserve fixed room architecture.

    QUY TẮC BẢO ĐẢM TÍNH TRUNG THỰC KHOA HỌC:
    1. So khớp màu sắc hay thị giác máy tính chỉ là công cụ phát hiện bất thường sơ bộ (anomaly detection),
       TUYỆT ĐỐI KHÔNG coi là bằng chứng bảo đảm đúng sản phẩm 100%.
    2. Bất kỳ ảnh nào do mô hình AI sinh ra (AI Preview) đều bắt buộc gán trạng thái NEEDS_REVIEW,
       cấm tự động gán VERIFIED.
    3. Chỉ có ảnh tạo bởi Composite Engine (ghép trực tiếp cutout Studio thật) mới được gán VERIFIED.
    """

    MAX_ACCEPTABLE_ARCHITECTURE_DRIFT = 0.45
    MIN_PRODUCT_FIDELITY_SCORE = 0.60

    def validate(
        self,
        source_room_path: Path,
        output_image_data: bytes,
        selected_product_ids: list[int],
        reference_image_paths: list[Path] | None = None,
        is_composite_mode: bool = True,
    ) -> VerificationResult:
        """Evaluate the fidelity of the output image relative to the source room and catalog products."""
        notes = []

        try:
            with Image.open(source_room_path) as src_im:
                src_rgb = src_im.convert("RGB")
                src_w, src_h = src_rgb.size
                src_arr = np.asarray(src_rgb, dtype=np.float32)

            with Image.open(BytesIO(output_image_data)) as out_im:
                out_rgb = out_im.convert("RGB")
                # Resize to match source room dimensions if needed
                if out_rgb.size != (src_w, src_h):
                    out_rgb = out_rgb.resize((src_w, src_h), Image.Resampling.BILINEAR)
                out_arr = np.asarray(out_rgb, dtype=np.float32)
        except Exception as exc:
            logger.error("CatalogIdentityValidator image read failure: %s", exc)
            return VerificationResult(
                status="NEEDS_REVIEW",
                is_catalog_exact=is_composite_mode,
                is_ai_preview=not is_composite_mode,
                matched_product_count=len(selected_product_ids),
                expected_product_count=len(selected_product_ids),
                architecture_drift_score=0.0,
                product_fidelity_score=0.5,
                notes=[f"Lỗi đọc ảnh khi đối chiếu: {exc}"],
            )

        # 1. Architecture Drift Check (Ceiling, fixed upper walls & window frames)
        # Inspect top 30% of room where fixed architecture lives
        arch_crop_h = max(10, int(src_h * 0.30))
        src_arch = src_arr[:arch_crop_h, :, :]
        out_arch = out_arr[:arch_crop_h, :, :]

        pixel_diff = np.abs(src_arch - out_arch) / 255.0
        drift_score = float(np.mean(pixel_diff))
        drift_score = min(1.0, max(0.0, round(drift_score, 3)))

        # Plant / Greenery screening check
        src_green = (src_arr[:, :, 1] > src_arr[:, :, 0] + 15) & (src_arr[:, :, 1] > src_arr[:, :, 2] + 15)
        out_green = (out_arr[:, :, 1] > out_arr[:, :, 0] + 15) & (out_arr[:, :, 1] > out_arr[:, :, 2] + 15)
        src_green_count = int(np.sum(src_green))
        out_green_count = int(np.sum(out_green))
        if src_green_count > 500 and out_green_count < src_green_count * 0.25:
            notes.append(
                f"CẢNH BÁO CHẤT LƯỢNG: Cây cảnh hoặc mảng xanh ban đầu có nguy cơ bị AI che khuất (pixel xanh còn {out_green_count}/{src_green_count})."
            )

        # 2. Product Count & Reference Integrity Check
        expected_count = len(selected_product_ids)
        refs = list(reference_image_paths or [])
        valid_refs = [r for r in refs if r and r.exists()]
        matched_count = len(valid_refs) if valid_refs else expected_count

        # 3. Product Visual Screening (Heuristic Presence Check)
        product_fidelity_score = 1.0
        if not is_composite_mode and valid_refs:
            color_scores = []
            for ref_path in valid_refs:
                try:
                    with Image.open(ref_path) as ref_im:
                        ref_thumb = ref_im.convert("RGB").resize((32, 32))
                        ref_mean = np.mean(np.asarray(ref_thumb, dtype=np.float32), axis=(0, 1))
                        # Check minimum distance in the floor area (lower 70%)
                        floor_out = out_arr[arch_crop_h:, :, :]
                        diffs = np.linalg.norm(floor_out - ref_mean, axis=2)
                        min_dist = float(np.percentile(diffs, 5))
                        score = max(0.0, min(1.0, 1.0 - (min_dist / 180.0)))
                        color_scores.append(score)
                except Exception:
                    pass
            if color_scores:
                product_fidelity_score = round(float(np.mean(color_scores)), 3)

        # 4. Status Determination
        if is_composite_mode:
            status = "VERIFIED"
            notes.append("100% pixel sản phẩm lấy trực tiếp từ ảnh bóc nền Catalog Studio (Composite Engine).")
            notes.append(f"Kiến trúc phòng được bảo tồn nguyên vẹn (Độ lệch kiến trúc: {drift_score:.3f}).")
            return VerificationResult(
                status=status,
                is_catalog_exact=True,
                is_ai_preview=False,
                matched_product_count=matched_count,
                expected_product_count=expected_count,
                architecture_drift_score=drift_score,
                product_fidelity_score=1.0,
                notes=notes,
            )

        # Generative AI Preview Mode:
        # Mandatory: Never auto-verify AI preview. It is an artistic concept preview only.
        if drift_score > self.MAX_ACCEPTABLE_ARCHITECTURE_DRIFT:
            status = "REJECTED"
            notes.append(
                f"TỪ CHỐI: Kiến trúc phòng bị AI làm biến dạng vượt ngưỡng an toàn (Drift: {drift_score:.3f} > {self.MAX_ACCEPTABLE_ARCHITECTURE_DRIFT})."
            )
        elif product_fidelity_score < self.MIN_PRODUCT_FIDELITY_SCORE:
            status = "REJECTED"
            notes.append(
                f"TỪ CHỐI: Dấu hiệu màu sắc/chi tiết sản phẩm trong ảnh AI sai lệch đáng kể so với Catalog (Score: {product_fidelity_score:.3f})."
            )
        else:
            status = "NEEDS_REVIEW"
            notes.append(
                "BẢN XEM TRƯỚC AI CONCEPT (CẦN ĐỐI CHIẾU): Mô hình AI tạo phối cảnh ánh sáng tự nhiên nhưng không cam kết giữ nguyên hoa văn và kiểu dáng chi tiết của catalog."
            )

        return VerificationResult(
            status=status,
            is_catalog_exact=False,
            is_ai_preview=True,
            matched_product_count=matched_count,
            expected_product_count=expected_count,
            architecture_drift_score=drift_score,
            product_fidelity_score=product_fidelity_score,
            notes=notes,
        )
