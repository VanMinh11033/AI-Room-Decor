from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.schemas.room_project import RoomAnalysisResult


class VisionProviderError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        transient: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.transient = transient
        self.status_code = status_code


class VisionProviderNotConfiguredError(VisionProviderError):
    def __init__(self) -> None:
        super().__init__("AI_PROVIDER_NOT_CONFIGURED", "Vision provider is not configured")


@dataclass
class VisionUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0


@dataclass
class VisionAnalysis:
    result: RoomAnalysisResult
    raw_response: dict[str, Any] | list[Any] | None = None
    usage: VisionUsage | None = None


class VisionProvider(Protocol):
    provider_name: str
    model_name: str

    def analyze_room(self, image_path: Path, content_type: str) -> VisionAnalysis:
        ...
