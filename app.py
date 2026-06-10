import os
import random
import time
import uuid
from datetime import timedelta

from dotenv import load_dotenv
load_dotenv()

import spotipy
from spotipy.cache_handler import FlaskSessionCacheHandler
from spotipy.oauth2 import SpotifyOAuth
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, render_template, request, jsonify, session, redirect, url_for


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(32)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

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
        print(
            "[DEBUG - BACKEND SESSION] Created new Flask session_id:",
            session["session_id"],
            "path:",
            request.path,
            "has_spotify_token_info:",
            has_spotify_token_info(),
        )
    else:
        print(
            "[DEBUG - BACKEND SESSION] Existing Flask session_id:",
            session.get("session_id"),
            "path:",
            request.path,
            "has_spotify_token_info:",
            has_spotify_token_info(),
        )


def get_spotify_cache_handler():
    return FlaskSessionCacheHandler(session)


def get_cached_spotify_token_info():
    cache_handler = get_spotify_cache_handler()
    token_info = cache_handler.get_cached_token()
    legacy_token_info = session.get(LEGACY_SPOTIFY_TOKEN_SESSION_KEY)

    if not token_info and legacy_token_info:
        print(
            "[DEBUG - BACKEND SESSION] Migrating legacy spotify_token_info into FlaskSessionCacheHandler:",
            {
                "session_id": session.get("session_id"),
                "legacy_token_info_keys": list(legacy_token_info.keys()),
            },
        )
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
    print(
        "[DEBUG - BACKEND SESSION] get_valid_spotify_token called:",
        {
            "session_id": session.get("session_id"),
            "has_spotify_token_info": bool(token_info),
            "token_info_keys": list(token_info.keys()) if token_info else [],
            "cache_handler": "FlaskSessionCacheHandler",
            "has_legacy_spotify_token_info": bool(session.get(LEGACY_SPOTIFY_TOKEN_SESSION_KEY)),
        },
    )
    if not token_info:
        print("[DEBUG - BACKEND SESSION] No spotify_token_info in Flask session.")
        return None

    expires_at = token_info.get("expires_at", 0)
    is_expired_or_stale = expires_at <= int(time.time()) + 60
    print(
        "[DEBUG - BACKEND SESSION] Spotify token freshness:",
        {
            "session_id": session.get("session_id"),
            "expires_at": expires_at,
            "is_expired_or_stale": is_expired_or_stale,
            "has_refresh_token": bool(token_info.get("refresh_token")),
            "has_access_token": bool(token_info.get("access_token")),
        },
    )

    if is_expired_or_stale:
        refresh_token = token_info.get("refresh_token")
        if not refresh_token:
            clear_spotify_token_info()
            print(
                "[DEBUG - BACKEND SESSION] Removed spotify_token_info because refresh_token is missing:",
                {"session_id": session.get("session_id")},
            )
            return None

        spotify_oauth = get_spotify_oauth()
        previous_refresh_token = refresh_token
        print(
            "[DEBUG - BACKEND SESSION] Refreshing Spotify access token:",
            {"session_id": session.get("session_id")},
        )
        token_info = spotify_oauth.refresh_access_token(refresh_token)
        if "refresh_token" not in token_info:
            token_info["refresh_token"] = previous_refresh_token
        session.modified = True
        print(
            "[DEBUG - BACKEND SESSION] Refreshed Spotify token stored in Flask session:",
            {
                "session_id": session.get("session_id"),
                "cache_handler": "FlaskSessionCacheHandler",
                "has_access_token": bool(token_info.get("access_token")),
                "has_refresh_token": bool(token_info.get("refresh_token")),
            },
        )

    access_token = token_info.get("access_token")
    print(
        "[DEBUG - BACKEND SESSION] Returning Spotify access token state:",
        {
            "session_id": session.get("session_id"),
            "has_access_token": bool(access_token),
            "access_token_length": len(access_token) if access_token else 0,
        },
    )
    return access_token


def query_bedrock(question, chat_id=None):
    client = boto3.client("bedrock-agent-runtime", region_name=AWS_REGION)
    spotify_access_token = get_valid_spotify_token()
    flask_session_id = session.get("session_id")
    if not flask_session_id:
        flask_session_id = str(uuid.uuid4())
        session["session_id"] = flask_session_id
        session.permanent = True
        session.modified = True
        print(
            "[DEBUG - BACKEND SESSION] query_bedrock created missing Flask session_id:",
            flask_session_id,
        )

    session_attributes = {}
    if spotify_access_token:
        session_attributes["spotify_token"] = spotify_access_token

    bedrock_session_id = flask_session_id
    bedrock_memory_id = flask_session_id
    print(
        "[DEBUG - BACKEND SESSION] Preparing InvokeAgent request:",
        {
            "flask_session_id": flask_session_id,
            "incoming_chat_id": chat_id,
            "incoming_matches_flask_session": chat_id == flask_session_id,
            "bedrock_session_id": bedrock_session_id,
            "bedrock_memory_id": bedrock_memory_id,
            "has_spotify_token_info": has_spotify_token_info(),
            "has_valid_spotify_access_token": bool(spotify_access_token),
            "question_length": len(question or ""),
        },
    )
    print(
        "[DEBUG - BACKEND SESSION] InvokeAgent SessionAttributes being sent:",
        session_attributes,
    )

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
        print(
            "[DEBUG - BACKEND SESSION] Spotify callback returned error:",
            {
                "session_id": session.get("session_id"),
                "error": request.args.get("error"),
            },
        )
        return redirect(url_for("index"))

    code = request.args.get("code")
    print(
        "[DEBUG - BACKEND SESSION] Spotify callback received:",
        {
            "session_id": session.get("session_id"),
            "has_code": bool(code),
            "has_spotify_token_info_before": has_spotify_token_info(),
            "cache_handler": "FlaskSessionCacheHandler",
        },
    )
    if code:
        spotify_oauth = get_spotify_oauth()
        token_info = spotify_oauth.get_access_token(code, as_dict=True, check_cache=False)
        session.pop(LEGACY_SPOTIFY_TOKEN_SESSION_KEY, None)
        session.modified = True
        print(
            "[DEBUG - BACKEND SESSION] Spotify token_info stored after callback:",
            {
                "session_id": session.get("session_id"),
                "cache_handler": "FlaskSessionCacheHandler",
                "token_info_keys": list(token_info.keys()),
                "has_access_token": bool(token_info.get("access_token")),
                "has_refresh_token": bool(token_info.get("refresh_token")),
                "expires_at": token_info.get("expires_at"),
            },
        )

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    print(
        "[DEBUG - BACKEND SESSION] Logout clearing Flask session:",
        {
            "session_id": session.get("session_id"),
            "had_spotify_token_info": has_spotify_token_info(),
        },
    )
    session.clear()
    return redirect(url_for("index"))


@app.route("/api/auth_status")
def auth_status():
    print(
        "[DEBUG - BACKEND SESSION] /api/auth_status request:",
        {
            "session_id": session.get("session_id"),
            "has_spotify_token_info": has_spotify_token_info(),
            "cache_handler": "FlaskSessionCacheHandler",
        },
    )
    access_token = get_valid_spotify_token()
    if not access_token:
        print(
            "[DEBUG - BACKEND SESSION] /api/auth_status returning guest:",
            {"session_id": session.get("session_id")},
        )
        return jsonify({"logged_in": False, "session_id": session.get("session_id")})

    try:
        sp = spotipy.Spotify(auth=access_token)
        user = sp.current_user()
        print(
            "[DEBUG - BACKEND SESSION] /api/auth_status Spotify current_user success:",
            {
                "session_id": session.get("session_id"),
                "spotify_user_id": user.get("id"),
                "display_name": user.get("display_name"),
            },
        )
    except Exception as error:
        clear_spotify_token_info()
        print(
            "[DEBUG - BACKEND SESSION] /api/auth_status current_user failed; cleared spotify_token_info:",
            {
                "session_id": session.get("session_id"),
                "error": str(error),
            },
        )
        return jsonify({"logged_in": False, "session_id": session.get("session_id")})

    print(
        "[DEBUG - BACKEND SESSION] /api/auth_status returning logged_in:",
        {
            "session_id": session.get("session_id"),
            "spotify_user_id": user.get("id"),
            "has_profile_image": bool(user.get("images")),
        },
    )
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
    print(
        "[DEBUG - BACKEND SESSION] /ask request state:",
        {
            "flask_session_id": session.get("session_id"),
            "incoming_chat_id": chat_id,
            "incoming_matches_flask_session": chat_id == session.get("session_id"),
            "has_spotify_token_info": has_spotify_token_info(),
            "question_length": len(question or ""),
        },
    )

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
    print(
        "[DEBUG - BACKEND SESSION] /chat request state:",
        {
            "flask_session_id": session.get("session_id"),
            "incoming_chat_id": chat_id,
            "incoming_matches_flask_session": chat_id == session.get("session_id"),
            "has_spotify_token_info": has_spotify_token_info(),
            "request_json_keys": list(data.keys()),
            "question_length": len(question or ""),
        },
    )

    if not question:
        return jsonify({"error": "Question is required."}), 400

    try:
        answer = query_bedrock(question, chat_id=chat_id)
    except (BotoCoreError, ClientError) as error:
        return jsonify({"error": f"Bedrock request failed: {error}"}), 500

    return jsonify({"response": answer, "answer": answer})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, ssl_context=("cert.pem", "key.pem"))
