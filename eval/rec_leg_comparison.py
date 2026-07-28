"""REC-LEG-001 / REC-LEG-002: legacy Bedrock vs. new LangGraph engine comparison
(plan §4.10).

Runs a shared prompt set through both routes and reports latency, response
shape, track/artist diversity, and (for the new engine) real cost/token data
scraped from recommendation-service's structured logs -- see the §4.9
node_metrics logging added alongside this script (graph_nodes.py::_metrics).

**Known limitation, by design, not a bug:** the new engine's provider search
is still fixture-backed until Phase 5 (search_providers always returns the
same two Bon Iver tracks), so track-level metrics (playable-track rate,
track diversity, track-level relevance) are not yet meaningful for the new
engine -- they will be once Phase 5 wires a real provider. Retrieval
grounding, latency, cost, and explanation quality ARE meaningful today.

**Explanation quality is not auto-scored.** The report leaves a blank column
for a manual 1-5 rating (or route the raw-output JSON through an LLM judge
separately) -- scoring prose quality is a judgment call this script does not
make for you.

Usage (from the repo root)::

    # New engine only -- works without AWS credentials.
    python eval/rec_leg_comparison.py --new-only

    # Both legs -- needs a running Flask app with working Bedrock credentials
    # (this machine does not have them locally; run from a host that does,
    # e.g. the EC2 instance -- see the plan doc's session bookmark).
    python eval/rec_leg_comparison.py

    python eval/rec_leg_comparison.py --prompts eval/prompts.json --out eval/rec_leg_report.md
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Prompt set includes Hebrew text; Windows consoles default to cp1252/cp437,
# which can't encode it -- force UTF-8 stdout so --new-only et al. don't crash
# on print() alone.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPTS = REPO_ROOT / "eval" / "prompts.json"
DEFAULT_OUT = REPO_ROOT / "eval" / "rec_leg_report.md"
DEFAULT_FLASK_URL = "http://localhost:5000"
DEFAULT_NEW_ENGINE_URL = "http://localhost:8001"
DEFAULT_CONTAINER = "melody-recommendation-service"


def post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return {
                "ok": True,
                "status": resp.status,
                "body": body,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
        return {
            "ok": False,
            "status": exc.code,
            "body": body,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
    except urllib.error.URLError as exc:
        return {
            "ok": False,
            "status": None,
            "body": {"error": str(exc.reason)},
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }


def run_new_engine(prompt_text: str, base_url: str, timeout: float) -> dict[str, Any]:
    result = post_json(f"{base_url}/recommendations/run", {"user_text": prompt_text}, timeout)
    body = result.get("body") or {}
    tracks = body.get("tracks", []) if result["ok"] else []
    artists = sorted({t.get("artist", "").strip() for t in tracks if t.get("artist")})
    return {
        **result,
        "playlist_title": body.get("playlist_title") if result["ok"] else None,
        "playlist_description": body.get("playlist_description") if result["ok"] else None,
        "tracks": tracks,
        "artists": artists,
        "engine": body.get("engine") if result["ok"] else None,
        "placeholder": body.get("placeholder") if result["ok"] else None,
    }


def run_legacy_engine(prompt_text: str, base_url: str, timeout: float) -> dict[str, Any]:
    result = post_json(f"{base_url}/chat", {"user_query": prompt_text}, timeout)
    body = result.get("body") or {}
    text = body.get("response") or body.get("answer") or body.get("error") or ""
    return {**result, "text": text}


def scrape_node_metrics(
    container: str, since_iso: str, node_name: str, timeout: float = 5.0
) -> Optional[dict[str, Any]]:
    """Best-effort: pull the node's structured node_metrics entry from docker
    logs emitted since ``since_iso``. Returns None if docker/the container
    isn't reachable or nothing was found -- never raises, this is optional
    enrichment, not a required signal."""
    if shutil.which("docker") is None:
        return None
    try:
        proc = subprocess.run(
            ["docker", "logs", "--since", since_iso, container],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    for line in reversed(proc.stdout.splitlines() + proc.stderr.splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = record.get("message", "")
        if not message.startswith("node_metrics: "):
            continue
        try:
            payload = json.loads(message[len("node_metrics: "):])
        except json.JSONDecodeError:
            continue
        if node_name in payload:
            return payload[node_name]
    return None


def load_prompts(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["prompts"]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--flask-url", default=DEFAULT_FLASK_URL)
    parser.add_argument("--new-engine-url", default=DEFAULT_NEW_ENGINE_URL)
    parser.add_argument("--new-only", action="store_true", help="Skip the legacy /chat leg entirely.")
    parser.add_argument("--docker-container", default=DEFAULT_CONTAINER)
    parser.add_argument("--no-log-scrape", action="store_true", help="Skip docker-log cost/token scraping.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-request HTTP timeout (seconds).")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    prompts = load_prompts(args.prompts)

    print(f"Running {len(prompts)} prompt(s) — new engine: {args.new_engine_url}"
          + ("" if args.new_only else f" | legacy: {args.flask_url}"))

    rows: list[dict[str, Any]] = []
    all_new_artists: set[str] = set()
    total_cost = 0.0
    cost_samples = 0

    for prompt in prompts:
        prompt_id, category, text = prompt["id"], prompt["category"], prompt["text"]
        print(f"  [{prompt_id}] {text[:60]!r} ...", end=" ", flush=True)

        since_iso = datetime.now(timezone.utc).isoformat()
        new_result = run_new_engine(text, args.new_engine_url, args.timeout)
        all_new_artists.update(new_result["artists"])

        cost_entry = None
        if new_result["ok"] and not args.no_log_scrape:
            cost_entry = scrape_node_metrics(
                args.docker_container, since_iso, "generate_grounded_explanation"
            )
            if cost_entry and cost_entry.get("estimated_cost_usd") is not None:
                total_cost += cost_entry["estimated_cost_usd"]
                cost_samples += 1

        legacy_result = None
        if not args.new_only:
            legacy_result = run_legacy_engine(text, args.flask_url, args.timeout)

        rows.append(
            {
                "id": prompt_id,
                "category": category,
                "text": text,
                "new": new_result,
                "new_cost": cost_entry,
                "legacy": legacy_result,
            }
        )
        status = "ok" if new_result["ok"] else f"HTTP {new_result['status']}"
        print(f"new={status} ({new_result['latency_ms']}ms)"
              + ("" if args.new_only else f", legacy={'ok' if legacy_result['ok'] else legacy_result['status']} ({legacy_result['latency_ms']}ms)"))

    write_report(args.out, rows, all_new_artists, total_cost, cost_samples, new_only=args.new_only)
    print(f"\nReport written to {args.out}")
    return 0


def write_report(
    out_path: Path,
    rows: list[dict[str, Any]],
    all_new_artists: set[str],
    total_cost: float,
    cost_samples: int,
    *,
    new_only: bool,
) -> None:
    lines: list[str] = []
    lines.append("# REC-LEG-001/002 — legacy Bedrock vs. new LangGraph engine")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append(
        "**Read before trusting track-level numbers:** the new engine's provider search is "
        "still fixture-backed until Phase 5, so track identity/diversity/playable-rate columns "
        "for the new engine are not yet meaningful — see the module docstring. Latency, cost, "
        "retrieval grounding, and explanation prose ARE meaningful today."
    )
    lines.append("")

    lines.append("## Per-prompt results")
    lines.append("")
    header = "| id | category | new latency (ms) | new cost (USD) | new tracks | new artists |"
    sep = "|---|---|---|---|---|---|"
    if not new_only:
        header += " legacy latency (ms) | legacy status | explanation quality (1-5, manual) |"
        sep += "---|---|---|"
    lines.append(header)
    lines.append(sep)

    for row in rows:
        new = row["new"]
        cost = row["new_cost"]
        cost_str = f"{cost['estimated_cost_usd']:.6f}" if cost and cost.get("estimated_cost_usd") is not None else "n/a"
        line = (
            f"| {row['id']} | {row['category']} | {new['latency_ms']} | {cost_str} | "
            f"{len(new['tracks'])} | {', '.join(new['artists']) or '—'} |"
        )
        if not new_only:
            legacy = row["legacy"]
            line += f" {legacy['latency_ms']} | {'ok' if legacy['ok'] else legacy['status']} | |"
        lines.append(line)

    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Prompts run: {len(rows)}")
    lines.append(f"- New engine: unique artists across all prompts: {len(all_new_artists)} ({', '.join(sorted(all_new_artists)) or '—'})")
    if cost_samples:
        lines.append(f"- New engine: total measured cost across {cost_samples} call(s): ${total_cost:.6f} (avg ${total_cost / cost_samples:.6f}/call)")
    else:
        lines.append("- New engine: no cost data scraped (pass --docker-container correctly, or check `docker logs` access).")
    if new_only:
        lines.append("- Legacy leg was skipped (`--new-only`). Re-run without it once Bedrock credentials are available (see plan doc).")

    lines.append("")
    lines.append("## Raw responses")
    lines.append("")
    for row in rows:
        lines.append(f"### {row['id']} — {row['text']}")
        lines.append("")
        lines.append("**New engine:**")
        lines.append("```json")
        lines.append(json.dumps({k: v for k, v in row["new"].items() if k != "body"}, ensure_ascii=False, indent=2))
        lines.append("```")
        if row["legacy"] is not None:
            lines.append("**Legacy:**")
            lines.append("```")
            lines.append(row["legacy"]["text"] or "(empty)")
            lines.append("```")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    raw_path = out_path.with_suffix(".json")
    raw_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
