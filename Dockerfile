# ---- CloudDeploy Monitor container image ----

# Small official Python image (Debian "slim" variant, no extra build tools).
FROM python:3.14-slim

# Don't write .pyc files, and print logs immediately (no buffering).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first. Docker caches this layer, so rebuilds are fast
# when only the app code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy only the files the app needs to run.
COPY app.py .
COPY templates/ templates/
COPY static/ static/

# Version details passed in by deploy.sh (docker build --build-arg ...).
# Baking them into the image means a rolled-back image still reports its own version.
ARG GIT_COMMIT=""
ARG GIT_BRANCH="local"
ARG BUILD_TIME=""
ENV GIT_COMMIT=${GIT_COMMIT} \
    GIT_BRANCH=${GIT_BRANCH} \
    BUILD_TIME=${BUILD_TIME}

# Run as a normal user instead of root (safer if the app is ever compromised).
RUN useradd --create-home appuser
USER appuser

# Documents the port the app listens on inside the container (override with -e PORT=...).
EXPOSE 8080

# Lets `docker ps` show whether the app is healthy. Uses Python because the
# slim image has no curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["sh", "-c", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${PORT}/health', timeout=4)\""]

# Start Gunicorn, a production web server, on 0.0.0.0 so traffic from outside
# the container can reach it. "sh -c" lets ${PORT} be filled in at runtime, and
# "exec" hands control to Gunicorn so it receives stop signals directly.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --access-logfile - app:app"]
