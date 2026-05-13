from __future__ import annotations

import re

from app.models import (
    AnnualFinancials,
    IndexQuote,
    Quote,
    Security,
    ValuationFields,
    parse_number,
    utc_now_iso,
)
from app.providers.base import HttpClient, ProviderError, strip_html


class NaverFinanceProvider:
    source = "naver"
    _KRW_EOKWON = 100_000_000
    _ANNUAL_METRIC_FIELDS = (
        "revenue",
        "operating_income",
        "net_income",
        "eps",
        "per",
        "bps",
        "pbr",
    )

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self.http = http_client or HttpClient()

    def _six_digit_code(self, security: Security) -> str:
        code = security.normalized_ticker.replace(".KS", "").replace(".KQ", "")
        if not re.fullmatch(r"\d{6}", code):
            raise ProviderError(f"Naver requires a six-digit Korean ticker: {security.ticker}")
        return code

    def fetch_current_price(self, security: Security) -> Quote:
        code = self._six_digit_code(security)
        html = self.http.get_text(
            "https://finance.naver.com/item/main.naver",
            {"code": code},
        )
        price = self._extract_by_id(html, "_nowVal") or self._extract_css_price(html)
        if price is None:
            raise ProviderError(f"Naver current price missing for {code}")
        return Quote(
            ticker=security.normalized_ticker,
            price=price,
            currency="KRW",
            source=self.source,
            as_of=utc_now_iso(),
            is_fallback=False,
        )

    def fetch_index(self, index_code: str) -> IndexQuote:
        normalized = index_code.strip().upper()
        if normalized not in {"KOSPI", "KOSDAQ"}:
            raise ProviderError(f"Unsupported Korean index: {index_code}")
        html = self.http.get_text(
            "https://finance.naver.com/sise/sise_index.naver",
            {"code": normalized},
        )
        value = self._extract_by_class(html, "now_value")
        if value is None:
            raise ProviderError(f"Naver index value missing for {normalized}")
        return IndexQuote(
            index_code=normalized,
            value=value,
            source=self.source,
            as_of=utc_now_iso(),
            is_fallback=False,
        )

    def fetch_valuation_fields(self, security: Security) -> ValuationFields:
        code = self._six_digit_code(security)
        html = self.http.get_text(
            "https://finance.naver.com/item/main.naver",
            {"code": code},
        )

        per = self._extract_by_id(html, "_per")
        pbr = self._extract_by_id(html, "_pbr")
        eps = self._extract_by_id(html, "_eps") or self._extract_label_value(html, "EPS")
        bps = self._extract_by_id(html, "_bps") or self._extract_label_value(html, "BPS")
        estimated_per = self._extract_by_id(html, "_cns_per")
        estimated_eps = self._extract_by_id(html, "_cns_eps")

        if all(value is None for value in (per, pbr, eps, bps, estimated_per, estimated_eps)):
            raise ProviderError(f"Naver valuation fields missing for {code}")

        return ValuationFields(
            ticker=security.normalized_ticker,
            per=per,
            pbr=pbr,
            eps=eps,
            bps=bps,
            estimated_per=estimated_per,
            estimated_eps=estimated_eps,
            source=self.source,
            as_of=utc_now_iso(),
            is_fallback=False,
        )

    def fetch_annual_metrics(self, security: Security) -> list[AnnualFinancials]:
        code = self._six_digit_code(security)
        html = self.http.get_text(
            "https://finance.naver.com/item/main.naver",
            {"code": code},
        )
        table = self._extract_financial_table(html)
        if table is None:
            raise ProviderError(f"Naver financial analysis table missing for {code}")

        periods = self._extract_annual_periods(table)
        if not periods:
            raise ProviderError(f"Naver annual periods missing for {code}")

        metrics_by_field = self._extract_annual_metric_values(table, len(periods))
        rows: list[AnnualFinancials] = []
        for index, (year, is_estimate) in enumerate(periods):
            values = {
                field: metrics_by_field.get(field, [None] * len(periods))[index]
                for field in self._ANNUAL_METRIC_FIELDS
            }
            for amount_field in ("revenue", "operating_income", "net_income"):
                if values[amount_field] is not None:
                    values[amount_field] = values[amount_field] * self._KRW_EOKWON
            if all(value is None for value in values.values()):
                continue
            rows.append(
                AnnualFinancials(
                    ticker=security.normalized_ticker,
                    year=year,
                    revenue=values["revenue"],
                    operating_income=values["operating_income"],
                    net_income=values["net_income"],
                    eps=values["eps"],
                    per=values["per"],
                    bps=values["bps"],
                    pbr=values["pbr"],
                    source=self.source,
                    as_of=utc_now_iso(),
                    is_fallback=False,
                    is_estimate=is_estimate,
                )
            )
        if not rows:
            raise ProviderError(f"Naver annual metrics empty for {code}")
        return rows

    def _extract_by_id(self, html: str, element_id: str) -> float | None:
        pattern = rf'id="{re.escape(element_id)}"[^>]*>(.*?)</'
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        return parse_number(strip_html(match.group(1)))

    def _extract_by_class(self, html: str, class_name: str) -> float | None:
        pattern = rf'class="{re.escape(class_name)}"[^>]*>(.*?)</'
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        return parse_number(strip_html(match.group(1)))

    def _extract_css_price(self, html: str) -> float | None:
        match = re.search(
            r'<p[^>]*class="no_today"[^>]*>.*?<span[^>]*class="blind"[^>]*>(.*?)</span>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None
        return parse_number(strip_html(match.group(1)))

    def _extract_label_value(self, html: str, label: str) -> float | None:
        table_pattern = (
            rf"<th[^>]*>\s*{re.escape(label)}(?:\([^<]*\))?\s*</th>\s*<td[^>]*>(.*?)</td>"
        )
        match = re.search(table_pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return parse_number(strip_html(match.group(1)))
        return None

    def _extract_financial_table(self, html: str) -> str | None:
        match = re.search(
            r'<table[^>]*class="tb_type1 tb_num tb_type1_ifrs"[^>]*>(.*?)</table>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None
        return match.group(0)

    def _extract_annual_periods(self, table_html: str) -> list[tuple[int, bool]]:
        thead_match = re.search(r"<thead>(.*?)</thead>", table_html, flags=re.IGNORECASE | re.DOTALL)
        if not thead_match:
            return []
        header_rows = re.findall(r"<tr[^>]*>(.*?)</tr>", thead_match.group(1), flags=re.DOTALL)
        if len(header_rows) < 2:
            return []
        periods: list[tuple[int, bool]] = []
        for cell in re.findall(r"<th[^>]*>(.*?)</th>", header_rows[1], flags=re.DOTALL):
            text = strip_html(cell).replace(" ", "")
            period = self._parse_annual_period(text)
            if period is None:
                continue
            if period[1] != 12:
                if periods:
                    break
                continue
            year = period[0]
            is_estimate = "(E)" in text.upper()
            periods.append((year, is_estimate))
        return periods

    def _parse_annual_period(self, text: str) -> tuple[int, int] | None:
        match = re.search(r"(20\d{2})\.(\d{2})", text)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2))

    def _extract_annual_metric_values(
        self,
        table_html: str,
        annual_count: int,
    ) -> dict[str, list[float | None]]:
        body_match = re.search(r"<tbody>(.*?)</tbody>", table_html, flags=re.IGNORECASE | re.DOTALL)
        if not body_match:
            return {}

        values: dict[str, list[float | None]] = {}
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body_match.group(1), flags=re.DOTALL):
            th_match = re.search(r"<th[^>]*>(.*?)</th>", row_html, flags=re.DOTALL)
            if not th_match:
                continue
            label = strip_html(th_match.group(1))
            field = self._map_metric_field(label)
            if field is None:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.DOTALL)
            parsed = [parse_number(strip_html(cell)) for cell in cells[:annual_count]]
            while len(parsed) < annual_count:
                parsed.append(None)
            values[field] = parsed
        return values

    def _map_metric_field(self, label: str) -> str | None:
        compact = label.replace(" ", "").upper()
        if compact.startswith("매출액"):
            return "revenue"
        if compact.startswith("영업이익"):
            return "operating_income"
        if compact.startswith("당기순이익"):
            return "net_income"
        if compact.startswith("EPS"):
            return "eps"
        if compact.startswith("PER"):
            return "per"
        if compact.startswith("BPS"):
            return "bps"
        if compact.startswith("PBR"):
            return "pbr"
        return None

