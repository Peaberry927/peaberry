from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase

from peaberry.domain.fundamentals import (
    Currency,
    DataSourceRef,
    FinancialStatement,
    MarketReference,
    SourceKind,
)
from peaberry.domain.market import Symbol
from peaberry.fundamentals import (
    CompositeFundamentalsSource,
    FundamentalDataResolver,
    FundamentalCoveragePlanner,
    InMemoryFundamentalsSource,
)


class FundamentalsResolverTests(TestCase):
    def test_composite_source_fills_missing_statement_facts_by_priority(self) -> None:
        symbol = Symbol("AAPL")
        filing_source = DataSourceRef(
            name="SEC Company Facts",
            kind=SourceKind.REGULATORY_FILING,
            as_of=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        ir_source = DataSourceRef(
            name="Company IR",
            kind=SourceKind.COMPANY_IR,
            as_of=datetime(2026, 2, 2, tzinfo=timezone.utc),
            confidence=Decimal("0.9"),
        )
        market_source = DataSourceRef(
            name="Realtime quote",
            kind=SourceKind.MARKET_DATA,
            as_of=datetime(2026, 2, 3, tzinfo=timezone.utc),
        )

        filing = InMemoryFundamentalsSource(
            name="filing",
            statements=[
                FinancialStatement(
                    symbol=symbol,
                    fiscal_period="2025.12",
                    currency=Currency("USD"),
                    source=filing_source,
                    revenue=Decimal("1000000"),
                    net_income=Decimal("100000"),
                    diluted_shares=Decimal("10000"),
                )
            ],
            market_references=[
                MarketReference(
                    symbol=symbol,
                    currency=Currency("USD"),
                    as_of=market_source.as_of,
                    source=market_source,
                    price=Decimal("200"),
                )
            ],
        )
        ir = InMemoryFundamentalsSource(
            name="ir",
            statements=[
                FinancialStatement(
                    symbol=symbol,
                    fiscal_period="2025.12",
                    currency=Currency("USD"),
                    source=ir_source,
                    operating_income=Decimal("200000"),
                    shareholders_equity=Decimal("500000"),
                    dividend_per_share=Decimal("2"),
                )
            ],
        )

        resolver = FundamentalDataResolver(CompositeFundamentalsSource([filing, ir]))
        row = resolver.rows(symbol, ["2025.12"])[0]

        self.assertEqual(row.revenue.amount, Decimal("1000000"))
        self.assertEqual(row.operating_income.amount, Decimal("200000"))
        self.assertEqual(row.revenue.source, filing_source)
        self.assertEqual(row.operating_income.source, ir_source)
        self.assertEqual(row.eps.amount, Decimal("10"))
        self.assertEqual(row.per.amount, Decimal("20"))
        self.assertEqual(row.bps.amount, Decimal("50"))
        self.assertEqual(row.pbr.amount, Decimal("4"))
        self.assertEqual(row.roe.amount, Decimal("20.0"))
        self.assertEqual(row.dividend_yield.amount, Decimal("1.00"))
        self.assertEqual(row.missing_fields, ())

    def test_missing_fields_remain_explicit_when_no_source_can_fill_them(self) -> None:
        symbol = Symbol("000660")
        source = DataSourceRef(
            name="DART",
            kind=SourceKind.REGULATORY_FILING,
            as_of=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        resolver = FundamentalDataResolver(
            InMemoryFundamentalsSource(
                name="dart",
                statements=[
                    FinancialStatement(
                        symbol=symbol,
                        fiscal_period="2026.12",
                        currency=Currency("KRW"),
                        source=source,
                        diluted_shares=Decimal("728002365"),
                        is_estimate=True,
                    )
                ],
            )
        )

        row = resolver.rows(symbol, ["2026.12"])[0]

        self.assertIn("revenue", row.missing_fields)
        self.assertIn("eps", row.missing_fields)
        self.assertTrue(row.sources)

    def test_market_cap_can_fill_valuation_price_when_quote_is_missing(self) -> None:
        symbol = Symbol("000660")
        source = DataSourceRef(
            name="DART",
            kind=SourceKind.REGULATORY_FILING,
            as_of=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        market_source = DataSourceRef(
            name="KRX",
            kind=SourceKind.MARKET_DATA,
            as_of=datetime(2026, 3, 2, tzinfo=timezone.utc),
        )
        resolver = FundamentalDataResolver(
            InMemoryFundamentalsSource(
                name="dart_krx",
                statements=[
                    FinancialStatement(
                        symbol=symbol,
                        fiscal_period="2025.12",
                        currency=Currency("KRW"),
                        source=source,
                        net_income=Decimal("1000000"),
                        shareholders_equity=Decimal("5000000"),
                        diluted_shares=Decimal("1000"),
                    )
                ],
                market_references=[
                    MarketReference(
                        symbol=symbol,
                        currency=Currency("KRW"),
                        as_of=market_source.as_of,
                        source=market_source,
                        market_cap=Decimal("10000000"),
                    )
                ],
            )
        )

        row = resolver.rows(symbol, ["2025.12"])[0]

        self.assertEqual(row.eps.amount, Decimal("1000"))
        self.assertEqual(row.per.amount, Decimal("10"))
        self.assertEqual(row.pbr.amount, Decimal("2"))

    def test_period_specific_market_reference_fills_yearly_valuation_cells(self) -> None:
        symbol = Symbol("AAPL")
        filing_source = DataSourceRef(
            name="SEC Company Facts",
            kind=SourceKind.REGULATORY_FILING,
            as_of=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        market_source = DataSourceRef(
            name="NYSE close",
            kind=SourceKind.MARKET_DATA,
            as_of=datetime(2026, 2, 2, tzinfo=timezone.utc),
        )
        source = InMemoryFundamentalsSource(
            name="sec_market",
            statements=[
                FinancialStatement(
                    symbol=symbol,
                    fiscal_period="2023.12",
                    currency=Currency("USD"),
                    source=filing_source,
                    net_income=Decimal("1000"),
                    shareholders_equity=Decimal("4000"),
                    diluted_shares=Decimal("100"),
                ),
                FinancialStatement(
                    symbol=symbol,
                    fiscal_period="2024.12",
                    currency=Currency("USD"),
                    source=filing_source,
                    net_income=Decimal("2000"),
                    shareholders_equity=Decimal("5000"),
                    diluted_shares=Decimal("100"),
                ),
            ],
            market_references=[
                MarketReference(
                    symbol=symbol,
                    currency=Currency("USD"),
                    fiscal_period="2023.12",
                    as_of=market_source.as_of,
                    source=market_source,
                    price=Decimal("50"),
                ),
                MarketReference(
                    symbol=symbol,
                    currency=Currency("USD"),
                    fiscal_period="2024.12",
                    as_of=market_source.as_of,
                    source=market_source,
                    price=Decimal("100"),
                ),
            ],
        )

        rows = FundamentalDataResolver(source).rows(symbol, ["2023.12", "2024.12"])

        self.assertEqual(rows[0].per.amount, Decimal("5"))
        self.assertEqual(rows[0].pbr.amount, Decimal("1.25"))
        self.assertEqual(rows[1].per.amount, Decimal("5"))
        self.assertEqual(rows[1].pbr.amount, Decimal("2"))

    def test_coverage_planner_creates_actionable_requests_for_unfilled_cells(self) -> None:
        symbol = Symbol("000660")
        source = DataSourceRef(
            name="fundamentals_fallback",
            kind=SourceKind.ANALYST_ESTIMATE,
            as_of=datetime(2026, 3, 1, tzinfo=timezone.utc),
            confidence=Decimal("0.7"),
        )
        resolver = FundamentalDataResolver(
            InMemoryFundamentalsSource(
                name="fallback",
                statements=[
                    FinancialStatement(
                        symbol=symbol,
                        fiscal_period="2027.12(E)",
                        currency=Currency("KRW"),
                        source=source,
                        net_income=Decimal("2406779340000000"),
                        diluted_shares=Decimal("728002365"),
                        is_estimate=True,
                    )
                ],
            )
        )
        row = resolver.rows(symbol, ["2027.12(E)"])[0]

        requests = FundamentalCoveragePlanner().plan((row,))
        by_field = {request.target_field: request for request in requests}

        self.assertIn("revenue", by_field)
        self.assertEqual(
            by_field["per"].required_fields,
            ("period_end_price_or_market_cap",),
        )
        self.assertIn(SourceKind.MARKET_DATA, by_field["per"].recommended_sources)
        self.assertTrue(by_field["revenue"].estimate_allowed)
