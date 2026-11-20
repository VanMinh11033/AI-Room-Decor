"""AI Room Decor Skill Bridge V1.0 Package.

Integrates .agents/skills/ai-room-decor-skill into the existing FastAPI backend:
- Structured Manifest 0..N
- Architectural Invariant Dynamic Prompting
- 6-component Quality Evaluator with Hard Gates
- Safe Versioned Prompt Metadata Serialization (Zero DB Migration)
- Cloudflare FLUX.2 Dev Neuron Estimation
"""

import json
import re
from typing import Any

from pydantic import BaseModel

from app.ai.skill_bridge.prompt_adapter import (
    CATALOG_TRAITS,
    build_skill_manifest,
    build_skill_prompt,
)
from app.ai.skill_bridge.quality_evaluator import (
    WEIGHTS,
    QualityEvaluator,
    estimate_cloudflare_neurons,
)
from app.ai.skill_bridge.schemas import (
    ComponentScores,
    QualityEvaluationResult,
    SkillBridgeMetadata,
    SkillInputRequest,
    SkillOutputResult,
    ValidationCheck,
)

METADATA_HEADER = "\n\n[SKILL_METADATA_V1]\n"
METADATA_HEADER_V2 = "\n\n[SKILL_METADATA_V2]\n"


def serialize_skill_metadata(raw_prompt: str, metadata: SkillBridgeMetadata | dict[str, Any], version: str = "1.0.0") -> str:
    """Safely append versioned JSON metadata to the stored prompt column.
    
    Ensures prompt length remains bounded and does not corrupt original prompt text.
    """
    header = METADATA_HEADER_V2 if str(version).startswith("2") else METADATA_HEADER
    clean_prompt = re.split(r"\n\n\[SKILL_METADATA_V\d+\]\n", raw_prompt)[0].strip()
    if isinstance(metadata, BaseModel):
        json_str = metadata.model_dump_json(exclude_none=True)
    elif isinstance(metadata, dict):
        json_str = json.dumps(metadata, ensure_ascii=False)
    else:
        json_str = json.dumps(dict(metadata), ensure_ascii=False)
    return f"{clean_prompt}{header}{json_str}"


def parse_skill_metadata(stored_prompt: str | None) -> tuple[str, SkillBridgeMetadata | None]:
    """Parse clean prompt text and structured SkillBridgeMetadata from stored prompt column.
    
    Fully backward-compatible with legacy generations lacking metadata.
    """
    if not stored_prompt:
        return "", None
    
    parts = re.split(r"\n\n\[SKILL_METADATA_V\d+\]\n", stored_prompt, maxsplit=1)
    clean_prompt = parts[0].strip()
    
    if len(parts) < 2:
        return clean_prompt, None
    
    try:
        data = json.loads(parts[1].strip())
        return clean_prompt, SkillBridgeMetadata.model_validate(data)
    except Exception:
        return clean_prompt, None


__all__ = [
    "CATALOG_TRAITS",
    "WEIGHTS",
    "QualityEvaluator",
    "SkillBridgeMetadata",
    "SkillInputRequest",
    "SkillOutputResult",
    "QualityEvaluationResult",
    "ValidationCheck",
    "ComponentScores",
    "build_skill_manifest",
    "build_skill_prompt",
    "estimate_cloudflare_neurons",
    "serialize_skill_metadata",
    "parse_skill_metadata",
]
