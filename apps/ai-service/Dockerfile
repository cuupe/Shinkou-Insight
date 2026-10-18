ARG BASE_IMAGE_REGISTRY=docker.io
FROM ${BASE_IMAGE_REGISTRY}/library/python:3.11-slim
ARG DEBIAN_MIRROR_URL=http://deb.debian.org

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/ai-service \
    STORAGE_ROOT=/app/data \
    HF_HOME=/app/model-cache

# Keep the repository layout: config.py resolves the project root two levels up.
WORKDIR /app/apps/ai-service
RUN rm -f /etc/apt/apt.conf.d/docker-clean \
    && sed -i "s|http://deb.debian.org|${DEBIAN_MIRROR_URL}|g" /etc/apt/sources.list.d/debian.sources
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        ffmpeg \
        libreoffice \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-eng
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
RUN useradd --create-home --uid 10001 shinkou \
    && mkdir -p /app/data /app/model-cache \
    && chown -R shinkou:shinkou /app
COPY . .

USER shinkou
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=12 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
