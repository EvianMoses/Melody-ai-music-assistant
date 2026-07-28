"""Audio service tests (§6.1 upload pipeline, §6.2 analysis).

Split by what they need:

* everything here runs on a plain Python install -- validation, sniffing,
  storage and job lifecycle have no DSP dependency, and that is deliberate
  (see `app/features.py::_load_dsp`);
* the tests that decode real audio are marked and skip automatically when
  librosa/FFmpeg are absent, so `pytest audio-service/` stays green on the host
  and covers the real path inside the container.
"""

from __future__ import annotations

import io
import os
import time

import pytest
from fastapi.testclient import TestClient

from app import config, features, jobs, sniffing, storage, transcode


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Point storage at a temp dir so tests never touch the real volume."""
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path / "clips")
    storage.ensure_storage_dir()
    yield


@pytest.fixture(autouse=True)
def offline_recognition(monkeypatch):
    """No test may call ACRCloud.

    This is not hypothetical tidiness: once real credentials landed in the
    container's environment, `/audio/identify` tests started making live,
    billable requests to `identify-ap-southeast-1` — visible in the log as real
    HTTP 200s, and one test failed because the provider answered something the
    fixture did not expect. Suite runs must not cost money, must not depend on a
    third party being up, and must not vary with whether a `.env` happens to be
    populated. The provider is exercised deliberately in `_fake_acr_result` with
    a stubbed transport, and for real only by `ml/recognition_poc.py`.
    """
    for name in (
        "ACRCLOUD_HOST", "ACRCLOUD_ACCESS_KEY", "ACRCLOUD_ACCESS_SECRET",
        "acrcloud_host", "acrcloud_api_key", "acrcloud_api_secret",
        "acrcloud_access_key", "acrcloud_access_secret",
    ):
        monkeypatch.delenv(name, raising=False)
    yield


@pytest.fixture()
def client():
    from main import app

    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Real audio fixtures
# ---------------------------------------------------------------------------


def _wav_bytes(seconds: float = 2.0, sample_rate: int = 22_050, freq: float = 440.0) -> bytes:
    """A valid PCM WAV, built with the stdlib so the test needs no numpy.

    A real header matters: the point of most of these tests is that detection
    reads the container, so a fake `b"RIFF...."` prefix would prove nothing
    about the FFmpeg path.
    """
    import math
    import struct
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for index in range(int(seconds * sample_rate)):
            value = int(0.4 * 32767 * math.sin(2 * math.pi * freq * index / sample_rate))
            frames += struct.pack("<h", value)
        handle.writeframes(bytes(frames))
    return buffer.getvalue()


def _upload(client, data: bytes, name="clip.wav", content_type="audio/wav"):
    return client.post(
        "/audio/uploads", files={"file": (name, io.BytesIO(data), content_type)}
    )


needs_dsp = pytest.mark.skipif(
    not features.available() or not transcode.ffmpeg_available(),
    reason="librosa/FFmpeg not installed (runs in the audio-service container)",
)


# ---------------------------------------------------------------------------
# Health and configuration
# ---------------------------------------------------------------------------


def test_health_live(client):
    assert client.get("/health/live").json() == {"status": "ok"}


def test_limits_are_configuration_not_constants(client, monkeypatch):
    """AUD-UP-002: the limits must be settable, and the UI reads them from here."""
    body = client.get("/audio/limits").json()
    assert body["max_upload_bytes"] == config.MAX_UPLOAD_BYTES
    assert body["max_duration_seconds"] == config.MAX_DURATION_SECONDS
    assert body["retention_minutes"] == config.RETENTION_MINUTES
    assert "webm" in body["allowed_formats"]


def test_malformed_limit_falls_back_to_default_not_unlimited(monkeypatch):
    """A broken limit must never become an absent limit."""
    monkeypatch.setenv("AUDIO_MAX_UPLOAD_BYTES", "not-a-number")
    assert config._int_env("AUDIO_MAX_UPLOAD_BYTES", 999, minimum=1) == 999
    monkeypatch.setenv("AUDIO_MAX_UPLOAD_BYTES", "0")
    assert config._int_env("AUDIO_MAX_UPLOAD_BYTES", 999, minimum=1) == 999


# ---------------------------------------------------------------------------
# AUD-UP-003 — container detection from bytes, not from the caller's claims
# ---------------------------------------------------------------------------


def test_sniff_recognizes_real_containers():
    assert sniffing.sniff(_wav_bytes(0.05)[: sniffing.SNIFF_BYTES]) == "wav"
    assert sniffing.sniff(b"fLaC\x00\x00\x00\x22") == "flac"
    assert sniffing.sniff(b"OggS\x00\x02" + b"\x00" * 20) == "ogg"
    assert sniffing.sniff(b"\x1a\x45\xdf\xa3" + b"\x00" * 20) == "webm"
    assert sniffing.sniff(b"ID3\x04\x00" + b"\x00" * 20) == "mp3"
    assert sniffing.sniff(b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 12) == "m4a"


def test_sniff_rejects_non_audio():
    assert sniffing.sniff(b"hello world") is None
    assert sniffing.sniff(b"MZ\x90\x00") is None  # a Windows executable
    assert sniffing.sniff(b"") is None


def test_upload_rejects_executable_named_wav(client):
    """The Phase 2 defect this replaces: `.wav` in the name was sufficient.

    An MZ executable declared as `audio/wav` and named `song.wav` satisfied both
    of the old checks. It must now be refused on its contents.
    """
    response = _upload(client, b"MZ\x90\x00" + b"\x00" * 200, name="song.wav")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_accepts_real_wav_with_a_lying_filename(client):
    """The mirror case: contents decide, so a wrong extension is not fatal."""
    response = _upload(client, _wav_bytes(0.5), name="recording.txt", content_type="")
    assert response.status_code == 200
    assert response.json()["container"] == "wav"


def test_upload_rejects_recognized_but_disallowed_format(client, monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_FORMATS", ("mp3",))
    response = _upload(client, _wav_bytes(0.5))
    assert response.status_code == 415
    assert "wav" in response.json()["error"]["message"]


# ---------------------------------------------------------------------------
# AUD-UP-002 — size limits
# ---------------------------------------------------------------------------


def test_upload_rejects_oversized_clip(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 2048)
    response = _upload(client, _wav_bytes(1.0))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_upload_rejects_empty_file(client):
    """422, not 415: nothing was sent, so there is no media type to reject."""
    response = _upload(client, b"")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_oversized_upload_is_not_stored(client, monkeypatch):
    """Rejection must leave nothing behind."""
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 2048)
    _upload(client, _wav_bytes(1.0))
    assert list(config.STORAGE_DIR.iterdir()) == []


# ---------------------------------------------------------------------------
# AUD-UP-004 — server-generated object IDs
# ---------------------------------------------------------------------------


def test_object_ids_are_server_generated_and_unguessable():
    first, second = storage.new_object_id(), storage.new_object_id()
    assert first != second
    assert len(first) == 32 and int(first, 16) >= 0


def test_path_for_refuses_anything_we_did_not_generate():
    """Traversal is rejected by grammar, not sanitized -- see storage.path_for."""
    for candidate in ("../../etc/passwd", "..", "a" * 33, "", "ABCDEF", "abc/def",
                      "a" * 31 + "\x00"):
        with pytest.raises(storage.StorageError):
            storage.path_for(candidate)


def test_upload_response_never_leaks_a_path_or_filename(client):
    body = _upload(client, _wav_bytes(0.5), name="my-private-demo.wav").json()
    serialized = str(body)
    assert "my-private-demo" not in serialized
    assert str(config.STORAGE_DIR) not in serialized
    assert set(body) == {
        "audio_job_id", "container", "size_bytes", "duration_seconds",
        "expires_in_seconds", "truncated",
    }


# ---------------------------------------------------------------------------
# AUD-UP-006 — cleanup
# ---------------------------------------------------------------------------


def test_expired_jobs_are_swept(client):
    job_id = _upload(client, _wav_bytes(0.5)).json()["audio_job_id"]
    assert storage.path_for(job_id).is_file()

    # Well past the retention window.
    removed = jobs.sweep_expired(now=time.time() + config.RETENTION_MINUTES * 60 + 1)
    assert removed >= 1
    assert not storage.path_for(job_id).is_file()


def test_sweep_leaves_fresh_jobs_alone(client):
    job_id = _upload(client, _wav_bytes(0.5)).json()["audio_job_id"]
    assert jobs.sweep_expired() == 0
    assert storage.path_for(job_id).is_file()


def test_orphaned_clip_without_metadata_still_expires():
    """A crash between the two writes must not pin bytes in storage forever."""
    object_id = storage.new_object_id()
    storage.write_object(object_id, _wav_bytes(0.2), "wav")
    assert jobs.sweep_expired(now=time.time() + config.RETENTION_MINUTES * 60 + 1) == 1
    assert not storage.path_for(object_id).is_file()


def test_explicit_disposal_removes_clip_and_metadata(client):
    job_id = _upload(client, _wav_bytes(0.5)).json()["audio_job_id"]
    assert client.delete(f"/audio/jobs/{job_id}").json()["deleted"] is True
    assert not storage.path_for(job_id).is_file()
    assert jobs.load(job_id) is None
    # Idempotent: disposing twice is not an error.
    assert client.delete(f"/audio/jobs/{job_id}").status_code == 200


def test_disposal_of_a_bogus_id_is_harmless(client):
    assert client.delete("/audio/jobs/..%2F..%2Fetc%2Fpasswd").status_code in (200, 404)


# ---------------------------------------------------------------------------
# Ownership — an unguessable ID is the first lock, not the only one
# ---------------------------------------------------------------------------


def test_job_owned_by_uploader_only(client):
    response = client.post(
        "/audio/uploads",
        files={"file": ("c.wav", io.BytesIO(_wav_bytes(0.5)), "audio/wav")},
        data={"user_id": "user-a"},
    )
    job_id = response.json()["audio_job_id"]
    job = jobs.load(job_id)
    assert job.owned_by("user-a", None) is True
    assert job.owned_by("user-b", None) is False
    assert job.owned_by(None, "guest-x") is False


def test_anonymous_job_stays_usable(client):
    job_id = _upload(client, _wav_bytes(0.5)).json()["audio_job_id"]
    assert jobs.load(job_id).owned_by(None, None) is True


def test_analyze_hides_existence_from_a_non_owner(client):
    response = client.post(
        "/audio/uploads",
        files={"file": ("c.wav", io.BytesIO(_wav_bytes(0.5)), "audio/wav")},
        data={"user_id": "user-a"},
    )
    job_id = response.json()["audio_job_id"]
    denied = client.post("/audio/analyze", data={"audio_job_id": job_id, "user_id": "user-b"})
    missing = client.post("/audio/analyze", data={"audio_job_id": storage.new_object_id()})
    # Identical responses: whether a job exists is not a non-owner's to learn.
    assert denied.status_code == missing.status_code == 404
    assert denied.json()["error"] == missing.json()["error"]


# ---------------------------------------------------------------------------
# Request shapes
# ---------------------------------------------------------------------------


def test_analyze_requires_some_input(client):
    assert client.post("/audio/analyze").status_code == 422


def test_analyze_accepts_json_from_n8n(client):
    """WF-003 has only a job ID and posts JSON; Form-only parsing 422'd it."""
    response = client.post("/audio/analyze", json={"audio_job_id": storage.new_object_id()})
    # Unknown-but-well-formed ID: reaches the lookup rather than failing parsing.
    assert response.status_code == 404


def test_expired_job_reports_not_found(client):
    job_id = _upload(client, _wav_bytes(0.5)).json()["audio_job_id"]
    job = jobs.load(job_id)
    job.expires_at = time.time() - 1
    jobs.save(job)
    assert client.post("/audio/analyze", data={"audio_job_id": job_id}).status_code == 404


# ---------------------------------------------------------------------------
# §6.4 — identification is honest about not existing yet
# ---------------------------------------------------------------------------


def test_identify_does_not_fabricate_a_match(client):
    """The old fixture claimed "Holocene" by Bon Iver at 0.88 for any input."""
    job_id = _upload(client, _wav_bytes(0.5)).json()["audio_job_id"]
    body = client.post("/audio/identify", data={"audio_job_id": job_id}).json()
    assert body["matched"] is False
    assert body["placeholder"] is True
    assert body["track"] == {}
    assert body["confidence"] == 0.0


# ---------------------------------------------------------------------------
# §6.2 — real measurement (container only)
# ---------------------------------------------------------------------------


def test_camelot_wheel_is_internally_consistent():
    """Relative major/minor share a number; a fifth up moves it by one.

    Pure table check, so it runs everywhere. §7.4's sequencer will mix on these
    numbers, and an off-by-one here would produce confidently wrong transitions.
    """
    assert features._CAMELOT_MAJOR["C"] == "8B" and features._CAMELOT_MINOR["A"] == "8A"
    assert features._CAMELOT_MAJOR["G"] == "9B" and features._CAMELOT_MINOR["E"] == "9A"
    assert len(set(features._CAMELOT_MAJOR.values())) == 12
    assert len(set(features._CAMELOT_MINOR.values())) == 12


@needs_dsp
def test_analyze_measures_a_real_tone(client):
    """A 440 Hz sine is A: the key detector must find A, not a fixed default."""
    job_id = _upload(client, _wav_bytes(4.0, freq=440.0)).json()["audio_job_id"]
    body = client.post("/audio/analyze", data={"audio_job_id": job_id}).json()
    assert body["placeholder"] is False
    assert body["features"]["source"] == features.SOURCE
    assert body["features"]["musical_key"].startswith("A")
    assert body["features"]["analyzed_seconds"] == pytest.approx(4.0, abs=0.2)


@needs_dsp
def test_analysis_is_not_the_phase_2_fixture(client):
    """Two different signals must not produce the same numbers."""
    quiet = _upload(client, _wav_bytes(3.0, freq=220.0)).json()["audio_job_id"]
    bright = _upload(client, _wav_bytes(3.0, freq=1760.0)).json()["audio_job_id"]
    a = client.post("/audio/analyze", data={"audio_job_id": quiet}).json()["features"]
    b = client.post("/audio/analyze", data={"audio_job_id": bright}).json()["features"]
    assert a["energy"] != b["energy"]
    assert (a["bpm"], a["musical_key"]) != (120.0, "A minor")


@needs_dsp
def test_toneless_input_reports_low_confidence_not_a_confident_guess(client):
    """A signal with no pulse must say so rather than assert a tempo."""
    job_id = _upload(client, _wav_bytes(3.0, freq=440.0)).json()["audio_job_id"]
    body = client.post("/audio/analyze", data={"audio_job_id": job_id}).json()
    # A pure sine has no onsets, so the tempo confidence must be poor even
    # though librosa will still report *some* BPM.
    assert body["features"]["field_confidence"]["tempo"] < 0.5
    # The headline number is the weakest field, never an average.
    assert body["features"]["confidence"] == min(
        body["features"]["field_confidence"].values()
    )


@needs_dsp
def test_analysis_leaves_no_decoded_copy_behind(client):
    job_id = _upload(client, _wav_bytes(2.0)).json()["audio_job_id"]
    client.post("/audio/analyze", data={"audio_job_id": job_id})
    # Only the clip and its sidecar; no analysis.wav anywhere in storage.
    names = {p.name for p in config.STORAGE_DIR.iterdir()}
    assert names == {f"{job_id}.bin", f"{job_id}.json"}


@needs_dsp
def test_direct_upload_to_analyze_is_not_retained(client):
    """A clip posted straight to /analyze has no ID, so it must not be kept."""
    response = client.post(
        "/audio/analyze",
        files={"file": ("c.wav", io.BytesIO(_wav_bytes(2.0)), "audio/wav")},
    )
    assert response.status_code == 200
    assert response.json()["audio_job_id"] is None
    assert list(config.STORAGE_DIR.iterdir()) == []


@needs_dsp
def test_undecodable_audio_fails_as_media_not_as_server_error(client):
    """Truncated-but-well-signed input: 415, never a 500."""
    job_id = None
    header = _wav_bytes(1.0)[:200]  # valid RIFF header, no usable frames
    response = _upload(client, header)
    if response.status_code == 200:
        job_id = response.json()["audio_job_id"]
        analysis = client.post("/audio/analyze", data={"audio_job_id": job_id})
        assert analysis.status_code in (200, 415)
        assert analysis.status_code != 500


# ---------------------------------------------------------------------------
# §6.4 — ACRCloud recognition adapter (REC-ID-004, REC-ID-005)
# ---------------------------------------------------------------------------


def test_recognition_status_reports_what_is_missing_without_revealing_it(client, monkeypatch):
    """`3001 Missing/Invalid Access Key` is ACRCloud's answer to a wrong key, a
    wrong host *and* a wrong product's credentials alike, so the only way to
    tell them apart from outside is to report what we hold. Lengths, never
    values."""
    # Set explicitly on top of the offline fixture, which strips them.
    monkeypatch.setenv("ACRCLOUD_ACCESS_KEY", "k" * 32)
    monkeypatch.setenv("ACRCLOUD_ACCESS_SECRET", "s" * 40)

    body = client.get("/audio/recognition/status").json()
    assert body["configured"] is False
    assert body["host_set"] is False
    assert body["access_key_length"] == 32
    # The values themselves must never appear.
    assert "k" * 32 not in str(body)
    assert "s" * 40 not in str(body)


def test_identify_is_a_placeholder_only_while_unconfigured(client, monkeypatch):
    """`placeholder` is a claim about the *response*: true only while there is
    no provider to ask. A configured provider answering "no match" is a real
    result, and calling it a placeholder would be as wrong as the reverse."""
    job_id = _upload(client, _wav_bytes(0.5)).json()["audio_job_id"]
    body = client.post("/audio/identify", data={"audio_job_id": job_id}).json()
    assert body["placeholder"] is True
    assert body["matched"] is False
    assert body["track"] == {}
    assert body["reason"].startswith("not_configured")


def test_identify_never_fabricates_a_match(client):
    """The fixture this replaces claimed "Holocene" by Bon Iver at 0.88 for any
    input, including silence."""
    job_id = _upload(client, _wav_bytes(0.5)).json()["audio_job_id"]
    body = client.post("/audio/identify", data={"audio_job_id": job_id}).json()
    assert body["confidence"] == 0.0
    assert not body["track"]


def test_recognition_thresholds_are_ordered_and_declared():
    """REC-ID-005 — fixed before any measurement, so they cannot be tuned to
    flatter a result afterwards."""
    from app import acrcloud

    assert 0 < acrcloud.LOW_CONFIDENCE_SCORE < acrcloud.MATCH_SCORE <= 100


@pytest.mark.parametrize(
    "score, expect_match, expect_low",
    [
        (95.0, True, False),   # confident
        (80.0, True, False),   # exactly at the match threshold
        (70.0, True, True),    # middle band: shown, flagged uncertain
        (59.9, False, False),  # below the floor: no track is named at all
    ],
)
def test_score_bands_map_to_distinct_outcomes(score, expect_match, expect_low):
    """The middle band is the one that matters: a noisy phone recording of a
    genuine match often lands in the 60s, and discarding it is as wrong as
    presenting it as certain."""
    from app import acrcloud

    payload = {
        "status": {"code": 0, "msg": "Success"},
        "metadata": {"music": [{
            "title": "Holocene", "score": score,
            "artists": [{"name": "Bon Iver"}],
            "album": {"name": "Bon Iver"},
            "external_metadata": {"spotify": {"track": {"id": "sp123"}}},
        }]},
    }
    result = _fake_acr_result(payload)
    assert result.matched is expect_match
    assert result.low_confidence is expect_low
    if expect_match:
        assert result.track["artist"] == "Bon Iver"
        # REC-ID-004: the external IDs are the point -- they let a recognized
        # track skip a provider text search entirely.
        assert result.track["external_ids"]["spotify"] == "sp123"


@pytest.mark.parametrize(
    "code, reason, configured",
    [
        (1001, "no_match", True),        # ran, recognized nothing -- a real answer
        (3001, "auth_rejected", False),  # our problem, never "your song is unknown"
        (3003, "quota_exceeded", True),
    ],
)
def test_provider_status_codes_are_not_flattened_into_no_match(code, reason, configured):
    """Telling a user their song is unrecognizable when the key is wrong is the
    exact failure this adapter is structured to prevent."""
    result = _fake_acr_result({"status": {"code": code, "msg": "x"}})
    assert result.matched is False
    assert result.reason == reason
    assert result.configured is configured


def _fake_acr_result(payload):
    """Run acrcloud.identify against a stubbed HTTP layer."""
    import asyncio

    import httpx

    from app import acrcloud

    class _Response:
        def json(self):
            return payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _Response()

    original_client = httpx.AsyncClient
    original_env = {k: os.environ.get(k) for k in
                    ("ACRCLOUD_HOST", "ACRCLOUD_ACCESS_KEY", "ACRCLOUD_ACCESS_SECRET")}
    httpx.AsyncClient = _Client
    os.environ.update({
        "ACRCLOUD_HOST": "identify-eu-west-1.acrcloud.com",
        "ACRCLOUD_ACCESS_KEY": "k" * 32,
        "ACRCLOUD_ACCESS_SECRET": "s" * 40,
    })
    try:
        path = config.STORAGE_DIR / "acr-sample.wav"
        path.write_bytes(_wav_bytes(0.2))
        return asyncio.run(acrcloud.identify(path))
    finally:
        httpx.AsyncClient = original_client
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_signature_matches_acrclouds_documented_string():
    """The signed string is positional and newline-separated; any line wrong
    yields the same 3001 as a wrong key, so it is pinned by test."""
    import base64
    import hashlib
    import hmac

    from app import acrcloud

    expected_input = "\n".join(["POST", "/v1/identify", "KEY", "audio", "1", "1700000000"])
    expected = base64.b64encode(
        hmac.new(b"SECRET", expected_input.encode(), hashlib.sha1).digest()
    ).decode()
    assert acrcloud._signature("SECRET", "KEY", "1700000000") == expected


# ---------------------------------------------------------------------------
# §6.4 — catalogue junk. The biggest source of *wrong* answers, and wrong is
# worse than missing: the user cannot tell a confident wrong answer from a
# right one.
# ---------------------------------------------------------------------------


def test_junk_catalogue_entries_are_rejected():
    """Both cases are real, observed, and scored differently.

    `'Remix' — 'DJ'` came back at score 64 for Ariana Grande's "Problem" in the
    field. `'Fingerprint Less' — 'Kanroc Xpitaf'` came back at **score 100** for
    a rock clip whose real identity is "Killing In The Name". The second is why
    this cannot be a low-score-only check: a placeholder row fingerprints as
    strongly as a real one, because score measures fingerprint agreement and
    says nothing about whether the row is worth showing anybody.
    """
    from app.acrcloud import is_plausible_release

    assert is_plausible_release("Remix", "DJ") is False
    assert is_plausible_release("Fingerprint Less", "Kanroc Xpitaf") is False
    assert is_plausible_release("Unknown", "Unknown Artist") is False
    assert is_plausible_release("", "Bon Iver") is False
    assert is_plausible_release("Holocene", None) is False


def test_plausible_releases_survive_the_filter():
    """Conservative on purpose -- a filter that eats real tracks is a worse bug
    than the one it fixes."""
    from app.acrcloud import is_plausible_release

    assert is_plausible_release("Killing In The Name", "Rage Against The Machine")
    assert is_plausible_release("Problem", "Ariana Grande")
    # One generic field is not enough on its own: plenty of real artists are
    # credited "DJ <something>", and "Intro" is a real track title.
    assert is_plausible_release("Intro", "DJ Shadow")
    assert is_plausible_release("Poison Remix", "DJ")
    assert is_plausible_release("Remix", "Aphex Twin")


def test_a_junk_top_hit_does_not_hide_the_real_track_behind_it():
    """Observed live: a placeholder entry scored 100 while the correct answer
    was the runner-up. Taking the top score outright threw the answer away."""
    payload = {
        "status": {"code": 0, "msg": "Success"},
        "metadata": {"music": [
            {"title": "Fingerprint Less", "score": 100,
             "artists": [{"name": "Kanroc Xpitaf"}]},
            {"title": "Killing In The Name", "score": 92,
             "artists": [{"name": "Rage Against The Machine"}]},
        ]},
    }
    result = _fake_acr_result(payload)
    assert result.matched is True
    assert result.track["title"] == "Killing In The Name"
    assert result.confidence == 0.92


def test_all_junk_reports_a_miss_distinguishable_from_a_plain_one():
    """We *did* recognize something -- it just was not worth showing. Logged as
    its own reason so the two can be told apart in production."""
    payload = {
        "status": {"code": 0, "msg": "Success"},
        "metadata": {"music": [
            {"title": "Remix", "score": 64, "artists": [{"name": "DJ"}]},
        ]},
    }
    result = _fake_acr_result(payload)
    assert result.matched is False
    assert result.reason == "junk_metadata_only"
    assert not result.track
