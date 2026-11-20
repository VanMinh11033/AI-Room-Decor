"""PARTIAL: real source-pixel composite, alpha edges, contact shadow; no novel view synthesis."""
import cv2
import numpy as np
from app.ai.skill_bridge.v2.architecture.protection import restore

def render(room: np.ndarray, products: list, plans: list, info: dict) -> tuple[np.ndarray, np.ndarray, dict]:
    original = room[:, :, :3]
    out = original.copy()
    h, w = out.shape[:2]
    editable = np.zeros((h, w), bool)
    locks = {}
    
    for (pid, rgba), p in zip(products, plans, strict=True):
        if pid != p['product_id']:
            raise ValueError('SKU_PLAN_MISMATCH')
            
        x, y, bw, bh = p['box']
        a = cv2.resize(
            rgba,
            (bw, bh),
            interpolation=cv2.INTER_AREA if bw < rgba.shape[1] else cv2.INTER_LINEAR
        )
        alpha = a[:, :, 3].astype(np.float32) / 255.0
        mask = alpha > 0
        
        if (mask & info['forbidden'][y:y + bh, x:x + bw]).any():
            raise ValueError('PROTECTED_OVERLAP')
            
        # Realistic contact shadow on floor plane
        shadow = np.zeros((h, w), np.uint8)
        shadow_rx = max(1, bw // 3)
        shadow_ry = max(1, bh // 16)
        cv2.ellipse(
            shadow,
            (x + bw // 2, min(h - 1, y + bh - 1)),
            (shadow_rx, shadow_ry),
            0, 0, 360, 80, -1
        )
        shadow = cv2.GaussianBlur(shadow, (0, 0), max(1.0, bw / 30.0))
        shadow[~info['placement']] = 0
        
        # Apply shadow darkening to editable region
        out = np.rint(out * (1.0 - shadow[:, :, None] / 255.0)).astype(np.uint8)
        editable |= (shadow > 0)
        
        # Alpha blend product onto out
        region = out[y:y + bh, x:x + bw]
        region[:] = np.rint(
            region * (1.0 - alpha[:, :, None]) + a[:, :, :3] * alpha[:, :, None]
        ).astype(np.uint8)
        editable[y:y + bh, x:x + bw] |= mask
        
        # Lock exact opaque pixels of product
        opaque = alpha >= 0.98
        locks[pid] = (p['box'], opaque, a[:, :, :3].copy())
        
    # Ensure later shadows or operations cannot silently modify opaque source pixels
    for box, opaque, expected in locks.values():
        x, y, bw, bh = box
        out[y:y + bh, x:x + bw][opaque] = expected[opaque]
        
    return restore(original, out, editable), editable, locks
