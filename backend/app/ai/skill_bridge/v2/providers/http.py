"""EXPERIMENTAL: HTTP adapters; no live inference tested. One request only, no retries."""
import base64
import httpx
import re
from app.ai.skill_bridge.v2.security.images import decode, png

class HTTPAdapter:
    def __init__(self, cap, key, account=None, timeout=90, transport=None):
        self.cap = cap
        self.key = key
        self.account = account
        self.timeout = timeout
        self.transport = transport
        
    def edit(self, prompt, images, *, budget, job_key, authorized=False):
        c = self.cap
        if not c.approved or not self.key or not 1 <= len(images) <= c.max_refs:
            raise ValueError('CAPABILITY_MISMATCH')
        if not re.fullmatch(r'[A-Za-z0-9_./@-]+', c.model):
            raise ValueError('MODEL_ID')
        if c.name == 'cloudflare' and (not self.account or not re.fullmatch(r'[A-Za-z0-9]+', self.account)):
            raise ValueError('ACCOUNT_ID')
            
        images = [png(decode(x)[:, :, :3]) for x in images]
        budget.reserve(job_key, c.upper_cost, authorized)
        
        with httpx.Client(timeout=self.timeout, transport=self.transport, follow_redirects=False) as client:
            if c.name == 'cloudflare':
                if any(max(decode(x).shape[:2]) > 2048 for x in images):
                    raise ValueError('REFERENCE_SIZE_REVIEW')
                r = client.post(
                    f'https://api.cloudflare.com/client/v4/accounts/{self.account}/ai/run/{c.model}',
                    headers={'Authorization': f'Bearer {self.key}'},
                    data={'prompt': prompt},
                    files=[(f'input_image_{i}', (f'{i}.png', x, 'image/png')) for i, x in enumerate(images)]
                )
            elif c.name == 'openai':
                r = client.post(
                    'https://api.openai.com/v1/images/edits',
                    headers={'Authorization': f'Bearer {self.key}'},
                    data={'model': c.model, 'prompt': prompt, 'n': '1'},
                    files=[('image[]', (f'{i}.png', x, 'image/png')) for i, x in enumerate(images)]
                )
            elif c.name == 'gemini':
                parts = [{'text': prompt}] + [{'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(x).decode()}} for x in images]
                r = client.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{c.model}:generateContent',
                    headers={'x-goog-api-key': self.key},
                    json={'contents': [{'parts': parts}], 'generationConfig': {'responseModalities': ['TEXT', 'IMAGE']}}
                )
            else:
                raise ValueError('UNKNOWN_PROVIDER')
                
            if r.status_code == 429:
                raise ValueError('QUOTA_EXCEEDED')
            r.raise_for_status()
            
            if r.headers.get('content-type', '').startswith('image/'):
                raw = r.content
            elif c.name == 'cloudflare':
                raw = base64.b64decode(r.json()['result']['image'], validate=True)
            elif c.name == 'openai':
                raw = base64.b64decode(r.json()['data'][0]['b64_json'], validate=True)
            else:
                raw = next((
                    base64.b64decode(p['inlineData']['data'], validate=True)
                    for x in r.json().get('candidates', [])
                    for p in x.get('content', {}).get('parts', [])
                    if p.get('inlineData', {}).get('mimeType', '').startswith('image/')
                ), None)
                if raw is None:
                    raise ValueError('NO_IMAGE')
        return png(decode(raw)[:, :, :3])
