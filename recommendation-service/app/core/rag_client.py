"""Thin HTTP client for the real rag-service `/rag/retrieve` endpoint.

Nodes 5-9 (§4.2) call this instead of re-implementing embedding/RRF/rerank
locally (Section 2.2: Recommendation Service must not own embedding math).
"""

from __future__ import annotations

import os
from typing import Any, Optional

from shared_lib.http import make_async_client

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://rag-service:8000")


async def retrieve(
    query: str,
    *,
    domain: str,
    top_k: int = 5,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> dict[str, Any]:
    """POST {RAG_SERVICE_URL}/rag/retrieve. Returns the parsed JSON body.

    Raises on failure (httpx.HTTPError / non-2xx) -- callers catch and degrade
    to empty results rather than failing the whole graph run.
    """
    filters: dict[str, Any] = {"domain": domain}
    if year_from is not None:
        filters["year_from"] = year_from
    if year_to is not None:
        filters["year_to"] = year_to

    async with make_async_client() as client:
        response = await client.post(
            f"{RAG_SERVICE_URL}/rag/retrieve",
            json={"query": query, "top_k": top_k, "filters": filters},
        )
        response.raise_for_status()
        return response.json()
