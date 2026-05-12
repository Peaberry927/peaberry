from __future__ import annotations

from typing import Any

from app.models import AnnualFinancials, Quote, Security, ValuationFields, utc_now_iso
from app.providers.base import HttpClient, ProviderError


class YahooFinanceProvider:
    source = "yahoo"

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self.http = http_client or HttpClient()

    def _require_us(self, security: Security) -> None:
        if not security.is_us:
            raise ProviderError(
                f"Yahoo fallback is allowed for US stocks only, got {security.ticker}"
            )

    def fetch_current_price(self, security: Security) -> Quote:
        self._require_us(security)
        quote = self._quote_summary(security.normalized_ticker)
        price = quote.get("regularMarketPrice")
        if isinstance(price, dict):
            price = price.get("raw")
        if price is None:
            raise ProviderError(f"Yahoo current price missing for {security.ticker}")
        return Quote(
            ticker=security.normalized_ticker,
            price=float(price),
            currency=quote.get("currency"),
            source=self.source,
            as_of=utc_now_iso(),
            is_fallback=True,
        )

    def fetch_valuation_fields(self, security: Security) -> ValuationFields:
        self._require_us(security)
        quote = self._quote_summary(security.normalized_ticker)
        summary = self._summary_detail(security.normalized_ticker)

        per = self._raw(quote.get("trailingPE")) or self._raw(summary.get("trailingPE"))
        pbr = self._raw(quote.get("priceToBook")) or self._raw(summary.get("priceToBook"))
        eps = self._raw(quote.get("epsTrailingTwelveMonths"))
        bps = None

        if all(value is None for value in (per, pbr, eps, bps)):
            raise ProviderError(f"Yahoo valuation fields missing for {security.ticker}")

        return ValuationFields(
            ticker=security.normalized_ticker,
            per=per,
            pbr=pbr,
            eps=eps,
            bps=bps,
            source=self.source,
            as_of=utc_now_iso(),
            is_fallback=True,
        )

    def fetch_annual_financials(self, security: Security, year: int) -> AnnualFinancials:
        self._require_us(security)
        payload = self.http.get_json(
            f"https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{security.normalized_ticker}",
            {
                "type": ",".join(
                    [
                        "annualTotalRevenue",
                        "annualOperatingIncome",
                        "annualNetIncome",
                        "annualTotalAssets",
                        "annualTotalLiabilitiesNetMinorityInterest",
                        "annualStockholdersEquity",
                    ]
                )
            },
        )
        timeseries = (payload.get("timeseries") or {}).get("result") or []
        metrics = self._extract_timeseries_metrics(timeseries, year)
        if all(value is None for value in metrics.values()):
            raise ProviderError(f"Yahoo annual financials missing for {security.ticker} {year}")
        return AnnualFinancials(
            ticker=security.normalized_ticker,
            year=year,
            revenue=metrics["annualTotalRevenue"],
            operating_income=metrics["annualOperatingIncome"],
            net_income=metrics["annualNetIncome"],
            assets=metrics["annualTotalAssets"],
            liabilities=metrics["annualTotalLiabilitiesNetMinorityInterest"],
            equity=metrics["annualStockholdersEquity"],
            source=self.source,
            as_of=utc_now_iso(),
            is_fallback=True,
        )

    def _quote_summary(self, symbol: str) -> dict[str, Any]:
        payload = self.http.get_json(
            "https://query1.finance.yahoo.com/v7/finance/quote",
            {"symbols": symbol},
        )
        result = ((payload.get("quoteResponse") or {}).get("result") or [])
        if not result:
            raise ProviderError(f"Yahoo quote response empty for {symbol}")
        return result[0]

    def _summary_detail(self, symbol: str) -> dict[str, Any]:
        payload = self.http.get_json(
            f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}",
            {"modules": "summaryDetail"},
        )
        result = ((payload.get("quoteSummary") or {}).get("result") or [])
        if not result:
            return {}
        return result[0].get("summaryDetail") or {}

    def _raw(self, value: Any) -> float | None:
        if isinstance(value, dict):
            value = value.get("raw")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _extract_timeseries_metrics(
        self, rows: list[dict[str, Any]], year: int
    ) -> dict[str, float | None]:
        metrics = {
            "annualTotalRevenue": None,
            "annualOperatingIncome": None,
            "annualNetIncome": None,
            "annualTotalAssets": None,
            "annualTotalLiabilitiesNetMinorityInterest": None,
            "annualStockholdersEquity": None,
        }
        for row in rows:
            metric_name = str(row.get("meta", {}).get("type", [""])[0])
            if metric_name not in metrics:
                continue
            for item in row.get(metric_name, []):
                as_of = str(item.get("asOfDate", ""))
                if as_of.startswith(str(year)):
                    metrics[metric_name] = self._raw(item.get("reportedValue"))
                    break
        return metrics

