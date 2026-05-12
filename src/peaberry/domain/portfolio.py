"""Portfolio accounting primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from peaberry.domain.market import Symbol


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(slots=True)
class Position:
    """Current quantity held for a symbol."""

    symbol: Symbol
    quantity: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        self.quantity = _to_decimal(self.quantity)

    def market_value(self, price: Decimal | int | float | str) -> Decimal:
        return self.quantity * _to_decimal(price)


@dataclass(frozen=True, slots=True)
class Trade:
    """An executed fill."""

    symbol: Symbol
    timestamp: datetime
    quantity: Decimal
    price: Decimal
    commission: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", _to_decimal(self.quantity))
        object.__setattr__(self, "price", _to_decimal(self.price))
        object.__setattr__(self, "commission", _to_decimal(self.commission))

        if self.price <= 0:
            raise ValueError("trade price must be positive")
        if self.commission < 0:
            raise ValueError("commission cannot be negative")

    @property
    def notional(self) -> Decimal:
        return self.quantity * self.price


@dataclass(slots=True)
class Portfolio:
    """Cash and positions with explicit mark-to-market inputs."""

    cash: Decimal
    positions: dict[Symbol, Position] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.cash = _to_decimal(self.cash)

    @property
    def readonly_positions(self) -> Mapping[Symbol, Position]:
        return MappingProxyType(self.positions)

    def quantity(self, symbol: Symbol) -> Decimal:
        position = self.positions.get(symbol)
        return Decimal("0") if position is None else position.quantity

    def apply_trade(self, trade: Trade) -> None:
        position = self.positions.setdefault(trade.symbol, Position(trade.symbol))
        position.quantity += trade.quantity
        if position.quantity == 0:
            del self.positions[trade.symbol]
        self.cash -= trade.notional + trade.commission

    def market_value(self, prices: Mapping[Symbol, Decimal]) -> Decimal:
        return sum(
            position.market_value(prices[symbol])
            for symbol, position in self.positions.items()
            if symbol in prices
        )

    def equity(self, prices: Mapping[Symbol, Decimal]) -> Decimal:
        return self.cash + self.market_value(prices)

    def gross_exposure(self, prices: Mapping[Symbol, Decimal]) -> Decimal:
        return sum(
            abs(position.market_value(prices[symbol]))
            for symbol, position in self.positions.items()
            if symbol in prices
        )
