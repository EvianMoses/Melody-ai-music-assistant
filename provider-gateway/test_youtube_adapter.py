"""Unit tests for the YouTube search adapter (Phase 5 §5.1/§5.3).

Pure-function tests for the parsing/confidence/dedup heuristics run with no
network at all; search() tests mock the httpx client (manual fakes, matching
the project's existing test style rather than a mock library) so they run
offline too.
"""

from __future__ import annotations

import asyncio

import pytest

from app import youtube_adapter as ya


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# _parse_title_artist
# ---------------------------------------------------------------------------


def test_parse_title_artist_dash_convention():
    title, artist, conf, source = ya._parse_title_artist("Bon Iver - Holocene", "Bon Iver - Topic")
    assert (title, artist) == ("Holocene", "Bon Iver")
    assert conf == 1.0
    # The channel corroborates the split, so the source records both signals
    # rather than implying the title alone decided it.
    assert source == "snippet.title+channelTitle"


def test_parse_title_artist_dash_convention_without_channel_evidence():
    """Still applied, but at reduced confidence -- it is a convention, a guess."""
    title, artist, conf, source = ya._parse_title_artist("Bon Iver - Holocene", "SomeUploader")
    assert (title, artist) == ("Holocene", "Bon Iver")
    assert conf == 0.9
    assert source == "snippet.title"


# Regression tests for four live title-parsing defects (2026-07-26). All four
# reached the UI as the displayed song name.
def test_parse_title_artist_strips_quality_token_inside_official_phrase():
    """"(Official HD Video)" was not matched, so it stayed in the song name."""
    title, artist, _, _ = ya._parse_title_artist(
        "Alice In Chains - Man in the Box (Official HD Video)", "AliceInChainsVEVO"
    )
    assert (title, artist) == ("Man in the Box", "Alice In Chains")


def test_parse_title_artist_strips_bare_trailing_qualifier():
    """"Slowdive - Alison (audio) - HD" kept "(audio) - HD" in the title."""
    title, artist, _, _ = ya._parse_title_artist("Slowdive - Alison (audio) - HD", "Slowdive")
    assert (title, artist) == ("Alison", "Slowdive")


def test_trailing_qualifier_is_not_mistaken_for_the_song_title():
    """The worst of the four: "Some Song (Official Audio) - HD" parsed to
    title="HD", artist="Some Song" -- both fields wrong."""
    title, artist, _, _ = ya._parse_title_artist("Some Song (Official Audio) - HD", "ArtistChannel")
    assert title == "Some Song"
    assert artist == "ArtistChannel"


def test_channel_evidence_beats_word_order():
    """When one side names the channel, that side is the artist regardless of
    which side of the separator it sits on."""
    title, artist, conf, source = ya._parse_title_artist(
        "Holocene | Bon Iver", "Bon Iver"
    )
    assert (title, artist) == ("Holocene", "Bon Iver")
    assert source == "snippet.title+channelTitle"


def test_pipe_separator_prefers_the_channel_as_artist():
    """Live case: "שלמים | Idan Rafael Haviv" on channel "עידן רפאל חביב".

    The two sides are the same name in different scripts, so no string match
    connects them, and applying the dash convention returned the *artist* as
    the song name. "|" is not an artist/title separator, so the channel wins.
    """
    title, artist, conf, _ = ya._parse_title_artist(
        "שלמים | Idan Rafael Haviv", "עידן רפאל חביב"
    )
    assert title == "שלמים"
    assert artist == "עידן רפאל חביב"
    assert conf == 0.7


def test_pipe_without_surrounding_spaces_is_still_split():
    """"שלמים| Idan Rafael Haviv" missed the " | " separator entirely, so the
    whole raw title reached the UI as the song name."""
    title, artist, _, _ = ya._parse_title_artist("שלמים| Idan Rafael Haviv", "עידן רפאל חביב")
    assert title == "שלמים"
    assert artist == "עידן רפאל חביב"


def test_pipe_split_keeps_channel_match_precedence():
    title, artist, conf, source = ya._parse_title_artist("Holocene|Bon Iver", "Bon Iver")
    assert (title, artist) == ("Holocene", "Bon Iver")
    assert source == "snippet.title+channelTitle"


def test_parse_title_artist_strips_official_suffix_before_splitting():
    title, artist, conf, _ = ya._parse_title_artist(
        "Daft Punk - One More Time (Official Music Video)", "Daft Punk"
    )
    assert (title, artist) == ("One More Time", "Daft Punk")
    assert conf == 1.0


def test_parse_title_artist_by_convention():
    title, artist, conf, _ = ya._parse_title_artist("Some Song by Some Artist (Lyrics)", "Lyrics Channel")
    assert (title, artist) == ("Some Song", "Some Artist")
    assert conf == 1.0


def test_parse_title_artist_falls_back_to_channel_when_no_separator():
    title, artist, conf, source = ya._parse_title_artist("my favorite song ever", "RandomUser123")
    assert artist == "RandomUser123"
    assert title == "my favorite song ever"
    assert conf == 0.6
    assert source == "snippet.channelTitle"  # §PROV-005: the fallback is recorded, not hidden


def test_parse_title_artist_never_returns_empty_on_garbage_input():
    title, artist, _, _ = ya._parse_title_artist("(Official Video)", "SomeChannel")
    assert title  # never silently drops a result
    assert artist


# ---------------------------------------------------------------------------
# _confidence_for
# ---------------------------------------------------------------------------


# Live-observed titles from a real "90s grunge" run -- the pipeline surfaced
# video essays instead of songs. Duration filtering can't catch these (a video
# essay sits squarely inside track range), so they need a title heuristic.
@pytest.mark.parametrize(
    "title",
    [
        "How Grunge Ended Hair Metal",
        "Top 5 Grunge Songs of All Time.",
        "The Different Styles of Post-Grunge",
        "Grunge Vs Post Grunge Guitar Riffs #guitar",
        "Top 50 Post Grunge Songs. The Best Post Grunge Songs",
        "Hair Metal Musicians Reacting to Grunge",
        "Best of 2025 Deep House",
        "Nirvana Documentary",
        "Smells Like Teen Spirit Guitar Lesson",
    ],
)
def test_looks_like_non_track_detects_commentary(title):
    assert ya._looks_like_non_track(title) is True


@pytest.mark.parametrize(
    "title",
    [
        "Bon Iver - Holocene",
        "Nirvana - Smells Like Teen Spirit",
        "Pearl Jam - Even Flow (Extended Version)",
        "Daft Punk - One More Time (Official Music Video)",
        "Larry Heard - Can You Feel It",
        "CANDLEBOX - Far Behind",
    ],
)
def test_looks_like_non_track_leaves_real_tracks_alone(title):
    assert ya._looks_like_non_track(title) is False


def test_non_track_titles_rank_below_real_tracks():
    essay = ya._confidence_for("Loudwire", "How Grunge Ended Hair Metal", parse_confidence=0.6)
    real = ya._confidence_for("SomeChannel", "Nirvana - Smells Like Teen Spirit", parse_confidence=1.0)
    assert essay < real
    assert essay > 0  # deprioritized, never hard-filtered


def test_confidence_topic_channel_is_highest():
    topic = ya._confidence_for("Bon Iver - Topic", "Bon Iver - Holocene", parse_confidence=1.0)
    official = ya._confidence_for("Daft Punk", "Daft Punk - One More Time (Official Video)", parse_confidence=1.0)
    plain = ya._confidence_for("RandomUser123", "my favorite song ever", parse_confidence=0.6)
    assert topic > official > plain
    assert 0.0 < plain  # never zero -- deprioritized, not filtered


# ---------------------------------------------------------------------------
# _dedupe
# ---------------------------------------------------------------------------


def test_dedupe_keeps_highest_confidence_among_near_duplicates():
    tracks = [
        {"provider": "youtube", "provider_track_id": "a", "title": "Holocene", "artist": "Bon Iver", "url": "x", "confidence": 0.5},
        {"provider": "youtube", "provider_track_id": "b", "title": "holocene", "artist": "bon iver", "url": "y", "confidence": 0.95},
    ]
    result = ya._dedupe(tracks)
    assert len(result) == 1
    assert result[0]["provider_track_id"] == "b"


# ---------------------------------------------------------------------------
# search() -- mocked httpx client
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """URL-aware fake: search.list and videos.list get different payloads."""

    def __init__(
        self,
        response=None,
        exc: Exception | None = None,
        captured: dict | None = None,
        videos_response=None,
        videos_exc: Exception | None = None,
    ):
        self._response = response
        self._exc = exc
        self._captured = captured
        self._videos_response = videos_response
        self._videos_exc = videos_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc_info):
        return False

    async def get(self, url, params=None, headers=None):
        is_videos = url == ya.VIDEOS_URL
        if self._captured is not None:
            self._captured.setdefault("calls", []).append(
                {"url": url, "params": params, "headers": headers}
            )
            if not is_videos:
                self._captured["url"] = url
                self._captured["params"] = params
                self._captured["headers"] = headers
        if is_videos:
            if self._videos_exc is not None:
                raise self._videos_exc
            return self._videos_response if self._videos_response is not None else _FakeResponse(200, {"items": []})
        if self._exc is not None:
            raise self._exc
        return self._response


def _client_factory(response=None, exc=None, captured=None, videos_response=None, videos_exc=None):
    def factory(*_args, **_kwargs):
        return _FakeAsyncClient(
            response=response,
            exc=exc,
            captured=captured,
            videos_response=videos_response,
            videos_exc=videos_exc,
        )

    return factory


def _video_item(video_id: str, duration: str, *, embeddable=True, blocked=None, allowed=None):
    content_details: dict = {"duration": duration}
    if blocked is not None or allowed is not None:
        restriction: dict = {}
        if blocked is not None:
            restriction["blocked"] = blocked
        if allowed is not None:
            restriction["allowed"] = allowed
        content_details["regionRestriction"] = restriction
    return {"id": video_id, "contentDetails": content_details, "status": {"embeddable": embeddable}}


SEARCH_PAYLOAD = {
    "items": [
        {"id": {"videoId": "abc123"}, "snippet": {"title": "Bon Iver - Holocene", "channelTitle": "Bon Iver - Topic"}},
        {"id": {"videoId": "def456"}, "snippet": {"title": "Bon Iver - Holocene (Live)", "channelTitle": "SomeFan"}},
    ]
}
# Both in-range and clearly different runtimes -> two distinct recordings.
VIDEOS_PAYLOAD = {"items": [_video_item("abc123", "PT5M36S"), _video_item("def456", "PT6M12S")]}


def test_search_happy_path(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(
        ya,
        "make_async_client",
        _client_factory(_FakeResponse(200, SEARCH_PAYLOAD), videos_response=_FakeResponse(200, VIDEOS_PAYLOAD)),
    )

    results = run(ya.search("bon iver holocene", limit=5))
    assert len(results) == 2
    assert results[0]["provider"] == "youtube"
    assert results[0]["confidence"] >= results[1]["confidence"]
    assert results[0]["duration_seconds"] == 336
    assert results[0]["embeddable"] is True


# Regression test: the API returns HTML-escaped snippet text (live-observed:
# `&quot;Holocene&quot;` instead of `"Holocene"`, `Warm &amp; Cozy` instead of
# `Warm & Cozy`) -- must be unescaped before parsing/display.
HTML_ESCAPED_PAYLOAD = {
    "items": [
        {
            "id": {"videoId": "xyz789"},
            "snippet": {"title": "&quot;Holocene&quot;", "channelTitle": "Bon Iver &amp; Friends - Topic"},
        }
    ]
}


def test_search_unescapes_html_entities(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(
        ya,
        "make_async_client",
        _client_factory(
            _FakeResponse(200, HTML_ESCAPED_PAYLOAD),
            videos_response=_FakeResponse(200, {"items": [_video_item("xyz789", "PT5M36S")]}),
        ),
    )

    results = run(ya.search("holocene", limit=5))
    assert len(results) == 1
    combined = results[0]["title"] + results[0]["artist"]
    assert "&quot;" not in combined
    assert "&amp;" not in combined
    assert '"' not in results[0]["title"]  # the stray quotes themselves get stripped, not just unescaped
    assert "&" in results[0]["artist"]  # unescaped to a literal "&"


# ---------------------------------------------------------------------------
# videos.list enrichment (§5.3): duration parsing, filtering, availability
# ---------------------------------------------------------------------------


def test_parse_iso8601_duration():
    assert ya._parse_iso8601_duration("PT4M13S") == 253
    assert ya._parse_iso8601_duration("PT1H2M3S") == 3723
    assert ya._parse_iso8601_duration("PT45S") == 45
    assert ya._parse_iso8601_duration("PT2H") == 7200


def test_parse_iso8601_duration_returns_none_on_garbage():
    # None, not a guess -- a wrong duration silently mis-filters a real track.
    assert ya._parse_iso8601_duration("") is None
    assert ya._parse_iso8601_duration("4:13") is None
    assert ya._parse_iso8601_duration("banana") is None


def test_region_blocked_via_blocked_list():
    assert ya._is_region_blocked({"regionRestriction": {"blocked": ["IL", "DE"]}}, "IL") is True
    assert ya._is_region_blocked({"regionRestriction": {"blocked": ["DE"]}}, "IL") is False


def test_region_blocked_via_allowed_list():
    assert ya._is_region_blocked({"regionRestriction": {"allowed": ["US"]}}, "IL") is True
    assert ya._is_region_blocked({"regionRestriction": {"allowed": ["US", "IL"]}}, "IL") is False


def test_region_unrestricted_is_never_blocked():
    assert ya._is_region_blocked({}, "IL") is False


def test_search_filters_out_long_dj_mixes(monkeypatch):
    """The headline goal: an hour-long mix must not outrank real tracks."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    search_payload = {
        "items": [
            {"id": {"videoId": "mix1"}, "snippet": {"title": "Deep House Mix 2026 | 1 Hour", "channelTitle": "DJ Someone"}},
            {"id": {"videoId": "trk1"}, "snippet": {"title": "Larry Heard - Can You Feel It", "channelTitle": "Larry Heard - Topic"}},
        ]
    }
    videos_payload = {
        "items": [
            _video_item("mix1", "PT1H3M20S"),  # 3800s -- way over the ceiling
            _video_item("trk1", "PT7M2S"),  # 422s -- a real track
        ]
    }
    monkeypatch.setattr(
        ya,
        "make_async_client",
        _client_factory(_FakeResponse(200, search_payload), videos_response=_FakeResponse(200, videos_payload)),
    )

    results = run(ya.search("deep house", limit=5))
    ids = [r["provider_track_id"] for r in results]
    assert ids[0] == "trk1", "the real track must rank first"
    mix = next(r for r in results if r["provider_track_id"] == "mix1")
    assert mix["duration_in_track_range"] is False
    assert mix["confidence"] < results[0]["confidence"]


def test_search_keeps_mixes_rather_than_returning_nothing(monkeypatch):
    """Regression guard: filtering must never recreate the zero-results bug.

    If *everything* is out of range, return the (deprioritized) mixes anyway
    instead of an empty list.
    """
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    search_payload = {
        "items": [
            {"id": {"videoId": "m1"}, "snippet": {"title": "Chill Mix Vol 1", "channelTitle": "Chan"}},
            {"id": {"videoId": "m2"}, "snippet": {"title": "Chill Mix Vol 2", "channelTitle": "Chan"}},
        ]
    }
    videos_payload = {"items": [_video_item("m1", "PT2H"), _video_item("m2", "PT90M")]}
    monkeypatch.setattr(
        ya,
        "make_async_client",
        _client_factory(_FakeResponse(200, search_payload), videos_response=_FakeResponse(200, videos_payload)),
    )

    results = run(ya.search("chill", limit=5))
    assert len(results) == 2, "must not return an empty list just because all results are mixes"
    assert all(r["duration_in_track_range"] is False for r in results)


def test_search_drops_region_blocked_videos(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_REGION", "IL")
    search_payload = {
        "items": [
            {"id": {"videoId": "ok1"}, "snippet": {"title": "A - Fine Song", "channelTitle": "A - Topic"}},
            {"id": {"videoId": "blk"}, "snippet": {"title": "A - Blocked Song", "channelTitle": "A - Topic"}},
        ]
    }
    videos_payload = {
        "items": [_video_item("ok1", "PT3M"), _video_item("blk", "PT3M", blocked=["IL"])]
    }
    monkeypatch.setattr(
        ya,
        "make_async_client",
        _client_factory(_FakeResponse(200, search_payload), videos_response=_FakeResponse(200, videos_payload)),
    )

    results = run(ya.search("a", limit=5))
    assert [r["provider_track_id"] for r in results] == ["ok1"]


def test_search_drops_videos_missing_from_videos_list(monkeypatch):
    """Absent from videos.list => deleted/private => unavailable item."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    search_payload = {
        "items": [
            {"id": {"videoId": "alive"}, "snippet": {"title": "A - Alive", "channelTitle": "A - Topic"}},
            {"id": {"videoId": "gone"}, "snippet": {"title": "A - Gone", "channelTitle": "A - Topic"}},
        ]
    }
    videos_payload = {"items": [_video_item("alive", "PT3M")]}  # "gone" simply isn't returned
    monkeypatch.setattr(
        ya,
        "make_async_client",
        _client_factory(_FakeResponse(200, search_payload), videos_response=_FakeResponse(200, videos_payload)),
    )

    results = run(ya.search("a", limit=5))
    assert [r["provider_track_id"] for r in results] == ["alive"]


def test_search_keeps_non_embeddable_but_flags_it(monkeypatch):
    """§PLAY-005 wants a plain provider link, so don't drop -- flag it."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    search_payload = {
        "items": [{"id": {"videoId": "ne1"}, "snippet": {"title": "A - Song", "channelTitle": "A - Topic"}}]
    }
    videos_payload = {"items": [_video_item("ne1", "PT3M", embeddable=False)]}
    monkeypatch.setattr(
        ya,
        "make_async_client",
        _client_factory(_FakeResponse(200, search_payload), videos_response=_FakeResponse(200, videos_payload)),
    )

    results = run(ya.search("a", limit=5))
    assert len(results) == 1
    assert results[0]["embeddable"] is False


def test_search_degrades_gracefully_when_enrichment_fails(monkeypatch):
    """Enrichment is an improvement, not a hard dependency."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(
        ya,
        "make_async_client",
        _client_factory(
            _FakeResponse(200, SEARCH_PAYLOAD),
            videos_response=_FakeResponse(500, {}),
        ),
    )

    results = run(ya.search("bon iver", limit=5))
    assert len(results) == 2, "search results must survive a failed videos.list"
    assert results[0]["duration_seconds"] is None


def test_dedupe_merges_same_recording_by_duration_and_similar_title():
    """§YT-004: same artist + near-identical runtime + similar title."""
    tracks = [
        {"provider_track_id": "a", "title": "Holocene", "artist": "Bon Iver", "confidence": 0.95, "duration_seconds": 336},
        {"provider_track_id": "b", "title": "Holocene ", "artist": "bon iver", "confidence": 0.5, "duration_seconds": 337},
    ]
    result = ya._dedupe(tracks)
    assert len(result) == 1
    assert result[0]["provider_track_id"] == "a"


def test_dedupe_keeps_distinct_recordings_with_different_durations():
    """A live version has a different runtime -- must NOT be merged away."""
    tracks = [
        {"provider_track_id": "studio", "title": "Holocene", "artist": "Bon Iver", "confidence": 0.95, "duration_seconds": 336},
        {"provider_track_id": "live", "title": "Holocene", "artist": "Bon Iver", "confidence": 0.5, "duration_seconds": 372},
    ]
    # Distinct exact keys are impossible here (same artist+title), so this
    # specifically exercises the duration gate in the fuzzy pass.
    tracks[1]["title"] = "Holocene (Live at Rock the Garden)"
    result = ya._dedupe(tracks)
    assert len(result) == 2


def test_dedupe_never_fuzzy_merges_without_known_durations():
    """Unenriched results fall back to exact-match dedupe only."""
    tracks = [
        {"provider_track_id": "a", "title": "Holocene", "artist": "Bon Iver", "confidence": 0.9, "duration_seconds": None},
        {"provider_track_id": "b", "title": "Holocene!", "artist": "Bon Iver", "confidence": 0.5, "duration_seconds": None},
    ]
    result = ya._dedupe(tracks)
    assert len(result) == 2


def test_search_records_quota_for_both_methods(monkeypatch, caplog):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(
        ya,
        "make_async_client",
        _client_factory(_FakeResponse(200, SEARCH_PAYLOAD), videos_response=_FakeResponse(200, VIDEOS_PAYLOAD)),
    )
    with caplog.at_level("INFO", logger="provider-gateway.youtube"):
        run(ya.search("bon iver", limit=5))

    logged = " ".join(r.getMessage() for r in caplog.records)
    assert '"method": "search.list", "units": 100' in logged
    assert '"method": "videos.list", "units": 1' in logged


def test_field_sources_record_per_field_provenance(monkeypatch):
    """§PROV-005: a consumer can tell a parsed artist from a channel fallback."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    search_payload = {
        "items": [
            {"id": {"videoId": "p1"}, "snippet": {"title": "Artist - Title", "channelTitle": "Chan"}},
            {"id": {"videoId": "f1"}, "snippet": {"title": "just a title", "channelTitle": "Chan"}},
        ]
    }
    videos_payload = {"items": [_video_item("p1", "PT3M"), _video_item("f1", "PT3M")]}
    monkeypatch.setattr(
        ya,
        "make_async_client",
        _client_factory(_FakeResponse(200, search_payload), videos_response=_FakeResponse(200, videos_payload)),
    )

    results = {r["provider_track_id"]: r for r in run(ya.search("x", limit=5))}
    assert results["p1"]["field_sources"]["artist"] == "search.list:snippet.title"
    assert results["f1"]["field_sources"]["artist"] == "search.list:snippet.channelTitle"
    assert "videos.list" in results["p1"]["field_sources"]["duration_seconds"]


# Regression test for a real leak: httpx's own request logger logs the full
# URL, and a live run showed the key in plaintext in container logs when it
# was a query param. The key must go in a header, never in params/URL.
def test_search_never_puts_api_key_in_query_params(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "secret-key-value")
    captured: dict = {}
    monkeypatch.setattr(
        ya, "make_async_client", _client_factory(_FakeResponse(200, {"items": []}), captured=captured)
    )

    run(ya.search("anything", limit=5))

    assert "secret-key-value" not in str(captured.get("params"))
    assert "secret-key-value" not in captured.get("url", "")
    assert captured["headers"]["X-Goog-Api-Key"] == "secret-key-value"


def test_search_missing_api_key_raises_provider_unavailable(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(ya.ProviderError) as exc_info:
        run(ya.search("anything", limit=5))
    assert exc_info.value.code == "PROVIDER_UNAVAILABLE"


def test_search_quota_exceeded(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    payload = {"error": {"errors": [{"reason": "quotaExceeded"}]}}
    monkeypatch.setattr(ya, "make_async_client", _client_factory(_FakeResponse(403, payload)))

    with pytest.raises(ya.ProviderError) as exc_info:
        run(ya.search("anything", limit=5))
    assert exc_info.value.code == "QUOTA_EXCEEDED"


def test_search_rate_limited(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(ya, "make_async_client", _client_factory(_FakeResponse(429, {})))

    with pytest.raises(ya.ProviderError) as exc_info:
        run(ya.search("anything", limit=5))
    assert exc_info.value.code == "RATE_LIMITED"


def test_search_outage_on_5xx(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(ya, "make_async_client", _client_factory(_FakeResponse(500, {})))

    with pytest.raises(ya.ProviderError) as exc_info:
        run(ya.search("anything", limit=5))
    assert exc_info.value.code == "PROVIDER_UNAVAILABLE"


def test_search_outage_on_connection_error(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(ya, "make_async_client", _client_factory(exc=ConnectionError("refused")))

    with pytest.raises(ya.ProviderError) as exc_info:
        run(ya.search("anything", limit=5))
    assert exc_info.value.code == "PROVIDER_UNAVAILABLE"
