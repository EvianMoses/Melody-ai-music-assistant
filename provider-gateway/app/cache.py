"""Tiny in-process TTL cache for provider search results (§PROV-004/§YT-006).

YouTube's search.list costs 100 quota units against a 10,000/day default quota
(~100 searches/day) -- caching repeated queries is not optional polish here.
Module-level singleton, mirrors rag-service/main.py's model-singleton pattern.

Known gap: in-process only, not shared across instances/restarts. A DB-backed
or Redis-backed cache would fix that -- deferred, same shape as the
model_usage-table gap already noted in the plan doc; provider-gateway has no
DB dependency today and adding one just for this would be disproportionate.
"""

from __future__ import annotations

import time
from typing import Any, Optional

DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h -- search results don't change hour to hour.

_store: dict[tuple[str, str, int], tuple[float, list[dict[str, Any]]]] = {}


def _key(provider: str, query: str, limit: int) -> tuple[str, str, int]:
    return (provider, " ".join(query.strip().lower().split()), limit)


def get(provider: str, query: str, limit: int) -> Optional[list[dict[str, Any]]]:
    entry = _store.get(_key(provider, query, limit))
    if entry is None:
        return None
    expires_at, value = entry
    if time.time() >= expires_at:
        _store.pop(_key(provider, query, limit), None)
        return None
    return value


def set(
    provider: str,
    query: str,
    limit: int,
    value: list[dict[str, Any]],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    _store[_key(provider, query, limit)] = (time.time() + ttl_seconds, value)
