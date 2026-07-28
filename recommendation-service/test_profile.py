"""Preference Profile v1 tests (§7.2, PERS-004/005/006).

PERS-006 names the cases: like, dislike, decay, conflict, guest migration. Each
has one below, plus the determinism property the whole design rests on.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core import profile as pf


def at(days: float = 0.0) -> datetime:
    return datetime(2026, 7, 28, tzinfo=timezone.utc) + timedelta(days=days)


def signal(action, **kw):
    return pf.FeedbackSignal.from_dict({"action": action, **kw})


# ---------------------------------------------------------------------------
# Like / dislike
# ---------------------------------------------------------------------------


def test_like_raises_genre_and_artist_affinity():
    p = pf.Profile()
    p = pf.update(p, signal("like", genre="Shoegaze", artist="Slowdive"), now=at())
    assert p.genres["shoegaze"] > 0
    assert p.artists["slowdive"] > p.genres["shoegaze"]  # narrower claim, faster move
    assert p.version == 1
    assert p.evidence_count == 1


def test_dislike_moves_less_than_like():
    """§7.2: dislike "decreases them more cautiously to avoid overfitting one
    click". The intuitive implementation is the opposite, so this is pinned."""
    liked = pf.update(pf.Profile(), signal("like", genre="jazz"), now=at())
    disliked = pf.update(pf.Profile(), signal("dislike", genre="jazz"), now=at())
    assert abs(disliked.genres["jazz"]) < abs(liked.genres["jazz"])


def test_one_dislike_cannot_erase_a_built_up_taste():
    """The concrete harm the asymmetry exists to prevent."""
    p = pf.Profile()
    for _ in range(5):
        p = pf.update(p, signal("like", genre="shoegaze"), now=at())
    before = p.genres["shoegaze"]
    p = pf.update(p, signal("dislike", genre="shoegaze"), now=at())
    assert p.genres["shoegaze"] > before * 0.85


def test_export_is_the_strongest_implicit_signal():
    """Keeping a track is a stronger statement than tapping like."""
    like = pf.update(pf.Profile(), signal("like", genre="funk"), now=at())
    export = pf.update(pf.Profile(), signal("export", genre="funk"), now=at())
    assert export.genres["funk"] > like.genres["funk"]


# ---------------------------------------------------------------------------
# Skip -- conditional, not a weak dislike
# ---------------------------------------------------------------------------


def test_skip_without_context_teaches_nothing():
    """§7.2: "a weak negative only when context supports that interpretation".
    With no played_fraction there is no context, so the event is recorded but
    changes no weight."""
    p = pf.update(pf.Profile(), signal("skip", genre="techno"), now=at())
    assert p.genres == {}
    assert p.version == 0


def test_early_skip_is_negative_and_late_skip_is_not():
    early = pf.update(pf.Profile(), signal("skip", genre="techno", played_fraction=0.05), now=at())
    late = pf.update(pf.Profile(), signal("skip", genre="techno", played_fraction=0.9), now=at())
    assert early.genres["techno"] < 0
    # Someone who heard 90% of a track did not reject it; they moved on.
    assert late.genres == {}


# ---------------------------------------------------------------------------
# Decay
# ---------------------------------------------------------------------------


def test_affinity_halves_over_the_half_life():
    p = pf.update(pf.Profile(), signal("like", genre="dub"), now=at())
    fresh = p.genres["dub"]
    aged = pf.apply_decay(pf.Profile.from_dict(p.to_dict()), at(pf.DECAY_HALF_LIFE_DAYS))
    assert aged.genres["dub"] == pytest.approx(fresh / 2, rel=0.05)


def test_decay_is_computed_from_elapsed_time_not_from_a_job():
    """The same profile read at the same instant must always give the same
    weights, however many times it is read."""
    p = pf.update(pf.Profile(), signal("like", genre="dub"), now=at())
    a = pf.apply_decay(pf.Profile.from_dict(p.to_dict()), at(10)).to_dict()
    b = pf.apply_decay(pf.Profile.from_dict(p.to_dict()), at(10)).to_dict()
    assert a == b


def test_explicit_preferences_never_decay():
    """Someone who said "I hate country" said something durable."""
    p = pf.set_explicit_genres(pf.Profile(), {"country": -0.9}, now=at())
    aged = pf.apply_decay(p, at(365))
    assert aged.explicit_genres["country"] == -0.9


def test_stale_affinities_are_pruned_rather_than_kept_as_noise():
    p = pf.update(pf.Profile(), signal("like", genre="dub"), now=at())
    aged = pf.apply_decay(pf.Profile.from_dict(p.to_dict()), at(365))
    assert "dub" not in aged.genres


# ---------------------------------------------------------------------------
# Conflict
# ---------------------------------------------------------------------------


def test_explicit_dislike_outranks_inferred_like():
    p = pf.Profile()
    for _ in range(6):
        p = pf.update(p, signal("like", genre="country"), now=at())
    p = pf.set_explicit_genres(p, {"country": -1.0}, now=at())
    assert "country" in p.avoided_genres()
    assert "country" not in p.top_genres()


def test_like_then_dislike_leaves_a_net_position_not_a_reset():
    p = pf.update(pf.Profile(), signal("like", genre="emo"), now=at())
    p = pf.update(p, signal("dislike", genre="emo"), now=at())
    assert 0 < p.genres["emo"] < pf.LIKE_STRENGTH


# ---------------------------------------------------------------------------
# Guest migration (PERS-003)
# ---------------------------------------------------------------------------


def test_guest_evidence_merges_at_reduced_weight():
    user = pf.Profile()
    for _ in range(3):
        user = pf.update(user, signal("like", genre="soul"), now=at())
    guest = pf.update(pf.Profile(), signal("like", genre="soul"), now=at())

    before = user.genres["soul"]
    merged = pf.merge_guest_into_user(user, guest, now=at())
    # Added, but at half weight -- a short unverified session must not be able
    # to overwrite a long history.
    assert merged.genres["soul"] > before
    assert merged.genres["soul"] < before + guest.genres["soul"]
    assert merged.version > 3


def test_empty_guest_profile_changes_nothing():
    user = pf.update(pf.Profile(), signal("like", genre="soul"), now=at())
    before = user.to_dict()
    merged = pf.merge_guest_into_user(user, pf.Profile(), now=at())
    assert merged.to_dict() == before


# ---------------------------------------------------------------------------
# Versioning (PERS-005) and determinism
# ---------------------------------------------------------------------------


def test_version_moves_only_when_something_changed():
    """A version that increments on every request is a counter, not a version,
    and makes "did the profile change?" unanswerable."""
    p = pf.update(pf.Profile(), signal("like", genre="ska"), now=at())
    assert p.version == 1
    unchanged = pf.update(p, signal("bogus-action", genre="ska"), now=at())
    assert unchanged.version == 1


def test_same_inputs_produce_an_identical_profile():
    def build():
        p = pf.Profile()
        for i, action in enumerate(["like", "dislike", "like", "export"]):
            p = pf.update(p, signal(action, genre="dream pop", artist="Beach House"), now=at(i))
        return p.to_dict()

    assert build() == build()


def test_round_trip_through_storage_is_lossless():
    p = pf.update(pf.Profile(), signal("like", genre="Dream Pop", artist="Beach House"), now=at())
    assert pf.Profile.from_dict(p.to_dict()).to_dict() == p.to_dict()


def test_labels_are_normalized_so_one_taste_is_not_learned_twice():
    p = pf.update(pf.Profile(), signal("like", genre="Indie  Folk"), now=at())
    p = pf.update(p, signal("like", genre="indie folk"), now=at())
    assert list(p.genres) == ["indie folk"]


# ---------------------------------------------------------------------------
# §7.3 -- discovery mode is the echo-chamber lever
# ---------------------------------------------------------------------------


def test_discovery_mode_scales_how_much_taste_influences_ranking():
    p = pf.Profile()
    for _ in range(6):
        p = pf.update(p, signal("like", genre="shoegaze"), now=at())
    safe = p.to_graph_profile("safe")["weights"]["personal_taste"]
    balanced = p.to_graph_profile("balanced")["weights"]["personal_taste"]
    adventurous = p.to_graph_profile("adventurous")["weights"]["personal_taste"]
    # Adventurous deliberately turns the profile DOWN -- that is what stops it
    # becoming an echo chamber.
    assert safe > balanced > adventurous > 0


def test_a_profile_with_no_evidence_claims_no_taste_weight():
    """The §4.7 failure this prevents: an empty profile silently zeroing a real
    signal, or worse, claiming taste it does not have."""
    weights = pf.Profile().to_graph_profile()["weights"]
    assert weights["personal_taste"] == 0.0
    assert weights["text_relevance"] == 1.0


def test_graph_profile_matches_the_shape_the_graph_already_accepts():
    p = pf.update(pf.Profile(), signal("like", genre="shoegaze"), now=at())
    shaped = p.to_graph_profile()
    assert {"profile_type", "discovery_mode", "weights", "version"} <= set(shaped)
    assert set(shaped["weights"]) == {"text_relevance", "personal_taste", "provider_taste"}


def test_explain_never_returns_nothing():
    assert pf.explain(pf.Profile())
    p = pf.update(pf.Profile(), signal("like", genre="shoegaze", energy=0.8), now=at())
    assert any("shoegaze" in line for line in pf.explain(p))
