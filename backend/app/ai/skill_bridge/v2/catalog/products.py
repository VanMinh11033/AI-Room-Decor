"""PARTIAL: alpha / border-connected background extraction, measured fingerprint; material and SKU semantics unknown."""
import cv2
import numpy as np
from app.ai.skill_bridge.v2.security.images import sha, png

def extract(a: np.ndarray) -> tuple[np.ndarray, dict]:
    rgb = a[:, :, :3]
    alpha = a[:, :, 3].copy()
    method = 'source_alpha'
    
    if np.all(alpha == 255):
        method = 'border_background'
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(float)
        border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
        bg = np.median(border, axis=0)
        if np.percentile(np.linalg.norm(border - bg, axis=1), 90) > 12:
            raise ValueError('LIFESTYLE_MASK_REQUIRED')
        near = (np.linalg.norm(lab - bg, axis=2) < 10).astype(np.uint8)
        n, labels = cv2.connectedComponents(near, connectivity=8)
        ids = set(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])) - {0}
        alpha[np.isin(labels, list(ids))] = 0
    
    # Suppress detached background specks only for inferred masks; retain source alpha.
    if method == 'border_background':
        n, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 127).astype(np.uint8), 8)
        if n > 1:
            main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            alpha[labels != main] = 0
            
    ys, xs = np.where(alpha > 127)
    if len(xs) < 25 or len(xs) > alpha.size * 0.97:
        raise ValueError('MASK_UNRELIABLE')
        
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    out = np.dstack([rgb, alpha])[y0:y1, x0:x1].copy()
    mask = out[:, :, 3] > 127
    pix = out[:, :, :3][mask]
    hist = np.histogramdd(pix, bins=(4, 4, 4), range=((0, 256),) * 3)[0]
    hist /= hist.sum()
    
    fingerprint = {
        'sha256': sha(png(out)),
        'method': method,
        'aspect': float(out.shape[1] / out.shape[0]),
        'fill': float(mask.mean()),
        'dimensions': [int(out.shape[1]), int(out.shape[0])],
        'median_rgb': [float(x) for x in np.median(pix, axis=0)],
        'histogram': hist.ravel().tolist(),
        'material': 'unknown',
        'sku_identity': 'source_reference_only'
    }
    return out, fingerprint
