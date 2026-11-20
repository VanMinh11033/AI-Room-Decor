"""IMPLEMENTED: bounded decoder; host resolves authorized opaque asset IDs."""
import io
import hashlib
from PIL import Image, ImageOps
import numpy as np

def decode(raw: bytes, max_pixels: int = 4_000_000) -> np.ndarray:
    if not isinstance(raw, bytes) or len(raw) > 12_000_000 or len(raw) == 0:
        raise ValueError('IMAGE_BYTES')
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format not in ('PNG', 'JPEG', 'WEBP') or im.width * im.height > max_pixels or getattr(im, 'n_frames', 1) != 1:
                raise ValueError('IMAGE_FORMAT_OR_SIZE')
            im.load()
            return np.array(ImageOps.exif_transpose(im).convert('RGBA'))
    except (Image.UnidentifiedImageError, OSError) as e:
        raise ValueError('IMAGE_FORMAT_OR_SIZE') from e

def png(a: np.ndarray) -> bytes:
    b = io.BytesIO()
    Image.fromarray(a).save(b, format='PNG')
    return b.getvalue()

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
