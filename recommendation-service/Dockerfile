# Build context is the repository root so shared_lib is available.
#   docker build -f recommendation-service/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Shared library first so the file: requirement resolves and this layer caches.
COPY shared_lib /app/shared_lib
# The frozen response contract, validated by node 18 (validate_output).
COPY contracts /app/contracts

COPY recommendation-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY recommendation-service/ /app/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
