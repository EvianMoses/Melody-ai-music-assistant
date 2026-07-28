"""Free-text negation extraction and exclusion plumbing (§3.8 negative constraints).

The §3.8 golden set scored the `negative_constraint` category at **0.00 context
precision** before this existed: retrieval had no notion of "not", so "rock but
nothing metal" returned metal.

The tests below are weighted toward FALSE POSITIVES rather than coverage, and
deliberately so. A missed exclusion returns evidence the user did not want; an
invented one silently deletes evidence they did, which is the worse failure and
the harder one to notice.
"""

from __future__ import annotations

import pytest

from app.core.graph_nodes import extract_negations, negative_terms, normalize_input


# ---------------------------------------------------------------------------
# What must be caught
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("rock music but nothing metal", ["metal"]),
        ("electronic music with no vocals", ["vocals"]),
        ("jazz but not modern", ["modern"]),
        ("something upbeat without rap", ["rap"]),
        ("indie folk, avoid country", ["country"]),
        ("anything except heavy metal", ["heavy metal"]),
        ("chill music excluding ambient", ["ambient"]),
    ],
)
def test_explicit_negations_are_extracted(text, expected):
    assert extract_negations(text) == expected


def test_multiple_negations_in_one_request():
    terms = extract_negations("rock but nothing metal, and no rap either")
    assert "metal" in terms
    assert "rap" in terms


def test_hebrew_negation():
    """The product is bilingual, so negation handling has to be."""
    # "רוק בלי מטאל" -- rock without metal
    terms = extract_negations("רוק בלי מטאל")
    assert terms, "Hebrew negation marker was not recognised"
    assert any("מטאל" in t for t in terms)


# ---------------------------------------------------------------------------
# What must NOT be caught -- the load-bearing half
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "warm indie folk for a rainy afternoon",
        "90s grunge for a moody evening",
        "deep house",
        "something calm and quiet",
        "music for studying",
        "",
    ],
)
def test_ordinary_requests_produce_no_exclusions(text):
    """The overwhelming majority of requests contain no negation at all.

    If this ever starts returning terms, every normal query begins silently
    losing evidence -- which is exactly the failure mode that makes an
    over-eager extractor worse than none.
    """
    assert extract_negations(text) == []


def test_stopwords_after_a_marker_are_not_exclusions():
    """"I do not want something loud" must not yield the exclusion "want"."""
    terms = extract_negations("I do not want something too loud")
    assert "want" not in terms
    assert "too" not in terms


def test_negation_of_a_bare_stopword_is_dropped_entirely():
    assert extract_negations("not really sure") == []


# ---------------------------------------------------------------------------
# Plumbing: extraction -> normalized_constraints -> flat term list
# ---------------------------------------------------------------------------


def test_normalize_input_records_text_negations():
    """Before this, negatives came only from `explicit_constraints`, which the
    UI never populates -- so they were empty on every real request."""
    result = normalize_input({"user_text": "rock but nothing metal"})
    negative = result["normalized_constraints"]["negative"]
    assert "metal" in negative.get("exclude", [])


def test_normalize_input_merges_ui_and_text_negations():
    result = normalize_input(
        {
            "user_text": "rock but nothing metal",
            "explicit_constraints": {"exclude_genres": ["country"]},
        }
    )
    terms = negative_terms({"negative_constraints": result["normalized_constraints"]["negative"]})
    assert "metal" in terms  # from the sentence
    assert "country" in terms  # from the UI


def test_negative_terms_flattens_every_origin():
    """rag-service does not care which door a term came through."""
    terms = negative_terms(
        {
            "negative_constraints": {
                "exclude_genres": ["Metal"],
                "exclude_artists": ["Some Band"],
                "exclude": ["rap"],
            }
        }
    )
    assert terms == ["metal", "some band", "rap"]


def test_negative_terms_of_an_empty_query_is_empty():
    assert negative_terms({}) == []
    assert negative_terms({"negative_constraints": {}}) == []
