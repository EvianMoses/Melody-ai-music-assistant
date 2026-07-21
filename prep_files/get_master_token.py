import os
from pathlib import Path

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)

CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:5000/callback")
SCOPE = (
    "user-read-recently-played user-top-read "
    "playlist-modify-public playlist-modify-private"
)
TOKEN_OUTPUT_PATH = Path(__file__).resolve().parent / ".spotify_refresh_token"

if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit(
        "Missing SPOTIPY_CLIENT_ID or SPOTIPY_CLIENT_SECRET. "
        "Set them in .env before running this script."
    )

print("Starting authentication process...")

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        open_browser=True,
    )
)

user = sp.current_user()
print(f"\nSuccess! Logged in as: {user['display_name']}")

auth_manager = sp.auth_manager
token_info = auth_manager.get_cached_token()
refresh_token = token_info.get("refresh_token")
if not refresh_token:
    raise SystemExit("Authentication succeeded but no refresh token was returned.")

TOKEN_OUTPUT_PATH.write_text(refresh_token, encoding="utf-8")
print("\n" + "=" * 40)
print("Master refresh token saved")
print("=" * 40)
print(f"File: {TOKEN_OUTPUT_PATH}")
print("Copy the token from that file and store it somewhere safe.")
print("The token is not printed here to avoid leaking it into logs.")
