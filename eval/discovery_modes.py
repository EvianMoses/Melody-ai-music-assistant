"""Do Safe / Balanced / Adventurous differ *measurably*? (§7.3, Phase 7 gate)

The gate criterion is "produce measurably different novelty behavior", and §7.3
is specific about what to measure: "evaluate catalog and genre diversity, not
only Like rate". A unit test showing the taste weight is ordered 1.4 > 1.0 >
0.55 proves the lever moves; it does not prove the output does.

    docker compose exec -e RECOMMENDATION_TRACK_LIMIT=8 \
      recommendation-service python -m eval.discovery_modes

**Method.** A profile is seeded with a known taste (shoegaze / Slowdive), then
the same query set runs in each mode. Seeding matters: with an empty profile
`personal_taste` weighs nothing whatever the mode says, so an unseeded run would
show three identical columns and "prove" the modes do not work.

**What is reported**

* *familiar share* — the fraction of returned tracks matching the profile's
  known artists or genres. This is the number the modes are supposed to move.
* *unique artists* — catalog diversity. A mode that returns novel-but-repetitive
  results is not exploring, it is just missing.
* *distinct genres* — genre diversity, per §7.3.
* *overlap with safe* — how much of the adventurous set the safe set already
  contained. Low overlap is the point of the mode existing.

The provider is live, so results move between runs. Anything reported from this
must state the query set and the date; it is a measurement, not a constant.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from app.core import profile as pf
from app.core.graph import recommendation_graph

MODES = ("safe", "balanced", "adventurous")

DEFAULT_QUERIES = [
    "dreamy shoegaze for a rainy night",
    "something warm and mellow for the evening",
    "energetic guitar music for running",
    "quiet music to read to",
]


def seeded_profile() -> dict[str, Any]:
    """A profile with real evidence, built through the public update path."""
    built = pf.Profile()
    for _ in range(6):
        built = pf.update(
            built,
            pf.FeedbackSignal.from_dict(
                {"action": "like", "genre": "shoegaze", "artist": "Slowdive", "energy": 0.4}
            ),
        )
    return built


async def run_query(text: str, mode: str, graph_profile: dict[str, Any]) -> list[dict]:
    state = {
        "request_id": f"eval-{mode}",
        "user_text": text,
        "discovery_mode": mode,
        "provider": "youtube",
        "user_profile": graph_profile,
        "audio_features": {},
        "explicit_constraints": {},
    }
    out = await recommendation_graph.ainvoke(state)
    return out.get("sequenced_tracks") or out.get("ranked_tracks") or []


def familiar(track: dict, profile: pf.Profile) -> bool:
    haystack = f"{track.get('title', '')} {track.get('artist', '')}".lower()
    if any(a in haystack for a in profile.artists):
        return True
    return any(g in haystack for g in profile.genres)


async def main(args) -> None:
    built = seeded_profile()
    print(f"seeded profile: v{built.version} "
          f"genres={dict(built.genres)} artists={dict(built.artists)}\n")

    results: dict[str, list[dict]] = {}
    for mode in MODES:
        graph_profile = built.to_graph_profile(mode)
        tracks: list[dict] = []
        for query in args.queries:
            tracks.extend(await run_query(query, mode, graph_profile))
        results[mode] = tracks
        print(f"  {mode:<12} taste_weight="
              f"{graph_profile['weights']['personal_taste']:<6} "
              f"tracks={len(tracks)}")

    safe_ids = {t.get("provider_track_id") for t in results["safe"]}

    print(f"\n{'mode':<13}{'tracks':>7}{'familiar':>10}{'artists':>9}"
          f"{'genres':>8}{'overlap/safe':>14}")
    report: dict[str, Any] = {"queries": args.queries, "modes": {}}
    for mode in MODES:
        tracks = results[mode]
        if not tracks:
            print(f"{mode:<13}{0:>7}{'-':>10}{'-':>9}{'-':>8}{'-':>14}")
            continue
        familiar_share = sum(familiar(t, built) for t in tracks) / len(tracks)
        artists = {str(t.get("artist", "")).strip().lower() for t in tracks if t.get("artist")}
        genres = {
            str((t.get("audio_features") or {}).get("genre") or t.get("genre") or "").lower()
            for t in tracks
        } - {""}
        ids = {t.get("provider_track_id") for t in tracks}
        overlap = len(ids & safe_ids) / len(ids) if ids else 0.0

        print(f"{mode:<13}{len(tracks):>7}{familiar_share:>10.2f}{len(artists):>9}"
              f"{len(genres):>8}{overlap:>14.2f}")
        report["modes"][mode] = {
            "tracks": len(tracks),
            "familiar_share": round(familiar_share, 3),
            "unique_artists": len(artists),
            "distinct_genres": len(genres),
            "overlap_with_safe": round(overlap, 3),
        }

    modes = report["modes"]
    if {"safe", "adventurous"} <= set(modes):
        delta = modes["safe"]["familiar_share"] - modes["adventurous"]["familiar_share"]
        report["safe_minus_adventurous_familiarity"] = round(delta, 3)
        print(f"\nfamiliarity gap safe - adventurous: {delta:+.2f}")
        print("  positive = safe returns more of what the profile already knows,"
              "\n  which is the behaviour the modes exist to produce.")

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwritten: {args.out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", nargs="*", default=DEFAULT_QUERIES)
    parser.add_argument("--out", default="/app/eval_discovery_modes.json")
    asyncio.run(main(parser.parse_args()))
