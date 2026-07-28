# Build context is the repository root so shared_lib and contracts are available.
#   docker build -f rag-service/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Make shared_lib + contracts importable regardless of the invoked script path.
    PYTHONPATH=/app \
    # Cache HuggingFace models under a mounted volume (see docker-compose.yml).
    HF_HOME=/app/.hf_cache

WORKDIR /app

COPY shared_lib /app/shared_lib
# The DB models used by ingestion / embedding / retrieval scripts.
COPY contracts /app/contracts

COPY rag-service/requirements.txt /app/requirements.txt
# Install the CPU-only torch build first so the heavy default (CUDA) wheel is
# never pulled; `torch==2.5.1` in requirements.txt is then already satisfied.
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY rag-service/ /app/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
