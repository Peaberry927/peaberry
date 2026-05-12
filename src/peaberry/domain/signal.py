"""Strategy intent expressed as portfolio targets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from peaberry.domain.market import Symbol


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True, slots=True)
class TargetAllocation:
    """Desired portfolio weight for a symbol.

    Expressing strategy output as target weights keeps alpha generation
    independent from execution details such as sizing, fills, and fees.
    """

    symbol: Symbol
    weight: Decimal
    generated_at: datetime
    strategy_id: str
    confidence: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        object.__setattr__(self, "weight", _to_decimal(self.weight))
        object.__setattr__(self, "confidence", _to_decimal(self.confidence))

        if self.weight < Decimal("-1") or self.weight > Decimal("1"):
            raise ValueError("target allocation weight must be between -1 and 1")
        if self.confidence < 0 or self.confidence > 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.strategy_id:
            raise ValueError("strategy_id is required")
