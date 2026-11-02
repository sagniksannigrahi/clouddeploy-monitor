"""CloudDeploy Monitor - a small Flask app that shows its own deployment and health status."""

import os
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template

APP_NAME = "CloudDeploy Monitor"

# Recorded once when the server starts. On Render every deploy starts a fresh
# container, so this doubles as "when the current version went live".
STARTED_AT = datetime.now(timezone.utc)

app = Flask(__name__)


def get_deployment_info():
    """Describe where the app is running.

    Render sets RENDER=true and RENDER_GIT_* variables in every service.
    When they are missing, we know the app is running locally.
    """
    on_render = os.environ.get("RENDER") == "true"
    commit = os.environ.get("RENDER_GIT_COMMIT", "")
    return {
        "platform": "Render" if on_render else "Local machine",
        "environment": "Production" if on_render else "Development",
        "service": os.environ.get("RENDER_SERVICE_NAME", "clouddeploy-monitor"),
        "branch": os.environ.get("RENDER_GIT_BRANCH", "local"),
        "commit": commit[:7] if commit else "not available",
        "url": os.environ.get("RENDER_EXTERNAL_URL", ""),
        "started_at": STARTED_AT.isoformat(timespec="seconds"),
        # Optional: link to your public UptimeRobot status page (set it in Render).
        "status_page": os.environ.get("STATUS_PAGE_URL", ""),
    }


@app.route("/")
def home():
    return render_template("index.html", app_name=APP_NAME, deploy=get_deployment_info())


@app.route("/health")
def health():
    # Used by UptimeRobot and Render's health check. Keep it fast and simple.
    return jsonify(status="healthy", application=APP_NAME)


if __name__ == "__main__":
    # Development server only. Docker and Render use Gunicorn instead (see Dockerfile).
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
