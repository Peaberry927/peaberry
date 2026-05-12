"""Application ports for interchangeable infrastructure.

Protocols keep the backtesting core independent from concrete data vendors,
strategy implementations, risk policies, and execution simulators.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable, Protocol, Sequence

from peaberry.domain.market import Bar, Symbol
from peaberry.domain.portfolio import Portfolio, Trade
from peaberry.domain.signal import TargetAllocation


class MarketDataSource(Protocol):
    """Historical market data provider."""

    def history(
        self,
        symbols: Sequence[Symbol],
        start: datetime,
        end: datetime,
    ) -> Iterable[Bar]:
        """Return bars for the requested symbols and interval."""


class Strategy(Protocol):
    """Stateful strategy that reacts to one bar at a time."""

    strategy_id: str

    def on_bar(self, bar: Bar, portfolio: Portfolio) -> Iterable[TargetAllocation]:
        """Generate target allocations from a new market observation."""


class RiskModel(Protocol):
    """Risk gate that can transform or reject targets before execution."""

    def evaluate(
        self,
        target: TargetAllocation,
        portfolio: Portfolio,
        latest_prices: dict[Symbol, Decimal],
    ) -> TargetAllocation | None:
        """Return an approved target or None if the target is rejected."""


class ExecutionModel(Protocol):
    """Execution simulator or live order adapter."""

    def rebalance(
        self,
        target: TargetAllocation,
        bar: Bar,
        portfolio: Portfolio,
        latest_prices: dict[Symbol, Decimal],
    ) -> Trade | None:
        """Execute the order required to reach the approved target."""
