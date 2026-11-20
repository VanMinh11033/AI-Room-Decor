"""PARTIAL orchestrator: offline candidate only; uncertain semantic checks block publication."""
import json
import time
import logging
from pathlib import Path
from jsonschema import Draft202012Validator
from app.ai.skill_bridge.v2.security.images import decode, png, sha
from app.ai.skill_bridge.v2.computer_vision.room import analyze
from app.ai.skill_bridge.v2.catalog.products import extract
from app.ai.skill_bridge.v2.layout.planner import plan
from app.ai.skill_bridge.v2.rendering.composite import render
from app.ai.skill_bridge.v2.validation.inspect import inspect
from app.ai.skill_bridge.v2.optimization.control import Cache

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger('room_decor.v2')

class Engine:
    def __init__(self):
        self.cache = Cache(8)
        
    def run(self, req: dict, load_asset, zones: dict, *, save_preview=None) -> dict:
        input_schema_path = ROOT / 'schemas' / 'input_schema.json'
        output_schema_path = ROOT / 'schemas' / 'output_schema.json'
        
        if input_schema_path.exists():
            Draft202012Validator(json.loads(input_schema_path.read_text(encoding='utf-8'))).validate(req)
            
        ids = [p['product_id'] for p in req['selected_products']]
        if len(set(ids)) != len(ids):
            raise ValueError('DUPLICATE_PRODUCT')
            
        unknown = {'status': 'unknown', 'evidence': 'Independent semantic verification unavailable'}
        result = dict(
            generated_design_image=None,
            selected_product_ids=ids,
            layout_description='',
            architecture_validation=unknown.copy(),
            catalog_fidelity_validation=[dict(product_id=i, **unknown) for i in ids],
            quality_score=None,
            warnings=[],
            generation_status='needs_review',
            provider='offline',
            model='pixel-composite-v2',
            attempts=0,
            provenance={'skill_version': '2.0.0', 'external_inference': 0}
        )
        t = time.monotonic()
        try:
            room_raw = load_asset(req['room_image'])
            room = decode(room_raw)
            info = analyze(room, zones)
            products = []
            fingerprints = {}
            sources = {}
            
            for p in req['selected_products']:
                pid = p['product_id']
                views = []
                for asset in p['product_images']:
                    raw = load_asset(asset)
                    a = decode(raw)
                    views.append((sha(raw), a))
                digest, a = views[0]
                cut, fp = self.cache.get_or_create(('v2', digest), lambda: extract(a))
                products.append((pid, cut))
                fingerprints[pid] = fp
                sources[pid] = [d for d, _ in views]
                
            plans = plan(info, products)
            candidate, editable, locks = render(room, products, plans, info)
            result['attempts'] = 1
            status, checks = inspect(room, candidate, editable, locks, ids, info)
            
            result.update(
                generation_status=status,
                layout_description=json.dumps(plans, ensure_ascii=False)
            )
            result['provenance'].update(
                room_sha256=sha(room_raw),
                product_sha256=sources,
                fingerprints=fingerprints,
                checks=checks,
                candidate_sha256=sha(png(candidate)),
                layout=plans,
                protected_fraction=float((~editable).mean())
            )
            
            if checks['architecture_pixels']['status'] == 'fail':
                result['architecture_validation'] = {
                    'status': 'fail',
                    'evidence': checks['architecture_pixels']['evidence']
                }
            else:
                result['architecture_validation'] = {
                    'status': 'pass',
                    'evidence': checks['architecture_pixels']['evidence']
                }
                
            result['warnings'] += [
                'Estimated image-space scale; physical fit unverified.',
                'First view used for composite; other views validated and hashed, not geometrically fused.',
                'Manual review required; offline preview is not a photorealistic guarantee.',
                'Style and free-text requests are not executed by offline renderer.'
            ]
            if save_preview and status != 'failed':
                result['provenance']['private_preview'] = save_preview(png(candidate))
                
        except (ValueError, OSError, KeyError) as e:
            result['warnings'].append('LOCAL_PIPELINE_REVIEW_REQUIRED: ' + type(e).__name__)
            log.info('local_pipeline_rejected', extra={'error_type': type(e).__name__})
            
        result['provenance']['elapsed_ms'] = round((time.monotonic() - t) * 1000)
        
        if output_schema_path.exists():
            Draft202012Validator(json.loads(output_schema_path.read_text(encoding='utf-8'))).validate(result)
            
        return result
