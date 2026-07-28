# Project Structure

Generated snapshot of `Melody-ai-music-assistant/` for architecture context.

Excluded from this tree: `.git`, `__pycache__`, `venv`, `env`, `.env`, `.pytest_cache`, `node_modules`, `.cursor`, `.venv`.

```
Melody-ai-music-assistant/
├── audio-service/
│   ├── .gitkeep
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   └── test_smoke.py
├── aws/
│   ├── bedrock_schemas/
│   │   ├── Extra_music_Tools.json
│   │   └── SpotifyTools.json
│   ├── info_lambda_package/
│   │   ├── bin/
│   │   │   ├── idna.exe
│   │   │   └── normalizer.exe
│   │   ├── certifi/
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py
│   │   │   ├── cacert.pem
│   │   │   ├── core.py
│   │   │   └── py.typed
│   │   ├── certifi-2026.5.20.dist-info/
│   │   │   ├── licenses/
│   │   │   │   └── LICENSE
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   ├── top_level.txt
│   │   │   └── WHEEL
│   │   ├── charset_normalizer/
│   │   │   ├── cli/
│   │   │   │   ├── __init__.py
│   │   │   │   └── __main__.py
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py
│   │   │   ├── api.py
│   │   │   ├── cd.cp314-win_amd64.pyd
│   │   │   ├── cd.py
│   │   │   ├── constant.py
│   │   │   ├── legacy.py
│   │   │   ├── md.cp314-win_amd64.pyd
│   │   │   ├── md.py
│   │   │   ├── models.py
│   │   │   ├── py.typed
│   │   │   ├── utils.py
│   │   │   └── version.py
│   │   ├── charset_normalizer-3.4.7.dist-info/
│   │   │   ├── licenses/
│   │   │   │   └── LICENSE
│   │   │   ├── entry_points.txt
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   ├── top_level.txt
│   │   │   └── WHEEL
│   │   ├── idna/
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py
│   │   │   ├── cli.py
│   │   │   ├── codec.py
│   │   │   ├── compat.py
│   │   │   ├── core.py
│   │   │   ├── idnadata.py
│   │   │   ├── intranges.py
│   │   │   ├── package_data.py
│   │   │   ├── py.typed
│   │   │   └── uts46data.py
│   │   ├── idna-3.18.dist-info/
│   │   │   ├── licenses/
│   │   │   │   └── LICENSE.md
│   │   │   ├── entry_points.txt
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   └── WHEEL
│   │   ├── requests/
│   │   │   ├── __init__.py
│   │   │   ├── __version__.py
│   │   │   ├── _internal_utils.py
│   │   │   ├── _types.py
│   │   │   ├── adapters.py
│   │   │   ├── api.py
│   │   │   ├── auth.py
│   │   │   ├── certs.py
│   │   │   ├── compat.py
│   │   │   ├── cookies.py
│   │   │   ├── exceptions.py
│   │   │   ├── help.py
│   │   │   ├── hooks.py
│   │   │   ├── models.py
│   │   │   ├── packages.py
│   │   │   ├── py.typed
│   │   │   ├── sessions.py
│   │   │   ├── status_codes.py
│   │   │   ├── structures.py
│   │   │   └── utils.py
│   │   ├── requests-2.34.2.dist-info/
│   │   │   ├── licenses/
│   │   │   │   ├── LICENSE
│   │   │   │   └── NOTICE
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   ├── REQUESTED
│   │   │   ├── top_level.txt
│   │   │   └── WHEEL
│   │   ├── urllib3/
│   │   │   ├── contrib/
│   │   │   │   ├── emscripten/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── connection.py
│   │   │   │   │   ├── emscripten_fetch_worker.js
│   │   │   │   │   ├── fetch.py
│   │   │   │   │   ├── request.py
│   │   │   │   │   └── response.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── pyopenssl.py
│   │   │   │   └── socks.py
│   │   │   ├── http2/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── connection.py
│   │   │   │   └── probe.py
│   │   │   ├── util/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── connection.py
│   │   │   │   ├── proxy.py
│   │   │   │   ├── request.py
│   │   │   │   ├── response.py
│   │   │   │   ├── retry.py
│   │   │   │   ├── ssl_.py
│   │   │   │   ├── ssl_match_hostname.py
│   │   │   │   ├── ssltransport.py
│   │   │   │   ├── timeout.py
│   │   │   │   ├── url.py
│   │   │   │   ├── util.py
│   │   │   │   └── wait.py
│   │   │   ├── __init__.py
│   │   │   ├── _base_connection.py
│   │   │   ├── _collections.py
│   │   │   ├── _request_methods.py
│   │   │   ├── _version.py
│   │   │   ├── connection.py
│   │   │   ├── connectionpool.py
│   │   │   ├── exceptions.py
│   │   │   ├── fields.py
│   │   │   ├── filepost.py
│   │   │   ├── poolmanager.py
│   │   │   ├── py.typed
│   │   │   └── response.py
│   │   ├── urllib3-2.7.0.dist-info/
│   │   │   ├── licenses/
│   │   │   │   └── LICENSE.txt
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   └── WHEEL
│   │   ├── 81d243bd2c585b0f4821__mypyc.cp314-win_amd64.pyd
│   │   └── extra_tools_lambda.py
│   ├── lambda_spotify_package/
│   │   ├── bin/
│   │   │   ├── idna.exe
│   │   │   └── normalizer.exe
│   │   ├── certifi/
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py
│   │   │   ├── cacert.pem
│   │   │   ├── core.py
│   │   │   └── py.typed
│   │   ├── certifi-2026.5.20.dist-info/
│   │   │   ├── licenses/
│   │   │   │   └── LICENSE
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   ├── top_level.txt
│   │   │   └── WHEEL
│   │   ├── charset_normalizer/
│   │   │   ├── cli/
│   │   │   │   ├── __init__.py
│   │   │   │   └── __main__.py
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py
│   │   │   ├── api.py
│   │   │   ├── cd.cp314-win_amd64.pyd
│   │   │   ├── cd.py
│   │   │   ├── constant.py
│   │   │   ├── legacy.py
│   │   │   ├── md.cp314-win_amd64.pyd
│   │   │   ├── md.py
│   │   │   ├── models.py
│   │   │   ├── py.typed
│   │   │   ├── utils.py
│   │   │   └── version.py
│   │   ├── charset_normalizer-3.4.7.dist-info/
│   │   │   ├── licenses/
│   │   │   │   └── LICENSE
│   │   │   ├── entry_points.txt
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   ├── top_level.txt
│   │   │   └── WHEEL
│   │   ├── idna/
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py
│   │   │   ├── cli.py
│   │   │   ├── codec.py
│   │   │   ├── compat.py
│   │   │   ├── core.py
│   │   │   ├── idnadata.py
│   │   │   ├── intranges.py
│   │   │   ├── package_data.py
│   │   │   ├── py.typed
│   │   │   └── uts46data.py
│   │   ├── idna-3.18.dist-info/
│   │   │   ├── licenses/
│   │   │   │   └── LICENSE.md
│   │   │   ├── entry_points.txt
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   └── WHEEL
│   │   ├── redis/
│   │   │   ├── _parsers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── commands.py
│   │   │   │   ├── encoders.py
│   │   │   │   ├── helpers.py
│   │   │   │   ├── hiredis.py
│   │   │   │   ├── resp2.py
│   │   │   │   ├── resp3.py
│   │   │   │   ├── response_callbacks.py
│   │   │   │   └── socket.py
│   │   │   ├── asyncio/
│   │   │   │   ├── http/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── http_client.py
│   │   │   │   ├── multidb/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── client.py
│   │   │   │   │   ├── command_executor.py
│   │   │   │   │   ├── config.py
│   │   │   │   │   ├── database.py
│   │   │   │   │   ├── event.py
│   │   │   │   │   ├── failover.py
│   │   │   │   │   ├── failure_detector.py
│   │   │   │   │   └── healthcheck.py
│   │   │   │   ├── observability/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── recorder.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── client.py
│   │   │   │   ├── cluster.py
│   │   │   │   ├── connection.py
│   │   │   │   ├── keyspace_notifications.py
│   │   │   │   ├── lock.py
│   │   │   │   ├── retry.py
│   │   │   │   ├── sentinel.py
│   │   │   │   └── utils.py
│   │   │   ├── auth/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── err.py
│   │   │   │   ├── idp.py
│   │   │   │   ├── token.py
│   │   │   │   └── token_manager.py
│   │   │   ├── commands/
│   │   │   │   ├── bf/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── commands.py
│   │   │   │   │   └── info.py
│   │   │   │   ├── json/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── _util.py
│   │   │   │   │   ├── commands.py
│   │   │   │   │   ├── decoders.py
│   │   │   │   │   └── path.py
│   │   │   │   ├── search/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── _util.py
│   │   │   │   │   ├── aggregation.py
│   │   │   │   │   ├── commands.py
│   │   │   │   │   ├── dialect.py
│   │   │   │   │   ├── document.py
│   │   │   │   │   ├── field.py
│   │   │   │   │   ├── hybrid_query.py
│   │   │   │   │   ├── hybrid_result.py
│   │   │   │   │   ├── index_definition.py
│   │   │   │   │   ├── profile_information.py
│   │   │   │   │   ├── query.py
│   │   │   │   │   ├── querystring.py
│   │   │   │   │   ├── reducers.py
│   │   │   │   │   ├── result.py
│   │   │   │   │   └── suggestion.py
│   │   │   │   ├── timeseries/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── commands.py
│   │   │   │   │   ├── info.py
│   │   │   │   │   └── utils.py
│   │   │   │   ├── vectorset/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── commands.py
│   │   │   │   │   └── utils.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── cluster.py
│   │   │   │   ├── core.py
│   │   │   │   ├── helpers.py
│   │   │   │   ├── policies.py
│   │   │   │   ├── redismodules.py
│   │   │   │   └── sentinel.py
│   │   │   ├── http/
│   │   │   │   ├── __init__.py
│   │   │   │   └── http_client.py
│   │   │   ├── multidb/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── circuit.py
│   │   │   │   ├── client.py
│   │   │   │   ├── command_executor.py
│   │   │   │   ├── config.py
│   │   │   │   ├── database.py
│   │   │   │   ├── event.py
│   │   │   │   ├── exception.py
│   │   │   │   ├── failover.py
│   │   │   │   └── failure_detector.py
│   │   │   ├── observability/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── attributes.py
│   │   │   │   ├── config.py
│   │   │   │   ├── metrics.py
│   │   │   │   ├── providers.py
│   │   │   │   ├── recorder.py
│   │   │   │   └── registry.py
│   │   │   ├── __init__.py
│   │   │   ├── _defaults.py
│   │   │   ├── background.py
│   │   │   ├── backoff.py
│   │   │   ├── cache.py
│   │   │   ├── client.py
│   │   │   ├── cluster.py
│   │   │   ├── connection.py
│   │   │   ├── crc.py
│   │   │   ├── credentials.py
│   │   │   ├── data_structure.py
│   │   │   ├── driver_info.py
│   │   │   ├── event.py
│   │   │   ├── exceptions.py
│   │   │   ├── keyspace_notifications.py
│   │   │   ├── lock.py
│   │   │   ├── maint_notifications.py
│   │   │   ├── ocsp.py
│   │   │   ├── py.typed
│   │   │   ├── retry.py
│   │   │   ├── sentinel.py
│   │   │   ├── typing.py
│   │   │   └── utils.py
│   │   ├── redis-8.0.0.dist-info/
│   │   │   ├── licenses/
│   │   │   │   └── LICENSE
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   └── WHEEL
│   │   ├── requests/
│   │   │   ├── __init__.py
│   │   │   ├── __version__.py
│   │   │   ├── _internal_utils.py
│   │   │   ├── _types.py
│   │   │   ├── adapters.py
│   │   │   ├── api.py
│   │   │   ├── auth.py
│   │   │   ├── certs.py
│   │   │   ├── compat.py
│   │   │   ├── cookies.py
│   │   │   ├── exceptions.py
│   │   │   ├── help.py
│   │   │   ├── hooks.py
│   │   │   ├── models.py
│   │   │   ├── packages.py
│   │   │   ├── py.typed
│   │   │   ├── sessions.py
│   │   │   ├── status_codes.py
│   │   │   ├── structures.py
│   │   │   └── utils.py
│   │   ├── requests-2.34.2.dist-info/
│   │   │   ├── licenses/
│   │   │   │   ├── LICENSE
│   │   │   │   └── NOTICE
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   ├── REQUESTED
│   │   │   ├── top_level.txt
│   │   │   └── WHEEL
│   │   ├── spotipy/
│   │   │   ├── __init__.py
│   │   │   ├── cache_handler.py
│   │   │   ├── client.py
│   │   │   ├── exceptions.py
│   │   │   ├── oauth2.py
│   │   │   └── util.py
│   │   ├── spotipy-2.26.0.dist-info/
│   │   │   ├── licenses/
│   │   │   │   └── LICENSE.md
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   ├── REQUESTED
│   │   │   ├── top_level.txt
│   │   │   └── WHEEL
│   │   ├── urllib3/
│   │   │   ├── contrib/
│   │   │   │   ├── emscripten/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── connection.py
│   │   │   │   │   ├── emscripten_fetch_worker.js
│   │   │   │   │   ├── fetch.py
│   │   │   │   │   ├── request.py
│   │   │   │   │   └── response.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── pyopenssl.py
│   │   │   │   └── socks.py
│   │   │   ├── http2/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── connection.py
│   │   │   │   └── probe.py
│   │   │   ├── util/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── connection.py
│   │   │   │   ├── proxy.py
│   │   │   │   ├── request.py
│   │   │   │   ├── response.py
│   │   │   │   ├── retry.py
│   │   │   │   ├── ssl_.py
│   │   │   │   ├── ssl_match_hostname.py
│   │   │   │   ├── ssltransport.py
│   │   │   │   ├── timeout.py
│   │   │   │   ├── url.py
│   │   │   │   ├── util.py
│   │   │   │   └── wait.py
│   │   │   ├── __init__.py
│   │   │   ├── _base_connection.py
│   │   │   ├── _collections.py
│   │   │   ├── _request_methods.py
│   │   │   ├── _version.py
│   │   │   ├── connection.py
│   │   │   ├── connectionpool.py
│   │   │   ├── exceptions.py
│   │   │   ├── fields.py
│   │   │   ├── filepost.py
│   │   │   ├── poolmanager.py
│   │   │   ├── py.typed
│   │   │   └── response.py
│   │   ├── urllib3-2.7.0.dist-info/
│   │   │   ├── licenses/
│   │   │   │   └── LICENSE.txt
│   │   │   ├── INSTALLER
│   │   │   ├── METADATA
│   │   │   ├── RECORD
│   │   │   └── WHEEL
│   │   ├── 81d243bd2c585b0f4821__mypyc.cp314-win_amd64.pyd
│   │   └── spotify_lambda.py
│   └── system_prompt.txt
├── contracts/
│   ├── __init__.py
│   ├── ai_recommendation_schema.json
│   ├── db_models.py
│   └── models.py
├── data/
│   ├── 18,393 Pitchfork Reviews/
│   │   └── database.sqlite
│   ├── all_songs_rating_review/
│   │   └── song.csv
│   ├── Contemporary album ratings and reviews/
│   │   ├── Review excerpts for NLP/
│   │   │   ├── test.csv
│   │   │   └── train.csv
│   │   └── album_ratings.csv
│   ├── genres_knowledge/
│   │   ├── BLUE NOTE BLUES.md
│   │   ├── BLUE NOTE GOSPEL & PIONEERS.md
│   │   ├── BLUE NOTE JAZZ.md
│   │   ├── COUNTRY.md
│   │   ├── DOWNTEMPO  AMBIENT.md
│   │   ├── EDM  DANCE BREAKBEAT.md
│   │   ├── EDM  DANCE DRUM 'N' BASS  JUNGLE.md
│   │   ├── EDM  DANCE HARDCORE (TECHNO).md
│   │   ├── EDM  DANCE HOUSE.md
│   │   ├── EDM  DANCE TECHNO.md
│   │   ├── EDM  DANCE TRANCE.md
│   │   ├── HEAVY METAL.md
│   │   ├── INDUSTRIAL & GOTHIC.md
│   │   ├── JAMAICAN MUSIC  REGGAE.md
│   │   ├── POP MUSIC.md
│   │   ├── RAP  HIP-HOP MUSIC.md
│   │   ├── RHYTHM 'N' BLUES (R&B).md
│   │   ├── ROCK, ALTERNATIVE ROCK , INDIE.md
│   │   ├── ROCK, CONTEMPORARY ROCK.md
│   │   ├── ROCK, GOLDEN AGE, CLASSIC ROCK.md
│   │   ├── ROCK, HARDCORE PUNK.md
│   │   ├── ROCK, PUNK ROCK , NEW WAVE.md
│   │   └── ROCK, ROCK 'N' ROLL (R'N'R) (ROCK & ROLL).md
│   ├── processed/
│   │   └── .gitkeep
│   ├── raw/
│   │   ├── genre_knowledge/
│   │   │   └── .gitkeep
│   │   ├── reviews_context/
│   │   │   └── .gitkeep
│   │   ├── track_metadata/
│   │   │   └── .gitkeep
│   │   └── .gitkeep
│   └── cleaned_large_dataset_t.csv
├── docs/
│   └── knowledge_inventory.md
├── f/
│   └── f/
├── guardrails-service/
│   ├── .gitkeep
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   └── test_smoke.py
├── migrations/
│   ├── versions/
│   │   ├── .gitkeep
│   │   ├── 98cd5d4fe8da_initial_core_tables.py
│   │   └── dc82e50ee3c9_add_remaining_tables_and_indexes.py
│   ├── env.py
│   ├── README
│   └── script.py.mako
├── poc/
│   └── test_musicapi.py
├── prep_files/
│   ├── get_master_token.py
│   ├── prepare_mvp_dataset.py
│   └── scrape_musicmap.py
├── provider-gateway/
│   ├── .gitkeep
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   └── test_smoke.py
├── rag-service/
│   ├── .gitkeep
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   └── test_smoke.py
├── recommendation-service/
│   ├── .gitkeep
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   └── test_smoke.py
├── shared_lib/
│   ├── shared_lib/
│   │   ├── __init__.py
│   │   ├── app_factory.py
│   │   ├── errors.py
│   │   ├── health.py
│   │   ├── http.py
│   │   ├── logging_config.py
│   │   └── request_context.py
│   └── pyproject.toml
├── static/
│   └── style.css
├── templates/
│   └── index.html
├── workflows/
│   └── n8n/
│       ├── .gitkeep
│       ├── WF-000 — Common Error Handler.json
│       ├── WF-001 — Main Request Router.json
│       ├── WF-002 — Text Recommendation.json
│       ├── WF-003 — Voice_Audio Recommendation.json
│       ├── WF-004 — Identify Track.json
│       ├── WF-005 — User Feedback Loop.json
│       └── WF-006 — Export Playlist.json
├── .cursorrules
├── .dockerignore
├── .env.example
├── .gitignore
├── alembic.ini
├── app.py
├── docker-compose.yml
├── Dockerfile
├── MELODY_AI_ORDERED_EXECUTION_PLAN.md
├── Melody_Beyond_the_Algorithm_(4).pdf
├── n8n_client.py
├── project_structure.md
├── README.md
└── requirements.txt
```
