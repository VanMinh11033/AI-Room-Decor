from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ImageProviderError(Exception):
    def __init__(self, code: str, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.transient = transient


class ImageProviderNotConfiguredError(ImageProviderError):
    def __init__(self) -> None:
        super().__init__("IMAGE_PROVIDER_NOT_CONFIGURED", "Image generation provider is not configured")


@dataclass
class ImageGenerationUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0


@dataclass
class GeneratedImage:
    data: bytes
    content_type: str = "image/png"
    usage: ImageGenerationUsage | None = None


class ImageProvider(Protocol):
    provider_name: str
    model_name: str

    def generate_design(
        self,
        source_image_path: Path,
        prompt: str,
        reference_image_paths: list[Path] | None = None,
    ) -> GeneratedImage:
        ...
