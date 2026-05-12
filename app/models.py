from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text in {"-", "N/A", "nan", "None"}:
        return None

    multiplier = 1.0
    if text.startswith("(") and text.endswith(")"):
        multiplier = -1.0
        text = text[1:-1]

    text = (
        text.replace(",", "")
        .replace("원", "")
        .replace("KRW", "")
        .replace("USD", "")
        .replace("%", "")
        .strip()
    )

    try:
        return float(text) * multiplier
    except ValueError:
        return None


def is_korean_ticker(ticker: str, market: str | None = None) -> bool:
    normalized_market = (market or "").upper()
    compact = ticker.strip().upper()
    return (
        normalized_market in {"KR", "KOSPI", "KOSDAQ"}
        or compact.endswith(".KS")
        or compact.endswith(".KQ")
        or (compact.isdigit() and len(compact) == 6)
    )


def is_us_ticker(ticker: str, market: str | None = None) -> bool:
    normalized_market = (market or "").upper()
    compact = ticker.strip().upper()
    if normalized_market in {"US", "NYSE", "NASDAQ", "AMEX"}:
        return True
    if is_korean_ticker(compact, normalized_market):
        return False
    return compact.replace(".", "").replace("-", "").isalnum() and any(
        char.isalpha() for char in compact
    )


@dataclass(frozen=True)
class Security:
    ticker: str
    market: str | None = None
    name: str | None = None
    corp_code: str | None = None

    @property
    def normalized_ticker(self) -> str:
        return self.ticker.strip().upper()

    @property
    def is_korean(self) -> bool:
        return is_korean_ticker(self.normalized_ticker, self.market)

    @property
    def is_us(self) -> bool:
        return is_us_ticker(self.normalized_ticker, self.market)


@dataclass(frozen=True)
class ProviderResult:
    source: str
    as_of: str
    is_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Quote(ProviderResult):
    ticker: str = ""
    price: float | None = None
    currency: str | None = None


@dataclass(frozen=True)
class IndexQuote(ProviderResult):
    index_code: str = ""
    value: float | None = None


@dataclass(frozen=True)
class AnnualFinancials(ProviderResult):
    ticker: str = ""
    year: int = 0
    revenue: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    assets: float | None = None
    liabilities: float | None = None
    equity: float | None = None


@dataclass(frozen=True)
class ValuationFields(ProviderResult):
    ticker: str = ""
    per: float | None = None
    pbr: float | None = None
    eps: float | None = None
    bps: float | None = None


@dataclass(frozen=True)
class ValuationSnapshot:
    security: Security
    quote: Quote | None
    annual_financials: list[AnnualFinancials]
    valuation: ValuationFields | None
    diagnostics: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "security": asdict(self.security),
            "quote": self.quote.to_dict() if self.quote else None,
            "annual_financials": [item.to_dict() for item in self.annual_financials],
            "valuation": self.valuation.to_dict() if self.valuation else None,
            "diagnostics": self.diagnostics,
        }

