"""Smart Sequencer v1 tests (§7.5, SEQ-001…005) and §7.4's RANK-004/005.

The §7.5 acceptance criteria are stated as four properties, so there is a test
per property rather than a test per function:

  * extreme BPM jumps are avoided when alternatives exist;
  * compatible key movement is preferred but never overrides relevance;
  * missing metadata produces lower confidence, not invented data;
  * the same inputs and version produce the same sequence.
"""

from __future__ import annotations

import pytest

from app.core import graph_nodes as nodes
from app.core import sequencer as seq


def track(title, *, artist="A", bpm=None, camelot=None, energy=None, genre=None, tid=None):
    return {
        "title": title,
        "artist": artist,
        "provider_track_id": tid or title,
        "bpm": bpm,
        "camelot": camelot,
        "energy": energy,
        "genre": genre,
    }


# ---------------------------------------------------------------------------
# SEQ-001 — the Camelot wheel
# ---------------------------------------------------------------------------


def test_camelot_distance_encodes_the_two_smooth_moves():
    """A fifth (±1, same letter) and the relative major/minor (same number,
    different letter) are both distance 1 -- those are what DJs mix on."""
    assert seq.camelot_distance("8A", "8A") == 0
    assert seq.camelot_distance("8A", "9A") == 1      # perfect fifth
    assert seq.camelot_distance("8A", "7A") == 1      # fifth the other way
    assert seq.camelot_distance("8A", "8B") == 1      # relative major
    assert seq.camelot_distance("8A", "2A") == 6      # opposite side of the wheel


def test_camelot_wheel_wraps():
    """12 and 1 are neighbours; treating the number as linear would call them
    eleven steps apart and refuse a perfectly smooth transition."""
    assert seq.camelot_distance("12A", "1A") == 1
    assert seq.camelot_distance("1A", "12A") == 1


def test_camelot_distance_is_none_when_unknown():
    """None, not a number -- so the caller must decide what unknown costs
    instead of silently being handed a real-looking distance."""
    assert seq.camelot_distance(None, "8A") is None
    assert seq.camelot_distance("8A", "banana") is None
    assert seq.camelot_distance("13A", "8A") is None   # out of range
    assert seq.camelot_distance("8C", "8A") is None    # not a Camelot letter


# ---------------------------------------------------------------------------
# SEQ-002/003 — transition cost and ordering
# ---------------------------------------------------------------------------


def test_extreme_bpm_jumps_are_avoided_when_an_alternative_exists():
    """The first acceptance criterion, stated exactly."""
    result = seq.sequence_tracks([
        track("anchor", bpm=120, camelot="8A", energy=0.5, genre="house"),
        track("far", bpm=175, camelot="8A", energy=0.5, genre="house"),
        track("near", bpm=124, camelot="8A", energy=0.5, genre="house"),
    ])
    order = [t["title"] for t in result["tracks"]]
    assert order == ["anchor", "near", "far"]


def test_compatible_keys_are_preferred_when_tempo_is_equal():
    result = seq.sequence_tracks([
        track("anchor", bpm=120, camelot="8A", energy=0.5, genre="g"),
        track("distant-key", bpm=120, camelot="2A", energy=0.5, genre="g"),
        track("fifth", bpm=120, camelot="9A", energy=0.5, genre="g"),
    ])
    assert [t["title"] for t in result["tracks"]] == ["anchor", "fifth", "distant-key"]


def test_key_compatibility_does_not_override_relevance_completely():
    """§7.5: "preferred but never overrides recommendation relevance
    completely". The list arrives relevance-ordered, and a harmonically perfect
    but far-down candidate must not leapfrog a near-perfect relevant one."""
    ranked = [track("anchor", bpm=120, camelot="8A", energy=0.5, genre="g")]
    ranked += [track(f"filler{i}", bpm=120, camelot="9A", energy=0.5, genre="g")
               for i in range(8)]
    ranked.append(track("perfect-but-last", bpm=120, camelot="8A", energy=0.5, genre="g"))
    result = seq.sequence_tracks(ranked)
    # The identical-key track is last in relevance; it must not come second.
    assert result["tracks"][1]["title"] != "perfect-but-last"


def test_anchor_is_the_most_relevant_track():
    result = seq.sequence_tracks([
        track("most-relevant", bpm=90),
        track("other", bpm=91),
    ])
    assert result["tracks"][0]["title"] == "most-relevant"


def test_weights_are_configurable():
    """SEQ-002 requires configurable weights -- with key weighted to zero, the
    ordering must stop caring about keys."""
    tracks = [
        track("anchor", bpm=120, camelot="8A", energy=0.5, genre="g"),
        track("same-key-slower", bpm=100, camelot="8A", energy=0.5, genre="g"),
        track("far-key-closer", bpm=121, camelot="2A", energy=0.5, genre="g"),
    ]
    keyless = seq.sequence_tracks(tracks, weights={"key": 0.0, "bpm": 0.6})
    assert [t["title"] for t in keyless["tracks"]][1] == "far-key-closer"


# ---------------------------------------------------------------------------
# SEQ-004 — missing metadata
# ---------------------------------------------------------------------------


def test_missing_features_lower_confidence_rather_than_being_invented():
    """The failure this prevents: assuming 120 BPM for every unknown track and
    producing a confident, meaningless ordering."""
    known = seq.sequence_tracks([
        track("a", bpm=120, camelot="8A", energy=0.5, genre="g"),
        track("b", bpm=122, camelot="9A", energy=0.5, genre="g"),
    ])
    unknown = seq.sequence_tracks([track("a"), track("b")])
    assert known["confidence"] == 1.0
    assert unknown["confidence"] == 0.0
    # No feature was fabricated on the way through.
    assert all(t.get("bpm") is None for t in unknown["tracks"])


def test_tracks_without_features_still_get_sequenced():
    """Most real tracks have no BPM or key -- provider-gateway supplies neither.
    A sequencer that only worked on analysed audio would never run."""
    result = seq.sequence_tracks([track(f"t{i}") for i in range(9)])
    assert len(result["tracks"]) == 9
    assert [t["position"] for t in result["tracks"]] == list(range(1, 10))


def test_partial_features_give_partial_confidence():
    result = seq.sequence_tracks([
        track("a", bpm=120, energy=0.5),
        track("b", bpm=122, energy=0.5),
    ])
    assert 0.0 < result["confidence"] < 1.0


# ---------------------------------------------------------------------------
# SEQ-005 — the order and its reasons are stored
# ---------------------------------------------------------------------------


def test_every_transition_carries_a_reason_and_its_components():
    result = seq.sequence_tracks([
        track("a", bpm=120, camelot="8A", energy=0.5, genre="house"),
        track("b", bpm=121, camelot="9A", energy=0.5, genre="house"),
    ])
    transition = result["tracks"][1]["transition"]
    assert transition["reason"]
    assert set(transition["parts"]) == {"bpm", "key", "energy", "genre", "relevance"}
    assert result["sequencer_version"] == seq.SEQUENCER_VERSION


def test_unknown_features_are_named_in_the_reason():
    result = seq.sequence_tracks([track("a", bpm=120), track("b", bpm=121)])
    transition = result["tracks"][1]["transition"]
    assert "key" in transition["unknown"]
    assert "unknown" in transition["reason"]


# ---------------------------------------------------------------------------
# Determinism — "the same inputs and version produce the same sequence"
# ---------------------------------------------------------------------------


def test_identical_input_produces_an_identical_sequence():
    tracks = [
        track(f"t{i}", bpm=100 + i * 3, camelot=f"{(i % 12) + 1}A", energy=i / 10, genre="g")
        for i in range(10)
    ]
    first = seq.sequence_tracks(list(tracks))
    second = seq.sequence_tracks(list(tracks))
    assert [t["title"] for t in first["tracks"]] == [t["title"] for t in second["tracks"]]


def test_equal_cost_candidates_break_ties_deterministically():
    """Three identical candidates: without an explicit tie-break the winner
    depends on iteration order, and the sequence changes between runs."""
    tracks = [track("anchor", bpm=120)] + [
        track(f"same{i}", bpm=130, tid=f"same{i}") for i in range(3)
    ]
    runs = {tuple(t["title"] for t in seq.sequence_tracks(list(tracks))["tracks"])
            for _ in range(5)}
    assert len(runs) == 1


def test_duplicates_are_removed_before_ordering():
    result = seq.sequence_tracks([
        track("a", tid="x"), track("a-again", tid="x"), track("b", tid="y"),
    ])
    assert len(result["tracks"]) == 2


def test_empty_input_is_not_an_error():
    result = seq.sequence_tracks([])
    assert result["tracks"] == []
    assert result["confidence"] == 0.0


def test_eight_to_twelve_tracks_order_completely():
    """SEQ-003 sizes a sequence at 8-12; every track must come out."""
    for size in (8, 10, 12):
        tracks = [track(f"t{i}", bpm=100 + i, camelot="8A") for i in range(size)]
        result = seq.sequence_tracks(tracks)
        assert len(result["tracks"]) == size
        assert len({t["title"] for t in result["tracks"]}) == size


# ---------------------------------------------------------------------------
# §7.4 — RANK-004 diversity, RANK-005 deterministic fixtures
# ---------------------------------------------------------------------------


def test_artist_repetition_is_capped():
    """§7.3's artist cap. The ranker pushes *towards* repetition -- if one track
    by an artist scores well, so will their next four -- so this is a correction
    to its own logic, not a general safeguard."""
    ranked = [
        {"title": f"s{i}", "artist": "Slowdive", "final_score": 0.9 - i / 100}
        for i in range(5)
    ] + [{"title": "other", "artist": "Ride", "final_score": 0.5}]
    out, demoted = nodes.apply_diversity_constraints(ranked, max_per_artist=2)
    head = [t["artist"] for t in out[:3]]
    assert head.count("Slowdive") == 2
    assert "Ride" in head
    assert demoted == 3


def test_over_cap_tracks_are_demoted_not_dropped():
    """A request that legitimately has one relevant artist must still return
    tracks -- "we found nothing" is a worse answer than "several by one artist"."""
    ranked = [{"title": f"s{i}", "artist": "Slowdive", "final_score": 0.9} for i in range(5)]
    out, demoted = nodes.apply_diversity_constraints(ranked, max_per_artist=2)
    assert len(out) == 5
    assert demoted == 3
    assert all(t.get("diversity_demoted") for t in out[2:])


def test_personal_taste_is_no_longer_a_constant():
    """It was hardcoded to 1.0, which made the component inert: a constant
    multiplied by any weight contributes equally to every candidate, so the
    profile could not reorder anything at all."""
    profile = {
        "preferred_artists": ["slowdive"],
        "preferred_genres": ["shoegaze"],
        "avoided_genres": ["country"],
    }
    loved = nodes._personal_taste_score({"title": "Alison", "artist": "Slowdive"}, profile)
    neutral = nodes._personal_taste_score({"title": "X", "artist": "Nobody"}, profile)
    avoided = nodes._personal_taste_score({"title": "Country Roads", "artist": "N"}, profile)
    assert loved > neutral > avoided
    assert neutral == 0.5          # unknown territory is neither rewarded nor punished


def test_no_profile_scores_every_track_neutrally():
    assert nodes._personal_taste_score({"title": "t", "artist": "a"}, {}) == 0.5


def test_ranking_is_deterministic_for_known_fixtures():
    """RANK-005. Equal scores previously left the order to `list.sort` stability
    over whatever order the candidates arrived in."""
    state = {
        "user_profile": {"weights": {"text_relevance": 1.0, "personal_taste": 0.0,
                                     "provider_taste": 0.0}},
        "retrieval_query": {"positive_constraints": {}},
        "normalized_text": "dreamy",
        "resolved_tracks": [
            {"title": "b", "artist": "x", "confidence": 0.5, "provider_track_id": "1"},
            {"title": "a", "artist": "y", "confidence": 0.5, "provider_track_id": "2"},
        ],
    }
    first = [t["title"] for t in nodes.rank_tracks(dict(state))["ranked_tracks"]]
    second = [t["title"] for t in nodes.rank_tracks(dict(state))["ranked_tracks"]]
    assert first == second
