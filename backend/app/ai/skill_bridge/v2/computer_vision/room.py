"""PARTIAL: verified-mask geometry, line cues; optional learned segmentation/depth in models.py."""
import cv2
import numpy as np

def polygon_mask(shape: tuple, points: list) -> np.ndarray:
    if len(points) < 3:
        raise ValueError('POLYGON')
    a = np.zeros(shape[:2], np.uint8)
    p = np.asarray(points, float)
    if (
        p.ndim != 2
        or p.shape[1] != 2
        or not np.isfinite(p).all()
        or (p < 0).any()
        or (p[:, 0] >= shape[1]).any()
        or (p[:, 1] >= shape[0]).any()
    ):
        raise ValueError('POLYGON_BOUNDS')
    cv2.fillPoly(a, [np.rint(p).astype(np.int32)], 1)
    return a.astype(bool)

def analyze(room: np.ndarray, zones: dict) -> dict:
    h, w = room.shape[:2]
    masks = {k: np.zeros((h, w), bool) for k in ('floor', 'wall', 'ceiling', 'door', 'window', 'existing', 'walkway')}
    for k, polys in zones.items():
        if k not in masks:
            raise ValueError('ZONE_NAME')
        for p in polys:
            masks[k] |= polygon_mask(room.shape, p)
            
    forbidden = masks['door'] | masks['window'] | masks['existing'] | masks['walkway'] | masks['ceiling']
    edges = cv2.Canny(cv2.cvtColor(room[:, :, :3], cv2.COLOR_RGB2GRAY), 60, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 50, minLineLength=max(20, w // 8), maxLineGap=12)
    return {
        'masks': masks,
        'forbidden': forbidden,
        'placement': masks['floor'] & ~forbidden,
        'line_count': 0 if lines is None else len(lines),
        'scale': 'estimated',
        'confidence': None
    }

def floor_homography(corners: list) -> np.ndarray:
    p = np.asarray(corners, np.float32)
    if p.shape != (4, 2) or not cv2.isContourConvex(p) or abs(cv2.contourArea(p)) < 10:
        raise ValueError('FLOOR_QUAD')
    return cv2.getPerspectiveTransform(np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32), p)
