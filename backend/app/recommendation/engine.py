"""Recommendation Engine for AI Room Decor (V1.0 Legacy & V1.5 PRO).

Supports:
- V1.5 PRO: Two-tier effective preference, MCDA multi-criteria scoring, behavioral boosts (Favorites & Orders), and Budget Bundle Optimization.
- V1.0 Legacy: Backward-compatible fallback when V1.5 feature flag is disabled.
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.entities import Cart, CartItem, Favorite, Order, OrderItem, Product, ProductStatus, RoomAnalysis, RoomPreference, User
from app.recommendation.bundle_optimizer import BudgetBundleOptimizer, OptimizedBundle
from app.recommendation.functional_planner import ProductRole
from app.recommendation.resolver import EffectivePreference
from app.recommendation.scoring import ScoredProduct, score_product_v1_5


class RecommendationEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.bundle_optimizer = BudgetBundleOptimizer(max_items=3)

    def recommend_v1_5(
        self,
        effective_pref: EffectivePreference,
        analysis: RoomAnalysis | None,
        user_id: int | None,
        limit: int = 50,
    ) -> tuple[list[ScoredProduct], OptimizedBundle]:
        """V1.5 PRO Recommendation pipeline with behavioral signals and budget bundle optimization."""
        # 1. Fetch Behavioral Signals (User Isolation enforced)
        favorite_ids: set[int] = set()
        cart_order_ids: set[int] = set()
        if user_id:
            favs = self.db.query(Favorite.product_id).filter(Favorite.user_id == user_id).all()
            favorite_ids = {f[0] for f in favs}

            cart_items = (
                self.db.query(CartItem.product_id)
                .join(Cart, Cart.id == CartItem.cart_id)
                .filter(Cart.user_id == user_id)
                .all()
            )
            order_items = (
                self.db.query(OrderItem.product_id)
                .join(Order, Order.id == OrderItem.order_id)
                .filter(Order.user_id == user_id)
                .all()
            )
            cart_order_ids = {c[0] for c in cart_items} | {o[0] for o in order_items}

        # 2. Fetch Active Catalog Candidates
        candidates = self._candidate_products_v1_5(effective_pref)

        # 3. Score Products with MCDA + Behavioral Signals
        scored = [
            score_product_v1_5(
                product=product,
                effective_pref=effective_pref,
                analysis=analysis,
                favorite_ids=favorite_ids,
                cart_order_ids=cart_order_ids,
            )
            for product in candidates
        ]
        scored.sort(key=lambda item: (-item.score, Decimal(item.product.price or 0), item.product.id))

        # 4. Optimize Budget Bundle (1 to 3 items under budget_max)
        bundle = self.bundle_optimizer.optimize_bundle(scored, effective_pref)

        # 5. Diversify ranked list for browsing
        diversified = self._diversify_v1_5(scored, effective_pref, limit)

        return diversified, bundle

    def recommend(self, preference: RoomPreference, analysis: RoomAnalysis, limit: int) -> list[ScoredProduct]:
        """Legacy V1.0 fallback interface."""
        # If V1.5 PRO is enabled, adapt legacy RoomPreference to EffectivePreference
        if getattr(settings, "room_decor_v1_5_personalization_enabled", True):
            from app.recommendation.resolver import EffectivePreferenceResolver
            user = preference.user if preference else None
            project = preference.room_project if preference else None
            if user and project:
                eff = EffectivePreferenceResolver(self.db).resolve(user, project, preference, analysis)
                diversified, _ = self.recommend_v1_5(eff, analysis, user.id, limit)
                return diversified

        # Original V1.0 implementation
        candidates = self._candidate_products_legacy(preference)
        from app.recommendation.scoring import score_product
        scored = [score_product(product, preference, analysis) for product in candidates]
        scored.sort(key=lambda item: (-item.score, Decimal(item.product.price), item.product.id))
        return self._diversify_legacy(scored, preference, limit)

    def _candidate_products_v1_5(self, effective_pref: EffectivePreference) -> list[Product]:
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
        # Note: Do not hard-filter by category_ids so customer can browse and select
        # from all active catalog products. Category preference is factored into MCDA scoring.
        if effective_pref.budget_max is not None:
            query = query.filter(Product.price <= effective_pref.budget_max)
        return query.all()

    def _candidate_products_legacy(self, preference: RoomPreference) -> list[Product]:
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

    def _diversify_v1_5(self, scored: list[ScoredProduct], pref: EffectivePreference, limit: int) -> list[ScoredProduct]:
        if not pref.category_ids or limit <= 0:
            return scored[:limit]

        grouped: dict[int, list[ScoredProduct]] = defaultdict(list)
        for item in scored:
            grouped[item.product.category_id].append(item)

        selected: list[ScoredProduct] = []
        selected_ids: set[int] = set()
        category_order = list(pref.category_ids)
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

    def _diversify_legacy(self, scored: list[ScoredProduct], preference: RoomPreference, limit: int) -> list[ScoredProduct]:
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
