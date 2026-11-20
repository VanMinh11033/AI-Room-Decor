"""Smart Recommendation Engine Scoring V1.5 PRO.

Implements Explainable Multi-Criteria Decision Analysis (MCDA) combining:
- 8 Core Attributes (Style 25%, Room Type 20%, Color 15%, Material 10%, Category 10%, Budget 10%, Purpose 5%, Spatial 5%)
- Behavioral Signals (Favorite Boost +10 pts, Cart/Order Affinity +5 pts)
- Explainable Reasons & Score Breakdown
- Safe Soft-Margin Normalization clamped between 0 and 100
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.models.entities import Product, RoomAnalysis, RoomPreference
from app.recommendation.functional_planner import ProductRole, get_product_role
from app.recommendation.resolver import EffectivePreference


WEIGHTS_V1_5: dict[str, float] = {
    "style": 25.0,
    "room_type": 20.0,
    "color": 15.0,
    "material": 10.0,
    "category": 10.0,
    "budget": 10.0,
    "purpose": 5.0,
    "spatial": 5.0,
}

PURPOSE_CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "nghỉ ngơi": {"sofa", "chair", "rug", "lighting", "bedding", "accessories"},
    "relaxation": {"sofa", "chair", "rug", "lighting", "bedding", "accessories"},
    "làm việc": {"table", "chair", "lighting", "storage"},
    "work": {"table", "chair", "lighting", "storage"},
    "học tập": {"table", "chair", "lighting", "storage"},
    "study": {"table", "chair", "lighting", "storage"},
    "tiếp khách": {"sofa", "table", "chair", "lighting", "rug", "wall-decor"},
    "entertaining": {"sofa", "table", "chair", "lighting", "rug", "wall-decor"},
    "giải trí": {"sofa", "lighting", "rug", "accessories"},
    "đọc sách": {"chair", "lighting", "storage"},
}

ROOM_TYPE_SYNONYMS: dict[str, set[str]] = {
    "phòng khách": {"living-room", "living room", "studio"},
    "living-room": {"living-room", "living room", "studio"},
    "living room": {"living-room", "living room", "studio"},
    "phòng ngủ": {"bedroom"},
    "bedroom": {"bedroom"},
    "góc làm việc": {"workspace", "study-room", "study room"},
    "phòng làm việc": {"workspace", "study-room", "study room"},
    "workspace": {"workspace", "study-room", "study room"},
    "phòng học": {"study-room", "study room", "workspace"},
    "study-room": {"study-room", "study room", "workspace"},
    "study room": {"study-room", "study room", "workspace"},
    "phòng ăn": {"dining-room", "dining room"},
    "dining-room": {"dining-room", "dining room"},
    "dining room": {"dining-room", "dining room"},
    "studio": {"studio", "living-room", "living room"},
    "phòng sinh hoạt": {"living-room", "living room", "studio"},
}

COLOR_SYNONYMS: dict[str, set[str]] = {
    "trắng": {"white", "cream"},
    "white": {"white", "cream"},
    "đen": {"black"},
    "black": {"black"},
    "gỗ sồi": {"oak", "walnut"},
    "oak": {"oak", "walnut"},
    "gỗ óc chó": {"walnut", "oak"},
    "walnut": {"walnut", "oak"},
    "kem": {"cream", "white"},
    "be": {"cream", "white", "oak"},
    "cream": {"cream", "white"},
    "beige": {"cream", "white", "oak"},
    "xám": {"gray"},
    "gray": {"gray"},
    "grey": {"gray"},
    "xanh sage": {"sage"},
    "sage": {"sage"},
    "đất nung": {"terracotta"},
    "terracotta": {"terracotta"},
    "xanh navy": {"navy"},
    "navy": {"navy"},
    "đồng thau": {"brass"},
    "brass": {"brass"},
}


@dataclass
class ScoredProduct:
    product: Product
    score: float
    raw_score: float = 0.0
    boost: float = 0.0
    penalty: float = 0.0
    role: ProductRole = ProductRole.ACCENT
    reasons: list[str] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)


def score_product_v1_5(
    product: Product,
    effective_pref: EffectivePreference,
    analysis: RoomAnalysis | None = None,
    favorite_ids: set[int] | None = None,
    cart_order_ids: set[int] | None = None,
) -> ScoredProduct:
    """Calculate multi-criteria recommendation score for a product with explainable breakdown."""
    fav_set = favorite_ids or set()
    cart_set = cart_order_ids or set()
    role = get_product_role(product)

    # 1. Attribute Breakdown
    breakdown: dict[str, float] = {
        "style": _score_style(product, effective_pref),
        "room_type": _score_room_type(product, effective_pref, analysis),
        "color": _score_color(product, effective_pref, analysis),
        "material": _score_material(product, effective_pref),
        "category": _score_category(product, effective_pref),
        "budget": _score_budget(product, effective_pref),
        "purpose": _score_purpose(product, effective_pref),
        "spatial": _score_spatial(product, analysis, role),
    }

    raw_score = sum(breakdown.values())

    # 2. Behavioral Signals (Cannot bypass budget limit: if price > budget_max, boost is 0)
    price = Decimal(product.price or 0)
    is_budget_exceeded = effective_pref.budget_max is not None and price > effective_pref.budget_max
    
    boost = 0.0
    if not is_budget_exceeded:
        if product.id in fav_set:
            boost += 10.0
        if product.id in cart_set:
            boost += 5.0

    penalty = 0.0
    if is_budget_exceeded:
        penalty = 50.0  # Heavy penalty for hard budget violation

    final_score = min(100.0, max(0.0, round(raw_score + boost - penalty, 2)))

    # 3. Explainable reasons
    reasons = _build_reasons_v1_5(product, effective_pref, analysis, breakdown, boost)

    return ScoredProduct(
        product=product,
        score=final_score,
        raw_score=round(raw_score, 2),
        boost=round(boost, 2),
        penalty=round(penalty, 2),
        role=role,
        reasons=reasons,
        breakdown={k: round(v, 2) for k, v in breakdown.items()},
        provenance=dict(effective_pref.provenance),
    )


def _score_style(product: Product, pref: EffectivePreference) -> float:
    weight = WEIGHTS_V1_5["style"]
    if not pref.style_ids:
        return weight * 0.5  # Neutral 50% if user has not indicated a style
    prod_styles = {item.id for item in product.styles}
    overlap = len(prod_styles & pref.style_ids)
    if overlap == 0:
        return 0.0
    return round(weight * min(1.0, overlap / len(pref.style_ids)), 2)


def _score_room_type(product: Product, pref: EffectivePreference, analysis: RoomAnalysis | None) -> float:
    weight = WEIGHTS_V1_5["room_type"]
    target = pref.room_type.strip().lower()
    product_room_types = {item.slug.lower() for item in product.room_types} | {item.name.lower() for item in product.room_types}
    
    if target in product_room_types:
        return weight

    synonyms = ROOM_TYPE_SYNONYMS.get(target, set())
    if synonyms & product_room_types:
        return weight

    if analysis and analysis.confidence:
        confidence = float(analysis.confidence)
        if confidence < 0.6:
            return round(weight * 0.25, 2)

    return 0.0


def _score_color(product: Product, pref: EffectivePreference, analysis: RoomAnalysis | None) -> float:
    weight = WEIGHTS_V1_5["color"]
    prod_colors = {item.id for item in product.colors}

    # 1. User explicit preferred colors
    if pref.color_ids:
        overlap = len(prod_colors & pref.color_ids)
        if overlap > 0:
            return round(weight * min(1.0, overlap / len(pref.color_ids)), 2)
        return round(weight * 0.2, 2)

    # 2. Match computer vision dominant colors
    if analysis and analysis.dominant_colors and isinstance(analysis.dominant_colors, list):
        detected_names = {str(item.get("name", "")).strip().lower() for item in analysis.dominant_colors if isinstance(item, dict)}
        prod_names = {item.name.lower() for item in product.colors} | {item.slug.lower() for item in product.colors}
        
        if detected_names & prod_names:
            return round(weight * 0.7, 2)

        expanded = set()
        for name in detected_names:
            expanded.add(name)
            expanded.update(COLOR_SYNONYMS.get(name, set()))
        if expanded & prod_names:
            return round(weight * 0.7, 2)

    return round(weight * 0.35, 2)


def _score_material(product: Product, pref: EffectivePreference) -> float:
    weight = WEIGHTS_V1_5["material"]
    if not pref.material_ids:
        return round(weight * 0.5, 2)
    prod_mats = {item.id for item in product.materials}
    overlap = len(prod_mats & pref.material_ids)
    if overlap == 0:
        return 0.0
    return round(weight * min(1.0, overlap / len(pref.material_ids)), 2)


def _score_category(product: Product, pref: EffectivePreference) -> float:
    weight = WEIGHTS_V1_5["category"]
    if not pref.category_ids:
        return round(weight * 0.5, 2)
    return weight if product.category_id in pref.category_ids else 0.0


def _score_budget(product: Product, pref: EffectivePreference) -> float:
    weight = WEIGHTS_V1_5["budget"]
    price = Decimal(product.price or 0)
    
    if pref.budget_max is None and pref.budget_min is None:
        return round(weight * 0.75, 2)  # Neutral good score when unrestricted

    if pref.budget_max is not None and price > pref.budget_max:
        return 0.0

    if pref.budget_min is not None and price < pref.budget_min:
        ratio = float(price / pref.budget_min) if pref.budget_min > 0 else 0.5
        soft_score = weight * max(0.4, min(1.0, 0.6 + 0.4 * ratio))
        return round(soft_score, 2)

    return weight


def _score_purpose(product: Product, pref: EffectivePreference) -> float:
    weight = WEIGHTS_V1_5["purpose"]
    if not pref.purpose:
        return round(weight * 0.5, 2)
    allowed = PURPOSE_CATEGORY_KEYWORDS.get(pref.purpose.strip().lower())
    if not allowed:
        return round(weight * 0.5, 2)
    cat_slug = getattr(product.category, "slug", "") if getattr(product, "category", None) else ""
    cat_name = getattr(product.category, "name", "").lower() if getattr(product, "category", None) else ""
    if cat_slug in allowed or cat_name in allowed:
        return weight
    return 0.0


def _score_spatial(product: Product, analysis: RoomAnalysis | None, role: ProductRole) -> float:
    weight = WEIGHTS_V1_5["spatial"]
    if analysis is None or not analysis.empty_areas:
        return round(weight * 0.7, 2)  # Estimated neutral when dimensions are unmeasured

    empty_areas = analysis.empty_areas if isinstance(analysis.empty_areas, list) else []
    
    # Large anchor items (sofas, desks, beds) need clear central floor area
    if role == ProductRole.ANCHOR:
        has_central_floor = any("sàn" in str(area.get("location", "")).lower() or "trung tâm" in str(area.get("location", "")).lower() for area in empty_areas)
        return weight if has_central_floor else round(weight * 0.5, 2)

    # Accent and functional pieces fit along perimeter and corners
    return weight


def _build_reasons_v1_5(
    product: Product,
    pref: EffectivePreference,
    analysis: RoomAnalysis | None,
    breakdown: dict[str, float],
    boost: float,
) -> list[str]:
    reasons: list[str] = []
    
    if boost >= 10.0:
        reasons.append("Sản phẩm trong danh sách yêu thích của bạn")
    elif boost >= 5.0:
        reasons.append("Phù hợp với lịch sử mua sắm / giỏ hàng")

    if breakdown["style"] >= WEIGHTS_V1_5["style"] * 0.5 and pref.styles:
        matched = sorted({item.name for item in product.styles} & set(pref.styles))
        if matched:
            reasons.append(f"Phù hợp phong cách {', '.join(matched[:2])}")
    
    if breakdown["room_type"] == WEIGHTS_V1_5["room_type"]:
        reasons.append(f"Phù hợp tối ưu cho {pref.room_type}")

    if breakdown["color"] >= WEIGHTS_V1_5["color"] * 0.5:
        reasons.append("Tông màu ăn khớp với căn phòng")

    if breakdown["material"] >= WEIGHTS_V1_5["material"] * 0.5 and pref.materials:
        reasons.append("Vật liệu đúng sở thích cá nhân")

    if breakdown["budget"] == WEIGHTS_V1_5["budget"]:
        reasons.append("Nằm trong khoảng ngân sách dự kiến")

    if breakdown["purpose"] == WEIGHTS_V1_5["purpose"] and pref.purpose:
        reasons.append(f"Hỗ trợ công năng {pref.purpose}")

    if breakdown["spatial"] == WEIGHTS_V1_5["spatial"]:
        reasons.append("Kích thước cân đối với không gian sàn")

    return reasons[:4] or ["Sản phẩm phù hợp với dữ liệu phòng và catalog hiện tại"]


# ---------------------------------------------------------------------------
# Legacy V1.0 Fallback Scoring Function & Helpers
# ---------------------------------------------------------------------------

LEGACY_WEIGHTS = {
    "style": 30,
    "room_type": 20,
    "color": 15,
    "material": 15,
    "category": 10,
    "budget": 8,
    "purpose": 2,
}


def score_product(product: Product, preference: RoomPreference, analysis: RoomAnalysis) -> ScoredProduct:
    breakdown = {
        "style": _legacy_overlap_score({item.id for item in product.styles}, {item.id for item in preference.styles}, LEGACY_WEIGHTS["style"]),
        "room_type": _legacy_room_type_score(product, analysis),
        "color": _legacy_color_score(product, preference, analysis),
        "material": _legacy_overlap_score({item.id for item in product.materials}, {item.id for item in preference.materials}, LEGACY_WEIGHTS["material"]),
        "category": _legacy_category_score(product, preference),
        "budget": _legacy_budget_score(product, preference),
        "purpose": _legacy_purpose_score(product, preference),
    }
    score = min(100, round(sum(breakdown.values()), 2))
    reasons = _legacy_build_reasons(product, preference, analysis, breakdown)
    return ScoredProduct(product=product, score=score, reasons=reasons, breakdown=breakdown)


def _legacy_overlap_score(product_ids: set[int], selected_ids: set[int], weight: float) -> float:
    if not selected_ids:
        return weight * 0.5
    overlap = len(product_ids & selected_ids)
    if overlap == 0:
        return 0
    return round(weight * min(1, overlap / len(selected_ids)), 2)


def _legacy_room_type_score(product: Product, analysis: RoomAnalysis) -> float:
    if not analysis.room_type:
        return LEGACY_WEIGHTS["room_type"] * 0.4
    detected = analysis.room_type.strip().lower()
    product_room_types = {item.slug.lower() for item in product.room_types} | {item.name.lower() for item in product.room_types}
    if detected in product_room_types:
        return LEGACY_WEIGHTS["room_type"]
    confidence = float(analysis.confidence or 0)
    return round(LEGACY_WEIGHTS["room_type"] * 0.25, 2) if confidence < 0.6 else 0


def _legacy_color_score(product: Product, preference: RoomPreference, analysis: RoomAnalysis) -> float:
    preferred_ids = {item.id for item in preference.colors}
    product_ids = {item.id for item in product.colors}
    if preferred_ids:
        return _legacy_overlap_score(product_ids, preferred_ids, LEGACY_WEIGHTS["color"])

    detected_names = {str(item.get("name", "")).lower() for item in (analysis.dominant_colors or []) if isinstance(item, dict)}
    product_names = {item.name.lower() for item in product.colors} | {item.slug.lower() for item in product.colors}
    if detected_names and detected_names & product_names:
        return round(LEGACY_WEIGHTS["color"] * 0.6, 2)
    return LEGACY_WEIGHTS["color"] * 0.25


def _legacy_category_score(product: Product, preference: RoomPreference) -> float:
    selected_ids = {item.id for item in preference.categories}
    if not selected_ids:
        return LEGACY_WEIGHTS["category"] * 0.5
    return LEGACY_WEIGHTS["category"] if product.category_id in selected_ids else 0


def _legacy_budget_score(product: Product, preference: RoomPreference) -> float:
    price = Decimal(product.price or 0)
    if preference.budget_max is None and preference.budget_min is None:
        return LEGACY_WEIGHTS["budget"] * 0.5
    if preference.budget_max is not None and price > preference.budget_max:
        return 0
    if preference.budget_min is not None and price < preference.budget_min:
        return round(LEGACY_WEIGHTS["budget"] * 0.65, 2)
    return LEGACY_WEIGHTS["budget"]


def _legacy_purpose_score(product: Product, preference: RoomPreference) -> float:
    if not preference.purpose:
        return 0
    allowed = PURPOSE_CATEGORY_KEYWORDS.get(preference.purpose.strip().lower())
    if not allowed:
        return 0
    if product.category and (product.category.slug in allowed or product.category.name.lower() in allowed):
        return LEGACY_WEIGHTS["purpose"]
    return 0


def _legacy_build_reasons(product: Product, preference: RoomPreference, analysis: RoomAnalysis, breakdown: dict[str, float]) -> list[str]:
    reasons: list[str] = []
    if breakdown["style"] >= LEGACY_WEIGHTS["style"] * 0.5 and preference.styles:
        matched = sorted({item.name for item in product.styles} & {item.name for item in preference.styles})
        if matched:
            reasons.append(f"Phù hợp phong cách {', '.join(matched[:2])}")
    if breakdown["room_type"] == LEGACY_WEIGHTS["room_type"] and analysis.room_type:
        reasons.append(f"Phù hợp với {analysis.room_type}")
    if breakdown["color"] >= LEGACY_WEIGHTS["color"] * 0.5:
        reasons.append("Màu sắc phù hợp sở thích")
    if breakdown["material"] >= LEGACY_WEIGHTS["material"] * 0.5 and preference.materials:
        reasons.append("Vật liệu đúng lựa chọn")
    if breakdown["category"] == LEGACY_WEIGHTS["category"] and preference.categories:
        reasons.append("Đúng loại sản phẩm bạn đang tìm")
    if breakdown["budget"] == LEGACY_WEIGHTS["budget"]:
        reasons.append("Phù hợp ngân sách")
    if breakdown["purpose"] > 0:
        reasons.append("Hỗ trợ mục đích sử dụng chính")
    return reasons[:4] or ["Sản phẩm phù hợp với dữ liệu phòng và catalog hiện tại"]
