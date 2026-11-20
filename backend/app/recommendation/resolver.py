"""Two-Tier Personalization Resolver for AI Room Decor V1.5 PRO.

Resolves effective design preferences by merging data sources in strict priority order:
1. Direct project request payload (if provided as ephemeral override).
2. RoomPreference (project-level explicit configuration).
3. UserProfile (account-level long-term aesthetic profile).
4. RoomAnalysis (computer vision detected room characteristics).
5. System defaults.

Key Principles:
- Project preferences always override user profile defaults.
- Clear provenance tracking: EXPLICIT_OVERRIDE vs INHERITED_PROFILE vs ROOM_ANALYSIS vs SYSTEM_DEFAULT vs EXPLICIT_EMPTY.
- User isolation: only accesses current_user's own profile and project.
- Non-destructive: resolving or altering room preferences never mutates UserProfile.
- Schema compatible: operates within existing SQLAlchemy models without database migration.
"""

from dataclasses import dataclass, field
from decimal import Decimal
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import Category, Color, Material, RoomAnalysis, RoomPreference, RoomProject, Style, User, UserProfile


class ProvenanceSource:
    EXPLICIT_OVERRIDE = "EXPLICIT_OVERRIDE"
    ROOM_PREFERENCE = "ROOM_PREFERENCE"
    INHERITED_PROFILE = "INHERITED_PROFILE"
    ROOM_ANALYSIS = "ROOM_ANALYSIS"
    SYSTEM_DEFAULT = "SYSTEM_DEFAULT"
    EXPLICIT_EMPTY = "EXPLICIT_EMPTY"


STYLE_TEXT_SYNONYMS: dict[str, list[str]] = {
    "japandi": ["japandi"],
    "scandinavian": ["scandinavian", "bắc âu", "bac au", "nordic"],
    "minimalist": ["minimalist", "tối giản", "toi gian", "minimal"],
    "modern": ["modern", "hiện đại", "hien dai"],
    "industrial": ["industrial", "công nghiệp", "cong nghiep"],
    "luxury": ["luxury", "sang trọng", "sang trong", "cao cấp", "trưởng thành", "truong thanh"],
    "vintage": ["vintage", "cổ điển", "co dien", "retro"],
    "bohemian": ["bohemian", "boho", "du mục", "du muc"],
}

COLOR_TEXT_SYNONYMS: dict[str, list[str]] = {
    "white": ["white", "trắng", "trang"],
    "black": ["black", "đen", "den"],
    "cream": ["cream", "kem", "be", "beige"],
    "oak": ["oak", "gỗ sồi", "go soi", "sồi", "soi"],
    "walnut": ["walnut", "gỗ óc chó", "go oc cho", "óc chó", "oc cho"],
    "gray": ["gray", "grey", "xám", "xam"],
    "sage": ["sage", "xanh sage", "xanh rêu", "xanh lá", "green"],
    "navy": ["navy", "xanh navy", "xanh dương", "blue"],
    "terracotta": ["terracotta", "đất nung", "dat nung", "cam đất"],
    "brass": ["brass", "đồng thau", "dong thau", "đồng", "gold"],
}

MATERIAL_TEXT_SYNONYMS: dict[str, list[str]] = {
    "wood": ["wood", "gỗ", "go", "gỗ tự nhiên"],
    "metal": ["metal", "kim loại", "kim loai", "thép", "sắt"],
    "fabric": ["fabric", "vải", "vai", "nỉ", "boucle", "linen"],
    "glass": ["glass", "kính", "kinh", "thủy tinh"],
    "bamboo": ["bamboo", "tre", "nứa", "bằng tre"],
    "rattan": ["rattan", "mây", "may", "mây tre"],
    "plastic": ["plastic", "nhựa", "nhua", "pvc", "nhựa pvc"],
    "stone": ["stone", "đá", "da", "marble", "cẩm thạch"],
}


@dataclass
class EffectivePreference:
    styles: list[str] = field(default_factory=list)
    style_ids: set[int] = field(default_factory=set)
    colors: list[str] = field(default_factory=list)
    color_ids: set[int] = field(default_factory=set)
    materials: list[str] = field(default_factory=list)
    material_ids: set[int] = field(default_factory=set)
    categories: list[str] = field(default_factory=list)
    category_ids: set[int] = field(default_factory=set)
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    currency: str = "VND"
    purpose: str | None = None
    notes: str | None = None
    room_type: str = "living-room"
    provenance: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "styles": self.styles,
            "style_ids": list(self.style_ids),
            "colors": self.colors,
            "color_ids": list(self.color_ids),
            "materials": self.materials,
            "material_ids": list(self.material_ids),
            "categories": self.categories,
            "category_ids": list(self.category_ids),
            "budget_min": float(self.budget_min) if self.budget_min is not None else None,
            "budget_max": float(self.budget_max) if self.budget_max is not None else None,
            "currency": self.currency,
            "purpose": self.purpose,
            "notes": self.notes,
            "room_type": self.room_type,
            "provenance": self.provenance,
        }


class EffectivePreferenceResolver:
    """Resolves and merges two-tier preferences strictly within user boundaries."""

    def __init__(self, db: Session) -> None:
        self.db = db
        # Pre-cache catalog lookup maps
        self._styles_by_slug = {s.slug.lower(): s for s in self.db.query(Style).all()}
        self._colors_by_slug = {c.slug.lower(): c for c in self.db.query(Color).all()}
        self._materials_by_slug = {m.slug.lower(): m for m in self.db.query(Material).all()}
        self._categories_by_slug = {c.slug.lower(): c for c in self.db.query(Category).all()}

    def resolve(
        self,
        current_user: User,
        project: RoomProject,
        room_preference: RoomPreference | None = None,
        analysis: RoomAnalysis | None = None,
        override_payload: dict[str, Any] | None = None,
    ) -> EffectivePreference:
        """Resolve effective preferences for a given user and room project."""
        # Enforce user boundary
        if project.user_id != current_user.id:
            raise PermissionError("Access denied: Project does not belong to current user.")

        user_profile: UserProfile | None = current_user.profile
        override = override_payload or {}
        provenance: dict[str, str] = {}

        # 1. Resolve room_type
        room_type = "living-room"
        if override.get("room_type"):
            room_type = str(override["room_type"]).strip()
            provenance["room_type"] = ProvenanceSource.EXPLICIT_OVERRIDE
        elif project.room_type:
            room_type = project.room_type.strip()
            provenance["room_type"] = ProvenanceSource.ROOM_PREFERENCE
        elif analysis and analysis.room_type:
            room_type = analysis.room_type.strip()
            provenance["room_type"] = ProvenanceSource.ROOM_ANALYSIS
        else:
            provenance["room_type"] = ProvenanceSource.SYSTEM_DEFAULT

        # 2. Resolve Styles
        style_ids: set[int] = set()
        styles: list[str] = []
        if "styles" in override:
            style_ids, styles = self._match_style_names_or_ids(override["styles"])
            provenance["styles"] = ProvenanceSource.EXPLICIT_OVERRIDE
        elif room_preference and room_preference.styles:
            style_ids = {s.id for s in room_preference.styles}
            styles = [s.name for s in room_preference.styles]
            provenance["styles"] = ProvenanceSource.ROOM_PREFERENCE
        elif user_profile and user_profile.preferred_style:
            style_ids, styles = self._parse_text_styles(user_profile.preferred_style)
            provenance["styles"] = ProvenanceSource.INHERITED_PROFILE if style_ids else ProvenanceSource.SYSTEM_DEFAULT
        else:
            provenance["styles"] = ProvenanceSource.SYSTEM_DEFAULT

        # 3. Resolve Colors
        color_ids: set[int] = set()
        colors: list[str] = []
        if "colors" in override:
            color_ids, colors = self._match_color_names_or_ids(override["colors"])
            provenance["colors"] = ProvenanceSource.EXPLICIT_OVERRIDE
        elif room_preference and room_preference.colors:
            color_ids = {c.id for c in room_preference.colors}
            colors = [c.name for c in room_preference.colors]
            provenance["colors"] = ProvenanceSource.ROOM_PREFERENCE
        elif user_profile and user_profile.preferred_colors:
            color_ids, colors = self._parse_text_colors(user_profile.preferred_colors)
            provenance["colors"] = ProvenanceSource.INHERITED_PROFILE if color_ids else ProvenanceSource.SYSTEM_DEFAULT
        elif analysis and analysis.dominant_colors and isinstance(analysis.dominant_colors, list):
            color_ids, colors = self._extract_analysis_colors(analysis.dominant_colors)
            provenance["colors"] = ProvenanceSource.ROOM_ANALYSIS if color_ids else ProvenanceSource.SYSTEM_DEFAULT
        else:
            provenance["colors"] = ProvenanceSource.SYSTEM_DEFAULT

        # 4. Resolve Materials
        material_ids: set[int] = set()
        materials: list[str] = []
        if "materials" in override:
            material_ids, materials = self._match_material_names_or_ids(override["materials"])
            provenance["materials"] = ProvenanceSource.EXPLICIT_OVERRIDE
        elif room_preference and room_preference.materials:
            material_ids = {m.id for m in room_preference.materials}
            materials = [m.name for m in room_preference.materials]
            provenance["materials"] = ProvenanceSource.ROOM_PREFERENCE
        elif user_profile and user_profile.preferred_materials:
            material_ids, materials = self._parse_text_materials(user_profile.preferred_materials)
            provenance["materials"] = ProvenanceSource.INHERITED_PROFILE if material_ids else ProvenanceSource.SYSTEM_DEFAULT
        else:
            provenance["materials"] = ProvenanceSource.SYSTEM_DEFAULT

        # 5. Resolve Categories
        category_ids: set[int] = set()
        categories: list[str] = []
        if "categories" in override:
            category_ids, categories = self._match_category_names_or_ids(override["categories"])
            provenance["categories"] = ProvenanceSource.EXPLICIT_OVERRIDE
        elif room_preference and room_preference.categories:
            category_ids = {c.id for c in room_preference.categories}
            categories = [c.name for c in room_preference.categories]
            provenance["categories"] = ProvenanceSource.ROOM_PREFERENCE
        else:
            # If no categories specified, include all active categories
            category_ids = {c.id for c in self._categories_by_slug.values()}
            categories = [c.name for c in self._categories_by_slug.values()]
            provenance["categories"] = ProvenanceSource.SYSTEM_DEFAULT

        # 6. Resolve Budget
        budget_min: Decimal | None = None
        budget_max: Decimal | None = None
        currency = "VND"
        if "budget_max" in override or "budget_min" in override:
            budget_max = Decimal(str(override["budget_max"])) if override.get("budget_max") is not None else None
            budget_min = Decimal(str(override["budget_min"])) if override.get("budget_min") is not None else None
            currency = override.get("currency", "VND")
            provenance["budget"] = ProvenanceSource.EXPLICIT_OVERRIDE
        elif room_preference and (room_preference.budget_max is not None or room_preference.budget_min is not None):
            budget_max = room_preference.budget_max
            budget_min = room_preference.budget_min
            currency = room_preference.currency or "VND"
            provenance["budget"] = ProvenanceSource.ROOM_PREFERENCE
        else:
            provenance["budget"] = ProvenanceSource.SYSTEM_DEFAULT

        # 7. Resolve Purpose
        purpose: str | None = None
        if "purpose" in override:
            purpose = str(override["purpose"]).strip() if override["purpose"] else None
            provenance["purpose"] = ProvenanceSource.EXPLICIT_OVERRIDE
        elif room_preference and room_preference.purpose:
            purpose = room_preference.purpose.strip()
            provenance["purpose"] = ProvenanceSource.ROOM_PREFERENCE
        else:
            provenance["purpose"] = ProvenanceSource.SYSTEM_DEFAULT

        # 8. Resolve Notes
        notes: str | None = None
        if "notes" in override:
            notes = str(override["notes"]).strip() if override["notes"] else None
            provenance["notes"] = ProvenanceSource.EXPLICIT_OVERRIDE
        elif room_preference and room_preference.notes:
            notes = room_preference.notes.strip()
            provenance["notes"] = ProvenanceSource.ROOM_PREFERENCE
        else:
            provenance["notes"] = ProvenanceSource.SYSTEM_DEFAULT

        return EffectivePreference(
            styles=styles,
            style_ids=style_ids,
            colors=colors,
            color_ids=color_ids,
            materials=materials,
            material_ids=material_ids,
            categories=categories,
            category_ids=category_ids,
            budget_min=budget_min,
            budget_max=budget_max,
            currency=currency,
            purpose=purpose,
            notes=notes,
            room_type=room_type,
            provenance=provenance,
        )

    # ---------------------------------------------------------
    # Parsing & Matching Helpers
    # ---------------------------------------------------------
    def _parse_text_styles(self, text: str) -> tuple[set[int], list[str]]:
        if not text:
            return set(), []
        lower = text.lower()
        matched_ids: set[int] = set()
        matched_names: list[str] = []
        for slug, syns in STYLE_TEXT_SYNONYMS.items():
            if any(syn in lower for syn in syns):
                style_obj = self._styles_by_slug.get(slug)
                if style_obj and style_obj.id not in matched_ids:
                    matched_ids.add(style_obj.id)
                    matched_names.append(style_obj.name)
        return matched_ids, matched_names

    def _parse_text_colors(self, text: str) -> tuple[set[int], list[str]]:
        if not text:
            return set(), []
        lower = text.lower()
        matched_ids: set[int] = set()
        matched_names: list[str] = []
        for slug, syns in COLOR_TEXT_SYNONYMS.items():
            if any(syn in lower for syn in syns):
                color_obj = self._colors_by_slug.get(slug)
                if color_obj and color_obj.id not in matched_ids:
                    matched_ids.add(color_obj.id)
                    matched_names.append(color_obj.name)
        return matched_ids, matched_names

    def _parse_text_materials(self, text: str) -> tuple[set[int], list[str]]:
        if not text:
            return set(), []
        lower = text.lower()
        matched_ids: set[int] = set()
        matched_names: list[str] = []
        for slug, syns in MATERIAL_TEXT_SYNONYMS.items():
            if any(syn in lower for syn in syns):
                mat_obj = self._materials_by_slug.get(slug)
                if mat_obj and mat_obj.id not in matched_ids:
                    matched_ids.add(mat_obj.id)
                    matched_names.append(mat_obj.name)
        return matched_ids, matched_names

    def _extract_analysis_colors(self, dominant_colors: list[Any]) -> tuple[set[int], list[str]]:
        matched_ids: set[int] = set()
        matched_names: list[str] = []
        for item in dominant_colors:
            if isinstance(item, dict):
                raw_name = str(item.get("name", "")).strip().lower()
            elif isinstance(item, str):
                raw_name = item.strip().lower()
            else:
                raw_name = ""
            if not raw_name:
                continue
            for slug, syns in COLOR_TEXT_SYNONYMS.items():
                if any(syn in raw_name for syn in syns):
                    color_obj = self._colors_by_slug.get(slug)
                    if color_obj and color_obj.id not in matched_ids:
                        matched_ids.add(color_obj.id)
                        matched_names.append(color_obj.name)
        return matched_ids, matched_names

    def _match_style_names_or_ids(self, items: list[Any]) -> tuple[set[int], list[str]]:
        ids: set[int] = set()
        names: list[str] = []
        for item in items:
            if isinstance(item, int):
                style_obj = next((s for s in self._styles_by_slug.values() if s.id == item), None)
                if style_obj:
                    ids.add(style_obj.id)
                    names.append(style_obj.name)
            elif isinstance(item, str):
                parsed_ids, parsed_names = self._parse_text_styles(item)
                ids.update(parsed_ids)
                names.extend(parsed_names)
        return ids, sorted(list(set(names)))

    def _match_color_names_or_ids(self, items: list[Any]) -> tuple[set[int], list[str]]:
        ids: set[int] = set()
        names: list[str] = []
        for item in items:
            if isinstance(item, int):
                color_obj = next((c for c in self._colors_by_slug.values() if c.id == item), None)
                if color_obj:
                    ids.add(color_obj.id)
                    names.append(color_obj.name)
            elif isinstance(item, str):
                parsed_ids, parsed_names = self._parse_text_colors(item)
                ids.update(parsed_ids)
                names.extend(parsed_names)
        return ids, sorted(list(set(names)))

    def _match_material_names_or_ids(self, items: list[Any]) -> tuple[set[int], list[str]]:
        ids: set[int] = set()
        names: list[str] = []
        for item in items:
            if isinstance(item, int):
                mat_obj = next((m for m in self._materials_by_slug.values() if m.id == item), None)
                if mat_obj:
                    ids.add(mat_obj.id)
                    names.append(mat_obj.name)
            elif isinstance(item, str):
                parsed_ids, parsed_names = self._parse_text_materials(item)
                ids.update(parsed_ids)
                names.extend(parsed_names)
        return ids, sorted(list(set(names)))

    def _match_category_names_or_ids(self, items: list[Any]) -> tuple[set[int], list[str]]:
        ids: set[int] = set()
        names: list[str] = []
        for item in items:
            if isinstance(item, int):
                cat_obj = next((c for c in self._categories_by_slug.values() if c.id == item), None)
                if cat_obj:
                    ids.add(cat_obj.id)
                    names.append(cat_obj.name)
            elif isinstance(item, str):
                raw = item.strip().lower()
                cat_obj = self._categories_by_slug.get(raw)
                if cat_obj:
                    ids.add(cat_obj.id)
                    names.append(cat_obj.name)
        return ids, sorted(list(set(names)))
