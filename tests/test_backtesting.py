from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import TestCase

from peaberry.backtesting import BacktestEngine
from peaberry.data import InMemoryMarketDataSource
from peaberry.domain.market import Bar, Symbol
from peaberry.domain.portfolio import Portfolio
from peaberry.execution import SimulatedExecutionModel
from peaberry.risk import LimitRiskModel, RiskLimits
from peaberry.strategies import MovingAverageCrossStrategy


def _bars(symbol: Symbol, closes: list[str]) -> list[Bar]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars: list[Bar] = []
    for index, close in enumerate(closes):
        price = Decimal(close)
        bars.append(
            Bar(
                symbol=symbol,
                timestamp=start + timedelta(days=index),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=Decimal("1000"),
            )
        )
    return bars


class BacktestingTests(TestCase):
    def test_moving_average_strategy_emits_target_after_warmup(self) -> None:
        strategy = MovingAverageCrossStrategy(
            fast_window=2,
            slow_window=3,
            long_weight=Decimal("0.5"),
        )
        symbol = Symbol("AAPL")
        targets = [
            target
            for bar in _bars(symbol, ["10", "11", "12"])
            for target in strategy.on_bar(bar, portfolio=Portfolio(Decimal("100000")))
        ]

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].symbol, symbol)
        self.assertEqual(targets[0].weight, Decimal("0.5"))

    def test_backtest_coordinates_strategy_risk_and_execution(self) -> None:
        symbol = Symbol("AAPL")
        bars = _bars(symbol, ["10", "11", "12", "13"])
        engine = BacktestEngine(
            data_source=InMemoryMarketDataSource(bars),
            strategy=MovingAverageCrossStrategy(
                fast_window=2,
                slow_window=3,
                long_weight=Decimal("0.8"),
            ),
            risk_model=LimitRiskModel(
                RiskLimits(
                    max_abs_weight=Decimal("0.5"),
                    max_gross_exposure=Decimal("1"),
                )
            ),
            execution_model=SimulatedExecutionModel(),
            initial_cash=Decimal("100000"),
        )

        result = engine.run(symbols=[symbol], start=bars[0].timestamp, end=bars[-1].timestamp)

        self.assertEqual(len(result.trades), 1)
        self.assertEqual(len(result.equity_curve), len(bars))
        self.assertGreater(result.final_equity, result.initial_cash)
        self.assertAlmostEqual(
            result.portfolio.quantity(symbol),
            Decimal("4166.666666666666666666666667"),
        )
