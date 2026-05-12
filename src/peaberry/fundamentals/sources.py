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

    def market_reference(
        self,
        symbol: Symbol,
        fiscal_period: str | None = None,
    ) -> MarketReference | None:
        """Return a period-specific or latest market reference for valuation metrics."""


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
        self._market_references = tuple(
            sorted(market_references, key=lambda reference: reference.as_of, reverse=True)
        )

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

    def market_reference(
        self,
        symbol: Symbol,
        fiscal_period: str | None = None,
    ) -> MarketReference | None:
        if fiscal_period is not None:
            for reference in self._market_references:
                if reference.symbol == symbol and reference.fiscal_period == fiscal_period:
                    return reference

        for reference in self._market_references:
            if reference.symbol == symbol and reference.fiscal_period is None:
                return reference
        return None


class CompositeFundamentalsSource:
    """Merge multiple sources by priority to reduce display gaps."""

    def __init__(self, sources: Sequence[FundamentalsSource]) -> None:
        if not sources:
            raise ValueError("at least one fundamentals source is required")
        self.sources = tuple(sources)
        self.name = "composite_fundamentals"
        self._source_errors: list[tuple[str, str]] = []

    @property
    def source_errors(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._source_errors)

    def statements(
        self,
        symbol: Symbol,
        fiscal_periods: Sequence[str],
    ) -> Iterable[FinancialStatement]:
        merged: dict[str, FinancialStatement] = {}
        for source in self.sources:
            try:
                statements = source.statements(symbol, fiscal_periods)
                for statement in statements:
                    existing = merged.get(statement.fiscal_period)
                    merged[statement.fiscal_period] = (
                        statement
                        if existing is None
                        else existing.merged_with(statement)
                    )
            except Exception as exc:
                self._record_error(source, exc)
        return tuple(merged[period] for period in fiscal_periods if period in merged)

    def market_reference(
        self,
        symbol: Symbol,
        fiscal_period: str | None = None,
    ) -> MarketReference | None:
        failed_sources: set[str] = set()
        if fiscal_period is not None:
            for source in self.sources:
                try:
                    reference = source.market_reference(symbol, fiscal_period)
                    if reference is not None and reference.fiscal_period == fiscal_period:
                        return reference
                except Exception as exc:
                    self._record_error(source, exc)
                    failed_sources.add(source.name)

        for source in self.sources:
            if source.name in failed_sources:
                continue
            try:
                reference = source.market_reference(symbol, fiscal_period)
                if reference is not None:
                    return reference
            except Exception as exc:
                self._record_error(source, exc)
        return None

    def _record_error(self, source: FundamentalsSource, exc: Exception) -> None:
        self._source_errors.append((source.name, str(exc)))
