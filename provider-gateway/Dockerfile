# Build context is the repository root so shared_lib is available.
#   docker build -f provider-gateway/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY shared_lib /app/shared_lib
# Phase 5 §5.5: playlist export reads the user's encrypted OAuth grant, so this
# service now needs the canonical ORM (db_models) and token_crypto.
COPY contracts /app/contracts

COPY provider-gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY provider-gateway/ /app/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
