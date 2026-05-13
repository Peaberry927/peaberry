from __future__ import annotations

import unittest

from app.parsing import parse_year_tokens


class MainParsingTests(unittest.TestCase):
    def test_parse_year_tokens_accepts_estimate_suffix(self) -> None:
        years = parse_year_tokens("2024, 2025.12, 2026(E), 2027.12(E)")
        self.assertEqual(years, [2024, 2025, 2026, 2027])

    def test_parse_year_tokens_rejects_invalid_tokens(self) -> None:
        with self.assertRaises(ValueError):
            parse_year_tokens("2024, foo")


if __name__ == "__main__":
    unittest.main()
