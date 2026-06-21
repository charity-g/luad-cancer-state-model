"""Simple in-process TTL cache for harmonized identifiers.

All agents share one module-level instance so KEGG/UniProt lookups for the same
gene are never repeated within a server process lifetime.
"""

from __future__ import annotations

import time
from typing import Any, Optional


_DEFAULT_TTL = 3600  # 1 hour


class TTLCache:
    def __init__(self, ttl: int = _DEFAULT_TTL) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._store[key] = (value, time.monotonic() + (ttl or self._ttl))

    def evict(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        now = time.monotonic()
        return sum(1 for _, (_, exp) in self._store.items() if exp > now)


# Module-level singleton shared across all resolvers
harmonizer_cache = TTLCache()
