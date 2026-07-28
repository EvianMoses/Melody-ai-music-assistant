# Melody Flask web application (INF-011, DEP-001).
#
# This is the browser-facing container: UI, session cookie, OAuth start/callback,
# the /api/v1 boundary and the audio upload hand-off. It owns no AI logic — it
# posts a RequestEnvelope to n8n and renders what comes back.
#
# Build context is the repo root, matching the five FastAPI services, so
# contracts/ and the templates are in scope:
#   docker compose build web
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# curl is here for the healthcheck only. openssl was dropped with the
# self-signed certificate below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Explicit copies rather than ~~`COPY . .`~~: the root context also holds the
# five services, the ML code and the evaluation harnesses, none of which this
# image runs. Listing what the web app actually needs keeps the image honest
# about its own dependencies — and makes an accidental new one fail the build
# rather than silently ride along.
#
# It also fixes a real defect in the previous version of this file: `COPY . .`
# looks like it copies everything, but .dockerignore excluded templates/ and
# static/, so the image built cleanly and then 500'd on the first page render.
COPY app.py auth_google.py n8n_client.py ./
COPY contracts ./contracts
COPY templates ./templates
COPY static ./static

# SEC-108 — run as an unprivileged user. Done after the copies so the files are
# owned by root and are not writable by the process that serves them.
RUN useradd --create-home --uid 10001 melody
USER melody

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 \
    CMD curl -fsS http://127.0.0.1:5000/health/live || exit 1

# ~~RUN openssl req -x509 ... -out cert.pem -keyout key.pem~~ — REMOVED.
# The image used to bake a self-signed certificate and serve TLS itself. A
# self-signed certificate fails validation in every browser, so it bought no
# security and produced an interstitial instead. TLS terminates at the reverse
# proxy (DEP-002); this container speaks plain HTTP on the private network.

# DEP-001 — Gunicorn, not ~~`python app.py`~~.
#
# Two workers, four threads: the request path is I/O-bound almost end to end
# (n8n -> services -> providers), so threads are the right unit here, and more
# processes would only multiply the memory of a mostly-idle app.
#
# --timeout 180 is deliberate and larger than it looks: a Hebrew recommendation
# has been measured at ~20 s, and Gunicorn's 30 s default would kill the worker
# mid-request and return a bare 502 carrying no error code the UI could act on.
# It sits above N8N_HTTP_TIMEOUT_SECONDS (120) so n8n's own timeout always fires
# first, producing a real error envelope instead.
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "180", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
