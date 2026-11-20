"""Budget Bundle Optimizer for AI Room Decor V1.5 PRO.

Performs exact combinatorial search to select the optimal bundle of up to 3 catalog items:
1. Enforces hard constraint: TOTAL_SELECTED_PRODUCTS_PRICE <= USER_BUDGET_MAX.
2. Provider reference constraint: Max 3 products per design generation (FLUX.2 Dev input limit).
3. Category diversity: All items in bundle must belong to distinct categories.
4. Functional balance: Prioritizes Anchor + Accent + Functional composition.
5. Style cohesion: Rewards combinations sharing common aesthetic styles.
6. Fallback resilience: Dynamically scales from 3 items -> 2 items -> 1 item when budget is tight.
7. Budget violation handling: Explains transparently when budget cannot accommodate catalog items.
"""

from dataclasses import dataclass, field
from decimal import Decimal
import itertools
from typing import Any

from app.models.entities import Product
from app.recommendation.functional_planner import ProductRole, get_product_role, get_recipe_for_room
from app.recommendation.resolver import EffectivePreference
from app.recommendation.scoring import ScoredProduct


@dataclass
class OptimizedBundle:
    items: list[ScoredProduct]
    total_price: Decimal
    total_score: float
    remaining_budget: Decimal | None
    is_budget_compliant: bool
    bundle_explanation: str
    roles_present: list[ProductRole] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_ids": [item.product.id for item in self.items],
            "product_names": [item.product.name for item in self.items],
            "total_price": float(self.total_price),
            "total_score": round(self.total_score, 2),
            "remaining_budget": float(self.remaining_budget) if self.remaining_budget is not None else None,
            "is_budget_compliant": self.is_budget_compliant,
            "bundle_explanation": self.bundle_explanation,
            "roles": [r.value for r in self.roles_present],
        }


class BudgetBundleOptimizer:
    """Exact combinatorial optimizer for catalog product bundles."""

    def __init__(self, max_items: int = 3) -> None:
        self.max_items = max(1, min(3, max_items))

    def optimize_bundle(
        self,
        scored_products: list[ScoredProduct],
        effective_pref: EffectivePreference,
    ) -> OptimizedBundle:
        """Find the optimal set of 1 to 3 products satisfying budget and functional constraints."""
        if not scored_products:
            return OptimizedBundle(
                items=[],
                total_price=Decimal(0),
                total_score=0.0,
                remaining_budget=effective_pref.budget_max,
                is_budget_compliant=True,
                bundle_explanation="Không có sản phẩm nào khả dụng trong catalog.",
            )

        budget_max = effective_pref.budget_max
        # Filter candidate pool: take top 12 scored products to keep combinatorial search instantaneous (< 2ms)
        candidate_pool = [sp for sp in scored_products if sp.score > 0][:15]
        if not candidate_pool:
            candidate_pool = scored_products[:5]

        best_bundle: list[ScoredProduct] | None = None
        best_objective: float = -1.0
        best_price = Decimal(0)

        # Search descending from max_items down to 1
        for k in range(self.max_items, 0, -1):
            combos = itertools.combinations(candidate_pool, k)
            for combo in combos:
                combo_list = list(combo)
                total_price = sum(Decimal(sp.product.price or 0) for sp in combo_list)

                # 1. Hard Budget Constraint
                if budget_max is not None and total_price > budget_max:
                    continue

                # 2. Hard Category Diversity: Distinct category_ids
                category_ids = {sp.product.category_id for sp in combo_list}
                if len(category_ids) < len(combo_list):
                    continue

                # 3. Maximum 1 major seating/bed anchor
                anchor_count = sum(1 for sp in combo_list if sp.role == ProductRole.ANCHOR)
                if anchor_count > 1 and len(combo_list) > 1:
                    continue

                # 4. Compute composite objective
                objective = self._evaluate_bundle_objective(combo_list, effective_pref)
                if objective > best_objective:
                    best_objective = objective
                    best_bundle = combo_list
                    best_price = total_price

            # If an optimal bundle of size k was found under budget, we prefer it over smaller sizes
            if best_bundle is not None:
                break

        # If no bundle fits within budget_max, find the single closest affordable item or report shortfall
        if best_bundle is None:
            affordable_single = [sp for sp in scored_products if budget_max is None or Decimal(sp.product.price or 0) <= budget_max]
            if affordable_single:
                best_item = max(affordable_single, key=lambda x: x.score)
                best_bundle = [best_item]
                best_price = Decimal(best_item.product.price or 0)
                remaining = budget_max - best_price if budget_max is not None else None
                return OptimizedBundle(
                    items=best_bundle,
                    total_price=best_price,
                    total_score=best_item.score,
                    remaining_budget=remaining,
                    is_budget_compliant=True,
                    bundle_explanation=f"Ngân sách giới hạn: Hệ thống chọn phương án 1 món tối ưu ({best_item.product.name}) với chi phí {best_price:,.0f} VND.",
                    roles_present=[best_item.role],
                )
            else:
                # Even cheapest item exceeds budget
                cheapest_item = min(scored_products, key=lambda x: Decimal(x.product.price or 0))
                cheapest_price = Decimal(cheapest_item.product.price or 0)
                diff = cheapest_price - budget_max if budget_max else Decimal(0)
                return OptimizedBundle(
                    items=[cheapest_item],
                    total_price=cheapest_price,
                    total_score=cheapest_item.score,
                    remaining_budget=None,
                    is_budget_compliant=False,
                    bundle_explanation=(
                        f"Ngân sách hiện tại ({budget_max:,.0f} VND) thấp hơn giá sản phẩm khởi điểm rẻ nhất trong catalog "
                        f"({cheapest_item.product.name}: {cheapest_price:,.0f} VND). Cần thêm khoảng {diff:,.0f} VND để hoàn thiện bộ nội thất."
                    ),
                    roles_present=[cheapest_item.role],
                )

        remaining_budget = budget_max - best_price if budget_max is not None else None
        roles_present = [item.role for item in best_bundle]
        explanation = self._generate_bundle_explanation(best_bundle, best_price, remaining_budget, effective_pref)

        return OptimizedBundle(
            items=best_bundle,
            total_price=best_price,
            total_score=round(sum(sp.score for sp in best_bundle) / len(best_bundle), 2),
            remaining_budget=remaining_budget,
            is_budget_compliant=True,
            bundle_explanation=explanation,
            roles_present=roles_present,
        )

    def _evaluate_bundle_objective(
        self,
        combo: list[ScoredProduct],
        pref: EffectivePreference,
    ) -> float:
        """Score bundle quality based on score sum, role cohesion, and style harmony."""
        base_sum = sum(sp.score for sp in combo)
        k = len(combo)

        # 1. Size reward: Favor multi-product complete design over single product when budget permits
        size_bonus = (k - 1) * 15.0

        # 2. Functional role cohesion: Having 1 Anchor + (Functional or Accent)
        roles = {sp.role for sp in combo}
        role_bonus = 0.0
        if ProductRole.ANCHOR in roles and (ProductRole.ACCENT in roles or ProductRole.FUNCTIONAL in roles):
            role_bonus += 12.0

        # 3. Style harmony: All items sharing common styles
        style_bonus = 0.0
        if k > 1:
            common_styles = set(combo[0].product.styles)
            for sp in combo[1:]:
                common_styles &= set(sp.product.styles)
            if common_styles:
                style_bonus += 10.0

        # 4. Color harmony: All items sharing neutral or common color palette
        color_bonus = 0.0
        if k > 1:
            common_colors = set(combo[0].product.colors)
            for sp in combo[1:]:
                common_colors &= set(sp.product.colors)
            if common_colors:
                color_bonus += 6.0

        return base_sum + size_bonus + role_bonus + style_bonus + color_bonus

    def _generate_bundle_explanation(
        self,
        bundle: list[ScoredProduct],
        total_price: Decimal,
        remaining_budget: Decimal | None,
        pref: EffectivePreference,
    ) -> str:
        names = ", ".join(item.product.name for item in bundle)
        count = len(bundle)
        rem_str = f", ngân sách còn lại {remaining_budget:,.0f} VND" if remaining_budget is not None else ""
        return f"Tổ hợp {count} sản phẩm tối ưu ({names}) với tổng giá {total_price:,.0f} VND{rem_str}, đảm bảo hài hòa công năng và phong cách."
