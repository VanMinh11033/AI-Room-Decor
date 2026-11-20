"""AI Room Decor Skill Bridge V2.0 PRO Namespaced Engineering Preview Package.

Provides:
- Architecture Pixel Protection (restore, compare)
- Product Intelligence & Fingerprinting (extract)
- Spatial Planner with Perspective & Relative Sizing (plan)
- Offline 2D Exact-Source Composite (render)
- Offline Hybrid Candidate Refinement (refine_offline_candidate)
- Independent Pixel Validation & Auditing (inspect)
- Fail-Closed Provider Router & Budget Reservation (Budget, choose)
- Engine Orchestration & Compatibility Layer (Engine, SkillBridgeV2)
"""

from app.ai.skill_bridge.v2.architecture.protection import compare, restore
from app.ai.skill_bridge.v2.catalog.products import extract
from app.ai.skill_bridge.v2.computer_vision.room import analyze, floor_homography, polygon_mask
from app.ai.skill_bridge.v2.core.engine import Engine
from app.ai.skill_bridge.v2.layout.planner import plan
from app.ai.skill_bridge.v2.optimization.control import Budget, Cache
from app.ai.skill_bridge.v2.providers.http import HTTPAdapter
from app.ai.skill_bridge.v2.providers.router import Capability, choose
from app.ai.skill_bridge.v2.rendering.composite import render
from app.ai.skill_bridge.v2.rendering.hybrid import edit_background, refine_offline_candidate
from app.ai.skill_bridge.v2.security.images import decode, png, sha
from app.ai.skill_bridge.v2.validation.inspect import inspect
from app.ai.skill_bridge.v2.api.compat import SkillBridgeV2

__all__ = [
    "Engine",
    "SkillBridgeV2",
    "compare",
    "restore",
    "extract",
    "analyze",
    "polygon_mask",
    "floor_homography",
    "plan",
    "render",
    "edit_background",
    "refine_offline_candidate",
    "inspect",
    "Budget",
    "Cache",
    "Capability",
    "choose",
    "HTTPAdapter",
    "decode",
    "png",
    "sha",
]
