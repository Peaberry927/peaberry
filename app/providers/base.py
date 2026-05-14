from __future__ import annotations

import json
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    """Raised when a market-data provider cannot return usable data."""


class HttpClient:
    def __init__(self, timeout_seconds: float = 8.0) -> None:
        self.timeout_seconds = timeout_seconds

    def get_text(self, url: str, params: dict[str, str] | None = None) -> str:
        target = f"{url}?{urlencode(params)}" if params else url
        request = Request(
            target,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 Chrome/124 Safari/537.36"
                )
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise ProviderError(f"GET failed for {target}: {exc}") from exc

    def get_json(self, url: str, params: dict[str, str] | None = None) -> dict:
        text = self.get_text(url, params)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Provider returned invalid JSON for {url}") from exc

    def get_bytes(self, url: str, params: dict[str, str] | None = None) -> bytes:
        target = f"{url}?{urlencode(params)}" if params else url
        request = Request(
            target,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 Chrome/124 Safari/537.36"
                )
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise ProviderError(f"GET failed for {target}: {exc}") from exc


def strip_html(value: str) -> str:
    output = []
    in_tag = False
    for char in value:
        if char == "<":
            in_tag = True
        elif char == ">":
            in_tag = False
        elif not in_tag:
            output.append(char)
    return " ".join(unescape("".join(output)).split())

