import os
from unittest import TestCase, skipUnless

from peaberry.domain.fundamentals import Currency
from peaberry.domain.market import Symbol
from peaberry.fundamentals import FundamentalDataPipeline, build_fundamentals_source


LIVE_SMOKE = os.environ.get("PEABERRY_LIVE_SMOKE") == "1"


class LiveFundamentalsSmokeTests(TestCase):
    @skipUnless(LIVE_SMOKE, "set PEABERRY_LIVE_SMOKE=1 to run live API smoke tests")
    def test_aapl_sec_and_yahoo_smoke(self) -> None:
        symbol = Symbol("AAPL")
        source = build_fundamentals_source(
            sec_ciks={symbol: "320193"},
            market_tickers={symbol: "AAPL"},
            market_currencies={symbol: Currency("USD")},
            sec_user_agent=os.environ.get(
                "SEC_USER_AGENT",
                "peaberry/0.1 smoke@example.com",
            ),
        )

        result = FundamentalDataPipeline(source).run(symbol, ["2024.12"])
        row = result.rows[0]

        self.assertIsNotNone(row.revenue)
        self.assertIsNotNone(row.eps)
        self.assertIsNotNone(row.per)

    @skipUnless(
        LIVE_SMOKE and bool(os.environ.get("DART_API_KEY")),
        "set PEABERRY_LIVE_SMOKE=1 and DART_API_KEY to run Korean live API smoke tests",
    )
    def test_korean_dart_and_market_fallback_smoke(self) -> None:
        symbol = Symbol(os.environ.get("PEABERRY_KR_SYMBOL", "000660"))
        corp_code = os.environ.get("PEABERRY_DART_CORP_CODE", "00164779")
        source = build_fundamentals_source(
            dart_corp_codes={symbol: corp_code},
            dart_api_key=os.environ["DART_API_KEY"],
            market_tickers={symbol: f"{symbol}.KS"},
            market_currencies={symbol: Currency("KRW")},
            domestic_market_codes={symbol: str(symbol)},
        )

        result = FundamentalDataPipeline(source).run(symbol, ["2024.12"])
        row = result.rows[0]

        self.assertTrue(row.sources)
        self.assertTrue(row.revenue or row.net_income or row.per or row.pbr)
