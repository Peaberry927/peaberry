"""Market data primitives.

The domain layer deliberately avoids data-vendor concerns so the same bar
objects can flow through research notebooks, live adapters, and backtests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import NewType


Symbol = NewType("Symbol", str)


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True, slots=True)
class Bar:
    """A single OHLCV observation for one instrument."""

    symbol: Symbol
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "open", _to_decimal(self.open))
        object.__setattr__(self, "high", _to_decimal(self.high))
        object.__setattr__(self, "low", _to_decimal(self.low))
        object.__setattr__(self, "close", _to_decimal(self.close))
        object.__setattr__(self, "volume", _to_decimal(self.volume))

        prices = (self.open, self.high, self.low, self.close)
        if any(price <= 0 for price in prices):
            raise ValueError("OHLC prices must be positive")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("high/low must bound open and close prices")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")
