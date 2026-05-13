from __future__ import annotations

import io
import os
import re
import xml.etree.ElementTree as ET
import zipfile

from app.models import AnnualFinancials, Security, parse_number, utc_now_iso
from app.providers.base import HttpClient, ProviderError


REPORT_CODE_ANNUAL = "11011"
PREFERRED_FS_DIVS = ("CFS", "OFS")
RETRYABLE_STATUS_CODES = {"013"}
DART_COMPANY_SEARCH_URL = "https://dart.fss.or.kr/html/search/SearchCompany_M2.html"


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
        self._corp_codes_by_stock: dict[str, str] | None = None

    def fetch_annual_financials(self, security: Security, year: int) -> AnnualFinancials:
        if not self.api_key:
            raise ProviderError("OPENDART_API_KEY is required for OpenDART annuals")
        corp_code = self._resolve_corp_code(security)

        for index, fs_div in enumerate(PREFERRED_FS_DIVS):
            payload = self._fetch_statement_payload(corp_code, year, fs_div)
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

    def _fetch_statement_payload(self, corp_code: str, year: int, fs_div: str) -> dict:
        return self.http.get_json(
            "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
            {
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": REPORT_CODE_ANNUAL,
                "fs_div": fs_div,
            },
        )

    def _resolve_corp_code(self, security: Security) -> str:
        if security.corp_code:
            return security.corp_code

        stock_code = security.normalized_ticker.replace(".KS", "").replace(".KQ", "")
        if not re.fullmatch(r"\d{6}", stock_code):
            raise ProviderError(f"OpenDART corp_code missing for {security.ticker}")

        if self._corp_codes_by_stock and stock_code in self._corp_codes_by_stock:
            return self._corp_codes_by_stock[stock_code]

        corp_code = self._fetch_corp_code_from_search(stock_code)
        if corp_code:
            if self._corp_codes_by_stock is None:
                self._corp_codes_by_stock = {}
            self._corp_codes_by_stock[stock_code] = corp_code
            return corp_code

        corp_code = self._load_corp_codes_by_stock().get(stock_code)
        if not corp_code:
            raise ProviderError(f"OpenDART corp_code not found for {security.ticker}")
        return corp_code

    def _fetch_corp_code_from_search(self, stock_code: str) -> str | None:
        try:
            html = self.http.get_text(DART_COMPANY_SEARCH_URL, {"textCrpNM": stock_code})
        except ProviderError:
            return None
        match = re.search(r'id="textCrpCik"[^>]*value=["\'](\d{8})["\']', html, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1)

    def _load_corp_codes_by_stock(self) -> dict[str, str]:
        if self._corp_codes_by_stock is not None:
            return self._corp_codes_by_stock

        payload = self.http.get_bytes(
            "https://opendart.fss.or.kr/api/corpCode.xml",
            {"crtfc_key": self.api_key},
        )
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                names = archive.namelist()
                if not names:
                    raise ProviderError("OpenDART corpCode archive was empty")
                with archive.open(names[0]) as xml_file:
                    xml_text = xml_file.read().decode("utf-8", errors="replace")
        except (zipfile.BadZipFile, OSError) as exc:
            raise ProviderError("OpenDART corpCode payload could not be decoded") from exc

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ProviderError("OpenDART corpCode XML could not be parsed") from exc

        mapping: dict[str, str] = {}
        for item in root.findall(".//list"):
            stock_code = (item.findtext("stock_code") or "").strip()
            corp_code = (item.findtext("corp_code") or "").strip()
            if re.fullmatch(r"\d{6}", stock_code) and corp_code:
                mapping[stock_code] = corp_code
        self._corp_codes_by_stock = mapping
        return mapping

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

