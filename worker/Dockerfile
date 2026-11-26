# Production Dockerfile for AdSync Cloud Video Rendering Worker
FROM python:3.11-slim-bookworm

# Prevent interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV CHROME_PATH=/usr/bin/chromium

# Install system dependencies: FFmpeg, Node.js, Chromium, and rendering libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ffmpeg \
    chromium \
    chromium-driver \
    ca-certificates \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    fonts-liberation \
    fonts-noto-color-emoji \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy root dependency manifests
COPY requirements.txt .

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir soundfile scipy numpy kokoro-onnx pillow \
    && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copy application source
COPY . .

# Expose Render default port
EXPOSE 8000

# Start Cloud Rendering Worker
CMD ["sh", "-c", "uvicorn worker.render_worker:app --host 0.0.0.0 --port ${PORT:-8000}"]
