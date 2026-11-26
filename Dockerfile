# Production Dockerfile for AdSync Control Center Backend & Dashboard
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libpq-dev \
    gcc \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure output directories exist for static file mounts
RUN mkdir -p /app/output/videos /app/trend_engine/data

EXPOSE 8000

CMD ["sh", "-c", "uvicorn dashboard.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
