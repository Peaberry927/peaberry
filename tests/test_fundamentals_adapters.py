from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest import TestCase

from peaberry.domain.fundamentals import Currency, SourceKind
from peaberry.domain.market import Symbol
from peaberry.fundamentals import FundamentalDataPipeline, build_fundamentals_source
from peaberry.fundamentals.adapters import (
    FallbackMarketDataSource,
    KrxDailyMarketDataSource,
    NaverChartMarketDataSource,
    OpenDartFundamentalsSource,
    SecCompanyFactsSource,
    YahooChartMarketDataSource,
)


class FakeJsonHttpClient:
    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self.responses = responses
        self.requested_urls: list[str] = []

    def get_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self.requested_urls.append(url)
        for key, response in self.responses.items():
            if key in url:
                return response
        raise AssertionError(f"unexpected URL: {url}")


class FundamentalsAdapterTests(TestCase):
    def test_sec_company_facts_source_parses_annual_statement_fields(self) -> None:
        symbol = Symbol("AAPL")
        source = SecCompanyFactsSource(
            symbol_to_cik={symbol: "320193"},
            http_client=FakeJsonHttpClient(
                {
                    "CIK0000320193.json": {
                        "facts": {
                            "us-gaap": {
                                "Revenues": {
                                    "units": {
                                        "USD": [
                                            {
                                                "fy": 2024,
                                                "fp": "FY",
                                                "form": "10-K",
                                                "val": 391035000000,
                                                "end": "2024-09-28",
                                                "filed": "2024-11-01",
                                                "accn": "a",
                                            }
                                        ]
                                    }
                                },
                                "OperatingIncomeLoss": {
                                    "units": {
                                        "USD": [
                                            {
                                                "fy": 2024,
                                                "fp": "FY",
                                                "form": "10-K",
                                                "val": 123216000000,
                                                "end": "2024-09-28",
                                                "filed": "2024-11-01",
                                                "accn": "a",
                                            }
                                        ]
                                    }
                                },
                                "NetIncomeLoss": {
                                    "units": {
                                        "USD": [
                                            {
                                                "fy": 2024,
                                                "fp": "FY",
                                                "form": "10-K",
                                                "val": 93736000000,
                                                "end": "2024-09-28",
                                                "filed": "2024-11-01",
                                                "accn": "a",
                                            }
                                        ]
                                    }
                                },
                                "StockholdersEquity": {
                                    "units": {
                                        "USD": [
                                            {
                                                "fy": 2024,
                                                "fp": "FY",
                                                "form": "10-K",
                                                "val": 56950000000,
                                                "end": "2024-09-28",
                                                "filed": "2024-11-01",
                                                "accn": "a",
                                            }
                                        ]
                                    }
                                },
                                "WeightedAverageNumberOfDilutedSharesOutstanding": {
                                    "units": {
                                        "shares": [
                                            {
                                                "fy": 2024,
                                                "fp": "FY",
                                                "form": "10-K",
                                                "val": 15343783000,
                                                "end": "2024-09-28",
                                                "filed": "2024-11-01",
                                                "accn": "a",
                                            }
                                        ]
                                    }
                                },
                            }
                        }
                    }
                }
            ),
        )

        statement = tuple(source.statements(symbol, ["2024.12"]))[0]

        self.assertEqual(statement.revenue, Decimal("391035000000"))
        self.assertEqual(statement.operating_income, Decimal("123216000000"))
        self.assertEqual(statement.net_income, Decimal("93736000000"))
        self.assertEqual(statement.diluted_shares, Decimal("15343783000"))
        self.assertEqual(statement.currency, Currency("USD"))

    def test_open_dart_source_parses_korean_statement_fields(self) -> None:
        symbol = Symbol("000660")
        source = OpenDartFundamentalsSource(
            api_key="test",
            symbol_to_corp_code={symbol: "00164779"},
            http_client=FakeJsonHttpClient(
                {
                    "fnlttSinglAcntAll.json": {
                        "status": "000",
                        "list": [
                            {"account_nm": "매출액", "thstrm_amount": "66,193,000,000,000"},
                            {"account_nm": "영업이익", "thstrm_amount": "23,467,300,000,000"},
                            {"account_nm": "당기순이익", "thstrm_amount": "19,796,900,000,000"},
                            {"account_nm": "자본총계", "thstrm_amount": "99,999,000,000,000"},
                        ],
                    }
                }
            ),
        )

        statement = tuple(source.statements(symbol, ["2024.12"]))[0]

        self.assertEqual(statement.currency, Currency("KRW"))
        self.assertEqual(statement.revenue, Decimal("66193000000000"))
        self.assertEqual(statement.operating_income, Decimal("23467300000000"))
        self.assertEqual(statement.net_income, Decimal("19796900000000"))
        self.assertEqual(statement.shareholders_equity, Decimal("99999000000000"))

    def test_yahoo_chart_source_parses_period_end_close(self) -> None:
        symbol = Symbol("AAPL")
        target = int(datetime(2024, 12, 31, tzinfo=timezone.utc).timestamp())
        source = YahooChartMarketDataSource(
            symbol_to_ticker={symbol: "AAPL"},
            http_client=FakeJsonHttpClient(
                {
                    "finance/chart/AAPL": {
                        "chart": {
                            "result": [
                                {
                                    "meta": {"currency": "USD"},
                                    "timestamp": [target - 86400, target],
                                    "indicators": {
                                        "quote": [{"close": [Decimal("249.50"), Decimal("250.00")]}]
                                    },
                                }
                            ]
                        }
                    }
                }
            ),
        )

        reference = source.market_reference(symbol, "2024.12")

        self.assertEqual(reference.price, Decimal("250.00"))
        self.assertEqual(reference.currency, Currency("USD"))
        self.assertEqual(reference.fiscal_period, "2024.12")

    def test_yahoo_chart_source_uses_latest_price_for_future_estimate_period(self) -> None:
        symbol = Symbol("AAPL")
        latest_at = int(datetime(2026, 5, 11, tzinfo=timezone.utc).timestamp())
        source = YahooChartMarketDataSource(
            symbol_to_ticker={symbol: "AAPL"},
            http_client=FakeJsonHttpClient(
                {
                    "finance/chart/AAPL": {
                        "chart": {
                            "result": [
                                {
                                    "meta": {"currency": "USD"},
                                    "timestamp": [latest_at],
                                    "indicators": {"quote": [{"close": [180.0]}]},
                                }
                            ]
                        }
                    }
                }
            ),
        )

        reference = source.market_reference(symbol, "2027.12(E)")

        self.assertEqual(reference.price, Decimal("180.0"))
        self.assertEqual(reference.fiscal_period, "2027.12(E)")

    def test_domestic_fallback_keeps_going_when_primary_market_source_fails(self) -> None:
        class BrokenMarketSource:
            name = "Yahoo Finance Chart"

            def statements(self, symbol, fiscal_periods):
                return ()

            def market_reference(self, symbol, fiscal_period=None):
                raise RuntimeError("too many requests")

        symbol = Symbol("000660")
        naver = NaverChartMarketDataSource(
            symbol_to_code={symbol: "000660"},
            http_client=FakeJsonHttpClient(
                {
                    "api.stock.naver.com": {
                        "data": [
                            {"localDate": "20241230", "closePrice": "171,000"},
                            {"localDate": "20241231", "closePrice": "173,000"},
                        ]
                    }
                }
            ),
        )
        fallback = FallbackMarketDataSource(
            "domestic_market_fallback",
            [BrokenMarketSource(), naver],
        )

        reference = fallback.market_reference(symbol, "2024.12")

        self.assertEqual(reference.price, Decimal("173000"))
        self.assertEqual(fallback.source_errors[0][0], "Yahoo Finance Chart")

    def test_krx_source_parses_close_and_market_cap(self) -> None:
        symbol = Symbol("000660")
        source = KrxDailyMarketDataSource(
            symbol_to_code={symbol: "000660"},
            http_client=FakeJsonHttpClient(
                {
                    "stk_bydd_trd": {
                        "OutBlock_1": [
                            {
                                "BAS_DD": "20241230",
                                "CLSPRC": "171,000",
                                "MKTCAP": "124,488,404,415,000",
                            }
                        ]
                    }
                }
            ),
        )

        reference = source.market_reference(symbol, "2024.12")

        self.assertEqual(reference.currency, Currency("KRW"))
        self.assertEqual(reference.price, Decimal("171000"))
        self.assertEqual(reference.market_cap, Decimal("124488404415000"))

    def test_factory_pipeline_acquires_and_resolves_sec_plus_market_data(self) -> None:
        symbol = Symbol("AAPL")
        close_at = int(datetime(2024, 12, 31, tzinfo=timezone.utc).timestamp())
        http = FakeJsonHttpClient(
            {
                "CIK0000320193.json": {
                    "facts": {
                        "us-gaap": {
                            "NetIncomeLoss": {
                                "units": {
                                    "USD": [
                                        {
                                            "fy": 2024,
                                            "fp": "FY",
                                            "form": "10-K",
                                            "val": 1000,
                                            "end": "2024-12-31",
                                            "filed": "2025-02-01",
                                            "accn": "a",
                                        }
                                    ]
                                }
                            },
                            "WeightedAverageNumberOfDilutedSharesOutstanding": {
                                "units": {
                                    "shares": [
                                        {
                                            "fy": 2024,
                                            "fp": "FY",
                                            "form": "10-K",
                                            "val": 100,
                                            "end": "2024-12-31",
                                            "filed": "2025-02-01",
                                            "accn": "a",
                                        }
                                    ]
                                }
                            },
                        }
                    }
                },
                "finance/chart/AAPL": {
                    "chart": {
                        "result": [
                            {
                                "meta": {"currency": "USD"},
                                "timestamp": [close_at],
                                "indicators": {"quote": [{"close": [200]}]},
                            }
                        ]
                    }
                },
            }
        )
        source = build_fundamentals_source(
            sec_ciks={symbol: "320193"},
            market_tickers={symbol: "AAPL"},
            http_client=http,
        )

        result = FundamentalDataPipeline(source).run(symbol, ["2024.12"])

        self.assertEqual(result.rows[0].eps.amount, Decimal("10"))
        self.assertEqual(result.rows[0].per.amount, Decimal("20"))
        self.assertEqual(result.rows[0].sources[0].kind, SourceKind.REGULATORY_FILING)

    def test_factory_domestic_market_fallback_reports_failed_provider(self) -> None:
        symbol = Symbol("000660")
        source = build_fundamentals_source(
            market_tickers={symbol: "000660.KS"},
            market_currencies={symbol: Currency("KRW")},
            domestic_market_codes={symbol: "000660"},
            http_client=FakeJsonHttpClient(
                {
                    "stk_bydd_trd": {
                        "OutBlock_1": [
                            {
                                "BAS_DD": "20241230",
                                "CLSPRC": "171,000",
                                "MKTCAP": "124,488,404,415,000",
                            }
                        ]
                    }
                }
            ),
        )

        reference = source.market_reference(symbol, "2024.12")

        self.assertEqual(reference.price, Decimal("171000"))
        self.assertEqual(source.source_errors[0][0], "Yahoo Finance Chart")
