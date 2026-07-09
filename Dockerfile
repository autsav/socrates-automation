FROM python:3.11-slim

# System deps: Pillow (libjpeg, zlib, libwebp) + ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libjpeg-dev \
        zlib1g-dev \
        libwebp-dev \
        libfreetype6-dev \
        liblcms2-dev \
        libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps before copying app (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy full app
COPY . .

# Non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
