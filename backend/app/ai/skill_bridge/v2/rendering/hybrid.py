"""PARTIAL: AI editing is opt-in; only allowed background region applied, source pixels restored."""
import cv2
import numpy as np
from app.ai.skill_bridge.v2.architecture.protection import restore
from app.ai.skill_bridge.v2.security.images import decode, png

def edit_background(
    original: np.ndarray,
    composite: np.ndarray,
    editable: np.ndarray,
    locks: dict,
    adapter,
    prompt: str,
    refs: list,
    **authorization
) -> np.ndarray:
    raw = adapter.edit(prompt, [png(composite), *refs], **authorization)
    candidate = decode(raw)[:, :, :3]
    if candidate.shape != original.shape:
        raise ValueError('CAMERA_OR_CANVAS_MISMATCH')
    allowed = editable.copy()
    for box, opaque, expected in locks.values():
        x, y, w, h = box
        allowed[y:y + h, x:x + w] = False
    result = restore(composite, candidate, allowed)
    return restore(original, result, editable)

def refine_offline_candidate(
    original: np.ndarray,
    composite: np.ndarray,
    editable: np.ndarray,
    locks: dict,
    candidate: np.ndarray,
    preserve_product_core: bool = True,
    feather_radius: int = 5
) -> np.ndarray:
    """Offline hybrid refinement reusing an existing AI candidate image (e.g. Gen #130).
    
    1. Ensures dimensions match exactly on common canvas.
    2. Allows AI atmospheric rendering only in the authorized editable zone.
    3. If preserve_product_core is True, locks the exact catalog cutout pixels in product centers.
    4. 100% strictly restores original room pixels outside the editable zone.
    """
    if candidate.shape != original.shape or composite.shape != original.shape:
        raise ValueError('CAMERA_OR_CANVAS_MISMATCH')
        
    allowed = editable.copy()
    if preserve_product_core:
        for box, opaque, expected in locks.values():
            x, y, w, h = box
            # Lock the core opaque region of the catalog product
            allowed[y:y + h, x:x + w][opaque] = False
            
    # Apply candidate in allowed region
    result = restore(composite, candidate, allowed)
    # Strictly restore original room outside editable
    return restore(original, result, editable)
