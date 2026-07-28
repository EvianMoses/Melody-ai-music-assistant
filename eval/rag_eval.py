"""Golden-set evaluation for the Melody RAG pipeline (plan §3.8, RAG-EVAL).

Two independent layers, deliberately separated because they answer different
questions and fail differently:

1. **Retrieval metrics** -- Recall@K, MRR, nDCG@K, plus latency. Deterministic,
   free, offline, and computed against the ground truth in `golden_set.json`.
   These answer "did the pipeline find the right chunks?".

2. **Ragas metrics** -- faithfulness, response relevancy, context precision and
   context recall, judged by an LLM. These answer "was the answer grounded in
   what was retrieved?", which no amount of rank math can tell you.

Layer 1 runs without an API key and is what you use while tuning knobs. Layer 2
costs money per run and is what you use to decide whether a change actually
improved the *answers*. `--no-ragas` runs layer 1 alone.

Usage (inside the rag-service container, which already has torch, the embedding
model and database access):

    docker exec melody-rag-service python /app/eval/rag_eval.py --no-ragas
    docker exec melody-rag-service python /app/eval/rag_eval.py --pool 20,50,100
    docker exec melody-rag-service python /app/eval/rag_eval.py --ragas

Reports are written to `eval/reports/` as JSON and Markdown.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

HERE = Path(__file__).resolve().parent
GOLDEN_SET = HERE / "golden_set.json"
REPORTS = HERE / "reports"

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8002")

# Ragas judges the *answer*, so the harness needs one. It asks the same
# generation surface the product uses rather than inventing a private prompt,
# because evaluating a prompt nobody ships tells you nothing about the product.
ANTHROPIC_MODEL = os.getenv("RAGAS_EVALUATOR_MODEL", "claude-haiku-4-5")


# ---------------------------------------------------------------------------
# Retrieval metrics (layer 1)
# ---------------------------------------------------------------------------


def _hits(retrieved_ids: list[str], expected: list[str]) -> list[int]:
    """Positions (1-based) of retrieved chunks matching any expected prefix.

    Prefix matching is deliberate: a section split across `~1`/`~2` parts is one
    conceptual target, and retrieving either part means retrieval found it.
    """
    positions = []
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if any(doc_id.startswith(exp) for exp in expected):
            positions.append(rank)
    return positions


def recall_at_k(retrieved_ids: list[str], expected: list[str], k: int) -> float:
    """Fraction of distinct expected targets found in the top k.

    Counts TARGETS covered, not hits returned -- returning three chunks of the
    same section is one target found, not three.
    """
    if not expected:
        return float("nan")
    top = retrieved_ids[:k]
    found = {exp for exp in expected if any(d.startswith(exp) for d in top)}
    return len(found) / len(expected)


def mrr(retrieved_ids: list[str], expected: list[str]) -> float:
    positions = _hits(retrieved_ids, expected)
    return 1.0 / positions[0] if positions else 0.0


def ndcg_at_k(retrieved_ids: list[str], expected: list[str], k: int) -> float:
    """Binary-relevance nDCG@k."""
    if not expected:
        return float("nan")
    dcg = 0.0
    seen: set[str] = set()
    for rank, doc_id in enumerate(retrieved_ids[:k], start=1):
        match = next((e for e in expected if doc_id.startswith(e)), None)
        # Credit each target once, so duplicates of one section cannot inflate.
        if match and match not in seen:
            seen.add(match)
            dcg += 1.0 / math.log2(rank + 1)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(expected), k)))
    return dcg / ideal if ideal else float("nan")


async def retrieve(
    client: httpx.AsyncClient,
    query: str,
    *,
    domain: str,
    top_k: int,
    candidate_pool: Optional[int],
) -> tuple[list[dict[str, Any]], float, float]:
    """Returns (chunks, retrieval_confidence, elapsed_seconds)."""
    payload: dict[str, Any] = {"query": query, "top_k": top_k, "filters": {"domain": domain}}
    if candidate_pool:
        payload["candidate_pool"] = candidate_pool
    started = time.perf_counter()
    response = await client.post(f"{RAG_SERVICE_URL}/rag/retrieve", json=payload, timeout=300)
    response.raise_for_status()
    body = response.json()
    return (
        body.get("chunks", []),
        float(body.get("retrieval_confidence", 0.0)),
        time.perf_counter() - started,
    )


async def run_retrieval(
    queries: list[dict[str, Any]], *, top_k: int, candidate_pool: Optional[int]
) -> list[dict[str, Any]]:
    """Run every golden query through both domains and score it."""
    results = []
    async with httpx.AsyncClient() as client:
        for q in queries:
            genre_chunks, genre_conf, genre_ms = await retrieve(
                client, q["query"], domain="genre", top_k=top_k, candidate_pool=candidate_pool
            )
            review_chunks, review_conf, review_ms = await retrieve(
                client, q["query"], domain="reviews", top_k=top_k, candidate_pool=candidate_pool
            )

            # The graph fuses both domains, so the evaluation must too -- scoring
            # one domain in isolation would measure something the product never
            # does. Ordered by cross-encoder score, which is the order the graph's
            # rerank stage produces.
            merged = sorted(
                genre_chunks + review_chunks,
                key=lambda c: c.get("score", -math.inf),
                reverse=True,
            )
            retrieved_ids = [
                (c.get("metadata", {}) or {}).get("doc_id") or c.get("document_id", "")
                for c in merged
            ]

            entry: dict[str, Any] = {
                "id": q["id"],
                "category": q["category"],
                "language": q["language"],
                "query": q["query"],
                "retrieval_scored": q["retrieval_scored"],
                "retrieved": retrieved_ids[:10],
                "genre_confidence": round(genre_conf, 4),
                "reviews_confidence": round(review_conf, 4),
                "latency_s": round(genre_ms + review_ms, 3),
                "contexts": [c.get("chunk_text", "") for c in merged[:top_k]],
            }
            if q["retrieval_scored"] and q["expected_docs"]:
                entry.update(
                    {
                        "recall@5": round(recall_at_k(retrieved_ids, q["expected_docs"], 5), 4),
                        "recall@10": round(recall_at_k(retrieved_ids, q["expected_docs"], 10), 4),
                        "mrr": round(mrr(retrieved_ids, q["expected_docs"]), 4),
                        "ndcg@10": round(ndcg_at_k(retrieved_ids, q["expected_docs"], 10), 4),
                    }
                )
            results.append(entry)
    return results


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in results if "recall@5" in r]

    def mean(key: str, rows: list[dict[str, Any]]) -> Optional[float]:
        vals = [r[key] for r in rows if key in r and not math.isnan(r[key])]
        return round(statistics.mean(vals), 4) if vals else None

    by_category: dict[str, Any] = {}
    for r in scored:
        by_category.setdefault(r["category"], []).append(r)
    by_language: dict[str, Any] = {}
    for r in scored:
        by_language.setdefault(r["language"], []).append(r)

    return {
        "queries_total": len(results),
        "queries_scored": len(scored),
        "recall@5": mean("recall@5", scored),
        "recall@10": mean("recall@10", scored),
        "mrr": mean("mrr", scored),
        "ndcg@10": mean("ndcg@10", scored),
        "latency_s_median": round(statistics.median([r["latency_s"] for r in results]), 3),
        "latency_s_max": round(max(r["latency_s"] for r in results), 3),
        "by_category": {
            k: {"n": len(v), "recall@5": mean("recall@5", v), "mrr": mean("mrr", v)}
            for k, v in sorted(by_category.items())
        },
        "by_language": {
            k: {"n": len(v), "recall@5": mean("recall@5", v), "mrr": mean("mrr", v)}
            for k, v in sorted(by_language.items())
        },
    }


# ---------------------------------------------------------------------------
# Ragas metrics (layer 2)
# ---------------------------------------------------------------------------


async def generate_answers(results: list[dict[str, Any]]) -> None:
    """Produce a grounded answer per query, in place, for Ragas to judge.

    Uses the same model family the product's curator uses so the evaluation
    describes the shipped system rather than a stand-in.
    """
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(model=ANTHROPIC_MODEL, temperature=0, max_tokens=400)
    for r in results:
        context = "\n\n---\n\n".join(r["contexts"][:5])
        # ⚠️ The two language rules below are not politeness -- they fix a
        # measured harness defect. The first version of this prompt said only
        # "answer using ONLY the context; if it does not support an answer, say
        # so", and on every Hebrew query the model refused with "the question is
        # in Hebrew and the context is in English" -- even on he-01, where
        # context_precision and context_recall both scored 1.0, i.e. retrieval
        # had found exactly the right chunk. he-03 went further and refused while
        # explicitly noting "the context DOES contain information about Grunge
        # from the 1990s".
        #
        # That drove Hebrew response_relevancy to 0.00 across the board and would
        # have been reported as a product failure. It was an evaluation failure:
        # the corpus is entirely English by design, so a cross-language answer is
        # the normal case, not a missing-context case.
        prompt = (
            "You are a music knowledge assistant. Answer the question using ONLY "
            "the context provided. If the context does not support an answer, say "
            "so plainly rather than inventing one.\n\n"
            "The knowledge base is written in English. A question asked in another "
            "language is normal and must still be answered from that English "
            "context -- a language difference is NOT a reason to refuse. "
            "Reply in the same language the question was asked in.\n\n"
            f"Context:\n{context}\n\nQuestion: {r['query']}\n\nAnswer:"
        )
        reply = await llm.ainvoke(prompt)
        r["answer"] = reply.content if isinstance(reply.content, str) else str(reply.content)


async def run_ragas(results: list[dict[str, Any]], queries: list[dict[str, Any]]) -> dict[str, Any]:
    """Score grounding with Ragas: faithfulness, relevancy, context precision/recall."""
    from langchain_anthropic import ChatAnthropic
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from ragas import SingleTurnSample
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithoutReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    # max_tokens=8192, not the obvious 1024. Faithfulness decomposes the answer
    # into atomic statements and emits a verdict per statement, so its output
    # grows with answer length -- at 1024 it truncated on 10 of 25 queries and
    # raised LLMDidNotFinishException. Those were recorded as errors rather than
    # scored as zero, which is the only reason the resulting 0.62 was visibly a
    # 15-query average instead of a quietly wrong 25-query one.
    llm = LangchainLLMWrapper(
        ChatAnthropic(model=ANTHROPIC_MODEL, temperature=0, max_tokens=8192)
    )
    # Local embeddings for ResponseRelevancy -- the same e5-small the retrieval
    # pipeline uses. Avoids a second paid provider purely to embed a question,
    # and keeps the evaluator consistent with the system under test.
    embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-small",
            cache_folder=os.getenv("HF_HOME", "/app/.hf_cache"),
        )
    )

    metrics = {
        "faithfulness": Faithfulness(llm=llm),
        "response_relevancy": ResponseRelevancy(llm=llm, embeddings=embeddings),
        "context_precision": LLMContextPrecisionWithoutReference(llm=llm),
        "context_recall": LLMContextRecall(llm=llm),
    }
    by_id = {q["id"]: q for q in queries}

    for r in results:
        sample = SingleTurnSample(
            user_input=r["query"],
            response=r.get("answer", ""),
            retrieved_contexts=r["contexts"][:5],
            reference=by_id[r["id"]]["reference"],
        )
        scores: dict[str, Any] = {}
        for name, metric in metrics.items():
            try:
                value = await metric.single_turn_ascore(sample)
                scores[name] = None if value is None or math.isnan(value) else round(float(value), 4)
            except Exception as exc:  # noqa: BLE001
                # A judge failure is recorded, never silently scored as zero --
                # "the evaluator errored" and "the system scored 0" are very
                # different facts and must not be averaged together.
                scores[name] = None
                scores.setdefault("_errors", {})[name] = f"{type(exc).__name__}: {exc}"[:160]
        r["ragas"] = scores

    def mean(name: str) -> Optional[float]:
        vals = [r["ragas"][name] for r in results if r.get("ragas", {}).get(name) is not None]
        return round(statistics.mean(vals), 4) if vals else None

    return {name: mean(name) for name in metrics}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def write_reports(payload: dict[str, Any], label: str) -> tuple[Path, Path]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = REPORTS / f"rag_eval_{label}_{stamp}.json"
    md_path = REPORTS / f"rag_eval_{label}_{stamp}.md"

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    agg = payload["retrieval"]
    lines = [
        f"# RAG evaluation — {label}",
        "",
        f"- Run (UTC): {payload['run_at']}",
        f"- Golden set: {payload['golden_set']} ({agg['queries_total']} queries, {agg['queries_scored']} retrieval-scored)",
        f"- Settings: top_k={payload['settings']['top_k']}, candidate_pool={payload['settings']['candidate_pool']}",
        "",
        "## Retrieval",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Recall@5 | {agg['recall@5']} |",
        f"| Recall@10 | {agg['recall@10']} |",
        f"| MRR | {agg['mrr']} |",
        f"| nDCG@10 | {agg['ndcg@10']} |",
        f"| Latency median (both domains) | {agg['latency_s_median']}s |",
        f"| Latency max | {agg['latency_s_max']}s |",
        "",
        "### By category",
        "",
        "| Category | n | Recall@5 | MRR |",
        "| --- | --- | --- | --- |",
    ]
    for cat, v in agg["by_category"].items():
        lines.append(f"| {cat} | {v['n']} | {v['recall@5']} | {v['mrr']} |")
    lines += ["", "### By language", "", "| Language | n | Recall@5 | MRR |", "| --- | --- | --- | --- |"]
    for lang, v in agg["by_language"].items():
        lines.append(f"| {lang} | {v['n']} | {v['recall@5']} | {v['mrr']} |")

    if payload.get("ragas"):
        lines += ["", "## Ragas", "", "| Metric | Value |", "| --- | --- |"]
        for k, v in payload["ragas"].items():
            lines.append(f"| {k} | {v} |")

    lines += ["", "## Per query", "", "| id | category | lang | R@5 | MRR | latency |", "| --- | --- | --- | --- | --- | --- |"]
    for r in payload["results"]:
        lines.append(
            f"| {r['id']} | {r['category']} | {r['language']} | "
            f"{r.get('recall@5', '—')} | {r.get('mrr', '—')} | {r['latency_s']}s |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


async def main() -> int:
    parser = argparse.ArgumentParser(description="Melody RAG golden-set evaluation (§3.8)")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--pool",
        default="",
        help="Comma-separated candidate_pool values to sweep, e.g. 20,50,100. Empty = service default.",
    )
    parser.add_argument("--ragas", action="store_true", help="Also run Ragas (costs API calls).")
    parser.add_argument("--no-ragas", dest="ragas", action="store_false")
    parser.add_argument("--label", default="baseline")
    parser.set_defaults(ragas=False)
    args = parser.parse_args()

    golden = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))
    queries = golden["queries"]
    pools: list[Optional[int]] = (
        [int(p) for p in args.pool.split(",") if p.strip()] if args.pool else [None]
    )

    written: list[Path] = []
    for pool in pools:
        label = f"{args.label}_pool{pool or 'default'}"
        print(f"\n=== retrieval: {len(queries)} queries, top_k={args.top_k}, pool={pool or 'default'} ===")
        results = await run_retrieval(queries, top_k=args.top_k, candidate_pool=pool)
        agg = aggregate(results)
        print(
            f"  Recall@5={agg['recall@5']}  Recall@10={agg['recall@10']}  "
            f"MRR={agg['mrr']}  nDCG@10={agg['ndcg@10']}  median={agg['latency_s_median']}s"
        )
        for lang, v in agg["by_language"].items():
            print(f"    {lang}: Recall@5={v['recall@5']}  MRR={v['mrr']}  (n={v['n']})")

        ragas_scores = None
        if args.ragas:
            print("  generating answers for Ragas...")
            await generate_answers(results)
            print("  scoring with Ragas (this makes API calls)...")
            ragas_scores = await run_ragas(results, queries)
            print(f"  ragas: {ragas_scores}")

        payload = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "golden_set": golden["name"],
            "settings": {"top_k": args.top_k, "candidate_pool": pool, "ragas": bool(args.ragas)},
            "retrieval": agg,
            "ragas": ragas_scores,
            "results": results,
        }
        j, m = write_reports(payload, label)
        written.append(m)
        print(f"  wrote {j.name} / {m.name}")

    print("\nReports:")
    for p in written:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
