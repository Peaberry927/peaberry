"""Small time-to-live cache for data acquisition adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Generic, Hashable, TypeVar


Value = TypeVar("Value")


@dataclass(frozen=True, slots=True)
class CacheEntry(Generic[Value]):
    value: Value
    expires_at: datetime


class TtlCache(Generic[Value]):
    """In-process TTL cache keyed by immutable request identity."""

    def __init__(self, ttl: timedelta) -> None:
        if ttl.total_seconds() <= 0:
            raise ValueError("ttl must be positive")
        self.ttl = ttl
        self._entries: dict[Hashable, CacheEntry[Value]] = {}

    def get(self, key: Hashable) -> Value | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= datetime.now(timezone.utc):
            del self._entries[key]
            return None
        return entry.value

    def set(self, key: Hashable, value: Value) -> Value:
        self._entries[key] = CacheEntry(
            value=value,
            expires_at=datetime.now(timezone.utc) + self.ttl,
        )
        return value

    def get_or_set(self, key: Hashable, loader) -> Value:
        cached = self.get(key)
        if cached is not None:
            return cached
        return self.set(key, loader())
