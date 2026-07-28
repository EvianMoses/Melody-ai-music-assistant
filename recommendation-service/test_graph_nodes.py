"""Unit tests for graph nodes 5-18 (plan §4.2/§4.3): idempotent, individually
testable, never raise. External calls (rag-service, provider-gateway,
Anthropic) are monkeypatched so these run fast and offline, matching the
project's pattern of keeping unit tests independent of docker/network.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core import graph_nodes as nodes
from app.core import llm_adapter, provider_client, rag_client
from app.core.graph import recommendation_graph


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fakes for the three external seams.
# ---------------------------------------------------------------------------


async def _fake_rag_retrieve_ok(query, *, domain, top_k=5, year_from=None, year_to=None):
    return {
        "query": query,
        "chunks": [
            {
                "document_id": f"doc-{domain}-1",
                "chunk_text": "Indie folk blends acoustic instrumentation.",
                "score": 0.8,
                "metadata": {"domain": domain},
            }
        ],
        "retrieval_confidence": 0.8,
        "matched_genres": {"indie folk": ["dream pop", "chamber pop"]},
    }


async def _fake_rag_retrieve_low_confidence(query, *, domain, top_k=5, year_from=None, year_to=None):
    return {"query": query, "chunks": [], "retrieval_confidence": 0.1, "matched_genres": {}}


async def _fake_rag_retrieve_error(*_args, **_kwargs):
    raise httpx.ConnectError("connection refused")


async def _fake_provider_search_ok(query, *, provider="youtube", limit=5):
    return {
        "provider": provider,
        "results": [
            {
                "provider": provider,
                "provider_track_id": "fixture-1",
                "title": "Holocene",
                "artist": "Bon Iver",
                "url": "https://youtube.example/fixture-1",
                "confidence": 0.9,
            }
        ],
    }


async def _fake_provider_search_error(*_args, **_kwargs):
    raise httpx.ConnectError("connection refused")


async def _fake_llm_success(**_kwargs):
    return llm_adapter.AdapterResult(
        success=True,
        model="claude-haiku-4-5",
        latency_ms=12.3,
        input_tokens=120,
        output_tokens=40,
        estimated_cost_usd=0.00032,
        request_id="req-fake-1",
        playlist_title="Warm Indie Evenings",
        playlist_description="A cozy set for a quiet night.",
        track_reasons={0: "Spacious, warm production fits the mood."},
    )


async def _fake_llm_failure(**_kwargs):
    return llm_adapter.AdapterResult(success=False, model="claude-haiku-4-5", error="connection refused")


# ---------------------------------------------------------------------------
# 5-6: retrieve_genres / retrieve_reviews
# ---------------------------------------------------------------------------


def test_retrieve_genres_happy_path(monkeypatch):
    monkeypatch.setattr(rag_client, "retrieve", _fake_rag_retrieve_ok)
    state = {"retrieval_query": {"text": "warm indie folk", "positive_constraints": {}, "discovery_mode": "balanced"}}
    result = run(nodes.retrieve_genres(state))
    assert len(result["retrieved_genres"]) == 1
    assert result["_retrieval_debug"]["genre"]["confidence"] == 0.8
    assert result["node_metrics"]["retrieve_genres"]["status"] == "ok"


def test_retrieve_genres_degrades_on_http_error(monkeypatch):
    monkeypatch.setattr(rag_client, "retrieve", _fake_rag_retrieve_error)
    state = {"retrieval_query": {"text": "warm indie folk", "positive_constraints": {}, "discovery_mode": "balanced"}}
    result = run(nodes.retrieve_genres(state))
    assert result["retrieved_genres"] == []
    assert result["node_metrics"]["retrieve_genres"]["status"] == "error"
    assert result["warnings"]


def test_retrieve_genres_skips_when_no_text(monkeypatch):
    called = False

    async def _should_not_be_called(*_a, **_k):
        nonlocal called
        called = True

    monkeypatch.setattr(rag_client, "retrieve", _should_not_be_called)
    result = run(nodes.retrieve_genres({"retrieval_query": {"text": "", "positive_constraints": {}}}))
    assert called is False
    assert result["node_metrics"]["retrieve_genres"]["status"] == "skipped"


def test_retrieve_reviews_merges_into_existing_debug(monkeypatch):
    monkeypatch.setattr(rag_client, "retrieve", _fake_rag_retrieve_ok)
    state = {
        "retrieval_query": {"text": "warm indie folk", "positive_constraints": {}, "discovery_mode": "balanced"},
        "_retrieval_debug": {"genre": {"matched_genres": {}, "confidence": 0.8}},
    }
    result = run(nodes.retrieve_reviews(state))
    # node 6 must not clobber node 5's entry.
    assert "genre" in result["_retrieval_debug"]
    assert "reviews" in result["_retrieval_debug"]


# ---------------------------------------------------------------------------
# 7-9: expand_genre_graph / fuse_results / rerank_documents
# ---------------------------------------------------------------------------


def test_expand_genre_graph_flattens_and_dedupes():
    state = {
        "_retrieval_debug": {
            "genre": {"matched_genres": {"indie folk": ["dream pop", "chamber pop"]}},
            "reviews": {"matched_genres": {"indie folk": ["dream pop"]}},
        }
    }
    result = nodes.expand_genre_graph(state)
    assert result["expanded_genre_terms"] == ["dream pop", "chamber pop"]


def test_fuse_results_dedupes_by_document_id_keeping_higher_score():
    state = {
        "retrieved_genres": [{"document_id": "doc-1", "score": 0.5}],
        "retrieved_reviews": [{"document_id": "doc-1", "score": 0.9}, {"document_id": "doc-2", "score": 0.3}],
    }
    result = nodes.fuse_results(state)
    fused = {c["document_id"]: c["score"] for c in result["fused_chunks"]}
    assert fused == {"doc-1": 0.9, "doc-2": 0.3}
    assert result["fused_chunks"][0]["document_id"] == "doc-1"  # sorted desc


def test_rerank_documents_slices_to_top_eight():
    chunks = [{"document_id": f"doc-{i}", "score": i / 10} for i in range(12)]
    result = nodes.rerank_documents({"fused_chunks": chunks})
    assert len(result["reranked_chunks"]) == 8
    assert result["reranked_chunks"][0]["document_id"] == "doc-11"


# ---------------------------------------------------------------------------
# 10-11: confidence gate and bounded rewrite
# ---------------------------------------------------------------------------


def test_evaluate_retrieval_confidence_averages_domains():
    state = {
        "_retrieval_debug": {"genre": {"confidence": 0.8}, "reviews": {"confidence": 0.4}},
        "reranked_chunks": [{"document_id": "doc-1"}],
    }
    result = nodes.evaluate_retrieval_confidence(state)
    assert result["retrieval_confidence"] == 0.6


def test_evaluate_retrieval_confidence_forced_zero_when_nothing_retrieved():
    state = {"_retrieval_debug": {"genre": {"confidence": 0.9}}, "reranked_chunks": []}
    result = nodes.evaluate_retrieval_confidence(state)
    assert result["retrieval_confidence"] == 0.0


def test_rewrite_query_drops_year_range_first():
    state = {
        "retrieval_query": {
            "positive_constraints": {"year_from": 2015, "year_to": 2020},
            "discovery_params": {"candidate_pool": 20, "genre_expansion": False},
        },
        "rewrite_count": 0,
    }
    result = nodes.rewrite_query(state)
    assert result["rewrite_count"] == 1
    assert "year_from" not in result["retrieval_query"]["positive_constraints"]
    assert "relaxed year range" in result["rewrite_reason"]


def test_rewrite_query_widens_pool_when_no_year_constraint():
    state = {
        "retrieval_query": {
            "positive_constraints": {},
            "discovery_params": {"candidate_pool": 20, "genre_expansion": False},
        },
        "rewrite_count": 0,
    }
    result = nodes.rewrite_query(state)
    assert result["retrieval_query"]["discovery_params"]["candidate_pool"] == 30
    assert "widened candidate pool" in result["rewrite_reason"]


def test_rewrite_query_enables_genre_expansion_last():
    state = {
        "retrieval_query": {
            "positive_constraints": {},
            "discovery_params": {"candidate_pool": 40, "genre_expansion": False},
        },
        "rewrite_count": 0,
    }
    result = nodes.rewrite_query(state)
    assert result["retrieval_query"]["discovery_params"]["genre_expansion"] is True
    assert "enabled genre expansion" in result["rewrite_reason"]


# ---------------------------------------------------------------------------
# 12-15: provider search intents, provider reads, dedup, ranking
# ---------------------------------------------------------------------------


def test_build_provider_search_intents_uses_constraints_and_evidence():
    state = {
        "retrieval_query": {"positive_constraints": {"artists": ["bon iver"], "genres": ["indie folk"]}, "text": "warm"},
        "reranked_chunks": [{"document_id": "genre:dream-pop", "metadata": {"domain": "genre"}}],
    }
    result = nodes.build_provider_search_intents(state)
    intent = result["provider_search_intents"][0]
    assert "bon iver" in intent["query"]
    assert intent["provider"] == "youtube"


def test_build_provider_search_intents_falls_back_to_text():
    state = {"retrieval_query": {"positive_constraints": {}, "text": "moody instrumental"}}
    result = nodes.build_provider_search_intents(state)
    assert result["provider_search_intents"][0]["query"] == "moody instrumental"


def test_clean_genre_slug_prefers_specific_subgenre():
    assert nodes._clean_genre_slug("genre:edm_dance_house#deep_house") == "deep house"


def test_clean_genre_slug_falls_back_to_parent_when_child_is_generic_overview():
    assert nodes._clean_genre_slug("genre:edm_dance_trance#overview") == "edm dance trance"


def test_clean_genre_slug_handles_no_hash():
    assert nodes._clean_genre_slug("genre:dream-pop") == "dream pop"


# Regression test for a real bug found live via REC-LEG-002 (2026-07-25): two
# unrelated genre chunks got concatenated into one incoherent compound query
# ("edm_dance_trance#overview rock_hardcore_punk#overview"), which returned
# zero YouTube results for 7/12 recommendations. Each chunk must become its
# own separate, focused intent instead.
def test_build_provider_search_intents_keeps_unrelated_chunks_as_separate_intents():
    state = {
        "retrieval_query": {"positive_constraints": {}, "text": "something"},
        "reranked_chunks": [
            {"document_id": "genre:edm_dance_trance#overview", "metadata": {"domain": "genre"}},
            {"document_id": "genre:rock_hardcore_punk#overview", "metadata": {"domain": "genre"}},
        ],
    }
    result = nodes.build_provider_search_intents(state)
    queries = [i["query"] for i in result["provider_search_intents"]]
    # Two chunk intents plus the user's own text (see the test below).
    assert len(queries) == 3
    # Never combined into one incoherent compound string.
    assert not any("trance" in q.lower() and "punk" in q.lower() for q in queries)
    assert any("edm dance trance" in q for q in queries)
    assert any("rock hardcore punk" in q for q in queries)
    assert all("_" not in q and "#" not in q for q in queries)


# Regression test for the defect found in the browser (2026-07-26): the user's
# own words were only searched when *nothing else* produced an intent, so
# "dreamy shoegaze for a rainy night" collapsed to the single derived query
# "dream pop shoegaze" -- whose entire first page was hour-long compilations
# and a 52-second explainer video, all of which reached the UI as tracks.
def test_build_provider_search_intents_always_searches_the_user_text():
    state = {
        "retrieval_query": {
            "positive_constraints": {"genres": ["dream pop", "shoegaze"]},
            "text": "dreamy shoegaze for a rainy night",
        },
    }
    result = nodes.build_provider_search_intents(state)
    queries = [i["query"] for i in result["provider_search_intents"]]
    assert "dreamy shoegaze for a rainy night" in queries
    # The derived-constraint intent is kept as well, not replaced.
    assert any("shoegaze" in q and q != "dreamy shoegaze for a rainy night" for q in queries)


# §5.6: the UI toggle sets a default; naming a provider in the message wins.
def test_resolve_provider_defaults_to_youtube():
    assert nodes.resolve_provider({}) == "youtube"


def test_resolve_provider_honours_the_selected_mode():
    assert nodes.resolve_provider({"provider": "spotify"}) == "spotify"


def test_resolve_provider_ignores_an_unknown_mode():
    assert nodes.resolve_provider({"provider": "soundcloud"}) == "youtube"


def test_explicit_spotify_request_overrides_a_youtube_toggle():
    state = {"provider": "youtube", "user_text": "find me something on Spotify"}
    assert nodes.resolve_provider(state) == "spotify"


def test_explicit_youtube_request_overrides_a_spotify_toggle():
    state = {"provider": "spotify", "user_text": "show me a YouTube video of this"}
    assert nodes.resolve_provider(state) == "youtube"


def test_explicit_provider_request_works_in_hebrew():
    state = {"provider": "youtube", "user_text": "תמצא לי שיר בספוטיפיי"}
    assert nodes.resolve_provider(state) == "spotify"


def test_search_intents_carry_the_resolved_provider():
    state = {
        "provider": "spotify",
        "retrieval_query": {"positive_constraints": {}, "text": "warm indie folk"},
    }
    result = nodes.build_provider_search_intents(state)
    assert all(i["provider"] == "spotify" for i in result["provider_search_intents"])


def test_build_provider_search_intents_does_not_duplicate_identical_text():
    """When the derived query equals the user text, it is searched once."""
    state = {"retrieval_query": {"positive_constraints": {"genres": ["jazz"]}, "text": "jazz"}}
    result = nodes.build_provider_search_intents(state)
    assert [i["query"] for i in result["provider_search_intents"]] == ["jazz"]


def test_search_providers_happy_path(monkeypatch):
    monkeypatch.setattr(provider_client, "search", _fake_provider_search_ok)
    state = {"provider_search_intents": [{"query": "warm indie", "provider": "youtube", "limit": 5}]}
    result = run(nodes.search_providers(state))
    assert len(result["candidate_tracks"]) == 1
    assert result["candidate_tracks"][0]["title"] == "Holocene"


def test_search_providers_degrades_on_error(monkeypatch):
    monkeypatch.setattr(provider_client, "search", _fake_provider_search_error)
    state = {"provider_search_intents": [{"query": "warm indie", "provider": "youtube", "limit": 5}]}
    result = run(nodes.search_providers(state))
    assert result["candidate_tracks"] == []
    assert result["node_metrics"]["search_providers"]["status"] == "error"


def test_deduplicate_and_resolve_tracks_keeps_highest_confidence():
    state = {
        "candidate_tracks": [
            {"title": "Holocene", "artist": "Bon Iver", "provider_track_id": "a", "confidence": 0.5},
            {"title": "Holocene", "artist": "Bon Iver", "provider_track_id": "b", "confidence": 0.9},
            {"title": "Unresolved", "artist": "Nobody", "provider_track_id": None, "confidence": 0.9},
        ]
    }
    result = nodes.deduplicate_and_resolve_tracks(state)
    assert len(result["resolved_tracks"]) == 1
    assert result["resolved_tracks"][0]["provider_track_id"] == "b"


def test_rank_tracks_redistributes_when_only_text_relevance_weighted():
    state = {
        "user_profile": {"weights": {"text_relevance": 1.0, "personal_taste": 0.0, "provider_taste": 0.0}},
        "retrieval_query": {"positive_constraints": {}},
        "normalized_text": "bon iver",
        "resolved_tracks": [{"title": "Holocene", "artist": "Bon Iver", "confidence": 0.9}],
    }
    result = nodes.rank_tracks(state)
    track = result["ranked_tracks"][0]
    assert 0.0 <= track["final_score"] <= 1.0
    assert set(track["score_components"]) == {
        "provider_confidence",
        "text_relevance",
        "personal_taste",
        "provider_taste",
    }


# Regression test for a real ranking bug found live (2026-07-25): the
# provider's result-quality confidence was mapped onto the guest profile's
# `provider_taste` weight of 0.0, so it was multiplied away and ranking
# collapsed to pure fuzzy text match -- which rewards titles that repeat the
# genre word. Result: a video essay titled "Top 5 Grunge Songs of All Time"
# outranked Nirvana's actual recording of "Smells Like Teen Spirit".
def test_rank_tracks_uses_provider_confidence_even_for_guest_profile():
    guest_weights = nodes.GUEST_PROFILE["weights"]
    assert guest_weights["provider_taste"] == 0.0, "guard: guests genuinely have no provider taste"

    state = {
        "user_profile": nodes.GUEST_PROFILE,
        "retrieval_query": {"positive_constraints": {}},
        "normalized_text": "90s grunge for a moody night",
        "resolved_tracks": [
            # Junk: provider scored it low, but its title is stuffed with the
            # query's words, so pure text relevance ranks it top.
            {"title": "Top 5 Grunge Songs of All Time", "artist": "Rock N Replay", "confidence": 0.1},
            # Real track: provider is confident, title shares fewer query words.
            {"title": "Smells Like Teen Spirit", "artist": "Nirvana", "confidence": 0.95},
        ],
    }
    ranked = nodes.rank_tracks(state)["ranked_tracks"]
    assert ranked[0]["artist"] == "Nirvana", (
        "provider confidence must outweigh keyword-stuffed titles: "
        f"got {[(t['artist'], t['final_score']) for t in ranked]}"
    )
    assert ranked[0]["score_components"]["provider_confidence"]["weight"] > 0


# ---------------------------------------------------------------------------
# 16-18: sequencing, grounded explanation, output validation
# ---------------------------------------------------------------------------


def test_sequence_tracks_stamps_position(monkeypatch):
    # Raise the limit so this stays a test of *position stamping* rather than
    # of the one-recommendation-per-request default (covered separately below).
    monkeypatch.setenv("RECOMMENDATION_TRACK_LIMIT", "10")
    state = {"ranked_tracks": [{"title": "A"}, {"title": "B"}]}
    result = nodes.sequence_tracks(state)
    assert [t["position"] for t in result["sequenced_tracks"]] == [1, 2]


def test_generate_grounded_explanation_skips_when_no_tracks():
    result = run(nodes.generate_grounded_explanation({"sequenced_tracks": []}))
    assert result["node_metrics"]["generate_grounded_explanation"]["status"] == "skipped"
    assert result["curator_explanation"]


def test_generate_grounded_explanation_success(monkeypatch):
    monkeypatch.setattr(llm_adapter, "generate_curator_explanation", _fake_llm_success)
    state = {"sequenced_tracks": [{"title": "Holocene", "artist": "Bon Iver", "position": 1}]}
    result = run(nodes.generate_grounded_explanation(state))
    assert result["playlist_title"] == "Warm Indie Evenings"
    assert result["sequenced_tracks"][0]["reasoning"]


def test_generate_grounded_explanation_failure_invalidates_output(monkeypatch):
    monkeypatch.setattr(llm_adapter, "generate_curator_explanation", _fake_llm_failure)
    state = {"sequenced_tracks": [{"title": "Holocene", "artist": "Bon Iver", "position": 1}]}
    result = run(nodes.generate_grounded_explanation(state))
    assert result["output_valid"] is False


# Regression test for the defect seen in the browser (2026-07-26): a 52-second
# explainer Short ranked first and three 49-91 minute compilations followed,
# all with Play buttons. provider-gateway flags them, but its "never return an
# empty list" fallback runs per search query, so they still reach this node.
def test_deduplicate_drops_non_track_lengths_when_enough_real_tracks():
    state = {
        "candidate_tracks": [
            {"title": "What's the difference between Shoegaze & Dreampop", "artist": "pedal partners",
             "provider_track_id": "v0", "confidence": 0.4, "duration_in_track_range": False},
            {"title": "that warm summer // shoegaze mix", "artist": "mentaldisorders",
             "provider_track_id": "v1", "confidence": 0.5, "duration_in_track_range": False},
            {"title": "Sometimes", "artist": "My Bloody Valentine",
             "provider_track_id": "v2", "confidence": 0.9, "duration_in_track_range": True},
            {"title": "Alison", "artist": "Slowdive",
             "provider_track_id": "v3", "confidence": 0.9, "duration_in_track_range": True},
            # Unknown duration must be kept: absent data is not bad data.
            {"title": "Vapour Trail", "artist": "Ride",
             "provider_track_id": "v4", "confidence": 0.8, "duration_in_track_range": None},
        ]
    }
    result = nodes.deduplicate_and_resolve_tracks(state)
    titles = {t["title"] for t in result["resolved_tracks"]}
    assert titles == {"Sometimes", "Alison", "Vapour Trail"}


def test_deduplicate_keeps_non_track_lengths_when_nothing_else_remains():
    """Never return an empty list just because everything was the wrong length."""
    state = {
        "candidate_tracks": [
            {"title": "90 minute shoegaze mix", "artist": "ch",
             "provider_track_id": "v1", "confidence": 0.5, "duration_in_track_range": False},
            {"title": "Sometimes", "artist": "My Bloody Valentine",
             "provider_track_id": "v2", "confidence": 0.9, "duration_in_track_range": True},
        ]
    }
    result = nodes.deduplicate_and_resolve_tracks(state)
    assert len(result["resolved_tracks"]) == 2


def test_sequence_tracks_returns_one_recommendation_by_default():
    """Product decision (2026-07-26): one recommendation per request."""
    state = {"ranked_tracks": [{"title": f"T{i}"} for i in range(25)]}
    result = nodes.sequence_tracks(state)
    assert len(result["sequenced_tracks"]) == 1
    assert result["sequenced_tracks"][0]["position"] == 1


def test_sequence_tracks_limit_is_configurable(monkeypatch):
    monkeypatch.setenv("RECOMMENDATION_TRACK_LIMIT", "5")
    state = {"ranked_tracks": [{"title": f"T{i}"} for i in range(25)]}
    result = nodes.sequence_tracks(state)
    assert len(result["sequenced_tracks"]) == 5


# Regression test for the §4.8 defect found live (2026-07-26): a query for
# "upbeat 90s grunge" returned 3 explained tracks followed by reaction videos,
# a visualizer and a #shorts clip, each carrying `reasoning: ""` and each
# presented to the user as a curated pick. §4.8 requires a reason per track and
# ADR-006 forbids inventing one, so an unexplained track must be dropped.
def test_generate_grounded_explanation_drops_unexplained_tracks(monkeypatch):
    async def _partial(**_kwargs):
        return llm_adapter.AdapterResult(
            success=True,
            model="claude-haiku-4-5",
            playlist_title="Grunge",
            playlist_description="d",
            # Index 1 -- the reaction video -- is deliberately unexplained.
            track_reasons={0: "The defining grunge anthem.", 2: "Carries the same rawness."},
        )

    monkeypatch.setattr(llm_adapter, "generate_curator_explanation", _partial)
    state = {
        "sequenced_tracks": [
            {"title": "Smells Like Teen Spirit", "artist": "Nirvana", "position": 1},
            {"title": "Hair Metal Musicians Reacting to Grunge", "artist": "Loudwire", "position": 2},
            {"title": "Man in the Box", "artist": "Alice In Chains", "position": 3},
        ]
    }
    result = run(nodes.generate_grounded_explanation(state))

    titles = [t["title"] for t in result["sequenced_tracks"]]
    assert titles == ["Smells Like Teen Spirit", "Man in the Box"]
    assert all(t["reasoning"] for t in result["sequenced_tracks"])
    # Positions are renumbered, not left with a hole where the drop happened.
    assert [t["position"] for t in result["sequenced_tracks"]] == [1, 2]


def test_generate_grounded_explanation_invalid_when_nothing_explained(monkeypatch):
    async def _explains_nothing(**_kwargs):
        return llm_adapter.AdapterResult(
            success=True,
            model="claude-haiku-4-5",
            playlist_title="t",
            playlist_description="d",
            track_reasons={},
        )

    monkeypatch.setattr(llm_adapter, "generate_curator_explanation", _explains_nothing)
    state = {"sequenced_tracks": [{"title": "A", "artist": "B", "position": 1}]}
    result = run(nodes.generate_grounded_explanation(state))
    # An empty playlist is not a valid success -- it is a failed run.
    assert result["output_valid"] is False
    assert "sequenced_tracks" not in result


# Regression test for the §4.8 leak found live via REC-LEG-002 (2026-07-25):
# a raw internal warning ("retrieval confidence was low; one bounded rewrite
# executed") reached the model and it repeated "confidence in the retrieval"
# in user-facing Hebrew prose. state["warnings"] must never reach the adapter.
_INTERNAL_JARGON = ("retrieval", "confidence", "rewrite", "rag-service", "provider-gateway")


def test_user_safe_caveats_excludes_internal_jargon():
    state = {
        "rewrite_count": 1,
        "warnings": [
            "retrieval confidence was low; one bounded rewrite executed (widened candidate pool)",
            "retrieve_genres: rag-service unreachable (ConnectError)",
        ],
    }
    caveats = nodes._user_safe_caveats(state)
    assert caveats  # a rewrite did happen, so a caveat should surface
    joined = " ".join(caveats).lower()
    for term in _INTERNAL_JARGON:
        assert term not in joined, f"internal jargon {term!r} leaked into a user-safe caveat: {caveats}"


def test_user_safe_caveats_empty_when_no_rewrite():
    assert nodes._user_safe_caveats({"rewrite_count": 0, "warnings": ["some internal note"]}) == []


def test_generate_grounded_explanation_never_passes_raw_warnings_to_adapter(monkeypatch):
    captured: dict[str, Any] = {}

    async def _capturing_fake(**kwargs):
        captured.update(kwargs)
        return llm_adapter.AdapterResult(
            success=True, model="claude-haiku-4-5", playlist_title="t",
            playlist_description="d", track_reasons={0: "r"},
        )

    monkeypatch.setattr(llm_adapter, "generate_curator_explanation", _capturing_fake)
    state = {
        "sequenced_tracks": [{"title": "Holocene", "artist": "Bon Iver", "position": 1}],
        "rewrite_count": 1,
        "warnings": ["retrieval confidence was low; one bounded rewrite executed (widened candidate pool)"],
    }
    run(nodes.generate_grounded_explanation(state))

    assert "warnings" not in captured  # the old, buggy kwarg name must not reappear
    assert "user_safe_caveats" in captured
    for term in _INTERNAL_JARGON:
        assert term not in " ".join(captured["user_safe_caveats"]).lower()


def test_validate_output_passes_for_well_formed_state():
    state = {
        "playlist_title": "Warm Indie Evenings",
        "curator_explanation": "A cozy set.",
        "sequenced_tracks": [{"title": "Holocene", "artist": "Bon Iver", "reasoning": "Fits the mood."}],
    }
    result = nodes.validate_output(state)
    assert result["output_valid"] is True


def test_validate_output_skips_when_already_invalid():
    result = nodes.validate_output({"output_valid": False, "sequenced_tracks": []})
    assert "output_valid" not in result
    assert result["node_metrics"]["validate_output"]["status"] == "skipped"


def test_validate_output_catches_contract_violation(monkeypatch):
    import jsonschema

    def _boom(*_a, **_k):
        raise jsonschema.ValidationError("tracks must be an array")

    monkeypatch.setattr(nodes.jsonschema, "validate", _boom)
    result = nodes.validate_output({"sequenced_tracks": []})
    assert result["output_valid"] is False
    assert result["node_metrics"]["validate_output"]["status"] == "error"


# ---------------------------------------------------------------------------
# End-to-end: the compiled graph, happy path and the forced-rewrite path.
# ---------------------------------------------------------------------------


def test_graph_end_to_end_happy_path(monkeypatch):
    monkeypatch.setattr(rag_client, "retrieve", _fake_rag_retrieve_ok)
    monkeypatch.setattr(provider_client, "search", _fake_provider_search_ok)
    monkeypatch.setattr(llm_adapter, "generate_curator_explanation", _fake_llm_success)

    final_state = run(recommendation_graph.ainvoke({"user_text": "warm indie folk for a rainy afternoon"}))

    assert final_state["rewrite_count"] == 0
    assert final_state["output_valid"] is True
    assert final_state["sequenced_tracks"]
    assert final_state["playlist_title"] == "Warm Indie Evenings"


def test_graph_end_to_end_forced_rewrite_runs_exactly_once(monkeypatch):
    monkeypatch.setattr(rag_client, "retrieve", _fake_rag_retrieve_low_confidence)
    monkeypatch.setattr(provider_client, "search", _fake_provider_search_ok)
    monkeypatch.setattr(llm_adapter, "generate_curator_explanation", _fake_llm_success)

    final_state = run(recommendation_graph.ainvoke({"user_text": "something nobody has ever heard of"}))

    assert final_state["rewrite_count"] == 1
    # The graph must still complete, not loop, even though confidence stayed low.
    assert "retrieve_genres" in final_state["node_metrics"]


# ---------------------------------------------------------------------------
# §6.5 — audio-conditioned retrieval (AUD-RAG-001..004)
# ---------------------------------------------------------------------------


# What audio-service actually returns from POST /audio/analyze, verbatim in
# shape. Written as the real payload rather than a tidied-up subset so the
# metadata keys (`source`, `model_version`, `field_confidence`, `genre_model`)
# are exercised -- they were previously treated as *features* and reached the
# retrieval query as terms like "librosa-dsp".
_ANALYZE_PAYLOAD = {
    "bpm": 128.0,
    "musical_key": "A minor",
    "camelot": "8A",
    "energy": 0.82,
    "genre": "disco",
    "source": "librosa-dsp",
    "confidence": 0.31,
    "model_version": "melody-dsp-1.0.0",
    "field_confidence": {"tempo": 0.91, "key": 0.31, "energy": 0.8, "genre": 0.77},
    "analyzed_seconds": 30.0,
    "genre_model": {"genre": "disco", "confidence": 0.77, "available": True},
}


def test_analysis_metadata_is_not_mistaken_for_a_feature():
    normalized = nodes._normalize_audio_features(_ANALYZE_PAYLOAD)
    for key in ("source", "model_version", "field_confidence", "analyzed_seconds",
                "genre_model", "confidence"):
        assert key not in normalized
    assert set(normalized) == {"bpm", "musical_key", "camelot", "energy", "genre"}


def test_per_field_confidence_beats_the_global_headline():
    """The headline confidence is the *weakest* field (0.31 here, the key).

    Applying it to every feature would demote a 0.91-confidence tempo to a soft
    hint because the key happened to be ambiguous.
    """
    normalized = nodes._normalize_audio_features(_ANALYZE_PAYLOAD)
    assert normalized["bpm"]["confidence"] == 0.91
    assert normalized["bpm"]["treat_as"] == "constraint"
    assert normalized["musical_key"]["confidence"] == 0.31
    assert normalized["musical_key"]["treat_as"] == "soft_hint"


def test_absent_measurements_are_not_zero_confidence_features():
    """No genre model means no genre -- not a genre we are unsure of."""
    normalized = nodes._normalize_audio_features({**_ANALYZE_PAYLOAD, "genre": None})
    assert "genre" not in normalized


def test_audio_features_become_retrieval_words():
    """AUD-RAG-001: BPM is invisible to a text/embedding search; words are not."""
    normalized = nodes._normalize_audio_features(_ANALYZE_PAYLOAD)
    described = nodes.describe_audio_features(normalized)
    assert "disco" in described["text"]
    assert "danceable" in described["text"]  # 128 BPM band
    assert "energetic" in described["text"]  # 0.82 energy band
    assert described["genre"] == "disco"


def test_uncertain_features_are_kept_out_of_the_query_text():
    """AUD-RAG-002. The key here is 0.31-confident, so it must not steer search."""
    normalized = nodes._normalize_audio_features(_ANALYZE_PAYLOAD)
    described = nodes.describe_audio_features(normalized)
    assert "minor key" not in described["text"]
    assert any("minor key" in hint for hint in described["soft_hints"])
    assert "musical_key" not in described["used"]


def test_audio_only_request_produces_a_real_query():
    """The §6.5 defect this fixes: nodes 5 and 6 skip on empty text, so an
    audio-only request retrieved nothing at all and the audio was inert."""
    state = {"normalized_text": "", "audio_features": _ANALYZE_PAYLOAD}
    query = nodes.build_retrieval_query(state)["retrieval_query"]
    assert query["text"]
    assert "disco" in query["text"]


def test_audio_changes_the_query_measurably():
    """AUD-RAG-004, stated as a comparison rather than an assertion of faith."""
    text_only = nodes.build_retrieval_query(
        {"normalized_text": "something for a party", "audio_features": {}}
    )["retrieval_query"]
    with_audio = nodes.build_retrieval_query(
        {"normalized_text": "something for a party", "audio_features": _ANALYZE_PAYLOAD}
    )["retrieval_query"]

    assert with_audio["text"] != text_only["text"]
    assert with_audio["text"].startswith("something for a party")  # the user still leads
    assert "disco" in with_audio["positive_constraints"].get("genres", [])
    assert "genres" not in text_only["positive_constraints"] or (
        "disco" not in text_only["positive_constraints"]["genres"]
    )


def test_audio_genre_does_not_overwrite_what_the_user_asked_for():
    state = {
        "normalized_text": "something jazzier",
        "normalized_constraints": {"positive": {"genres": ["jazz"]}, "negative": {}},
        "audio_features": _ANALYZE_PAYLOAD,
    }
    genres = nodes.build_retrieval_query(state)["retrieval_query"]["positive_constraints"]["genres"]
    assert genres == ["jazz", "disco"]


def test_no_audio_leaves_the_query_untouched():
    """The text-only path must be byte-identical to what it was before §6.5."""
    state = {"normalized_text": "warm indie folk", "audio_features": {}}
    query = nodes.build_retrieval_query(state)["retrieval_query"]
    assert query["text"] == "warm indie folk"
    assert query["audio_query"]["terms"] == []
