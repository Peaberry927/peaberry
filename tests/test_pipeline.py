from __future__ import annotations

import tempfile
import unittest

from app.models import AnnualFinancials, Quote, Security, ValuationFields, utc_now_iso
from app.pipeline import QuantDataPipeline
from app.providers import ProviderError
from app.storage import SQLiteStore


class FakeNaver:
    def __init__(self) -> None:
        self.price_calls = 0
        self.valuation_calls = 0

    def fetch_current_price(self, security: Security) -> Quote:
        self.price_calls += 1
        return Quote(
            ticker=security.normalized_ticker,
            price=194000,
            currency="KRW",
            source="naver",
            as_of=utc_now_iso(),
            is_fallback=False,
        )

    def fetch_index(self, index_code: str):
        raise NotImplementedError

    def fetch_valuation_fields(self, security: Security) -> ValuationFields:
        self.valuation_calls += 1
        return ValuationFields(
            ticker=security.normalized_ticker,
            per=8.1,
            pbr=1.3,
            eps=24000,
            bps=149000,
            source="naver",
            as_of=utc_now_iso(),
            is_fallback=False,
        )


class FakeOpenDart:
    def __init__(self, should_fail: bool = False, fail_years: set[int] | None = None) -> None:
        self.calls = 0
        self.should_fail = should_fail
        self.fail_years = fail_years or set()

    def fetch_annual_financials(self, security: Security, year: int) -> AnnualFinancials:
        self.calls += 1
        if self.should_fail or year in self.fail_years:
            raise ProviderError("OpenDART unavailable")
        return AnnualFinancials(
            ticker=security.normalized_ticker,
            year=year,
            revenue=100,
            operating_income=20,
            net_income=10,
            assets=500,
            liabilities=200,
            equity=300,
            source="opendart",
            as_of=utc_now_iso(),
            is_fallback=False,
        )


class FakeYahoo:
    def __init__(self) -> None:
        self.price_calls = 0
        self.valuation_calls = 0
        self.annual_calls = 0

    def fetch_current_price(self, security: Security) -> Quote:
        self.price_calls += 1
        return Quote(
            ticker=security.normalized_ticker,
            price=200,
            currency="USD",
            source="yahoo",
            as_of=utc_now_iso(),
            is_fallback=True,
        )

    def fetch_valuation_fields(self, security: Security) -> ValuationFields:
        self.valuation_calls += 1
        return ValuationFields(
            ticker=security.normalized_ticker,
            per=30,
            pbr=9,
            eps=6,
            bps=None,
            source="yahoo",
            as_of=utc_now_iso(),
            is_fallback=True,
        )

    def fetch_annual_financials(self, security: Security, year: int) -> AnnualFinancials:
        self.annual_calls += 1
        return AnnualFinancials(
            ticker=security.normalized_ticker,
            year=year,
            revenue=400,
            operating_income=120,
            net_income=90,
            assets=800,
            liabilities=300,
            equity=500,
            source="yahoo",
            as_of=utc_now_iso(),
            is_fallback=True,
        )


class PipelineTests(unittest.TestCase):
    def make_pipeline(self, naver=None, opendart=None, yahoo=None):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        store = SQLiteStore(f"{temp_dir.name}/test.db")
        return QuantDataPipeline(
            store=store,
            naver=naver or FakeNaver(),
            opendart=opendart or FakeOpenDart(),
            yahoo=yahoo or FakeYahoo(),
        )

    def test_korean_equity_uses_naver_and_opendart_not_yahoo(self) -> None:
        naver = FakeNaver()
        opendart = FakeOpenDart()
        yahoo = FakeYahoo()
        pipeline = self.make_pipeline(naver=naver, opendart=opendart, yahoo=yahoo)
        security = Security(ticker="000660", market="KOSPI", corp_code="00164779")

        pipeline.get_current_price(security)
        pipeline.get_annual_financials(security, [2024])
        pipeline.get_valuation_fields(security)

        self.assertEqual(naver.price_calls, 1)
        self.assertEqual(naver.valuation_calls, 1)
        self.assertEqual(opendart.calls, 1)
        self.assertEqual(yahoo.price_calls, 0)
        self.assertEqual(yahoo.annual_calls, 0)
        self.assertEqual(yahoo.valuation_calls, 0)

    def test_us_equity_uses_yahoo_fallback(self) -> None:
        yahoo = FakeYahoo()
        pipeline = self.make_pipeline(yahoo=yahoo)
        security = Security(ticker="AAPL", market="US")

        quote = pipeline.get_current_price(security)
        annual = pipeline.get_annual_financials(security, [2024])[0]
        valuation = pipeline.get_valuation_fields(security)

        self.assertTrue(quote.is_fallback)
        self.assertTrue(annual.is_fallback)
        self.assertTrue(valuation.is_fallback)
        self.assertEqual(yahoo.price_calls, 1)
        self.assertEqual(yahoo.annual_calls, 1)
        self.assertEqual(yahoo.valuation_calls, 1)

    def test_open_dart_failure_does_not_call_yahoo_for_korean_stock(self) -> None:
        yahoo = FakeYahoo()
        pipeline = self.make_pipeline(opendart=FakeOpenDart(should_fail=True), yahoo=yahoo)
        security = Security(ticker="000660", market="KOSPI", corp_code="00164779")

        with self.assertRaises(ProviderError):
            pipeline.get_annual_financials(security, [2024])

        self.assertEqual(yahoo.annual_calls, 0)

    def test_partial_annual_failures_keep_available_years(self) -> None:
        pipeline = self.make_pipeline(opendart=FakeOpenDart(fail_years={2025}))
        security = Security(ticker="000660", market="KOSPI", corp_code="00164779")

        annuals = pipeline.get_annual_financials(security, [2025, 2024, 2023])

        self.assertEqual([item.year for item in annuals], [2024, 2023])

    def test_clear_stale_fallback_values_removes_non_us_fallbacks_only(self) -> None:
        pipeline = self.make_pipeline()
        kr = Security(ticker="000660", market="KOSPI")
        us = Security(ticker="AAPL", market="US")
        pipeline.store.upsert_security(kr)
        pipeline.store.upsert_security(us)

        pipeline.store.save_valuation_fields(
            ValuationFields(
                ticker="000660",
                per=10,
                pbr=1,
                eps=100,
                bps=1000,
                source="yahoo",
                as_of=utc_now_iso(),
                is_fallback=True,
            )
        )
        pipeline.store.save_valuation_fields(
            ValuationFields(
                ticker="AAPL",
                per=30,
                pbr=9,
                eps=6,
                bps=None,
                source="yahoo",
                as_of=utc_now_iso(),
                is_fallback=True,
            )
        )

        deleted = pipeline.clear_stale_fallback_values()

        self.assertEqual(deleted, 1)
        self.assertIsNone(pipeline.store.load_valuation_fields("000660"))
        self.assertIsNotNone(pipeline.store.load_valuation_fields("AAPL"))


if __name__ == "__main__":
    unittest.main()

