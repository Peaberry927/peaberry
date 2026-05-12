"""Small JSON HTTP client used by data acquisition adapters."""

from __future__ import annotations

import json
import gzip
import zlib
from typing import Any, Protocol
from urllib.request import Request, urlopen


class JsonHttpClient(Protocol):
    """Fetch JSON documents from an HTTP endpoint."""

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        """Return a parsed JSON object."""


class UrlLibJsonHttpClient:
    """Standard-library JSON client with explicit headers."""

    def __init__(
        self,
        timeout_seconds: float = 20,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.default_headers = {
            "User-Agent": "peaberry/0.1",
            "Accept": "application/json",
            **(default_headers or {}),
        }

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        request_headers = {**self.default_headers, **(headers or {})}
        request = Request(url, headers=request_headers)
        with urlopen(request, timeout=self.timeout_seconds) as response:
            raw_payload = response.read()
            encoding = response.headers.get("Content-Encoding", "").lower()
        if encoding == "gzip":
            raw_payload = gzip.decompress(raw_payload)
        elif encoding == "deflate":
            raw_payload = zlib.decompress(raw_payload)
        payload = raw_payload.decode("utf-8")
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("expected JSON object response")
        return data
