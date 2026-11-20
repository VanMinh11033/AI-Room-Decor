"""IMPLEMENTED: exact pixel restoration outside explicit edit mask; semantic completeness not implied."""
import numpy as np

def restore(original: np.ndarray, candidate: np.ndarray, editable: np.ndarray) -> np.ndarray:
    if original.shape != candidate.shape or editable.shape != original.shape[:2] or editable.dtype != bool:
        raise ValueError('GEOMETRY_MISMATCH')
    out = original.copy()
    out[editable] = candidate[editable]
    return out

def compare(original: np.ndarray, candidate: np.ndarray, protected: np.ndarray) -> dict:
    if original.shape != candidate.shape or protected.shape != original.shape[:2] or not protected.any():
        return {'status': 'unknown', 'evidence': 'Missing comparable protected pixels', 'confidence': None}
    changed = int(np.any(original != candidate, axis=2)[protected].sum())
    n = int(protected.sum())
    return {
        'status': 'fail' if changed else 'pass',
        'evidence': f'{changed}/{n} protected pixels changed',
        'confidence': 1.0,
        'changed': changed,
        'count': n
    }
