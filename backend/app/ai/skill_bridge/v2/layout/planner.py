"""IMPROVED: perspective-aware spatial placement, relative product scaling, and boundary safety."""
import cv2
import numpy as np

def plan(room_info: dict, products: list) -> list:
    floor = room_info['placement']
    forbidden = room_info['forbidden']
    h, w = floor.shape
    occupied = np.zeros_like(floor)
    plans = []
    
    ys, xs = np.where(floor)
    if not len(xs):
        raise ValueError('FLOOR_UNKNOWN')
        
    for i, (pid, rgba) in enumerate(products):
        aspect = float(rgba.shape[1] / rgba.shape[0])
        found = None
        
        # Determine candidate scales based on product category / aspect ratio
        if aspect > 1.4:
            # Seating / horizontal furniture (e.g. Sofa): width-driven scaling
            # Primary item should span ~36% - 46% of room width
            target_fracs = [0.44, 0.40, 0.36, 0.32, 0.28]
            scale_candidates = []
            for frac in target_fracs:
                bw = max(16, int(w * frac))
                bh = max(16, int(bw / aspect))
                if bh < h * 0.45 and bw < w * 0.90:
                    scale_candidates.append((bw, bh))
            preferred_x_ratio = 0.52 if i == 0 else 0.42
        elif aspect < 0.7:
            # Vertical accent / lighting (e.g. Floor Lamp): height-driven scaling
            # Accent lighting height should be ~32% - 40% of room height, never dominating
            target_height_fracs = [0.38, 0.35, 0.32, 0.28]
            scale_candidates = []
            for h_frac in target_height_fracs:
                bh = max(16, int(h * h_frac))
                bw = max(8, int(bh * aspect))
                if bw < w * 0.35 and bh < h * 0.50:
                    scale_candidates.append((bw, bh))
            preferred_x_ratio = 0.74 if i % 2 == 1 else 0.28
        else:
            # Intermediate / compact items (e.g. armchair, side table)
            target_fracs = [0.26, 0.22, 0.18]
            scale_candidates = []
            for frac in target_fracs:
                bw = max(12, int(w * frac))
                bh = max(12, int(bw / aspect))
                if bh < h * 0.45 and bw < w * 0.50:
                    scale_candidates.append((bw, bh))
            preferred_x_ratio = 0.35 if i % 2 == 1 else 0.65

        # Fallback to standard fractions if specific scaling had no candidates
        if not scale_candidates:
            for frac in (0.38, 0.30, 0.24, 0.18):
                bw = max(8, int(w * frac))
                bh = max(8, int(bw / aspect))
                if bh > h * 0.75:
                    bh = int(h * 0.55)
                    bw = max(8, int(bh * aspect))
                if bw < w and bh < h:
                    scale_candidates.append((bw, bh))

        # Search for valid floor placement
        min_border_margin = max(8, int(w * 0.02))
        for bw, bh in scale_candidates:
            mask = cv2.resize(rgba[:, :, 3], (bw, bh)) > 0
            
            # Floor scan from lower floor (front) to upper floor (back)
            y_candidates = range(int(ys.max()), max(bh, int(ys.min())), -max(4, h // 40))
            
            # Sort x positions prioritizing the preferred focal area
            x_range = range(min_border_margin, w - bw - min_border_margin + 1, max(4, w // 40))
            sorted_x = sorted(x_range, key=lambda x_pos: abs(x_pos + bw / 2 - w * preferred_x_ratio))
            
            for y in y_candidates:
                for x in sorted_x:
                    top = y - bh + 1
                    if top < 0 or y >= h or x + bw > w:
                        continue
                        
                    # Verify ground contact on floor: center base and feet/corners
                    base_y = min(h - 1, y)
                    p_mid = floor[base_y, min(w - 1, x + bw // 2)]
                    p_left = floor[base_y, min(w - 1, x + int(0.15 * bw))]
                    p_right = floor[base_y, min(w - 1, x + int(0.85 * bw))]
                    
                    if not (p_mid or (p_left and p_right)):
                        continue
                        
                    # Collision check against forbidden zones (doors, windows, existing items) and occupied items
                    placed_region = (forbidden | occupied)[top:y + 1, x:x + bw]
                    if placed_region.shape != mask.shape:
                        continue
                        
                    if (mask & placed_region).any():
                        continue
                        
                    found = (int(x), int(top), int(bw), int(bh))
                    occupied[top:y + 1, x:x + bw] |= mask
                    break
                if found:
                    break
            if found:
                break
                
        if not found:
            raise ValueError('NO_SAFE_IMAGE_SPACE_LAYOUT')
            
        plans.append({
            'product_id': pid,
            'box': found,
            'aspect_ratio': aspect,
            'estimated_scale': True,
            'confidence': None
        })
        
    return plans
