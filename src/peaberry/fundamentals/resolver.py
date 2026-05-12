"""Resolve complete display rows from raw fundamentals and market inputs."""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from peaberry.domain.fundamentals import (
    Currency,
    DataSourceRef,
    FinancialStatement,
    FundamentalRow,
    FundamentalValue,
    MarketReference,
    SourceKind,
)
from peaberry.domain.market import Symbol
from peaberry.fundamentals.sources import FundamentalsSource


class FundamentalDataResolver:
    """Fill fundamental display gaps with sourced and derived values."""

    def __init__(self, source: FundamentalsSource) -> None:
        self.source = source

    def rows(self, symbol: Symbol, fiscal_periods: Sequence[str]) -> tuple[FundamentalRow, ...]:
        statements = {
            statement.fiscal_period: statement
            for statement in self.source.statements(symbol, fiscal_periods)
        }
        return tuple(
            self._row_from_statement(
                statement=statements.get(period),
                symbol=symbol,
                fiscal_period=period,
                market=self.source.market_reference(symbol, period),
            )
            for period in fiscal_periods
        )

    def _row_from_statement(
        self,
        statement: FinancialStatement | None,
        symbol: Symbol,
        fiscal_period: str,
        market: MarketReference | None,
    ) -> FundamentalRow:
        currency = self._currency(statement, market)
        sources = self._sources(statement, market)
        if statement is None:
            return FundamentalRow(
                symbol=symbol,
                fiscal_period=fiscal_period,
                currency=currency,
                sources=sources,
            )

        revenue = self._sourced(
            statement.revenue,
            statement.source_for("revenue"),
            statement.estimate_for("revenue"),
        )
        operating_income = self._sourced(
            statement.operating_income,
            statement.source_for("operating_income"),
            statement.estimate_for("operating_income"),
        )
        net_income = self._sourced(
            statement.net_income,
            statement.source_for("net_income"),
            statement.estimate_for("net_income"),
        )
        eps = self._derived_eps(statement)
        bps = self._derived_bps(statement)
        roe = self._derived_roe(statement)
        market_price = self._market_price(statement, market)
        per = self._derived_per(eps, market, market_price)
        pbr = self._derived_pbr(bps, market, market_price)
        dividend_yield = self._derived_dividend_yield(statement, market, market_price)

        return FundamentalRow(
            symbol=symbol,
            fiscal_period=fiscal_period,
            currency=currency,
            revenue=revenue,
            operating_income=operating_income,
            net_income=net_income,
            roe=roe,
            eps=eps,
            per=per,
            bps=bps,
            pbr=pbr,
            dividend_yield=dividend_yield,
            sources=sources,
        )

    def _currency(
        self,
        statement: FinancialStatement | None,
        market: MarketReference | None,
    ) -> Currency:
        if statement is not None:
            return statement.currency
        if market is not None:
            return market.currency
        return Currency("UNKNOWN")

    def _sources(
        self,
        statement: FinancialStatement | None,
        market: MarketReference | None,
    ) -> tuple[DataSourceRef, ...]:
        sources: list[DataSourceRef] = []
        if statement is not None:
            sources.append(statement.source)
        if market is not None and market.source not in sources:
            sources.append(market.source)
        return tuple(sources)

    def _sourced(
        self,
        amount: Decimal | None,
        source: DataSourceRef,
        is_estimate: bool,
    ) -> FundamentalValue | None:
        if amount is None:
            return None
        return FundamentalValue(amount=amount, source=source, is_estimate=is_estimate)

    def _derived_source(
        self,
        statement: FinancialStatement,
        field_names: tuple[str, ...],
        market: MarketReference | None = None,
    ) -> DataSourceRef:
        confidence = min(
            statement.source_for(field_name).confidence for field_name in field_names
        )
        if any(statement.estimate_for(field_name) for field_name in field_names):
            confidence *= Decimal("0.85")
        if market is not None:
            confidence = min(confidence, market.source.confidence)
        return DataSourceRef(
            name=self.source.name,
            kind=SourceKind.DERIVED,
            as_of=market.as_of if market is not None else statement.source.as_of,
            confidence=confidence,
        )

    def _derived_eps(self, statement: FinancialStatement) -> FundamentalValue | None:
        if statement.net_income is None or statement.diluted_shares is None:
            return None
        fields = ("net_income", "diluted_shares")
        return FundamentalValue(
            amount=statement.net_income / statement.diluted_shares,
            source=self._derived_source(statement, fields),
            is_estimate=any(statement.estimate_for(field_name) for field_name in fields),
        )

    def _derived_bps(self, statement: FinancialStatement) -> FundamentalValue | None:
        if statement.shareholders_equity is None or statement.diluted_shares is None:
            return None
        fields = ("shareholders_equity", "diluted_shares")
        return FundamentalValue(
            amount=statement.shareholders_equity / statement.diluted_shares,
            source=self._derived_source(statement, fields),
            is_estimate=any(statement.estimate_for(field_name) for field_name in fields),
        )

    def _derived_roe(self, statement: FinancialStatement) -> FundamentalValue | None:
        if statement.net_income is None or statement.shareholders_equity in (None, Decimal("0")):
            return None
        fields = ("net_income", "shareholders_equity")
        return FundamentalValue(
            amount=statement.net_income / statement.shareholders_equity * Decimal("100"),
            source=self._derived_source(statement, fields),
            is_estimate=any(statement.estimate_for(field_name) for field_name in fields),
        )

    def _derived_per(
        self,
        eps: FundamentalValue | None,
        market: MarketReference | None,
        market_price: Decimal | None,
    ) -> FundamentalValue | None:
        if eps is None or eps.amount <= 0 or market is None or market_price is None:
            return None
        return FundamentalValue(
            amount=market_price / eps.amount,
            source=self._derived_source_from_values(eps, market),
            is_estimate=eps.is_estimate,
        )

    def _derived_pbr(
        self,
        bps: FundamentalValue | None,
        market: MarketReference | None,
        market_price: Decimal | None,
    ) -> FundamentalValue | None:
        if bps is None or bps.amount <= 0 or market is None or market_price is None:
            return None
        return FundamentalValue(
            amount=market_price / bps.amount,
            source=self._derived_source_from_values(bps, market),
            is_estimate=bps.is_estimate,
        )

    def _derived_dividend_yield(
        self,
        statement: FinancialStatement,
        market: MarketReference | None,
        market_price: Decimal | None,
    ) -> FundamentalValue | None:
        if (
            statement.dividend_per_share is None
            or market is None
            or market_price is None
            or market_price <= 0
        ):
            return None
        fields = ("dividend_per_share",)
        return FundamentalValue(
            amount=statement.dividend_per_share / market_price * Decimal("100"),
            source=self._derived_source(statement, fields, market),
            is_estimate=statement.estimate_for("dividend_per_share"),
        )

    def _market_price(
        self,
        statement: FinancialStatement,
        market: MarketReference | None,
    ) -> Decimal | None:
        if market is None or market.currency != statement.currency:
            return None
        if market.price is not None:
            return market.price
        if market.market_cap is not None and statement.diluted_shares is not None:
            return market.market_cap / statement.diluted_shares
        return None

    def _derived_source_from_values(
        self,
        value: FundamentalValue,
        market: MarketReference,
    ) -> DataSourceRef:
        return DataSourceRef(
            name=self.source.name,
            kind=SourceKind.DERIVED,
            as_of=market.as_of,
            confidence=min(value.source.confidence, market.source.confidence),
        )
