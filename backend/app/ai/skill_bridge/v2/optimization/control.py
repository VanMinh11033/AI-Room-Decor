"""IMPLEMENTED process-local reservation and bounded cache; distributed durability host-owned."""
from threading import RLock
from collections import OrderedDict
from decimal import Decimal

class Budget:
    def __init__(self, ceiling='0', calls=0):
        self.ceiling = Decimal(str(ceiling))
        self.calls = calls
        self.used = Decimal(0)
        self.count = 0
        self.lock = RLock()
        self.keys = set()
        
    def reserve(self, key, cost, authorized):
        cost = Decimal(str(cost))
        with self.lock:
            if key in self.keys:
                raise ValueError('DUPLICATE_INFERENCE')
            if not authorized or not cost.is_finite() or cost < 0 or self.count >= self.calls or self.used + cost > self.ceiling:
                raise ValueError('QUOTA_OR_AUTHORIZATION')
            self.keys.add(key)
            self.used += cost
            self.count += 1

class Cache:
    def __init__(self, limit=8):
        self.limit = limit
        self.data = OrderedDict()
        self.lock = RLock()
        
    def get_or_create(self, key, fn):
        with self.lock:
            if key not in self.data:
                self.data[key] = fn()
                if len(self.data) > self.limit:
                    self.data.popitem(last=False)
            self.data.move_to_end(key)
            return self.data[key]
