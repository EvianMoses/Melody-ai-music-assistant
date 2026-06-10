import json
import os

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


def build_response(event, body, status_code=200):
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "apiPath": event.get("apiPath"),
            "httpMethod": event.get("httpMethod"),
            "httpStatusCode": status_code,
            "responseBody": {
                "application/json": {
                    "body": body,
                }
            },
        },
    }


def get_parameter(event, name):
    for parameter in event.get("parameters", []) or []:
        if parameter.get("name") == name:
            return parameter.get("value")
    return None


def get_spotify_client(event):
    user_token = event.get("sessionAttributes", {}).get("spotify_token")
    session_state = event.get("sessionState", {}) or {}
    nested_session_attributes = session_state.get("sessionAttributes", {}) or {}
    print(
        "[DEBUG - LAMBDA SESSION] Spotify client selection state:",
        {
            "apiPath": event.get("apiPath"),
            "httpMethod": event.get("httpMethod"),
            "event_keys": list(event.keys()),
            "top_level_session_attribute_keys": list((event.get("sessionAttributes") or {}).keys()),
            "nested_session_attribute_keys": list(nested_session_attributes.keys()),
            "has_top_level_spotify_token": bool(user_token),
            "top_level_spotify_token_length": len(user_token) if user_token else 0,
            "has_nested_spotify_token": bool(nested_session_attributes.get("spotify_token")),
            "nested_spotify_token_length": len(nested_session_attributes.get("spotify_token", "")),
        },
    )
    if user_token:
        print(
            "[DEBUG - LAMBDA SESSION] Using user Spotify token from Bedrock sessionAttributes:",
            {
                "apiPath": event.get("apiPath"),
                "token_length": len(user_token),
            },
        )
        return spotipy.Spotify(auth=user_token), user_token

    print(
        "[DEBUG - LAMBDA SESSION] No user Spotify token found; using SpotifyClientCredentials fallback:",
        {
            "apiPath": event.get("apiPath"),
            "has_client_id_env": bool(os.environ.get("SPOTIPY_CLIENT_ID")),
            "has_client_secret_env": bool(os.environ.get("SPOTIPY_CLIENT_SECRET")),
        },
    )
    auth_manager = SpotifyClientCredentials(
        client_id=os.environ["SPOTIPY_CLIENT_ID"],
        client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
    )
    return spotipy.Spotify(auth_manager=auth_manager), None


def get_user_taste(sp):
    top_artists = sp.current_user_top_artists(limit=5)
    top_tracks = sp.current_user_top_tracks(limit=5)

    artist_parts = []
    for artist in top_artists.get("items", []):
        name = artist.get("name", "Unknown artist")
        genres = artist.get("genres", [])
        genre_text = ", ".join(genres) if genres else "no listed genres"
        artist_parts.append(f"{name} ({genre_text})")

    track_parts = []
    for track in top_tracks.get("items", []):
        track_name = track.get("name", "Unknown track")
        artists = ", ".join(
            artist.get("name", "Unknown artist")
            for artist in track.get("artists", [])
        )
        track_parts.append(f"{track_name} by {artists}")

    artists_text = "; ".join(artist_parts) if artist_parts else "No top artists found"
    tracks_text = "; ".join(track_parts) if track_parts else "No top tracks found"

    return (
        f"The user's top artists are: {artists_text}. "
        f"The user's top tracks are: {tracks_text}."
    )


def search_track(sp, event):
    query = get_parameter(event, "search_query")
    if not query:
        return json.dumps({"error": "Missing required search_query parameter"})

    results = sp.search(q=query, type="track", limit=1)
    tracks = results.get("tracks", {}).get("items", [])

    if not tracks:
        return json.dumps({"error": f"No track found for query: {query}"})

    track = tracks[0]
    artist = track.get("artists", [{}])[0].get("name")

    return json.dumps(
        {
            "track_name": track.get("name"),
            "artist": artist,
            "track_id": track.get("id"),
            "preview_url": track.get("preview_url"),
        }
    )


def search_playlist(sp, event):
    query = get_parameter(event, "search_query")
    if not query:
        return json.dumps({"error": "Missing required search_query parameter"})

    results = sp.search(q=query, type="playlist", limit=1)
    playlist_items = (results.get("playlists") or {}).get("items") or []

    if not playlist_items:
        return json.dumps({"error": f"No playlist found for query: {query}"})

    playlist = playlist_items[0] or {}
    playlist_id = playlist.get("id")
    if not playlist_id:
        return json.dumps({"error": f"No playlist ID found for query: {query}"})

    owner = playlist.get("owner") or {}

    return json.dumps(
        {
            "playlist_name": playlist.get("name"),
            "owner": owner.get("display_name"),
            "playlist_id": playlist_id,
        }
    )


def search_album(sp, event):
    query = get_parameter(event, "search_query")
    if not query:
        return json.dumps({"error": "Missing required search_query parameter"})

    results = sp.search(q=query, type="album", limit=1)
    albums = results.get("albums", {}).get("items", [])

    if not albums:
        return json.dumps({"error": f"No album found for query: {query}"})

    album = albums[0]
    artist = album.get("artists", [{}])[0].get("name")

    return json.dumps(
        {
            "album_name": album.get("name"),
            "artist": artist,
            "album_id": album.get("id"),
        }
    )


def search_artist(sp, event):
    query = get_parameter(event, "search_query")
    if not query:
        return json.dumps({"error": "Missing required search_query parameter"})

    results = sp.search(q=query, type="artist", limit=1)
    artists = results.get("artists", {}).get("items", [])

    if not artists:
        return json.dumps({"error": f"No artist found for query: {query}"})

    artist = artists[0]

    return json.dumps(
        {
            "artist_name": artist.get("name"),
            "artist_id": artist.get("id"),
        }
    )


def lambda_handler(event, context):
    print(
        "[DEBUG - LAMBDA SESSION] Lambda handler received event:",
        {
            "apiPath": event.get("apiPath"),
            "httpMethod": event.get("httpMethod"),
            "actionGroup": event.get("actionGroup"),
            "event_keys": list(event.keys()),
            "parameters": event.get("parameters", []),
            "has_top_level_sessionAttributes": bool(event.get("sessionAttributes")),
            "has_sessionState": bool(event.get("sessionState")),
        },
    )
    sp, user_token = get_spotify_client(event)

    api_path = event.get("apiPath")
    http_method = event.get("httpMethod")
    print(
        "[DEBUG - LAMBDA SESSION] Route dispatch state:",
        {
            "apiPath": api_path,
            "httpMethod": http_method,
            "is_authenticated_user_flow": bool(user_token),
        },
    )

    try:
        if api_path == "/get_user_taste" and http_method == "GET":
            if not user_token:
                result = "Error: Guest users have no personal taste profile."
            else:
                result = get_user_taste(sp)
        elif api_path == "/search_track" and http_method == "GET":
            result = search_track(sp, event)
        elif api_path == "/search_playlist" and http_method == "GET":
            result = search_playlist(sp, event)
        elif api_path == "/search_album" and http_method == "GET":
            result = search_album(sp, event)
        elif api_path == "/search_artist" and http_method == "GET":
            result = search_artist(sp, event)
        else:
            result = f"Unsupported route: {http_method} {api_path}"
    except Exception as error:
        result = f"Spotify action failed: {error}"

    return build_response(event, result)
