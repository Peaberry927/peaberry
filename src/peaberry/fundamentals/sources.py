"""Fundamental data source composition.

Adapters for DART, SEC Company Facts, company IR spreadsheets, or analyst
estimate feeds can implement ``FundamentalsSource`` and be composed here.
"""

from __future__ import annotations

from typing import Iterable, Protocol, Sequence

from peaberry.domain.fundamentals import FinancialStatement, MarketReference
from peaberry.domain.market import Symbol


class FundamentalsSource(Protocol):
    """Source of statement facts and market references."""

    name: str

    def statements(
        self,
        symbol: Symbol,
        fiscal_periods: Sequence[str],
    ) -> Iterable[FinancialStatement]:
        """Return available statement facts for requested fiscal periods."""

    def market_reference(self, symbol: Symbol) -> MarketReference | None:
        """Return the latest price or market-cap reference for valuation metrics."""


class InMemoryFundamentalsSource:
    """Deterministic source for tests, fixtures, and offline imports."""

    def __init__(
        self,
        name: str,
        statements: Iterable[FinancialStatement] = (),
        market_references: Iterable[MarketReference] = (),
    ) -> None:
        self.name = name
        self._statements = tuple(statements)
        self._market_references = {
            reference.symbol: reference for reference in market_references
        }

    def statements(
        self,
        symbol: Symbol,
        fiscal_periods: Sequence[str],
    ) -> Iterable[FinancialStatement]:
        requested = set(fiscal_periods)
        return (
            statement
            for statement in self._statements
            if statement.symbol == symbol and statement.fiscal_period in requested
        )

    def market_reference(self, symbol: Symbol) -> MarketReference | None:
        return self._market_references.get(symbol)


class CompositeFundamentalsSource:
    """Merge multiple sources by priority to reduce display gaps."""

    def __init__(self, sources: Sequence[FundamentalsSource]) -> None:
        if not sources:
            raise ValueError("at least one fundamentals source is required")
        self.sources = tuple(sources)
        self.name = "composite_fundamentals"

    def statements(
        self,
        symbol: Symbol,
        fiscal_periods: Sequence[str],
    ) -> Iterable[FinancialStatement]:
        merged: dict[str, FinancialStatement] = {}
        for source in self.sources:
            for statement in source.statements(symbol, fiscal_periods):
                existing = merged.get(statement.fiscal_period)
                merged[statement.fiscal_period] = (
                    statement
                    if existing is None
                    else existing.merged_with(statement)
                )
        return tuple(merged[period] for period in fiscal_periods if period in merged)

    def market_reference(self, symbol: Symbol) -> MarketReference | None:
        for source in self.sources:
            reference = source.market_reference(symbol)
            if reference is not None:
                return reference
        return None
