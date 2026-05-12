from __future__ import annotations

import os

from app.models import AnnualFinancials, Security, parse_number, utc_now_iso
from app.providers.base import HttpClient, ProviderError


REPORT_CODE_ANNUAL = "11011"
DEFAULT_FS_DIV = "CFS"


class OpenDartProvider:
    source = "opendart"

    ACCOUNT_ALIASES = {
        "revenue": {"매출액", "수익(매출액)", "영업수익"},
        "operating_income": {"영업이익", "영업손실"},
        "net_income": {"당기순이익", "당기순손실", "분기순이익"},
        "assets": {"자산총계"},
        "liabilities": {"부채총계"},
        "equity": {"자본총계"},
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

        payload = self.http.get_json(
            "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
            {
                "crtfc_key": self.api_key,
                "corp_code": security.corp_code,
                "bsns_year": str(year),
                "reprt_code": REPORT_CODE_ANNUAL,
                "fs_div": DEFAULT_FS_DIV,
            },
        )

        status = str(payload.get("status", ""))
        if status and status != "000":
            message = payload.get("message", "unknown OpenDART error")
            raise ProviderError(f"OpenDART status {status}: {message}")

        rows = payload.get("list") or []
        if not rows:
            raise ProviderError(f"OpenDART annual statement empty for {security.ticker} {year}")

        metrics: dict[str, float | None] = {
            "revenue": None,
            "operating_income": None,
            "net_income": None,
            "assets": None,
            "liabilities": None,
            "equity": None,
        }

        for row in rows:
            account_name = str(row.get("account_nm", "")).strip()
            amount = parse_number(row.get("thstrm_amount"))
            if amount is None:
                continue
            for metric_name, aliases in self.ACCOUNT_ALIASES.items():
                if metrics[metric_name] is None and account_name in aliases:
                    metrics[metric_name] = amount

        if all(value is None for value in metrics.values()):
            raise ProviderError(
                f"OpenDART annual statement did not contain recognized accounts for "
                f"{security.ticker} {year}"
            )

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

