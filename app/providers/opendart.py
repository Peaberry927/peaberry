from __future__ import annotations

import os
import re

from app.models import AnnualFinancials, Security, parse_number, utc_now_iso
from app.providers.base import HttpClient, ProviderError


REPORT_CODE_ANNUAL = "11011"
PREFERRED_FS_DIVS = ("CFS", "OFS")
RETRYABLE_STATUS_CODES = {"013"}


class OpenDartProvider:
    source = "opendart"

    ACCOUNT_ALIASES = {
        "revenue": {"매출액", "수익(매출액)", "영업수익", "매출액(영업수익)", "수익"},
        "operating_income": {"영업이익", "영업손실", "영업이익(손실)"},
        "net_income": {"당기순이익", "당기순손실", "당기순손익", "분기순이익", "반기순이익"},
        "assets": {"자산총계"},
        "liabilities": {"부채총계"},
        "equity": {"자본총계"},
    }
    ACCOUNT_ID_ALIASES = {
        "revenue": {"ifrs-full_revenue"},
        "operating_income": {
            "dart_operatingincomeloss",
            "ifrs-full_profitlossfromoperatingactivities",
        },
        "net_income": {"ifrs-full_profitloss", "dart_profitloss"},
        "assets": {"ifrs-full_assets"},
        "liabilities": {"ifrs-full_liabilities"},
        "equity": {"ifrs-full_equity"},
    }

    def __init__(
        self,
        api_key: str | None = None,
        http_client: HttpClient | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENDART_API_KEY")
        self.http = http_client or HttpClient()

    def fetch_annual_financials(self, security: Security, year: int) -> AnnualFinancials:
        if not self.api_key:
            raise ProviderError("OPENDART_API_KEY is required for OpenDART annuals")
        if not security.corp_code:
            raise ProviderError(f"OpenDART corp_code missing for {security.ticker}")

        for index, fs_div in enumerate(PREFERRED_FS_DIVS):
            payload = self._fetch_statement_payload(security, year, fs_div)
            status = str(payload.get("status", ""))
            rows = payload.get("list") or []

            if status and status != "000":
                if status in RETRYABLE_STATUS_CODES and index < len(PREFERRED_FS_DIVS) - 1:
                    continue
                message = payload.get("message", "unknown OpenDART error")
                raise ProviderError(f"OpenDART status {status}: {message}")

            if not rows:
                if index < len(PREFERRED_FS_DIVS) - 1:
                    continue
                raise ProviderError(f"OpenDART annual statement empty for {security.ticker} {year}")

            metrics = self._extract_metrics(rows)
            if any(value is not None for value in metrics.values()):
                return AnnualFinancials(
                    ticker=security.normalized_ticker,
                    year=year,
                    revenue=metrics["revenue"],
                    operating_income=metrics["operating_income"],
                    net_income=metrics["net_income"],
                    assets=metrics["assets"],
                    liabilities=metrics["liabilities"],
                    equity=metrics["equity"],
                    source=self.source,
                    as_of=utc_now_iso(),
                    is_fallback=False,
                )

            if index < len(PREFERRED_FS_DIVS) - 1:
                continue
            raise ProviderError(
                f"OpenDART annual statement did not contain recognized accounts for "
                f"{security.ticker} {year}"
            )

        raise ProviderError(f"OpenDART annual statement empty for {security.ticker} {year}")

    def _fetch_statement_payload(self, security: Security, year: int, fs_div: str) -> dict:
        return self.http.get_json(
            "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
            {
                "crtfc_key": self.api_key,
                "corp_code": security.corp_code,
                "bsns_year": str(year),
                "reprt_code": REPORT_CODE_ANNUAL,
                "fs_div": fs_div,
            },
        )

    def _extract_metrics(self, rows: list[dict]) -> dict[str, float | None]:
        metrics: dict[str, float | None] = {
            "revenue": None,
            "operating_income": None,
            "net_income": None,
            "assets": None,
            "liabilities": None,
            "equity": None,
        }
        for row in rows:
            amount = parse_number(row.get("thstrm_amount"))
            if amount is None:
                continue
            for metric_name in metrics:
                if metrics[metric_name] is None and self._matches_metric(metric_name, row):
                    metrics[metric_name] = amount
        return metrics

    def _matches_metric(self, metric_name: str, row: dict) -> bool:
        account_name = self._normalize(str(row.get("account_nm", "")))
        account_id = self._normalize(str(row.get("account_id", "")))
        for alias in self.ACCOUNT_ALIASES[metric_name]:
            normalized_alias = self._normalize(alias)
            if normalized_alias and normalized_alias in account_name:
                return True
        return any(account_id == self._normalize(alias) for alias in self.ACCOUNT_ID_ALIASES[metric_name])

    def _normalize(self, value: str) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]+", "", value).lower()

