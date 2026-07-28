import os
import random
import time
import uuid
import logging
from datetime import timedelta
from typing import Any, Optional

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

import requests
import spotipy
from spotipy.cache_handler import FlaskSessionCacheHandler
from spotipy.oauth2 import SpotifyOAuth
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from contracts.models import (
    DEFAULT_PROVIDER,
    ClientRequestPayload,
    DiscoveryMode,
    Identity,
    Intent,
    RecommendationContext,
    RequestBody,
    RequestEnvelope,
)
from n8n_client import N8nClient, N8nClientError
import auth_google

logging.getLogger("spotipy").setLevel(logging.WARNING)
logging.getLogger("spotipy.oauth2").setLevel(logging.WARNING)
logging.getLogger("spotipy.client").setLevel(logging.WARNING)


app = Flask(__name__)
# A random fallback key means every restart invalidates all sessions -- which
# also invalidates any in-flight OAuth `state`, so a sign-in started before a
# reload can never complete. Tolerable for the legacy chat routes, so it stays,
# but auth_google warns at startup when the key is ephemeral.
_FLASK_SECRET_KEY_IS_EPHEMERAL = not os.getenv("FLASK_SECRET_KEY")
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(32)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
# Session-cookie hardening (Phase 5 §5.2). SameSite must be "Lax", not "Strict":
# the Google OAuth callback is a cross-site top-level GET, and "Strict" would
# withhold the cookie on that navigation, losing the session the flow is bound
# to. "Lax" still blocks cross-site POST/subresource sends.
# Re-read templates when they change on disk. Without this Flask caches the
# compiled template for the life of the process, so a UI edit is invisible until
# a restart -- and the failure mode is the dangerous kind: the page loads fine,
# it is just the previous version, so a change looks like it did not work when
# in fact it was never served. Costs a stat() per render.
app.config["TEMPLATES_AUTO_RELOAD"] = os.getenv("FLASK_TEMPLATES_AUTO_RELOAD", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(os.getenv("FLASK_TLS_CERT"))

KNOWLEDGE_BASE_ID = "AOGLLMF80H"
MODEL_ARN = MODEL_ARN = MODEL_ARN = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_AGENT_ID = os.getenv("BEDROCK_AGENT_ID")
BEDROCK_AGENT_ALIAS_ID = os.getenv("BEDROCK_AGENT_ALIAS_ID")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-2")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
SPOTIFY_SCOPE = "user-top-read playlist-modify-public playlist-modify-private user-library-modify"
SYSTEM_PROMPT = ""
SPOTIFY_TOKEN_SESSION_KEY = "token_info"
LEGACY_SPOTIFY_TOKEN_SESSION_KEY = "spotify_token_info"

# n8n orchestrator (WF-001) — Phase 2 cutover path; Bedrock routes remain intact.
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()
# Must exceed WF-002's own HTTP timeout (90s) plus router overhead, or Flask
# gives up on a request n8n is still successfully working on -- the caller then
# sees "the orchestrator timed out" for a recommendation that actually
# completed. Raised from 30s on 2026-07-26 after Hebrew requests, which are
# legitimately slower, began failing at ~22s of real work.
N8N_HTTP_TIMEOUT_SECONDS = float(os.getenv("N8N_HTTP_TIMEOUT_SECONDS", "120"))
# Optional gate for the new path (default on). Set to "false" to disable /api/v1/requests.
USE_N8N_ORCHESTRATOR = os.getenv("USE_N8N_ORCHESTRATOR", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

app.config["N8N_WEBHOOK_URL"] = N8N_WEBHOOK_URL
app.config["N8N_HTTP_TIMEOUT_SECONDS"] = N8N_HTTP_TIMEOUT_SECONDS
app.config["USE_N8N_ORCHESTRATOR"] = USE_N8N_ORCHESTRATOR

# Audio Service (§6.1). Flask is the browser's only origin, so the clip is
# uploaded here and forwarded once; the browser never talks to audio-service and
# never learns an internal URL. Deliberately NOT routed through n8n: n8n's HTTP
# node would have to buffer and re-encode the whole multipart body, and an
# orchestrator is the wrong place for bytes. Only the resulting `audio_job_id`
# goes through n8n, which is what WF-003/WF-004 are built to receive.
AUDIO_SERVICE_URL = os.getenv("AUDIO_SERVICE_URL", "http://localhost:8003").rstrip("/")
# Generous: a large clip crosses the wire twice (browser -> Flask -> service)
# and ffprobe runs before the response.
AUDIO_UPLOAD_TIMEOUT_SECONDS = float(os.getenv("AUDIO_UPLOAD_TIMEOUT_SECONDS", "90"))


# ---------------------------------------------------------------------------
# Database access (Phase 5 §5.2). Flask's first DB dependency: Google sign-in
# writes the application's first real `users` rows and the `oauth_accounts`
# grants. Reuses the canonical ORM in contracts/db_models.py rather than
# redefining the schema. Engine creation is lazy so the app still starts (and
# the legacy routes still work) when the database is unreachable.
# ---------------------------------------------------------------------------
_db_engine = None
_db_session_factory = None


def _normalize_database_url(url: str) -> str:
    """Force the psycopg (v3) dialect, matching migrations/env.py."""
    for prefix, repl in (
        ("postgresql+psycopg2://", "postgresql+psycopg://"),
        ("postgresql://", "postgresql+psycopg://"),
        ("postgres://", "postgresql+psycopg://"),
    ):
        if url.startswith(prefix):
            return repl + url[len(prefix):]
    return url


def _database_url_from_postgres_vars() -> str:
    """Assemble the URL from POSTGRES_* parts, or "" when they are absent."""
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    if not (user and password):
        return ""

    from urllib.parse import quote_plus

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", user)
    return (
        f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{database}"
    )


def _resolve_database_url() -> str:
    """POSTGRES_* when compose sets POSTGRES_HOST, else DATABASE_URL.

    The ordering is deliberate and matches provider-gateway's `app/db.py`.
    docker-compose.yml loads the whole `.env` into the container -- including a
    `DATABASE_URL` whose host is `localhost`, correct for a host-run process and
    useless inside the network -- and then sets `POSTGRES_HOST: postgres` on top.
    An explicitly set POSTGRES_HOST is therefore the signal that we are running
    inside the compose network (INF-011) and must build the URL from the parts.
    Outside a container nothing sets it, so `DATABASE_URL` still wins and
    `python app.py` behaves exactly as it did before.
    """
    if os.getenv("POSTGRES_HOST"):
        assembled = _database_url_from_postgres_vars()
        if assembled:
            return assembled

    explicit = (os.getenv("DATABASE_URL") or "").strip()
    if explicit:
        return _normalize_database_url(explicit)

    return _database_url_from_postgres_vars()


def get_db_session_factory():
    global _db_engine, _db_session_factory
    if _db_session_factory is None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        database_url = _resolve_database_url()
        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        _db_engine = create_engine(database_url, future=True, pool_pre_ping=True)
        _db_session_factory = sessionmaker(bind=_db_engine, future=True)
    return _db_session_factory


def _lazy_session():
    """Indirection so auth_google resolves the factory at request time, not
    import time -- otherwise importing app.py would require a live database."""
    return get_db_session_factory()()


auth_google.init_app(app, _lazy_session)
if auth_google.is_configured() and _FLASK_SECRET_KEY_IS_EPHEMERAL:
    logging.getLogger("melody.auth.google").warning(
        "FLASK_SECRET_KEY is unset, so a random key is generated per start. "
        "Sessions -- including in-flight OAuth state -- are invalidated on every "
        "restart. Set FLASK_SECRET_KEY before relying on Google sign-in."
    )


def get_n8n_client() -> N8nClient:
    webhook_url = app.config.get("N8N_WEBHOOK_URL") or ""
    if not webhook_url:
        raise N8nClientError(
            "N8N_WEBHOOK_URL is not configured.",
            code="CONFIG_ERROR",
            status_code=503,
        )
    return N8nClient(
        webhook_url=webhook_url,
        timeout_seconds=app.config.get("N8N_HTTP_TIMEOUT_SECONDS", 30.0),
    )


def _current_identity(request_id: str) -> Identity:
    """Resolve who is asking, for any intent.

    WF-001 upserts `guest_sessions` on the `guest_id` sent here and passes an
    authenticated `user_id` straight through, so this is the single point that
    decides whether a request is attributed to a signed-in user or a guest.
    """
    session_id = session.get("session_id") or request_id
    return Identity(
        guest_id=session.get("guest_id") or session_id,
        session_id=session_id,
        user_id=session.get("user_id"),
    )


def build_envelope(
    intent: Intent,
    body: RequestBody,
    *,
    locale: str = "en",
    idempotency_key: Optional[str] = None,
) -> RequestEnvelope:
    """Wrap an intent-specific body in the canonical WF-001 envelope.

    WF-001's `Validate Request Schema` requires an `idempotency_key` for the
    side-effecting intents (feedback, playlist_export, auth_connection_sync)
    and rejects the request without one, so callers for those intents must
    supply it.
    """
    request_id = str(uuid.uuid4())
    return RequestEnvelope(
        api_version="v1",
        request_id=request_id,
        intent=intent,
        identity=_current_identity(request_id),
        locale=locale,
        body=body,
        idempotency_key=idempotency_key,
    )


def build_text_recommendation_envelope(
    prompt: str,
    *,
    locale: str = "en",
    discovery_mode: DiscoveryMode = DiscoveryMode.BALANCED,
    provider: str = DEFAULT_PROVIDER,
) -> RequestEnvelope:
    """Map a text prompt into the canonical WF-001 request envelope."""
    envelope = build_envelope(
        Intent.TEXT_RECOMMENDATION,
        RequestBody(prompt=prompt, provider=provider),
        locale=locale,
    )
    envelope.body.recommendation_context = RecommendationContext(
        request_id=envelope.request_id,
        user_text=prompt,
        discovery_mode=discovery_mode,
        locale=locale,
        provider=provider,
    )
    return envelope

QUESTIONS_LIST = [
    "Recommend indie-folk song from the late 2000s.",
    "What are some essential tracks with an acoustic, intimate vibe?",
    "Suggest an album filled with earnest lyrics and group vocals.",
    "Find artists who capture a cozy campfire aesthetic.",
    "What standout releases occurred between 2008 and 2009.",
    "Recommend something with jangly guitars and orchestral brightness.",
    "Which albums feature heart-on-sleeve vulnerability?",
    "Suggest upbeat indie-pop tracks to lift my mood.",
    "Find music that blends melancholy with high infectious energy.",
    "What are the best collaborative or band-centric projects?",
    "Recommend an album with raw, spontaneous production qualities.",
    "Find artists from the Welsh or UK indie scene.",
    "Suggest music perfect for thawing out on a cold winter night.",
    "What are some hidden gems in the indie rock genre?",
    "Give me a recommendation that feels completely organic and handmade.",
    "Suggest a high-energy dance track for a weekend party.",
     "What are some iconic pop albums with incredible vocal performances?",
     "Find an EDM artist known for heavy bass and fast tempos.",
     "Recommend a classic electronic album that defined the genre.",
     "Suggest an upbeat pop-dance track to get me moving.",
     "Find R&B or soul music with a modern, electronic twist.",
     "What are some highly-rated club anthems from the database?",
]


@app.before_request
def ensure_session_id():
    session.permanent = True
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        session.modified = True


def get_spotify_cache_handler():
    return FlaskSessionCacheHandler(session)


def get_cached_spotify_token_info():
    cache_handler = get_spotify_cache_handler()
    token_info = cache_handler.get_cached_token()
    legacy_token_info = session.get(LEGACY_SPOTIFY_TOKEN_SESSION_KEY)

    if not token_info and legacy_token_info:
        cache_handler.save_token_to_cache(legacy_token_info)
        session.pop(LEGACY_SPOTIFY_TOKEN_SESSION_KEY, None)
        session.modified = True
        token_info = legacy_token_info

    return token_info


def has_spotify_token_info():
    return bool(
        session.get(SPOTIFY_TOKEN_SESSION_KEY)
        or session.get(LEGACY_SPOTIFY_TOKEN_SESSION_KEY)
    )


def clear_spotify_token_info():
    session.pop(SPOTIFY_TOKEN_SESSION_KEY, None)
    session.pop(LEGACY_SPOTIFY_TOKEN_SESSION_KEY, None)
    session.modified = True


def get_spotify_oauth():
    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SPOTIFY_SCOPE,
        cache_handler=get_spotify_cache_handler(),
        show_dialog=True,
    )


def get_valid_spotify_token():
    token_info = get_cached_spotify_token_info()
    if not token_info:
        return None

    expires_at = token_info.get("expires_at", 0)
    is_expired_or_stale = expires_at <= int(time.time()) + 60

    if is_expired_or_stale:
        refresh_token = token_info.get("refresh_token")
        if not refresh_token:
            clear_spotify_token_info()
            return None

        spotify_oauth = get_spotify_oauth()
        previous_refresh_token = refresh_token
        token_info = spotify_oauth.refresh_access_token(refresh_token)
        if "refresh_token" not in token_info:
            token_info["refresh_token"] = previous_refresh_token
        session.modified = True

    return token_info.get("access_token")


def query_bedrock(question, chat_id=None):
    client = boto3.client("bedrock-agent-runtime", region_name=AWS_REGION)
    spotify_access_token = get_valid_spotify_token()
    flask_session_id = session.get("session_id")
    if not flask_session_id:
        flask_session_id = str(uuid.uuid4())
        session["session_id"] = flask_session_id
        session.permanent = True
        session.modified = True

    session_attributes = {}
    if spotify_access_token:
        session_attributes["spotify_token"] = spotify_access_token

    bedrock_session_id = flask_session_id
    bedrock_memory_id = flask_session_id

    response = client.invoke_agent(
        agentId=BEDROCK_AGENT_ID,
        agentAliasId=BEDROCK_AGENT_ALIAS_ID,
        sessionId=bedrock_session_id,
        memoryId=bedrock_memory_id,
        inputText=question,
        sessionState={
            "sessionAttributes": session_attributes
        },
    )

    final_text = ""
    for event in response.get("completion", []):
        if "chunk" in event:
            chunk = event["chunk"].get("bytes", b"")
            final_text += chunk.decode("utf-8")

    return final_text


def parse_chat_payload():
    data = request.get_json(silent=True) or {}
    question = (
        data.get("user_query")
        or data.get("question")
        or data.get("message")
        or ""
    ).strip()
    chat_id = (data.get("session_id") or data.get("chat_id") or "").strip()
    return question, chat_id


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        question = (
            request.form.get("user_query")
            or request.form.get("question")
            or request.form.get("message")
            or data.get("user_query")
            or data.get("question")
            or data.get("message")
            or ""
        ).strip()
        if not question:
            return render_template("index.html", error="Question is required.")

        try:
            answer = query_bedrock(question)
        except (BotoCoreError, ClientError) as error:
            return render_template("index.html", error=f"Bedrock request failed: {error}")

        return render_template("index.html", response=answer, answer=answer, question=question)

    sample_queries = random.sample(QUESTIONS_LIST, 4)
    return render_template("index.html", sample_queries=sample_queries)


@app.route("/login")
def login():
    spotify_oauth = get_spotify_oauth()
    authorization_url = spotify_oauth.get_authorize_url()
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    if request.args.get("error"):
        return redirect(url_for("index"))

    code = request.args.get("code")
    if code:
        spotify_oauth = get_spotify_oauth()
        spotify_oauth.get_access_token(code, as_dict=True, check_cache=False)
        session.pop(LEGACY_SPOTIFY_TOKEN_SESSION_KEY, None)
        session.modified = True

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/api/auth_status")
def auth_status():
    access_token = get_valid_spotify_token()
    if not access_token:
        return jsonify({"logged_in": False, "session_id": session.get("session_id")})

    try:
        sp = spotipy.Spotify(auth=access_token)
        user = sp.current_user()
    except Exception:
        clear_spotify_token_info()
        return jsonify({"logged_in": False, "session_id": session.get("session_id")})

    return jsonify(
        {
            "logged_in": True,
            "display_name": user["display_name"],
            "profile_image_url": user["images"][0]["url"] if user["images"] else None,
            "session_id": session.get("session_id"),
        }
    )


@app.route("/ask", methods=["POST"])
def ask():
    question, chat_id = parse_chat_payload()

    if not question:
        return jsonify({"error": "Question is required."}), 400

    if KNOWLEDGE_BASE_ID == "YOUR_KB_ID_HERE":
        return (
            jsonify(
                {
                    "error": (
                        "Set KNOWLEDGE_BASE_ID in app.py before querying "
                        "Amazon Bedrock Knowledge Bases."
                    )
                }
            ),
            500,
        )

    try:
        answer = query_bedrock(question, chat_id=chat_id)
    except (BotoCoreError, ClientError) as error:
        return jsonify({"error": f"Bedrock request failed: {error}"}), 500

    return jsonify({"response": answer, "answer": answer})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    question = (
        data.get("user_query")
        or data.get("question")
        or data.get("message")
        or ""
    ).strip()
    chat_id = data.get("session_id") or data.get("chat_id")

    if not question:
        return jsonify({"error": "Question is required."}), 400

    try:
        answer = query_bedrock(question, chat_id=chat_id)
    except (BotoCoreError, ClientError) as error:
        return jsonify({"error": f"Bedrock request failed: {error}"}), 500

    return jsonify({"response": answer, "answer": answer})


@app.route("/api/v1/requests", methods=["POST"])
def api_v1_requests():
    """Forward a text recommendation request to n8n WF-001 (Phase 2 path).

    Legacy Bedrock routes (/chat, /ask) remain unchanged for rollback.
    """
    raw = request.get_json(silent=True) or {}
    try:
        payload = ClientRequestPayload.from_dict(raw)
    except ValueError as error:
        return _error("VALIDATION_ERROR", str(error), 400)

    prompt = payload.resolved_prompt()
    if not prompt:
        return _error("VALIDATION_ERROR", "A text prompt is required.", 400)

    envelope = build_text_recommendation_envelope(
        prompt,
        locale=_safe_locale(payload.locale),
        discovery_mode=payload.discovery_mode or DiscoveryMode.BALANCED,
        provider=payload.provider or DEFAULT_PROVIDER,
    )
    return _post_envelope(envelope)


def _error(code: str, message: str, status_code: int):
    """Section 3.4 error envelope: no stack traces, tokens, or internal URLs."""
    return jsonify({"ok": False, "error": {"code": code, "message": message}}), status_code


def _post_envelope(envelope: RequestEnvelope):
    """Send an envelope to WF-001 and forward its response verbatim."""
    if not app.config.get("USE_N8N_ORCHESTRATOR"):
        return _error("FEATURE_DISABLED", "The n8n orchestrator path is disabled.", 503)
    try:
        client = get_n8n_client()
        body, status_code = client.post_envelope(envelope.to_dict())
    except N8nClientError as error:
        return jsonify(error.to_error_envelope(envelope.request_id)), error.status_code
    return jsonify(body), status_code


@app.route("/api/v1/audio/uploads", methods=["POST"])
def api_v1_audio_upload():
    """AUD-UP-001: accept a recorded or uploaded clip and return an audio_job_id.

    Flask holds no audio itself -- it streams the part straight to audio-service,
    which owns validation, storage and expiry (§6.1). Keeping the bytes in one
    service is what makes "cleanup on success, failure, timeout and expiry"
    checkable in one place instead of two.
    """
    file_storage = request.files.get("file")
    if file_storage is None:
        return _error("VALIDATION_ERROR", "No audio file was uploaded.", 400)

    identity = _current_identity(str(uuid.uuid4()))
    try:
        response = requests.post(
            f"{AUDIO_SERVICE_URL}/audio/uploads",
            files={
                "file": (
                    # The original filename is not forwarded. It is caller-
                    # controlled and often personal, and nothing downstream uses
                    # it -- the container is detected from the bytes (AUD-UP-003,
                    # AUD-UP-007).
                    "clip",
                    file_storage.stream,
                    file_storage.mimetype or "application/octet-stream",
                )
            },
            data={
                "user_id": identity.user_id or "",
                "guest_id": identity.guest_id or "",
            },
            timeout=AUDIO_UPLOAD_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        return _error("UPSTREAM_TIMEOUT", "The audio upload timed out. Try a shorter clip.", 504)
    except requests.RequestException:
        # The exception text can carry the internal host; §3.4 keeps it out.
        app.logger.exception("audio_upload_failed")
        return _error("UPSTREAM_ERROR", "Audio upload is unavailable right now.", 502)

    try:
        body = response.json()
    except ValueError:
        return _error("UPSTREAM_INVALID_RESPONSE", "The audio service returned an invalid response.", 502)
    # Forwarded verbatim, including rejections: audio-service's 413/415 messages
    # name the actual limit and format, which is what the user needs to act on.
    return jsonify(body), response.status_code


@app.route("/api/v1/audio/requests", methods=["POST"])
def api_v1_audio_request():
    """UI-002: run an uploaded clip through identification or vibe matching.

    The mode is explicit and required (AUD-UP-001: "explicit mode selection").
    Guessing between "what is this song" and "find me something like this" from
    the audio alone is not possible, and picking one silently gives the user a
    confidently wrong kind of answer.
    """
    raw = request.get_json(silent=True) or {}
    audio_job_id = _optional_text(raw.get("audio_job_id"))
    if not audio_job_id:
        return _error("VALIDATION_ERROR", "audio_job_id is required.", 400)

    mode = str(raw.get("mode") or "").strip().lower()
    modes = {
        "identify": Intent.AUDIO_IDENTIFICATION,
        "similar": Intent.AUDIO_VIBE_RECOMMENDATION,
    }
    if mode not in modes:
        return _error("VALIDATION_ERROR", "mode must be one of: identify, similar.", 400)

    locale = _safe_locale(raw.get("locale"))
    prompt = _optional_text(raw.get("prompt")) or ""
    envelope = build_envelope(
        modes[mode],
        RequestBody(
            audio_job_id=audio_job_id,
            prompt=prompt,
            provider=_optional_text(raw.get("provider")) or DEFAULT_PROVIDER,
        ),
        locale=locale,
    )
    if modes[mode] is Intent.AUDIO_VIBE_RECOMMENDATION:
        # The same context the text path builds, so both intents reach the graph
        # through one shape. `user_text` may legitimately be empty here: §6.5
        # composes the retrieval query from the audio features when it is.
        envelope.body.recommendation_context = RecommendationContext(
            request_id=envelope.request_id,
            user_text=prompt,
            audio_job_id=audio_job_id,
            discovery_mode=raw.get("discovery_mode") or DiscoveryMode.BALANCED,
            locale=locale,
            provider=_optional_text(raw.get("provider")) or DEFAULT_PROVIDER,
        )
    return _post_envelope(envelope)


@app.route("/api/v1/audio/limits", methods=["GET"])
def api_v1_audio_limits():
    """Serve the service's real limits so the UI enforces the same numbers.

    Hardcoding them in JavaScript is how a client ends up rejecting a file the
    server would accept, or -- worse -- uploading 40 MB to be told no.
    """
    try:
        response = requests.get(f"{AUDIO_SERVICE_URL}/audio/limits", timeout=10)
        return jsonify(response.json()), response.status_code
    except (requests.RequestException, ValueError):
        return _error("UPSTREAM_ERROR", "Audio limits are unavailable.", 502)


@app.route("/api/v1/auth/status", methods=["GET"])
def api_v1_auth_status():
    """UI-003/UI-004: who the caller is and which provider scopes they hold.

    One call, so the UI can decide between "Sign in", "Connect YouTube" and
    "Export" without stitching together several endpoints. Returns connection
    metadata only -- never tokens.
    """
    google = auth_google.connection_status()
    return jsonify(
        {
            "ok": True,
            "session_id": session.get("session_id"),
            "authenticated": bool(session.get("user_id")),
            "guest": not session.get("user_id"),
            "providers": {"google": google},
            # The UI gates the export button on this rather than re-deriving
            # the scope rule client-side.
            "can_export": bool(google.get("youtube_authorized")),
        }
    )


@app.route("/api/v1/feedback", methods=["POST"])
def api_v1_feedback():
    """UI-006: record Like/Dislike/Skip against a recommended track (WF-005)."""
    raw = request.get_json(silent=True) or {}
    action = str(raw.get("action") or "").strip().lower()
    if action not in {"like", "dislike", "skip"}:
        return _error("VALIDATION_ERROR", "action must be one of: like, dislike, skip.", 400)

    envelope = build_envelope(
        Intent.FEEDBACK,
        RequestBody(
            feedback={
                "action": action,
                "provider_track_id": _optional_text(raw.get("provider_track_id")),
                "provider": _optional_text(raw.get("provider")),
                "title": _optional_text(raw.get("title")),
                "artist": _optional_text(raw.get("artist")),
                "source_request_id": _optional_text(raw.get("source_request_id")),
                # §7.2 builds affinities from a track's *features*, so the
                # features have to travel with the click. Without these the
                # profile received an action and a title and learned nothing
                # it could apply to any other track -- the update ran, the
                # version moved, and the next recommendation was unchanged.
                "genre": _optional_text(raw.get("genre")),
                "genres": raw.get("genres") if isinstance(raw.get("genres"), list) else None,
                "energy": raw.get("energy"),
                # Distinguishes a rejection from a finished listen (§7.2's
                # "skip is a weak negative only when context supports it").
                "played_fraction": raw.get("played_fraction"),
            }
        ),
        locale=_safe_locale(raw.get("locale")),
        # ARC-003: feedback is immutable and side-effecting, so WF-001 rejects
        # it without a key. The client supplies a stable one so that a
        # double-click records one event, not two.
        idempotency_key=_optional_text(raw.get("idempotency_key")) or str(uuid.uuid4()),
    )
    return _post_envelope(envelope)


@app.route("/api/v1/playlists/export", methods=["POST"])
def api_v1_playlists_export():
    """UI-009: export the current recommendation to the provider (WF-006).

    Only ever called after an explicit user confirmation in the UI -- this
    writes to a real YouTube account.
    """
    raw = request.get_json(silent=True) or {}
    track_ids = raw.get("track_ids")
    if not isinstance(track_ids, list) or not track_ids:
        return _error("VALIDATION_ERROR", "track_ids must be a non-empty list.", 400)
    track_ids = [str(t).strip() for t in track_ids if str(t).strip()]
    if not track_ids:
        return _error("VALIDATION_ERROR", "track_ids must contain at least one track id.", 400)

    envelope = build_envelope(
        Intent.PLAYLIST_EXPORT,
        RequestBody(
            playlist={
                "provider": _optional_text(raw.get("provider")) or "youtube",
                "name": _optional_text(raw.get("name")) or "Melody Export",
                "description": _optional_text(raw.get("description")) or "",
                "track_ids": track_ids,
            }
        ),
        locale=_safe_locale(raw.get("locale")),
        # EXPORT-002: the same key must map to the same playlist, so a
        # double-click cannot create two real playlists.
        idempotency_key=_optional_text(raw.get("idempotency_key")) or str(uuid.uuid4()),
    )
    return _post_envelope(envelope)


@app.after_request
def _no_store_html(response):
    """Never let a browser hold on to the app shell.

    The whole UI — markup, styles and every line of JavaScript — is inside one
    rendered template, so a cached copy of it is a cached copy of the entire
    client. Flask sets no cache headers on a rendered response, which leaves the
    decision to browser heuristics, and a tab that simply stays open never
    re-requests the document at all.

    That produced the worst kind of bug report during the §6.1 work: a fix was
    verified as correct in a fresh browser and still reproduced for the
    developer, because their page had been loaded before the fix existed. The
    symptom (a UI change that "did not work") is indistinguishable from a real
    defect, and chasing it costs far more than the bytes this saves.

    Static assets keep their own validators — this is only about the shell.
    """
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


@app.route("/health/live", methods=["GET"])
def health_live():
    """Process liveness — deliberately checks nothing external."""
    return jsonify({"status": "ok"})


@app.route("/health/ready", methods=["GET"])
def health_ready():
    """Dependency readiness: the orchestrator and the database.

    Reports per-dependency detail and returns 503 when any required one is
    down, so a load balancer sees the difference between "alive" and "able to
    serve a recommendation".
    """
    checks: dict[str, Any] = {}

    checks["n8n"] = {
        "configured": bool(app.config.get("N8N_WEBHOOK_URL")),
        "enabled": bool(app.config.get("USE_N8N_ORCHESTRATOR")),
    }
    checks["n8n"]["ok"] = checks["n8n"]["configured"] and checks["n8n"]["enabled"]

    try:
        from sqlalchemy import text as sa_text

        with get_db_session_factory()() as db:
            db.execute(sa_text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as error:
        # The class name only -- a driver message can carry the DSN, and this
        # endpoint is reachable without authentication.
        checks["database"] = {"ok": False, "error": type(error).__name__}

    ready = all(c.get("ok") for c in checks.values())
    return jsonify({"status": "ready" if ready else "not_ready", "checks": checks}), (
        200 if ready else 503
    )


def _optional_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_locale(value) -> str:
    """WF-001 rejects any locale outside its allowlist, so clamp rather than
    forward whatever the browser sent."""
    locale = (str(value or "").strip().lower())[:2]
    return locale if locale in {"en", "he"} else "en"


def _resolve_ssl_context():
    """TLS when certificates are configured and present, plain HTTP otherwise.

    The startup used to hardcode ``ssl_context=("cert.pem", "key.pem")``, which
    crashed on any machine without those files — including a clean checkout.
    Local development runs over HTTP; the VPS terminates TLS at the reverse
    proxy (DEP-002) or supplies real certificate paths through the environment.
    """
    cert = os.getenv("FLASK_TLS_CERT", "cert.pem").strip()
    key = os.getenv("FLASK_TLS_KEY", "key.pem").strip()
    if cert and key and os.path.isfile(cert) and os.path.isfile(key):
        return (cert, key)
    return None


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    ssl_context = _resolve_ssl_context()
    scheme = "https" if ssl_context else "http"
    print(f" * Melody starting on {scheme}://localhost:{port}")
    if ssl_context is None:
        print(" * TLS certificates not found — serving plain HTTP (local development).")
        print("   Set FLASK_TLS_CERT / FLASK_TLS_KEY to enable HTTPS.")
    print(f" * n8n orchestrator: {'enabled' if USE_N8N_ORCHESTRATOR else 'disabled'}")
    app.run(host=host, port=port, ssl_context=ssl_context)
