"""Pydantic schemas for AI Room Decor Skill Bridge V1.0.

Fully compatible with .agents/skills/ai-room-decor-skill input_schema.json
and output_schema.json, while integrating natively with FastAPI & SQLAlchemy.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


class ProductDimensionSchema(BaseModel):
    width_cm: float = Field(gt=0)
    depth_cm: float = Field(gt=0)
    height_cm: float = Field(gt=0)


class SelectedProductInput(BaseModel):
    product_id: str | int = Field(...)
    product_name: str = Field(min_length=1, max_length=2000)
    product_images: list[str] = Field(min_length=1, max_length=8)
    product_dimensions: ProductDimensionSchema | None = None


class RoomDimensionSchema(BaseModel):
    width_cm: float = Field(gt=0)
    depth_cm: float = Field(gt=0)
    height_cm: float = Field(gt=0)


class SkillInputRequest(BaseModel):
    room_image: str = Field(min_length=1, max_length=512)
    room_type: str = Field(min_length=1, max_length=2000)
    selected_products: list[SelectedProductInput] = Field(min_length=1, max_length=10)
    design_style: str = Field(default="modern", min_length=1, max_length=2000)
    user_requirements: str = Field(default="", max_length=4000)
    room_dimensions: RoomDimensionSchema | None = None


class ValidationCheck(BaseModel):
    status: Literal["pass", "fail", "unknown"]
    evidence: str = Field(min_length=1)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    score: float | None = Field(default=None, ge=0.0, le=100.0)


class ProductFidelityCheck(ValidationCheck):
    product_id: str | int


class ComponentScores(BaseModel):
    catalog: float | None = None       # 35%
    architecture: float | None = None  # 25%
    proportion: float | None = None    # 15%
    perspective: float | None = None   # 10%
    lighting: float | None = None      # 10%
    realism: float | None = None       # 5%


class QualityEvaluationResult(BaseModel):
    quality_score: float | None = None
    component_scores: ComponentScores = Field(default_factory=ComponentScores)
    generation_status: Literal["succeeded", "needs_review", "rejected", "failed"] = "needs_review"
    hard_gates_passed: bool = False
    failed_gates: list[str] = Field(default_factory=list)
    architecture: ValidationCheck
    access: ValidationCheck
    extras: ValidationCheck
    products: dict[str, ValidationCheck] = Field(default_factory=dict)
    referenced_product_ids: list[int] = Field(default_factory=list)
    verified_product_ids: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    neuron_estimate: int = 0


class SkillBridgeMetadata(BaseModel):
    version: str = "1.0.0"
    quality_score: float | None = None
    component_scores: dict[str, float | None] = Field(default_factory=dict)
    generation_status: str = "needs_review"
    gates: dict[str, Any] = Field(default_factory=dict)
    referenced_product_ids: list[int] = Field(default_factory=list)
    verified_product_ids: list[int] = Field(default_factory=list)
    hard_gates_passed: bool = False
    neuron_estimate: int = 0
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class SkillOutputResult(BaseModel):
    generated_design_image: str | None = None
    selected_product_ids: list[str] = Field(default_factory=list)
    layout_description: str = ""
    architecture_validation: ValidationCheck
    catalog_fidelity_validation: list[ProductFidelityCheck] = Field(default_factory=list)
    quality_score: float | None = None
    warnings: list[str] = Field(default_factory=list)
    generation_status: Literal["succeeded", "needs_review", "rejected", "failed"]
    provider: str
    model: str
    attempts: int = 1
    provenance: dict[str, Any] = Field(default_factory=dict)
