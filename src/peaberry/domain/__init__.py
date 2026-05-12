"""Domain objects shared across research, risk, execution, and backtesting."""

from peaberry.domain.fundamentals import (
    Currency,
    DataSourceRef,
    FinancialStatement,
    FundamentalRow,
    FundamentalValue,
    MarketReference,
    SourceKind,
)
from peaberry.domain.market import Bar, Symbol
from peaberry.domain.portfolio import Portfolio, Position, Trade
from peaberry.domain.signal import TargetAllocation

__all__ = [
    "Bar",
    "Currency",
    "DataSourceRef",
    "FinancialStatement",
    "FundamentalRow",
    "FundamentalValue",
    "MarketReference",
    "Portfolio",
    "Position",
    "SourceKind",
    "Symbol",
    "TargetAllocation",
    "Trade",
]
