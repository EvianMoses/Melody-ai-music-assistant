"""HTTP client factory with explicit, bounded timeouts (Section 2.4)."""

from __future__ import annotations

from typing import Optional

import httpx

# Explicit dependency timeouts: fail fast rather than hanging a worker.
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def make_async_client(timeout: Optional[httpx.Timeout] = None) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient with a bounded default timeout."""
    return httpx.AsyncClient(timeout=timeout or DEFAULT_TIMEOUT)
