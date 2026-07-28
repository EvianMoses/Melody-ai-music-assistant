"""Smart Sequencer v1 — deterministic track ordering (§7.5, SEQ-001…005).

Orders a set of tracks so consecutive ones sit well together: no jarring tempo
jumps, keys that move sensibly, energy that follows the requested shape.

Three properties the section demands, each of which shapes the code:

**Deterministic.** "The same inputs and version produce the same sequence."
Every tie is broken explicitly — by cost, then by the track's own identity —
because a greedy search over equal-cost candidates is otherwise at the mercy of
dict ordering, and a sequencer that shuffles between runs cannot be tested,
compared or explained.

**Missing metadata lowers confidence; it never invents data.** Most tracks
arrive with no BPM and no key at all — provider-gateway does not supply them and
§6.2 only analyses a clip the *user* uploaded. A sequencer that assumed 120 BPM
for those would produce confident, meaningless orderings. Instead a comparison
against a missing feature contributes a neutral mid-cost, and the reported
confidence falls in proportion to how much was unknown.

**Relevance is not overridden.** "Compatible key movement is preferred but never
overrides recommendation relevance completely." The anchor is the most relevant
track, and rank position stays a term in the cost, so the sequencer can reorder
a good set but cannot promote an irrelevant track for being harmonically handy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

SEQUENCER_VERSION = "smart-sequencer-v1"

# SEQ-002: configurable weights. They sum to 1.0 so a transition cost is
# directly readable as "how bad, out of 1".
DEFAULT_WEIGHTS: dict[str, float] = {
    "bpm": 0.35,
    "key": 0.25,
    "energy": 0.20,
    "genre": 0.10,
    # Keeps the ordering tethered to relevance (see the module docstring).
    "relevance": 0.10,
}

# A tempo change beyond this is jarring however well the keys line up, so the
# BPM term saturates here rather than growing without bound.
MAX_BPM_DISTANCE = 40.0

# What an unknown comparison costs. Deliberately mid-range: a missing feature is
# neither an endorsement nor an objection, and scoring it 0 would make
# featureless tracks win every transition.
UNKNOWN_COST = 0.5

# How far ahead the greedy walk looks. Two is enough to avoid the classic greedy
# trap -- taking a cheap step into a corner with no cheap exit -- without the
# cost of a full search.
LOOK_AHEAD = 2

_CAMELOT_LETTERS = ("A", "B")


def parse_camelot(code: Optional[str]) -> Optional[tuple[int, str]]:
    """`"8A"` → `(8, "A")`. None for anything unparseable."""
    if not code:
        return None
    text = str(code).strip().upper()
    if len(text) < 2:
        return None
    number, letter = text[:-1], text[-1]
    if letter not in _CAMELOT_LETTERS:
        return None
    try:
        value = int(number)
    except ValueError:
        return None
    return (value, letter) if 1 <= value <= 12 else None


def camelot_distance(a: Optional[str], b: Optional[str]) -> Optional[int]:
    """SEQ-001: distance around the Camelot wheel. None if either is unknown.

    The wheel encodes two relationships DJs actually mix on:

    * **±1 at the same letter** is a perfect fifth — the smoothest move there is;
    * **the same number, different letter** is the relative major/minor — equally
      smooth, and the reason mode changes are not simply penalised.

    Both are distance 1. Everything else grows with the number of steps around
    the ring, plus one for also changing mode. Maximum is 7.
    """
    left, right = parse_camelot(a), parse_camelot(b)
    if left is None or right is None:
        return None
    (number_a, letter_a), (number_b, letter_b) = left, right
    ring = min((number_a - number_b) % 12, (number_b - number_a) % 12)
    if letter_a == letter_b:
        return ring
    # Relative major/minor sits at the same number and is a smooth move.
    return 1 if ring == 0 else ring + 1


@dataclass
class TransitionCost:
    total: float
    parts: dict[str, float] = field(default_factory=dict)
    unknown: list[str] = field(default_factory=list)
    reason: str = ""


def _feature(track: dict[str, Any], name: str) -> Any:
    """Read a feature from either the track or a nested `audio_features`."""
    if track.get(name) is not None:
        return track.get(name)
    nested = track.get("audio_features")
    if isinstance(nested, dict):
        return nested.get(name)
    return None


def _describe(parts: dict[str, float], unknown: list[str]) -> str:
    """A short, human sentence about the transition (SEQ-005).

    §7.3 requires unusual recommendations to be explainable, and a sequence is
    the most obviously "unusual" output the app produces — a user who sees an
    order they would not have chosen deserves to know why it was chosen.
    """
    if parts.get("bpm", 1.0) <= 0.15 and parts.get("key", 1.0) <= 0.2:
        base = "tempo and key both line up"
    elif parts.get("bpm", 1.0) <= 0.15:
        base = "close in tempo"
    elif parts.get("key", 1.0) <= 0.2:
        base = "harmonically compatible"
    elif parts.get("energy", 1.0) <= 0.2:
        base = "similar energy"
    else:
        base = "best available step"
    if unknown:
        base += f" ({', '.join(unknown)} unknown)"
    return base


def transition_cost(
    current: dict[str, Any],
    candidate: dict[str, Any],
    *,
    weights: Optional[dict[str, float]] = None,
    candidate_rank: int = 0,
    pool_size: int = 1,
) -> TransitionCost:
    """SEQ-002: cost of playing `candidate` straight after `current`."""
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    parts: dict[str, float] = {}
    unknown: list[str] = []

    bpm_a, bpm_b = _feature(current, "bpm"), _feature(candidate, "bpm")
    if isinstance(bpm_a, (int, float)) and isinstance(bpm_b, (int, float)) and bpm_a and bpm_b:
        parts["bpm"] = min(1.0, abs(float(bpm_a) - float(bpm_b)) / MAX_BPM_DISTANCE)
    else:
        parts["bpm"] = UNKNOWN_COST
        unknown.append("bpm")

    distance = camelot_distance(_feature(current, "camelot"), _feature(candidate, "camelot"))
    if distance is None:
        parts["key"] = UNKNOWN_COST
        unknown.append("key")
    else:
        parts["key"] = min(1.0, distance / 6.0)

    energy_a, energy_b = _feature(current, "energy"), _feature(candidate, "energy")
    if isinstance(energy_a, (int, float)) and isinstance(energy_b, (int, float)):
        parts["energy"] = min(1.0, abs(float(energy_a) - float(energy_b)))
    else:
        parts["energy"] = UNKNOWN_COST
        unknown.append("energy")

    genre_a = str(_feature(current, "genre") or "").lower()
    genre_b = str(_feature(candidate, "genre") or "").lower()
    if genre_a and genre_b:
        parts["genre"] = 0.0 if genre_a == genre_b else 1.0
    else:
        parts["genre"] = UNKNOWN_COST
        unknown.append("genre")

    # Rank position, normalized. This is what stops a harmonically perfect but
    # irrelevant track from climbing the order.
    parts["relevance"] = (candidate_rank / max(1, pool_size - 1)) if pool_size > 1 else 0.0

    total = sum(weights.get(name, 0.0) * value for name, value in parts.items())
    return TransitionCost(
        total=round(total, 6),
        parts={k: round(v, 4) for k, v in parts.items()},
        unknown=unknown,
        reason=_describe(parts, unknown),
    )


def _track_key(track: dict[str, Any], index: int) -> str:
    """A stable identity for tie-breaking. Falls back to position, never to
    object identity -- `id()` varies between runs and would destroy
    determinism."""
    return str(
        track.get("provider_track_id")
        or f"{track.get('artist', '')}|{track.get('title', '')}"
        or index
    )


def sequence_tracks(
    tracks: list[dict[str, Any]],
    *,
    weights: Optional[dict[str, float]] = None,
    look_ahead: int = LOOK_AHEAD,
) -> dict[str, Any]:
    """SEQ-003/004/005: order the tracks and explain each transition.

    Greedy from the most relevant anchor, with a short look-ahead so a cheap
    step into a dead end is avoided. Returns the ordered tracks (each stamped
    with `position` and `transition`), a confidence, and the version.
    """
    if not tracks:
        return {
            "tracks": [],
            "sequencer_version": SEQUENCER_VERSION,
            "confidence": 0.0,
            "transitions": [],
        }

    # SEQ-004 / "remove duplicates": same provider id, or same artist+title.
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, track in enumerate(tracks):
        key = _track_key(track, index)
        if key in seen:
            continue
        seen.add(key)
        unique.append(track)

    pool_size = len(unique)
    # Step 2 of the algorithm: "choose an anchor consistent with the request".
    # The incoming list is already relevance-ordered by `rank_tracks`, so the
    # anchor is its head -- which is what keeps the sequence tethered to what
    # was actually asked for.
    remaining = {_track_key(t, i): (i, t) for i, t in enumerate(unique)}
    anchor_key = _track_key(unique[0], 0)
    order = [remaining.pop(anchor_key)[1]]
    transitions: list[dict[str, Any]] = []

    def best_next(current: dict[str, Any], pool: dict[str, tuple[int, dict]], depth: int):
        """Cheapest next track, looking `depth` steps ahead. Deterministic."""
        best = None
        for key in sorted(pool):                     # sorted: no dict-order luck
            rank, candidate = pool[key]
            cost = transition_cost(
                current, candidate, weights=weights,
                candidate_rank=rank, pool_size=pool_size,
            )
            total = cost.total
            if depth > 1 and len(pool) > 1:
                rest = {k: v for k, v in pool.items() if k != key}
                nxt = best_next(candidate, rest, depth - 1)
                if nxt is not None:
                    # Discounted: the immediate step matters more than a
                    # hypothetical one, but a cheap step into a corner with no
                    # cheap exit should still lose to a slightly dearer step.
                    total += 0.5 * nxt[1]
            # Ties break on the key, so the result cannot depend on iteration
            # order or on how the caller built the list.
            if best is None or (total, key) < (best[1], best[0]):
                best = (key, total, cost)
        return best

    while remaining:
        choice = best_next(order[-1], remaining, look_ahead)
        if choice is None:
            break
        key, _, cost = choice
        _, track = remaining.pop(key)
        transitions.append(
            {
                "from": order[-1].get("title"),
                "to": track.get("title"),
                "cost": cost.total,
                "parts": cost.parts,
                "unknown": cost.unknown,
                "reason": cost.reason,
            }
        )
        order.append(track)

    sequenced = []
    for position, track in enumerate(order, start=1):
        entry = {**track, "position": position}
        if position > 1:
            entry["transition"] = transitions[position - 2]
        sequenced.append(entry)

    # Confidence is the share of comparisons that had real data behind them.
    # Reported rather than assumed, per §7.5's acceptance criteria: "missing
    # metadata produces lower confidence, not invented data".
    if transitions:
        known = sum(4 - len(t["unknown"]) for t in transitions)
        confidence = round(known / (4 * len(transitions)), 3)
    else:
        confidence = 0.0

    return {
        "tracks": sequenced,
        "transitions": transitions,
        "sequencer_version": SEQUENCER_VERSION,
        "confidence": confidence,
    }
