"""Deterministic execution model for backtests."""

from __future__ import annotations

from decimal import Decimal

from peaberry.domain.market import Bar, Symbol
from peaberry.domain.portfolio import Portfolio, Trade
from peaberry.domain.signal import TargetAllocation


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class SimulatedExecutionModel:
    """Fill target-weight rebalances at bar close with fees and slippage."""

    def __init__(
        self,
        commission_bps: Decimal | int | float | str = Decimal("0"),
        slippage_bps: Decimal | int | float | str = Decimal("0"),
        min_trade_notional: Decimal | int | float | str = Decimal("0"),
    ) -> None:
        self.commission_bps = _to_decimal(commission_bps)
        self.slippage_bps = _to_decimal(slippage_bps)
        self.min_trade_notional = _to_decimal(min_trade_notional)
        if self.commission_bps < 0:
            raise ValueError("commission_bps cannot be negative")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps cannot be negative")
        if self.slippage_bps >= Decimal("10000"):
            raise ValueError("slippage_bps must be less than 10000")
        if self.min_trade_notional < 0:
            raise ValueError("min_trade_notional cannot be negative")

    def rebalance(
        self,
        target: TargetAllocation,
        bar: Bar,
        portfolio: Portfolio,
        latest_prices: dict[Symbol, Decimal],
    ) -> Trade | None:
        equity = portfolio.equity(latest_prices)
        if equity <= 0:
            return None

        current_value = portfolio.quantity(target.symbol) * bar.close
        desired_value = equity * target.weight
        delta_value = desired_value - current_value
        if abs(delta_value) <= self.min_trade_notional:
            return None

        direction = Decimal("1") if delta_value > 0 else Decimal("-1")
        slippage_multiplier = Decimal("1") + direction * self.slippage_bps / Decimal("10000")
        execution_price = bar.close * slippage_multiplier
        quantity = delta_value / execution_price
        commission = abs(delta_value) * self.commission_bps / Decimal("10000")

        trade = Trade(
            symbol=target.symbol,
            timestamp=bar.timestamp,
            quantity=quantity,
            price=execution_price,
            commission=commission,
        )
        portfolio.apply_trade(trade)
        return trade
