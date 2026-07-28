"""RAG generation: retrieve → rerank → synthesize with a local Ollama LLM (§3.7).

End-to-end demo of the full Melody RAG answer path:

1. Retrieval (reuses the exact §3.5/§3.6 pipeline from ``test_hybrid_retrieval``):
   Dense (pgvector) + Lexical (Postgres FTS) → Reciprocal Rank Fusion → local
   cross-encoder rerank → top ``--final-k`` (default 5) ``chunk_text`` passages.
2. Prompt assembly: a strict RAG system message + the retrieved chunks wrapped in
   a ``<context>`` block + the user question.
3. Generation: the prompt is sent to a **local** Ollama server (default model
   ``llama3.1``). The response is streamed token-by-token to the terminal.

Ollama endpoint resolution (no secrets, fully local):
- ``--ollama-url`` CLI flag wins if given.
- else the ``OLLAMA_BASE_URL`` env var.
- else ``http://ollama:11434`` (the compose service on the ``melody-net`` network).

When running a one-off container with ``--no-deps`` (so the compose ``ollama``
service is not started) point it at the host daemon instead, e.g.
``-e OLLAMA_BASE_URL=http://host.docker.internal:11434``.

Only ``httpx`` (already a rag-service dependency) is used to talk to Ollama's
REST API, so no new runtime dependency is introduced.

Usage (inside the rag-service container)::

    python scripts/test_generation.py "Tell me about the origins of rock music"
    python scripts/test_generation.py --model llama3:8b --domain genre "what is post-punk?"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_PATH.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_PATH.parent))

# Reuse the proven retrieval + rerank building blocks verbatim (single source of
# truth for the pipeline — this script never re-implements retrieval).
from _db import resolve_database_url  # noqa: E402
from test_hybrid_retrieval import (  # noqa: E402
    CE_MODEL_NAME,
    DEFAULT_FINAL_K,
    MODEL_NAME,
    QUERY_PREFIX,
    build_lexical_or_query,
    build_metadata_filters,
    cross_encoder_rerank,
    dense_search,
    fulltext_search,
    reciprocal_rank_fusion,
)

DEFAULT_QUERY = "Tell me about the origins of rock music"
DEFAULT_LLM_MODEL = "llama3.1"
DEFAULT_OLLAMA_URL = "http://ollama:11434"

SYSTEM_PROMPT = (
    "You are Melody, an expert music AI assistant. Answer the user's question "
    "using ONLY the provided context. If the context does not contain the answer, "
    "say you do not know. Be concise, accurate, and cite the relevant genres or "
    "eras from the context when helpful."
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="*", help=f'User question (default "{DEFAULT_QUERY}").')
    # LLM / Ollama options.
    parser.add_argument(
        "--model", default=DEFAULT_LLM_MODEL, help="Ollama model (default llama3.1)."
    )
    parser.add_argument(
        "--ollama-url",
        default=None,
        help="Ollama base URL (else $OLLAMA_BASE_URL, else http://ollama:11434).",
    )
    parser.add_argument(
        "--stream",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stream tokens as they arrive (default on; --no-stream for one shot).",
    )
    parser.add_argument(
        "--temperature", type=float, default=0.2, help="Sampling temperature (default 0.2)."
    )
    parser.add_argument(
        "--timeout", type=float, default=600.0, help="LLM read timeout seconds (default 600)."
    )
    # Retrieval options (mirror test_hybrid_retrieval so behaviour is identical).
    parser.add_argument(
        "--final-k",
        type=int,
        default=DEFAULT_FINAL_K,
        help=f"Chunks passed to the LLM as context (default {DEFAULT_FINAL_K}).",
    )
    parser.add_argument(
        "--pool", type=int, default=20, help="Candidates retrieved per method (default 20)."
    )
    parser.add_argument(
        "--candidates",
        type=int,
        default=20,
        help="Top fused candidates sent to the cross-encoder (default 20).",
    )
    parser.add_argument(
        "--rerank",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Cross-encoder rerank the fused candidates (default on).",
    )
    parser.add_argument("--k-rrf", type=int, default=60, help="RRF constant k (default 60).")
    parser.add_argument("--embed-model", default=MODEL_NAME, help="Bi-encoder retrieval model id.")
    parser.add_argument("--ce-model", default=CE_MODEL_NAME, help="Cross-encoder rerank model id.")
    # Metadata pre-filters.
    parser.add_argument("--year-from", type=int, default=None, help="Min era/year (inclusive).")
    parser.add_argument("--year-to", type=int, default=None, help="Max era/year (inclusive).")
    parser.add_argument("--source", default=None, help='Filter metadata.source (e.g. "metacritic").')
    parser.add_argument("--domain", default=None, help='Filter metadata.domain ("genre"|"reviews").')
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL.")
    return parser


def resolve_ollama_url(cli_value: Optional[str]) -> str:
    """CLI flag > OLLAMA_BASE_URL env > compose default. Trailing slash trimmed."""
    url = cli_value or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_URL
    return url.rstrip("/")


def retrieve_context(args, query: str) -> list[dict]:
    """Run Dense + Lexical → RRF → (optional) cross-encoder rerank → top final_k.

    Returns the selected candidate dicts (each has ``text``/``doc_id``/``domain``
    plus scoring metadata), reusing the identical functions from the hybrid
    retrieval script so generation sees exactly what retrieval evaluation showed.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    filters = build_metadata_filters(
        year_from=args.year_from,
        year_to=args.year_to,
        source=args.source,
        domain=args.domain,
    )
    or_query, matched_genres = build_lexical_or_query(query)

    print(f"Loading retrieval model '{args.embed_model}'...", file=sys.stderr)
    from sentence_transformers import SentenceTransformer

    embedder = SentenceTransformer(args.embed_model)
    query_vector = embedder.encode(
        QUERY_PREFIX + query, normalize_embeddings=True, convert_to_numpy=True
    ).tolist()

    engine = create_engine(resolve_database_url(args.database_url), future=True)
    try:
        with Session(engine) as session:
            dense = dense_search(session, query_vector, args.pool, filters)
            fulltext = fulltext_search(session, or_query, args.pool, filters)
    finally:
        engine.dispose()

    info = {cid: (txt, doc_id, domain) for cid, txt, doc_id, domain in fulltext}
    info.update({cid: (txt, doc_id, domain) for cid, txt, doc_id, domain in dense})

    fused = reciprocal_rank_fusion(dense, fulltext, args.k_rrf)
    fused_ranked = sorted(
        fused.items(),
        key=lambda kv: (-kv[1]["rrf"], kv[1]["vec_rank"] or 1e9, kv[1]["ft_rank"] or 1e9),
    )

    candidates = []
    for chunk_id, entry in fused_ranked[: args.candidates]:
        text_val, doc_id, domain = info.get(chunk_id, ("", None, None))
        candidates.append(
            {
                "id": chunk_id,
                "text": text_val,
                "doc_id": doc_id,
                "domain": domain,
                "rrf": entry["rrf"],
                "vec_rank": entry["vec_rank"],
                "ft_rank": entry["ft_rank"],
            }
        )

    if args.rerank and candidates:
        print(f"Reranking {len(candidates)} candidates with '{args.ce_model}'...", file=sys.stderr)
        candidates = cross_encoder_rerank(query, candidates, args.ce_model)

    if matched_genres:
        expansion = "; ".join(f"{g} -> {', '.join(s)}" for g, s in matched_genres.items())
        print(f"genre-graph expansion: {expansion}", file=sys.stderr)

    return candidates[: args.final_k]


def build_prompt(query: str, chunks: list[dict]) -> str:
    """Assemble the RAG user prompt: numbered <context> block + the question."""
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        header = f"[{i}] ({chunk.get('domain') or 'unknown'}) {chunk.get('doc_id') or ''}".strip()
        body = " ".join((chunk.get("text") or "").split())
        blocks.append(f"{header}\n{body}")
    context = "\n\n".join(blocks) if blocks else "(no context retrieved)"
    return (
        "<context>\n"
        f"{context}\n"
        "</context>\n\n"
        f"Question: {query}\n\n"
        "Answer using only the context above:"
    )


def generate(base_url: str, model: str, system: str, prompt: str, *, stream: bool,
             temperature: float, timeout: float) -> str:
    """Call Ollama's /api/generate. Streams tokens to stdout; returns full text."""
    import httpx

    payload = {
        "model": model,
        "system": system,
        "prompt": prompt,
        "stream": stream,
        "options": {"temperature": temperature},
    }
    url = f"{base_url}/api/generate"
    client_timeout = httpx.Timeout(timeout, connect=10.0)
    collected: list[str] = []

    try:
        if stream:
            with httpx.stream("POST", url, json=payload, timeout=client_timeout) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    obj = json.loads(line)
                    if obj.get("error"):
                        raise RuntimeError(obj["error"])
                    token = obj.get("response", "")
                    if token:
                        collected.append(token)
                        print(token, end="", flush=True)
                    if obj.get("done"):
                        break
            print()
        else:
            response = httpx.post(url, json=payload, timeout=client_timeout)
            response.raise_for_status()
            obj = response.json()
            if obj.get("error"):
                raise RuntimeError(obj["error"])
            text = obj.get("response", "")
            collected.append(text)
            print(text)
    except httpx.HTTPStatusError as exc:
        # Streaming responses must be drained before .text is readable.
        try:
            if not exc.response.is_closed:
                exc.response.read()
            body = (exc.response.text or "").strip()
        except Exception:
            body = f"(unable to read error body; status={exc.response.status_code})"
        raise RuntimeError(
            f"Ollama returned HTTP {exc.response.status_code} from {url}. "
            f"Is model '{model}' pulled? (run: ollama pull {model}). Detail: {body}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {base_url} ({exc}). Ensure the ollama service "
            f"is running and OLLAMA_BASE_URL points to it (compose: http://ollama:11434; "
            f"host daemon from a --no-deps container: http://host.docker.internal:11434)."
        ) from exc

    return "".join(collected)


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    query = " ".join(args.query) if args.query else DEFAULT_QUERY
    base_url = resolve_ollama_url(args.ollama_url)

    chunks = retrieve_context(args, query)

    print("\n" + "=" * 78)
    print(f"RAG GENERATION — QUERY: {query}")
    print(f"ollama: {base_url}  |  model: {args.model}  |  context chunks: {len(chunks)}")
    print("-" * 78)
    print("RETRIEVED CONTEXT (top {}):".format(len(chunks)))
    for i, chunk in enumerate(chunks, start=1):
        ce = chunk.get("ce_score")
        score = f"CE={ce:+.4f}  " if ce is not None else ""
        snippet = " ".join((chunk.get("text") or "").split())[:140]
        print(f"  [{i}] {score}[{chunk.get('domain')}] {chunk.get('doc_id')}")
        print(f"      {snippet}...")
    print("=" * 78)

    prompt = build_prompt(query, chunks)

    print("\nMELODY (generated answer):\n" + "-" * 78)
    generate(
        base_url,
        args.model,
        SYSTEM_PROMPT,
        prompt,
        stream=args.stream,
        temperature=args.temperature,
        timeout=args.timeout,
    )
    print("-" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
