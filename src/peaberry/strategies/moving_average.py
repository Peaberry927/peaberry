"""Reference moving-average crossover strategy."""

from __future__ import annotations

from collections import defaultdict, deque
from decimal import Decimal
from statistics import mean
from typing import Deque, Iterable

from peaberry.domain.market import Bar, Symbol
from peaberry.domain.portfolio import Portfolio
from peaberry.domain.signal import TargetAllocation


class MovingAverageCrossStrategy:
    """Emit a target weight when the fast average crosses above the slow average."""

    strategy_id = "moving_average_cross"

    def __init__(
        self,
        fast_window: int,
        slow_window: int,
        long_weight: Decimal | int | float | str = Decimal("1"),
    ) -> None:
        if fast_window <= 0:
            raise ValueError("fast_window must be positive")
        if slow_window <= fast_window:
            raise ValueError("slow_window must be greater than fast_window")

        self.fast_window = fast_window
        self.slow_window = slow_window
        self.long_weight = (
            long_weight if isinstance(long_weight, Decimal) else Decimal(str(long_weight))
        )
        if self.long_weight <= 0 or self.long_weight > 1:
            raise ValueError("long_weight must be greater than 0 and less than or equal to 1")

        self._closes: dict[Symbol, Deque[Decimal]] = defaultdict(
            lambda: deque(maxlen=self.slow_window)
        )
        self._last_weight: dict[Symbol, Decimal] = {}

    def on_bar(self, bar: Bar, portfolio: Portfolio) -> Iterable[TargetAllocation]:
        closes = self._closes[bar.symbol]
        closes.append(bar.close)
        if len(closes) < self.slow_window:
            return ()

        fast_average = Decimal(str(mean(list(closes)[-self.fast_window :])))
        slow_average = Decimal(str(mean(closes)))
        target_weight = self.long_weight if fast_average > slow_average else Decimal("0")

        if self._last_weight.get(bar.symbol) == target_weight:
            return ()

        self._last_weight[bar.symbol] = target_weight
        return (
            TargetAllocation(
                symbol=bar.symbol,
                weight=target_weight,
                generated_at=bar.timestamp,
                strategy_id=self.strategy_id,
            ),
        )
