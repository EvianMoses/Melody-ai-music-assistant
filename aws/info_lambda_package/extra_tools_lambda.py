import os

import requests

LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"


def get_parameter(event, name):
    for parameter in event.get("parameters", []) or []:
        if parameter.get("name") == name:
            return parameter.get("value")
    return None


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


def format_artist_info(data):
    artist = data.get("artist", {})
    name = artist.get("name", "Unknown artist")

    bio = artist.get("bio", {}).get("summary", "").strip()
    if not bio:
        bio = "No biography available."

    tags = [
        tag.get("name")
        for tag in artist.get("tags", {}).get("tag", [])
        if tag.get("name")
    ][:3]
    tags_text = ", ".join(tags) if tags else "None listed"

    similar = [
        similar_artist.get("name")
        for similar_artist in artist.get("similar", {}).get("artist", [])
        if similar_artist.get("name")
    ][:3]
    similar_text = ", ".join(similar) if similar else "None listed"

    return (
        f"Artist: {name}\n"
        f"Bio: {bio}\n"
        f"Top tags: {tags_text}\n"
        f"Similar artists: {similar_text}"
    )


def get_artist_info(event):
    artist_name = get_parameter(event, "artist_name")
    if not artist_name:
        return "No artist_name parameter provided."

    api_key = os.environ.get("LASTFM_API_KEY")
    if not api_key:
        return "Error: LASTFM_API_KEY is not configured."

    params = {
        "method": "artist.getinfo",
        "artist": artist_name,
        "api_key": api_key,
        "format": "json",
    }

    try:
        response = requests.get(LASTFM_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            message = data.get("message", "Unknown Last.fm error")
            return f"Error: Could not find info for '{artist_name}'. {message}"

        if not data.get("artist"):
            return f"Error: No artist information found for '{artist_name}'."

        return format_artist_info(data)
    except requests.RequestException as error:
        return f"Error: Failed to reach Last.fm API for '{artist_name}'. {error}"
    except ValueError as error:
        return f"Error: Could not parse Last.fm response for '{artist_name}'. {error}"


def lambda_handler(event, context):
    api_path = event.get("apiPath")

    try:
        if api_path == "/get-artist-info":
            result = get_artist_info(event)
        else:
            result = f"Unsupported apiPath: {api_path}"
    except Exception as error:
        result = f"Action failed: {error}"

    return build_response(event, result)
