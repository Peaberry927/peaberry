from __future__ import annotations

import re

from app.models import IndexQuote, Quote, Security, ValuationFields, parse_number, utc_now_iso
from app.providers.base import HttpClient, ProviderError, strip_html


class NaverFinanceProvider:
    source = "naver"

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
        eps = self._extract_label_value(html, "EPS")
        bps = self._extract_label_value(html, "BPS")

        if all(value is None for value in (per, pbr, eps, bps)):
            raise ProviderError(f"Naver valuation fields missing for {code}")

        return ValuationFields(
            ticker=security.normalized_ticker,
            per=per,
            pbr=pbr,
            eps=eps,
            bps=bps,
            source=self.source,
            as_of=utc_now_iso(),
            is_fallback=False,
        )

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
        pattern = rf">{re.escape(label)}<.*?<em[^>]*>(.*?)</em>"
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return parse_number(strip_html(match.group(1)))

        table_pattern = rf"{re.escape(label)}\s*</th>\s*<td[^>]*>(.*?)</td>"
        match = re.search(table_pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return parse_number(strip_html(match.group(1)))
        return None

