"""Fundamental data primitives and derived valuation metrics."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import NewType

from peaberry.domain.market import Symbol


Currency = NewType("Currency", str)


def _to_decimal(value: Decimal | int | float | str | None) -> Decimal | None:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


class SourceKind(str, Enum):
    """Types of sources used to fill a fundamental row."""

    REGULATORY_FILING = "regulatory_filing"
    COMPANY_IR = "company_ir"
    MARKET_DATA = "market_data"
    ANALYST_ESTIMATE = "analyst_estimate"
    DERIVED = "derived"


@dataclass(frozen=True, slots=True)
class DataSourceRef:
    """Provenance for a fundamental value."""

    name: str
    kind: SourceKind
    as_of: datetime
    confidence: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _to_decimal(self.confidence))
        if not self.name:
            raise ValueError("source name is required")
        if self.confidence is None or self.confidence < 0 or self.confidence > 1:
            raise ValueError("source confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class FundamentalValue:
    """A single value with provenance and an estimate marker."""

    amount: Decimal
    source: DataSourceRef
    is_estimate: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _to_decimal(self.amount))


@dataclass(frozen=True, slots=True)
class FinancialStatement:
    """Annual or quarterly statement facts in base currency units."""

    symbol: Symbol
    fiscal_period: str
    currency: Currency
    source: DataSourceRef
    revenue: Decimal | None = None
    operating_income: Decimal | None = None
    net_income: Decimal | None = None
    shareholders_equity: Decimal | None = None
    diluted_shares: Decimal | None = None
    dividend_per_share: Decimal | None = None
    is_estimate: bool = False
    value_sources: tuple[tuple[str, DataSourceRef], ...] = ()
    estimated_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "revenue",
            "operating_income",
            "net_income",
            "shareholders_equity",
            "diluted_shares",
            "dividend_per_share",
        ):
            object.__setattr__(self, field_name, _to_decimal(getattr(self, field_name)))
        if not self.fiscal_period:
            raise ValueError("fiscal_period is required")
        if self.diluted_shares is not None and self.diluted_shares <= 0:
            raise ValueError("diluted_shares must be positive")

    def source_for(self, field_name: str) -> DataSourceRef:
        return dict(self.value_sources).get(field_name, self.source)

    def estimate_for(self, field_name: str) -> bool:
        return self.is_estimate or field_name in self.estimated_fields

    def merged_with(self, lower_priority: "FinancialStatement") -> "FinancialStatement":
        """Fill missing statement facts from a lower-priority source."""

        if (
            self.symbol != lower_priority.symbol
            or self.fiscal_period != lower_priority.fiscal_period
        ):
            raise ValueError("cannot merge statements for different symbols or periods")
        if self.currency != lower_priority.currency:
            raise ValueError("cannot merge statements with different currencies")

        values = {}
        value_sources = dict(self.value_sources)
        estimated_fields = set(self.estimated_fields)
        for field_name in (
            "revenue",
            "operating_income",
            "net_income",
            "shareholders_equity",
            "diluted_shares",
            "dividend_per_share",
        ):
            current_value = getattr(self, field_name)
            lower_value = getattr(lower_priority, field_name)
            if current_value is not None or lower_value is None:
                values[field_name] = current_value
                continue

            values[field_name] = lower_value
            value_sources[field_name] = lower_priority.source_for(field_name)
            if lower_priority.estimate_for(field_name):
                estimated_fields.add(field_name)

        return replace(
            self,
            **values,
            value_sources=tuple(value_sources.items()),
            estimated_fields=tuple(sorted(estimated_fields)),
        )


@dataclass(frozen=True, slots=True)
class MarketReference:
    """Market inputs required to derive valuation multiples."""

    symbol: Symbol
    currency: Currency
    as_of: datetime
    source: DataSourceRef
    price: Decimal | None = None
    market_cap: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "price", _to_decimal(self.price))
        object.__setattr__(self, "market_cap", _to_decimal(self.market_cap))
        if self.price is not None and self.price <= 0:
            raise ValueError("price must be positive")
        if self.market_cap is not None and self.market_cap <= 0:
            raise ValueError("market_cap must be positive")


@dataclass(frozen=True, slots=True)
class FundamentalRow:
    """A display-ready row with raw facts, derived metrics, and gaps."""

    symbol: Symbol
    fiscal_period: str
    currency: Currency
    revenue: FundamentalValue | None = None
    operating_income: FundamentalValue | None = None
    net_income: FundamentalValue | None = None
    roe: FundamentalValue | None = None
    eps: FundamentalValue | None = None
    per: FundamentalValue | None = None
    bps: FundamentalValue | None = None
    pbr: FundamentalValue | None = None
    dividend_yield: FundamentalValue | None = None
    sources: tuple[DataSourceRef, ...] = ()

    @property
    def missing_fields(self) -> tuple[str, ...]:
        return tuple(
            field_name
            for field_name in (
                "revenue",
                "operating_income",
                "net_income",
                "roe",
                "eps",
                "per",
                "bps",
                "pbr",
                "dividend_yield",
            )
            if getattr(self, field_name) is None
        )
