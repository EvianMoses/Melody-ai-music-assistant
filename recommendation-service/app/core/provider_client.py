"""Thin HTTP client for the provider-gateway `/providers/search` endpoint.

Node 13 (§4.2, search_providers) reads through this. Provider results are
schema-valid fixtures until Phase 5 (§4.3: only reads happen inside LangGraph;
Provider Adapter supplies real IDs/metadata, never the graph itself).
"""

from __future__ import annotations

import os
from typing import Any

from shared_lib.http import make_async_client

PROVIDER_GATEWAY_URL = os.getenv("PROVIDER_GATEWAY_URL", "http://provider-gateway:8000")


async def search(query: str, *, provider: str = "youtube", limit: int = 5) -> dict[str, Any]:
    """POST {PROVIDER_GATEWAY_URL}/providers/search. Returns the parsed JSON body.

    Raises on failure -- callers catch and degrade to no candidates.
    """
    async with make_async_client() as client:
        response = await client.post(
            f"{PROVIDER_GATEWAY_URL}/providers/search",
            json={"query": query, "provider": provider, "limit": limit},
        )
        response.raise_for_status()
        return response.json()
