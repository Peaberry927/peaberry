from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase

from peaberry.domain.market import Bar, Symbol
from peaberry.domain.signal import TargetAllocation


class MarketDomainTests(TestCase):
    def test_bar_rejects_inconsistent_ohlc(self) -> None:
        with self.assertRaises(ValueError):
            Bar(
                symbol=Symbol("AAPL"),
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                open=Decimal("100"),
                high=Decimal("99"),
                low=Decimal("95"),
                close=Decimal("98"),
            )

    def test_target_allocation_rejects_over_sized_weight(self) -> None:
        with self.assertRaises(ValueError):
            TargetAllocation(
                symbol=Symbol("AAPL"),
                weight=Decimal("1.5"),
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                strategy_id="test",
            )
