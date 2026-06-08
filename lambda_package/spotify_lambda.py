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


def get_request_property(event, name):
    properties = (
        event.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("properties", {})
    )

    if isinstance(properties, list):
        for prop in properties:
            if prop.get("name") == name:
                return prop.get("value")

    if isinstance(properties, dict):
        value = properties.get(name)
        if isinstance(value, dict):
            return value.get("value")
        return value

    return None


def get_spotify_client(event):
    user_token = event.get("sessionAttributes", {}).get("spotify_token")
    if user_token:
        return spotipy.Spotify(auth=user_token), user_token

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


def save_track(sp, event):
    track_id = get_request_property(event, "track_id")
    if not track_id:
        return "Missing required track_id in request body."

    sp.current_user_saved_tracks_add(tracks=[track_id])
    return f"Track {track_id} was saved successfully to the user's Spotify library."


def lambda_handler(event, context):
    sp, user_token = get_spotify_client(event)

    api_path = event.get("apiPath")
    http_method = event.get("httpMethod")

    try:
        if api_path == "/get_user_taste" and http_method == "GET":
            if not user_token:
                result = "Error: Guest users have no personal taste profile."
            else:
                result = get_user_taste(sp)
        elif api_path == "/search_track" and http_method == "GET":
            result = search_track(sp, event)
        elif api_path == "/save_track" and http_method == "POST":
            if not user_token:
                result = "Error: Guest users cannot save tracks. Tell them to log in."
            else:
                result = save_track(sp, event)
        else:
            result = f"Unsupported route: {http_method} {api_path}"
    except Exception as error:
        result = f"Spotify action failed: {error}"

    return build_response(event, result)
