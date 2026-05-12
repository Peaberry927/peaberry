import gzip
from unittest import TestCase
from unittest.mock import patch

from peaberry.fundamentals.http import UrlLibJsonHttpClient


class FakeResponse:
    def __init__(self, payload: bytes, encoding: str) -> None:
        self.payload = payload
        self.headers = {"Content-Encoding": encoding}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class UrlLibJsonHttpClientTests(TestCase):
    def test_get_json_decodes_gzip_response(self) -> None:
        payload = gzip.compress(b'{"ok": true}')

        with patch(
            "peaberry.fundamentals.http.urlopen",
            return_value=FakeResponse(payload, "gzip"),
        ):
            result = UrlLibJsonHttpClient().get_json("https://example.com/data.json")

        self.assertEqual(result, {"ok": True})
