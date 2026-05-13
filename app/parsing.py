from __future__ import annotations

import re


def parse_year_tokens(years: str) -> list[int]:
    parsed: list[int] = []
    for token in years.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        match = re.search(r"(20\d{2})", stripped)
        if not match:
            raise ValueError(f"Invalid year token: {stripped}")
        parsed.append(int(match.group(1)))
    return parsed
