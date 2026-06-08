Please write an AWS Lambda function named `spotify_lambda.py` designed to be invoked by an Amazon Bedrock Agent.
The Agent uses an OpenAPI schema with 3 API paths:
1. `/get_user_taste` (GET)
2. `/search_track` (GET) - receives a 'search_query' parameter.
3. `/save_track` (POST) - receives 'track_id' in the request body.

The event payload from the Bedrock Agent includes: `actionGroup`, `apiPath`, `httpMethod`, `parameters`, `requestBody`, and `sessionAttributes`.

Logic requirements for the Python code:
- Import `spotipy` and `os`.
- Check `event.get('sessionAttributes', {}).get('spotify_token')`. If it exists, initialize `spotipy.Spotify` with this token.
- If not (guest user), fallback to `os.environ.get('MASTER_SPOTIFY_TOKEN')`.
- For `/get_user_taste`: Call `sp.current_user_top_artists(limit=5)` and `sp.current_user_top_tracks(limit=5)`, extract the names and genres, and return them as a single descriptive string.
- For `/search_track`: Extract the `search_query` from `event.get('parameters', [])` (find the dict where name == 'search_query' and get its 'value'). Call `sp.search(q=query, type='track', limit=1)`. Return a JSON string containing track_name, artist, track_id, and preview_url.
- For `/save_track`: Extract `track_id` from `event.get('requestBody', {}).get('content', {}).get('application/json', {}).get('properties', {})` (parse safely based on Bedrock's property list structure). Call `sp.current_user_saved_tracks_add(tracks=[track_id])`. Return a success message string.
- The Lambda MUST return the response in the exact format required by Bedrock Action Groups:
  {
      "messageVersion": "1.0",
      "response": {
          "actionGroup": event.get('actionGroup'),
          "apiPath": event.get('apiPath'),
          "httpMethod": event.get('httpMethod'),
          "httpStatusCode": 200,
          "responseBody": {
              "application/json": {
                  "body": <YOUR_STRINGIFIED_RESULT_HERE>
              }
          }
      }
  }
Provide only the Python code.