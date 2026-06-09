import json

import requests


def get_parameter(event, name):
    for parameter in event.get("parameters", []) or []:
        if parameter.get("name") == name:
            return parameter.get("value")
    return None


def build_response(event, body):
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "apiPath": event.get("apiPath"),
            "httpMethod": event.get("httpMethod"),
            "httpStatusCode": 200,
            "responseBody": {
                "application/json": {
                    "body": body,
                }
            },
        },
    }


def get_artist_info(event):
    artist_name = get_parameter(event, "artist_name")
    if not artist_name:
        return "No artist_name parameter provided."

    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts",
        "exintro": 1,
        "explaintext": 1,
        "titles": artist_name,
        "format": "json",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        first_page = next(iter(pages.values()), {})
        return first_page.get("extract") or "No Wikipedia info found for this artist."
    except (requests.RequestException, ValueError, StopIteration):
        return "No Wikipedia info found for this artist."


def get_global_charts(event):
    url = "https://itunes.apple.com/us/rss/topsongs/limit=10/json"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        entries = data.get("feed", {}).get("entry", [])

        if not entries:
            return "Global charts data is currently unavailable."

        chart_lines = []
        for index, entry in enumerate(entries[:10], start=1):
            title = entry.get("title", {}).get("label", "Unknown")
            chart_lines.append(f"{index}. {title}")

        return (
            "Global Top 10 Trending Songs right now: "
            + ", ".join(chart_lines)
            + "."
        )
    except (requests.RequestException, ValueError, TypeError):
        return "Global charts data is currently unavailable."


def lambda_handler(event, context):
    api_path = event.get("apiPath")

    if api_path == "/get_artist_info":
        result = get_artist_info(event)
    elif api_path == "/get_global_charts":
        result = get_global_charts(event)
    else:
        result = f"Unsupported apiPath: {api_path}"

    return build_response(event, result)
