"""Event-driven backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from peaberry.domain.market import Symbol
from peaberry.domain.portfolio import Portfolio, Trade
from peaberry.ports import ExecutionModel, MarketDataSource, RiskModel, Strategy


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """Portfolio equity after processing a bar."""

    timestamp: datetime
    equity: Decimal


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Backtest output with enough detail for diagnostics and reporting."""

    start: datetime
    end: datetime
    initial_cash: Decimal
    final_equity: Decimal
    equity_curve: tuple[EquityPoint, ...]
    trades: tuple[Trade, ...]
    portfolio: Portfolio


class BacktestEngine:
    """Coordinate market data, strategy, risk, execution, and accounting."""

    def __init__(
        self,
        data_source: MarketDataSource,
        strategy: Strategy,
        risk_model: RiskModel,
        execution_model: ExecutionModel,
        initial_cash: Decimal | int | float | str = Decimal("1000000"),
    ) -> None:
        self.data_source = data_source
        self.strategy = strategy
        self.risk_model = risk_model
        self.execution_model = execution_model
        self.initial_cash = (
            initial_cash if isinstance(initial_cash, Decimal) else Decimal(str(initial_cash))
        )
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")

    def run(
        self,
        symbols: Sequence[Symbol],
        start: datetime,
        end: datetime,
    ) -> BacktestResult:
        if start > end:
            raise ValueError("start must be before or equal to end")

        portfolio = Portfolio(cash=self.initial_cash)
        latest_prices: dict[Symbol, Decimal] = {}
        trades: list[Trade] = []
        equity_curve: list[EquityPoint] = []
        bars = sorted(
            self.data_source.history(symbols=symbols, start=start, end=end),
            key=lambda bar: (bar.timestamp, str(bar.symbol)),
        )

        for bar in bars:
            latest_prices[bar.symbol] = bar.close
            for target in self.strategy.on_bar(bar, portfolio):
                approved = self.risk_model.evaluate(target, portfolio, latest_prices)
                if approved is None:
                    continue
                trade = self.execution_model.rebalance(
                    approved,
                    bar,
                    portfolio,
                    latest_prices,
                )
                if trade is not None:
                    trades.append(trade)

            equity_curve.append(
                EquityPoint(
                    timestamp=bar.timestamp,
                    equity=portfolio.equity(latest_prices),
                )
            )

        final_equity = (
            portfolio.equity(latest_prices) if equity_curve else self.initial_cash
        )
        return BacktestResult(
            start=start,
            end=end,
            initial_cash=self.initial_cash,
            final_equity=final_equity,
            equity_curve=tuple(equity_curve),
            trades=tuple(trades),
            portfolio=portfolio,
        )
