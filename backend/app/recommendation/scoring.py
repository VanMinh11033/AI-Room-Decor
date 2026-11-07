from dataclasses import dataclass, field
from decimal import Decimal

from app.models.entities import Product, RoomAnalysis, RoomPreference


WEIGHTS = {
    "style": 30,
    "room_type": 20,
    "color": 15,
    "material": 15,
    "category": 10,
    "budget": 8,
    "purpose": 2,
}

PURPOSE_CATEGORY_KEYWORDS = {
    "nghỉ ngơi": {"sofa", "chair", "rug", "lighting", "bedding", "accessories"},
    "relaxation": {"sofa", "chair", "rug", "lighting", "bedding", "accessories"},
    "làm việc": {"table", "chair", "lighting", "storage"},
    "work": {"table", "chair", "lighting", "storage"},
    "học tập": {"table", "chair", "lighting", "storage"},
    "study": {"table", "chair", "lighting", "storage"},
    "tiếp khách": {"sofa", "table", "chair", "lighting", "rug", "wall-decor"},
    "giải trí": {"sofa", "lighting", "rug", "accessories"},
    "đọc sách": {"chair", "lighting", "storage"},
}


@dataclass
class ScoredProduct:
    product: Product
    score: float
    reasons: list[str] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)


def score_product(product: Product, preference: RoomPreference, analysis: RoomAnalysis) -> ScoredProduct:
    breakdown = {
        "style": overlap_score({item.id for item in product.styles}, {item.id for item in preference.styles}, WEIGHTS["style"]),
        "room_type": room_type_score(product, analysis),
        "color": color_score(product, preference, analysis),
        "material": overlap_score({item.id for item in product.materials}, {item.id for item in preference.materials}, WEIGHTS["material"]),
        "category": category_score(product, preference),
        "budget": budget_score(product, preference),
        "purpose": purpose_score(product, preference),
    }
    score = min(100, round(sum(breakdown.values()), 2))
    reasons = build_reasons(product, preference, analysis, breakdown)
    return ScoredProduct(product=product, score=score, reasons=reasons, breakdown=breakdown)


def overlap_score(product_ids: set[int], selected_ids: set[int], weight: float) -> float:
    if not selected_ids:
        return weight * 0.5
    overlap = len(product_ids & selected_ids)
    if overlap == 0:
        return 0
    return round(weight * min(1, overlap / len(selected_ids)), 2)


def room_type_score(product: Product, analysis: RoomAnalysis) -> float:
    if not analysis.room_type:
        return WEIGHTS["room_type"] * 0.4
    detected = analysis.room_type.strip().lower()
    product_room_types = {item.slug.lower() for item in product.room_types} | {item.name.lower() for item in product.room_types}
    if detected in product_room_types:
        return WEIGHTS["room_type"]
    confidence = float(analysis.confidence or 0)
    return round(WEIGHTS["room_type"] * 0.25, 2) if confidence < 0.6 else 0


def color_score(product: Product, preference: RoomPreference, analysis: RoomAnalysis) -> float:
    preferred_ids = {item.id for item in preference.colors}
    product_ids = {item.id for item in product.colors}
    if preferred_ids:
        return overlap_score(product_ids, preferred_ids, WEIGHTS["color"])

    detected_names = {str(item.get("name", "")).lower() for item in (analysis.dominant_colors or []) if isinstance(item, dict)}
    product_names = {item.name.lower() for item in product.colors} | {item.slug.lower() for item in product.colors}
    if detected_names and detected_names & product_names:
        return round(WEIGHTS["color"] * 0.6, 2)
    return WEIGHTS["color"] * 0.25


def category_score(product: Product, preference: RoomPreference) -> float:
    selected_ids = {item.id for item in preference.categories}
    if not selected_ids:
        return WEIGHTS["category"] * 0.5
    return WEIGHTS["category"] if product.category_id in selected_ids else 0


def budget_score(product: Product, preference: RoomPreference) -> float:
    price = Decimal(product.price or 0)
    if preference.budget_max is None and preference.budget_min is None:
        return WEIGHTS["budget"] * 0.5
    if preference.budget_max is not None and price > preference.budget_max:
        return 0
    if preference.budget_min is not None and price < preference.budget_min:
        return round(WEIGHTS["budget"] * 0.65, 2)
    return WEIGHTS["budget"]


def purpose_score(product: Product, preference: RoomPreference) -> float:
    if not preference.purpose:
        return 0
    allowed = PURPOSE_CATEGORY_KEYWORDS.get(preference.purpose.strip().lower())
    if not allowed:
        return 0
    if product.category and (product.category.slug in allowed or product.category.name.lower() in allowed):
        return WEIGHTS["purpose"]
    return 0


def build_reasons(product: Product, preference: RoomPreference, analysis: RoomAnalysis, breakdown: dict[str, float]) -> list[str]:
    reasons: list[str] = []
    if breakdown["style"] >= WEIGHTS["style"] * 0.5 and preference.styles:
        matched = sorted({item.name for item in product.styles} & {item.name for item in preference.styles})
        if matched:
            reasons.append(f"Phù hợp phong cách {', '.join(matched[:2])}")
    if breakdown["room_type"] == WEIGHTS["room_type"] and analysis.room_type:
        reasons.append(f"Phù hợp với {analysis.room_type}")
    if breakdown["color"] >= WEIGHTS["color"] * 0.5:
        reasons.append("Màu sắc phù hợp sở thích")
    if breakdown["material"] >= WEIGHTS["material"] * 0.5 and preference.materials:
        reasons.append("Vật liệu đúng lựa chọn")
    if breakdown["category"] == WEIGHTS["category"] and preference.categories:
        reasons.append("Đúng loại sản phẩm bạn đang tìm")
    if breakdown["budget"] == WEIGHTS["budget"]:
        reasons.append("Phù hợp ngân sách")
    if breakdown["purpose"] > 0:
        reasons.append("Hỗ trợ mục đích sử dụng chính")
    return reasons[:4] or ["Sản phẩm phù hợp với dữ liệu phòng và catalog hiện tại"]
