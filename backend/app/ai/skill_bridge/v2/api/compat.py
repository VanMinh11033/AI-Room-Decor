"""PARTIAL host integration; no endpoint or DB changes. No silent fallback after inference."""
from app.ai.skill_bridge.v2.core.engine import Engine

class SkillBridgeV2:
    def __init__(self, v1_run, enabled=False):
        self.v1_run = v1_run
        self.enabled = enabled
        self.engine = Engine()
        
    def run(self, req: dict, *, load_asset, zones=None, save_preview=None, v1_kwargs=None):
        if not self.enabled:
            return self.v1_run(req, **(v1_kwargs or {}))
        return self.engine.run(req, load_asset, zones or {}, save_preview=save_preview)
