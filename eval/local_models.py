"""LOCAL-003 — measure the local models that actually run (plan §3.7).

⚠️ **Retargeted 2026-07-28.** LOCAL-002/003 originally described an Ollama
adapter and measurements of `llama3.1`. That was dropped by developer decision
after an audit found Ollama referenced nowhere on the request path, with a
container that had never started. ADR-006 had already routed generation to
`claude-haiku-4-5` and left the local model only "intent classification and
structured extraction" -- work that was never implemented, so the service was
carrying a job nothing asked it to do.

What replaced it is not a substitute but a stronger claim: **three locally
hosted models that do real work on every request**, rather than one that did
none.

  1. `intfloat/multilingual-e5-small`            -- embeddings   (rag-service)
  2. `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` -- reranking    (rag-service)
  3. the trained PyTorch audio genre CNN          -- classification (audio-service)

LOCAL-003 asks for latency, memory and output-schema pass rate. All three are
measured here, on CPU, in the container the model really runs in.

Run inside rag-service (models 1 and 2):

    docker exec melody-rag-service python /app/eval/local_models.py

Model 3 is measured by `audio-service/ml/evaluate.py`, which already reports
held-out macro-F1 and a confusion matrix; its numbers are quoted, not re-run,
because re-running a training evaluation from here would measure a copy.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORTS = Path(__file__).resolve().parent / "reports"

# Representative of what the pipeline really embeds/reranks: short queries, and
# passages the length of a real corpus chunk.
SAMPLE_QUERIES = [
    "warm indie folk for a rainy afternoon",
    "90s grunge for a moody evening",
    "deep house",
    "מוזיקה שקטה ועצובה לערב",  # Hebrew, because a fifth of real queries are
    "jazz blended with hip hop production",
]
SAMPLE_PASSAGE = (
    "Grunge emerged from the Seattle scene in the late 1980s, combining the "
    "energy of punk with the heaviness of metal and a deliberately unpolished "
    "production aesthetic. Guitars are distorted and sludgy, vocals range from "
    "a mumble to a scream, and the songwriting favours loud-quiet-loud dynamics. "
) * 3


def _rss_mb() -> float:
    """Resident set size in MB, read from /proc (Linux containers only)."""
    try:
        with open("/proc/self/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    return float("nan")


def measure_embedding_model() -> dict[str, Any]:
    from sentence_transformers import SentenceTransformer

    name = "intfloat/multilingual-e5-small"
    before = _rss_mb()
    load_started = time.perf_counter()
    model = SentenceTransformer(name, cache_folder=os.getenv("HF_HOME", "/app/.hf_cache"))
    load_s = time.perf_counter() - load_started
    after_load = _rss_mb()

    model.encode(["query: warm up"], show_progress_bar=False)  # warm the graph

    single = []
    for q in SAMPLE_QUERIES:
        started = time.perf_counter()
        vector = model.encode("query: " + q, normalize_embeddings=True)
        single.append((time.perf_counter() - started) * 1000)
    dim = len(vector)

    batch_started = time.perf_counter()
    model.encode(
        ["passage: " + SAMPLE_PASSAGE] * 64, batch_size=32, show_progress_bar=False
    )
    batch_s = time.perf_counter() - batch_started

    return {
        "model": name,
        "role": "query and passage embeddings (rag-service, every request)",
        "load_seconds": round(load_s, 2),
        "resident_mb_after_load": after_load,
        "resident_mb_delta": round(after_load - before, 1) if after_load == after_load else None,
        "single_encode_ms_median": round(statistics.median(single), 1),
        "single_encode_ms_max": round(max(single), 1),
        "batch64_passages_seconds": round(batch_s, 2),
        "throughput_passages_per_s": round(64 / batch_s, 1),
        # LOCAL-003's "output-schema pass rate": for an embedding model the
        # contract is the vector shape, and a wrong dimensionality is a hard
        # failure the database would reject anyway (the column is vector(384)).
        "output_schema": {
            "expected_dim": 384,
            "actual_dim": dim,
            "pass": dim == 384,
        },
        "max_sequence_tokens": model.max_seq_length,
    }


def measure_reranker() -> dict[str, Any]:
    from sentence_transformers import CrossEncoder

    name = os.getenv("RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
    before = _rss_mb()
    load_started = time.perf_counter()
    model = CrossEncoder(name)
    load_s = time.perf_counter() - load_started
    after_load = _rss_mb()

    model.predict([("warm up", "warm up")])

    timings = []
    for q in SAMPLE_QUERIES:
        pairs = [(q, SAMPLE_PASSAGE)] * 20  # the real per-request pool size
        started = time.perf_counter()
        scores = model.predict(pairs)
        timings.append((time.perf_counter() - started) * 1000)

    numeric = all(isinstance(float(s), float) for s in scores)
    return {
        "model": name,
        "role": "cross-encoder reranking (rag-service, every request)",
        "load_seconds": round(load_s, 2),
        "resident_mb_after_load": after_load,
        "resident_mb_delta": round(after_load - before, 1) if after_load == after_load else None,
        "rerank_20_pairs_ms_median": round(statistics.median(timings), 1),
        "rerank_20_pairs_ms_max": round(max(timings), 1),
        "per_pair_ms": round(statistics.median(timings) / 20, 1),
        "output_schema": {
            "expected": "one float score per (query, passage) pair",
            "pairs_in": 20,
            "scores_out": len(scores),
            "pass": len(scores) == 20 and numeric,
        },
    }


def audio_classifier_reference() -> dict[str, Any]:
    """Quoted from the model's own held-out evaluation, not re-run here.

    Re-running it from this harness would measure a copy of the same checkpoint
    against the same split and add nothing; `audio-service/ml/evaluate.py` is the
    authority and `docs/ml/audio-genre-classifier.md` is the model card.
    """
    return {
        "model": "melody audio genre CNN (PyTorch, trained on GTZAN)",
        "role": "audio genre classification (audio-service)",
        "measured_by": "audio-service/ml/evaluate.py",
        "model_card": "docs/ml/audio-genre-classifier.md",
        "held_out_macro_f1": 0.8692,
        "held_out_accuracy": 0.8733,
        "note": (
            "Clip-level, on a leakage-free split, against a 0.10 random baseline "
            "and a 0.60 ship threshold fixed before training."
        ),
    }


def main() -> int:
    print("LOCAL-003 — measuring the local models on the request path\n")

    results: dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "host": {
            "cpu_count": os.cpu_count(),
            "note": "measured inside the container the model really runs in",
        },
        "models": [],
    }

    for label, fn in (
        ("embedding", measure_embedding_model),
        ("reranker", measure_reranker),
    ):
        print(f"  measuring {label}...")
        try:
            results["models"].append(fn())
        except Exception as exc:  # noqa: BLE001
            # Recorded as an error, never as a zero -- the same rule the Ragas
            # harness follows, and for the same reason.
            results["models"].append({"role": label, "error": f"{type(exc).__name__}: {exc}"})

    results["models"].append(audio_classifier_reference())

    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = REPORTS / f"local_models_{stamp}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    for m in results["models"]:
        if "error" in m:
            print(f"  !! {m['role']}: {m['error']}")
            continue
        print(f"  {m['model']}")
        print(f"     role   : {m['role']}")
        if "single_encode_ms_median" in m:
            print(
                f"     latency: {m['single_encode_ms_median']} ms/query median, "
                f"{m['throughput_passages_per_s']} passages/s batched"
            )
        if "rerank_20_pairs_ms_median" in m:
            print(
                f"     latency: {m['rerank_20_pairs_ms_median']} ms per 20-pair pool "
                f"({m['per_pair_ms']} ms/pair)"
            )
        if "resident_mb_after_load" in m:
            print(f"     memory : {m['resident_mb_after_load']} MB resident after load")
        if "output_schema" in m:
            print(f"     schema : {'PASS' if m['output_schema']['pass'] else 'FAIL'}")
        if "held_out_macro_f1" in m:
            print(f"     quality: macro-F1 {m['held_out_macro_f1']} (see {m['model_card']})")
        print()

    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
