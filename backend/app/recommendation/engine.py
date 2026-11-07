from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models.entities import Product, ProductStatus, RoomAnalysis, RoomPreference
from app.recommendation.scoring import ScoredProduct, score_product


class RecommendationEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def recommend(self, preference: RoomPreference, analysis: RoomAnalysis, limit: int) -> list[ScoredProduct]:
        candidates = self._candidate_products(preference)
        scored = [score_product(product, preference, analysis) for product in candidates]
        scored.sort(key=lambda item: (-item.score, Decimal(item.product.price), item.product.id))
        return self._diversify(scored, preference, limit)

    def _candidate_products(self, preference: RoomPreference) -> list[Product]:
        query = (
            self.db.query(Product)
            .options(
                joinedload(Product.category),
                joinedload(Product.images),
                joinedload(Product.materials),
                joinedload(Product.styles),
                joinedload(Product.room_types),
                joinedload(Product.colors),
            )
            .filter(
                Product.is_active.is_(True),
                Product.status == ProductStatus.ACTIVE,
                Product.stock_quantity > 0,
            )
        )
        if preference.categories:
            query = query.filter(Product.category_id.in_([item.id for item in preference.categories]))
        if preference.budget_max is not None:
            query = query.filter(Product.price <= preference.budget_max)
        return query.all()

    def _diversify(self, scored: list[ScoredProduct], preference: RoomPreference, limit: int) -> list[ScoredProduct]:
        if not preference.categories or limit <= 0:
            return scored[:limit]

        grouped: dict[int, list[ScoredProduct]] = defaultdict(list)
        for item in scored:
            grouped[item.product.category_id].append(item)

        selected: list[ScoredProduct] = []
        selected_ids: set[int] = set()
        category_order = [category.id for category in preference.categories]
        while len(selected) < limit:
            added = False
            for category_id in category_order:
                bucket = grouped.get(category_id) or []
                while bucket and bucket[0].product.id in selected_ids:
                    bucket.pop(0)
                if bucket:
                    item = bucket.pop(0)
                    selected.append(item)
                    selected_ids.add(item.product.id)
                    added = True
                    if len(selected) == limit:
                        break
            if not added:
                break

        for item in scored:
            if len(selected) == limit:
                break
            if item.product.id not in selected_ids:
                selected.append(item)
                selected_ids.add(item.product.id)
        return selected
