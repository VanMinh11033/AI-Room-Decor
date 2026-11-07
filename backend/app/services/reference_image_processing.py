from collections import deque
from pathlib import Path

from PIL import Image

BORDER_UNIFORMITY_THRESHOLD = 0.90
CORNER_SIMILARITY_THRESHOLD = 0.85
BACKGROUND_REMOVAL_TOLERANCE = 40
MAX_REFERENCE_SIDE = 1024
TRIM_PADDING = 8

_EXTENSION_TO_FORMAT = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".avif": "AVIF",
    ".gif": "GIF",
}

_MAX_RGB_DISTANCE = (3 * 255 * 255) ** 0.5


def _color_distance(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _uniformity_score(mean_distance: float) -> float:
    if _MAX_RGB_DISTANCE == 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - mean_distance / _MAX_RGB_DISTANCE))


def _border_pixels(rgb: Image.Image, step: int | None = None) -> list[tuple[int, int, int]]:
    width, height = rgb.size
    if step is None:
        step = max(1, min(width, height) // 200)
    px = rgb.load()
    samples: list[tuple[int, int, int]] = []
    for x in range(0, width, step):
        samples.append(px[x, 0][:3])
        samples.append(px[x, height - 1][:3])
    for y in range(0, height, step):
        samples.append(px[0, y][:3])
        samples.append(px[width - 1, y][:3])
    return samples


def _border_uniformity(rgb: Image.Image) -> float:
    samples = _border_pixels(rgb)
    if not samples:
        return 1.0
    n = len(samples)
    mean = tuple(sum(c[i] for c in samples) / n for i in range(3))
    total = sum(_color_distance(c, mean) for c in samples) / n
    return _uniformity_score(total)


def _corner_similarity(rgb: Image.Image) -> float:
    width, height = rgb.size
    patch = max(1, min(8, width // 4, height // 4))
    px = rgb.load()
    corners: list[tuple[float, float, float]] = []
    for x0, y0 in ((0, 0), (width - patch, 0), (0, height - patch), (width - patch, height - patch)):
        acc = [0, 0, 0]
        count = 0
        for y in range(y0, y0 + patch):
            for x in range(x0, x0 + patch):
                c = px[x, y][:3]
                acc[0] += c[0]
                acc[1] += c[1]
                acc[2] += c[2]
                count += 1
        corners.append((acc[0] / count, acc[1] / count, acc[2] / count))
    max_distance = 0.0
    for i in range(len(corners)):
        for j in range(i + 1, len(corners)):
            max_distance = max(max_distance, _color_distance(corners[i], corners[j]))
    return _uniformity_score(max_distance)


def analyze_reference_image(
    path: Path,
    border_threshold: float = BORDER_UNIFORMITY_THRESHOLD,
    corner_threshold: float = CORNER_SIMILARITY_THRESHOLD,
) -> dict:
    result = {
        "decodable": False,
        "detected_format": None,
        "extension_matches_format": None,
        "width": None,
        "height": None,
        "has_alpha": False,
        "has_transparency": False,
        "border_uniformity": None,
        "corner_similarity": None,
        "background_removal_candidate": False,
        "reason": "",
    }

    if not path.exists():
        result["reason"] = "missing file"
        return result

    try:
        with Image.open(path) as im:
            im.load()
            result["decodable"] = True
            result["detected_format"] = im.format
            result["width"], result["height"] = im.size
            result["extension_matches_format"] = _EXTENSION_TO_FORMAT.get(path.suffix.lower()) == im.format
            bands = im.getbands()
            result["has_alpha"] = "A" in bands
            if "A" in bands:
                result["has_transparency"] = im.getchannel("A").getextrema()[0] < 255
            rgba = im.convert("RGBA")
    except Exception as exc:
        result["reason"] = f"unreadable: {str(exc)[:120]}"
        return result

    if result["has_transparency"]:
        result["background_removal_candidate"] = True
        result["reason"] = "already transparent"
        return result

    rgb = rgba.convert("RGB")
    border_uniformity = _border_uniformity(rgb)
    corner_similarity = _corner_similarity(rgb)
    result["border_uniformity"] = round(border_uniformity, 4)
    result["corner_similarity"] = round(corner_similarity, 4)
    if border_uniformity >= border_threshold and corner_similarity >= corner_threshold:
        result["background_removal_candidate"] = True
        result["reason"] = "uniform background"
    else:
        result["background_removal_candidate"] = False
        result["reason"] = "non-uniform background"
    return result


def estimate_background_color(rgba: Image.Image) -> tuple[int, int, int]:
    samples = _border_pixels(rgba.convert("RGB"))
    if not samples:
        return (255, 255, 255)
    n = len(samples)
    return tuple(round(sum(c[i] for c in samples) / n) for i in range(3))


def remove_uniform_background(
    rgba: Image.Image,
    background_color: tuple[int, int, int],
    tolerance: float = BACKGROUND_REMOVAL_TOLERANCE,
) -> Image.Image:
    width, height = rgba.size
    px = rgba.load()
    visited = bytearray(width * height)
    queue = deque()

    def try_add(x: int, y: int) -> None:
        idx = y * width + x
        if visited[idx]:
            return
        r, g, b, _a = px[x, y]
        if _color_distance((r, g, b), background_color) <= tolerance:
            visited[idx] = 1
            px[x, y] = (r, g, b, 0)
            queue.append((x, y))

    for x in range(width):
        try_add(x, 0)
        try_add(x, height - 1)
    for y in range(height):
        try_add(0, y)
        try_add(width - 1, y)

    while queue:
        x, y = queue.popleft()
        if x > 0:
            try_add(x - 1, y)
        if x < width - 1:
            try_add(x + 1, y)
        if y > 0:
            try_add(x, y - 1)
        if y < height - 1:
            try_add(x, y + 1)

    return rgba


def trim_transparent(rgba: Image.Image, padding: int = TRIM_PADDING) -> Image.Image | None:
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(rgba.width, right + padding)
    bottom = min(rgba.height, bottom + padding)
    return rgba.crop((left, top, right, bottom))


def cap_dimensions(image: Image.Image, max_side: int = MAX_REFERENCE_SIDE) -> Image.Image:
    width, height = image.size
    if max(width, height) <= max_side:
        return image
    scale = max_side / max(width, height)
    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
