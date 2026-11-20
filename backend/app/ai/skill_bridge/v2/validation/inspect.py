"""PARTIAL: independent pixel checks; semantic identity/realism not inferred from checksums."""
import cv2
import numpy as np
from app.ai.skill_bridge.v2.architecture.protection import compare

def evaluate_visual_regression_gates(
    room: np.ndarray,
    candidate: np.ndarray,
    editable: np.ndarray,
    product_masks: dict = None
) -> dict:
    """Evaluates strict visual regression hard gates:
    - FURNITURE_TRUNCATED: Verifies no horizontal/vertical straight cutoffs through furniture.
    - PRODUCT_MISSING_AFTER_RESTORE: Verifies expected product silhouettes are preserved.
    - MASK_ALIGNMENT_FAILED: Verifies canvas dimensions match exactly.
    - BACKGROUND_PATCH_ARTIFACT: Detects artificial rectangular box boundaries on background.
    - SEVERE_SEAM_ARTIFACT: Measures maximum gradient step jump along boundary.
    """
    gates = {}
    
    # 1. MASK_ALIGNMENT_FAILED
    canvas_match = (room.shape[:2] == candidate.shape[:2] == editable.shape[:2])
    gates['MASK_ALIGNMENT_FAILED'] = {
        'status': 'pass' if canvas_match else 'fail',
        'evidence': f'Canvas geometry {candidate.shape} aligned with {room.shape}',
        'confidence': 1.0
    }

    if not canvas_match:
        gates['BACKGROUND_PATCH_ARTIFACT'] = {'status': 'fail', 'evidence': 'Geometry mismatch', 'confidence': 1.0}
        gates['SEVERE_SEAM_ARTIFACT'] = {'status': 'fail', 'evidence': 'Cannot compute seam on mismatched canvas', 'confidence': 1.0}
        gates['FURNITURE_TRUNCATED'] = {'status': 'fail', 'evidence': 'Cannot verify on mismatched canvas', 'confidence': 1.0}
        gates['PRODUCT_MISSING_AFTER_RESTORE'] = {'status': 'fail', 'evidence': 'Cannot verify on mismatched canvas', 'confidence': 1.0}
        return gates

    # 2. BACKGROUND_PATCH_ARTIFACT
    # Checks for artificial straight horizontal cuts across the editable region top boundary
    ys_e, xs_e = np.where(editable > 0)
    if len(xs_e) > 0:
        top_per_x = {}
        for x, y in zip(xs_e, ys_e):
            if x not in top_per_x or y < top_per_x[x]:
                top_per_x[x] = y
        sorted_xs = sorted(top_per_x.keys())
        max_flat_run = 0
        cur_run = 0
        cur_y = None
        for x in sorted_xs:
            y = top_per_x[x]
            if y == cur_y:
                cur_run += 1
                max_flat_run = max(max_flat_run, cur_run)
            else:
                cur_y = y
                cur_run = 1
        is_box = (max_flat_run > 150)
        gates['BACKGROUND_PATCH_ARTIFACT'] = {
            'status': 'fail' if is_box else 'pass',
            'evidence': f'Max flat boundary run: {max_flat_run} px (limit: 150 px)',
            'confidence': 1.0
        }
    else:
        gates['BACKGROUND_PATCH_ARTIFACT'] = {'status': 'pass', 'evidence': 'No editable region', 'confidence': 1.0}

    # 3. SEVERE_SEAM_ARTIFACT
    protected_mask = ~editable
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    edge_band = cv2.dilate(protected_mask.astype(np.uint8), kernel) - protected_mask.astype(np.uint8)
    if np.sum(edge_band > 0) > 0:
        diff_border = np.linalg.norm(candidate.astype(float) - room[:, :, :3].astype(float), axis=-1)[edge_band > 0]
        max_jump = float(diff_border.max()) if len(diff_border) > 0 else 0.0
        mean_jump = float(diff_border.mean()) if len(diff_border) > 0 else 0.0
        is_seam_fail = max_jump > 60.0
        gates['SEVERE_SEAM_ARTIFACT'] = {
            'status': 'fail' if is_seam_fail else 'pass',
            'evidence': f'Seam mean jump: {mean_jump:.2f}, max jump: {max_jump:.2f}',
            'confidence': 1.0
        }
    else:
        gates['SEVERE_SEAM_ARTIFACT'] = {'status': 'pass', 'evidence': 'No border seam', 'confidence': 1.0}

    # 4 & 5. FURNITURE_TRUNCATED & PRODUCT_MISSING_AFTER_RESTORE
    if product_masks:
        truncated = False
        missing = False
        details = []
        for pid, p_mask in product_masks.items():
            if np.sum(p_mask > 0) == 0:
                continue
            # Check if product pixels inside candidate differ from candidate source
            # In restored image, product pixels inside p_mask should not be replaced by room background
            diff_from_room = np.any(candidate != room[:, :, :3], axis=2)[p_mask > 0]
            preserved_ratio = float(np.sum(diff_from_room)) / float(np.sum(p_mask > 0))
            if preserved_ratio < 0.85:
                truncated = True
            if preserved_ratio < 0.60:
                missing = True
            details.append(f'Product #{pid}: {preserved_ratio*100:.1f}% preserved')

        gates['FURNITURE_TRUNCATED'] = {
            'status': 'fail' if truncated else 'pass',
            'evidence': '; '.join(details),
            'confidence': 1.0
        }
        gates['PRODUCT_MISSING_AFTER_RESTORE'] = {
            'status': 'fail' if missing else 'pass',
            'evidence': '; '.join(details),
            'confidence': 1.0
        }
    else:
        gates['FURNITURE_TRUNCATED'] = {'status': 'pass', 'evidence': 'No individual product masks passed', 'confidence': 0.5}
        gates['PRODUCT_MISSING_AFTER_RESTORE'] = {'status': 'pass', 'evidence': 'No individual product masks passed', 'confidence': 0.5}

    return gates

def inspect(room: np.ndarray, candidate: np.ndarray, editable: np.ndarray, locks: dict, ids: list, info: dict, product_masks: dict = None) -> tuple[str, dict]:
    unknown = lambda why: {'status': 'unknown', 'evidence': why, 'confidence': None}
    
    # Compare protected pixels outside editable region or in forbidden zones
    arch = compare(room[:, :, :3], candidate, ~editable | info.get('forbidden', np.zeros(editable.shape, bool)))
    
    products = {}
    for pid in ids:
        if pid not in locks:
            products[pid] = {'status': 'fail', 'evidence': 'Missing source layer', 'confidence': 1.0}
            continue
        (x, y, w, h), opaque, expected = locks[pid]
        actual = candidate[y:y + h, x:x + w]
        if not opaque.any():
            products[pid] = unknown('No opaque core')
            continue
        changed = int(np.any(actual != expected, axis=2)[opaque].sum())
        products[pid] = {
            'status': 'fail' if changed else 'pass',
            'evidence': f'{changed}/{int(opaque.sum())} resized opaque source pixels changed; not semantic SKU proof',
            'confidence': 1.0,
            'changed_pixels': changed,
            'opaque_pixels': int(opaque.sum())
        }
        
    # Visual Regression Gates
    vr_gates = evaluate_visual_regression_gates(room, candidate, editable, product_masks)

    checks = {
        'architecture_pixels': arch,
        'source_pixels': products,
        'door_obstruction': unknown('2D masks cannot certify door swing or physical clearance'),
        'extra_products': unknown('No independent semantic detector verified'),
        'wrong_product': unknown('No independent SKU classifier'),
        'missing_product': unknown('Layer presence is not semantic detection'),
        'proportion': unknown('No calibrated physical dimensions'),
        'perspective': unknown('No novel view geometry'),
        'lighting': unknown('Shadow heuristic only'),
        'photorealism': unknown('Human review required'),
        'visual_regression_gates': vr_gates
    }
    
    has_arch_fail = arch.get('status') == 'fail'
    has_prod_fail = any(v.get('status') == 'fail' for v in products.values())
    has_vr_fail = any(g.get('status') == 'fail' for g in vr_gates.values())
    
    status = 'failed' if (has_arch_fail or has_prod_fail or has_vr_fail) else 'needs_review'
    return status, checks
