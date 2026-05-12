"""In-memory market data source for tests and research prototypes."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from peaberry.domain.market import Bar, Symbol


class InMemoryMarketDataSource:
    """Serve deterministic bars from memory."""

    def __init__(self, bars: Iterable[Bar]) -> None:
        self._bars = tuple(sorted(bars, key=lambda bar: (bar.timestamp, str(bar.symbol))))

    def history(
        self,
        symbols: Sequence[Symbol],
        start: datetime,
        end: datetime,
    ) -> Iterable[Bar]:
        requested = set(symbols)
        return (
            bar
            for bar in self._bars
            if bar.symbol in requested and start <= bar.timestamp <= end
        )
