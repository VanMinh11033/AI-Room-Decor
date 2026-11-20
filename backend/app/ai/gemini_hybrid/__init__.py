"""Gemini Hybrid Integration package for AI Room Decor.

Provides:
- GeminiRoomAnalyzer: Multimodal room architecture & lighting analysis.
- GeminiLayoutPlanner: Constrained spatial & z-order layout planning for selected catalog products.
- GeminiImageRenderer: Photorealistic image rendering with strict catalog guards.
- CatalogIdentityValidator: Objective verification of catalog product preservation and architecture stability.
- CompositeFallbackManager: Automatic fallback to local deterministic compositor on API error or drift.
"""

from app.ai.gemini_hybrid.catalog_validator import CatalogIdentityValidator, VerificationResult
from app.ai.gemini_hybrid.fallback_manager import CompositeFallbackManager
from app.ai.gemini_hybrid.image_renderer import GeminiImageRenderer
from app.ai.gemini_hybrid.layout_planner import GeminiLayoutPlanner, PlannedPlacement
from app.ai.gemini_hybrid.room_analyzer import GeminiRoomAnalyzer
from app.ai.gemini_hybrid.schemas import (
    DecorSpot,
    GeminiLayoutPlan,
    GeminiRoomAnalysisSchema,
    LightingAnalysisSchema,
)

__all__ = [
    "CatalogIdentityValidator",
    "CompositeFallbackManager",
    "DecorSpot",
    "GeminiImageRenderer",
    "GeminiLayoutPlan",
    "GeminiLayoutPlanner",
    "GeminiRoomAnalysisSchema",
    "GeminiRoomAnalyzer",
    "LightingAnalysisSchema",
    "PlannedPlacement",
    "VerificationResult",
]
