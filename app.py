import os
import random
import time
import uuid

from dotenv import load_dotenv
load_dotenv()

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, render_template, request, jsonify, session, redirect, url_for


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(32)

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
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        session.modified = True


def get_spotify_oauth():
    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SPOTIFY_SCOPE,
        cache_handler=None,
        show_dialog=True,
    )


def get_valid_spotify_token():
    token_info = session.get("spotify_token_info")
    if not token_info:
        return None

    expires_at = token_info.get("expires_at", 0)
    is_expired_or_stale = expires_at <= int(time.time()) + 60

    if is_expired_or_stale:
        refresh_token = token_info.get("refresh_token")
        if not refresh_token:
            session.pop("spotify_token_info", None)
            return None

        spotify_oauth = get_spotify_oauth()
        previous_refresh_token = refresh_token
        token_info = spotify_oauth.refresh_access_token(refresh_token)
        if "refresh_token" not in token_info:
            token_info["refresh_token"] = previous_refresh_token
        session["spotify_token_info"] = token_info
        session.modified = True

    return token_info.get("access_token")


def query_bedrock(question, chat_id=None):
    client = boto3.client("bedrock-agent-runtime", region_name=AWS_REGION)
    spotify_access_token = get_valid_spotify_token()

    session_attributes = {}
    if spotify_access_token:
        session_attributes["spotify_token"] = spotify_access_token

    response = client.invoke_agent(
        agentId=BEDROCK_AGENT_ID,
        agentAliasId=BEDROCK_AGENT_ALIAS_ID,
        sessionId=chat_id if chat_id else str(uuid.uuid4()),
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
    chat_id = (data.get("chat_id") or "").strip()
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
        token_info = spotify_oauth.get_access_token(code, as_dict=True)
        session["spotify_token_info"] = token_info
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
        session.pop("spotify_token_info", None)
        session.modified = True
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
    chat_id = data.get("chat_id")

    if not question:
        return jsonify({"error": "Question is required."}), 400

    try:
        answer = query_bedrock(question, chat_id=chat_id)
    except (BotoCoreError, ClientError) as error:
        return jsonify({"error": f"Bedrock request failed: {error}"}), 500

    return jsonify({"response": answer, "answer": answer})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, ssl_context=("cert.pem", "key.pem"))
