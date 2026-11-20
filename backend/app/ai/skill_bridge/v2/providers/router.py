"""IMPLEMENTED fail-closed selection; external contract and price approval required."""
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Capability:
    name: str
    model: str
    max_refs: int
    mask: bool
    upper_cost: str
    approved: bool = False
    benchmark: float | None = None

def choose(options: list[Capability], refs: int, authorized: list[str], budget: str | float, requires_mask: bool = False) -> Capability:
    eligible = [
        x for x in options
        if x.approved
        and x.name in authorized
        and x.max_refs >= refs
        and (x.mask or not requires_mask)
        and Decimal(0) <= Decimal(x.upper_cost) <= Decimal(str(budget))
    ]
    if not eligible:
        raise ValueError('NO_APPROVED_PROVIDER')
    return sorted(eligible, key=lambda x: (x.benchmark is None, -(x.benchmark or 0), Decimal(x.upper_cost), x.name))[0]
