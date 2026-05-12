"""Simple portfolio-level limit checks."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from peaberry.domain.market import Symbol
from peaberry.domain.portfolio import Portfolio
from peaberry.domain.signal import TargetAllocation


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Risk configuration applied before execution."""

    max_abs_weight: Decimal = Decimal("1")
    max_gross_exposure: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_abs_weight", _to_decimal(self.max_abs_weight))
        object.__setattr__(
            self,
            "max_gross_exposure",
            _to_decimal(self.max_gross_exposure),
        )
        if self.max_abs_weight <= 0 or self.max_abs_weight > 1:
            raise ValueError("max_abs_weight must be greater than 0 and at most 1")
        if self.max_gross_exposure <= 0:
            raise ValueError("max_gross_exposure must be positive")


class LimitRiskModel:
    """Clamp target weights and reject targets that breach gross exposure."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def evaluate(
        self,
        target: TargetAllocation,
        portfolio: Portfolio,
        latest_prices: dict[Symbol, Decimal],
    ) -> TargetAllocation | None:
        weight = max(
            -self.limits.max_abs_weight,
            min(self.limits.max_abs_weight, target.weight),
        )
        approved = TargetAllocation(
            symbol=target.symbol,
            weight=weight,
            generated_at=target.generated_at,
            strategy_id=target.strategy_id,
            confidence=target.confidence,
        )

        equity = portfolio.equity(latest_prices)
        if equity <= 0:
            return None

        gross_ratio = portfolio.gross_exposure(latest_prices) / equity
        current_weight = (
            portfolio.quantity(target.symbol) * latest_prices[target.symbol] / equity
            if target.symbol in latest_prices
            else Decimal("0")
        )
        projected_gross = gross_ratio - abs(current_weight) + abs(approved.weight)
        if projected_gross > self.limits.max_gross_exposure:
            return None
        return approved
