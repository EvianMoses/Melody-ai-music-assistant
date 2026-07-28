# Build context is the repository root so shared_lib is available.
#   docker build -f audio-service/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # librosa/numba need a writable cache; without one every import re-JITs.
    NUMBA_CACHE_DIR=/tmp/numba-cache

WORKDIR /app

# FFmpeg is the decode boundary for every allowed container (§6.1, AUD-UP-005),
# and libsndfile backs soundfile for the WAV reads. `--no-install-recommends`
# keeps the image from pulling ffmpeg's full suggestion set.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY shared_lib /app/shared_lib

COPY audio-service/requirements.txt /app/requirements.txt
# torch defaults to a ~2 GB CUDA build; this service is CPU-only inference, so
# the CPU wheel index keeps the image to a fraction of that.
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

COPY audio-service/ /app/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
