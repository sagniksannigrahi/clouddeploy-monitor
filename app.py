"""CloudDeploy Monitor - a small Flask app that shows its own deployment and health status."""

import os
import platform
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template

APP_NAME = "CloudDeploy Monitor"
APP_VERSION = "1.0.0"

# Recorded once when the server starts. Each deployment starts a fresh
# container, so this is also "when the current version went live".
STARTED_AT = datetime.now(timezone.utc)

app = Flask(__name__)


def get_deployment_info():
    """Describe the running deployment.

    The values come from environment variables:
      - GIT_COMMIT, GIT_BRANCH, BUILD_TIME are baked into the Docker image at build time.
      - CLOUD_* are passed in by deploy.sh, which reads them from the EC2 instance metadata.
    When they are missing, the app is running on a developer machine.
    """
    provider = os.environ.get("CLOUD_PROVIDER", "")
    commit = os.environ.get("GIT_COMMIT", "")
    return {
        "platform": provider or "Local machine",
        "environment": "Production" if provider else "Development",
        "region": os.environ.get("CLOUD_REGION", "not available"),
        "zone": os.environ.get("CLOUD_ZONE", "not available"),
        "instance_type": os.environ.get("CLOUD_INSTANCE_TYPE", "not available"),
        "os": os.environ.get("HOST_OS", platform.system()),
        "commit": commit[:7] if commit else "not available",
        "branch": os.environ.get("GIT_BRANCH", "local"),
        "built_at": os.environ.get("BUILD_TIME", ""),
        "deployed_by": os.environ.get("DEPLOYED_BY", "Manual"),
        "started_at": STARTED_AT.isoformat(timespec="seconds"),
        # Optional: link to a public UptimeRobot status page.
        "status_page": os.environ.get("STATUS_PAGE_URL", ""),
    }


@app.route("/")
def home():
    return render_template("index.html", app_name=APP_NAME, deploy=get_deployment_info())


@app.route("/health")
def health():
    # Used by UptimeRobot and the deployment health check. Keep it fast and simple.
    return jsonify(status="healthy", application=APP_NAME)


@app.route("/api/status")
def api_status():
    # Useful details for humans and scripts. Contains no secrets, IP addresses,
    # instance IDs or account information.
    info = get_deployment_info()
    now = datetime.now(timezone.utc)
    return jsonify(
        application=APP_NAME,
        version=APP_VERSION,
        status="healthy",
        environment=info["environment"],
        deployment={
            "platform": info["platform"],
            "region": info["region"],
            "instance_type": info["instance_type"],
            "commit": info["commit"],
            "branch": info["branch"],
            "built_at": info["built_at"] or None,
            "deployed_by": info["deployed_by"],
        },
        runtime={
            "python_version": platform.python_version(),
            "started_at": info["started_at"],
            "uptime_seconds": int((now - STARTED_AT).total_seconds()),
        },
        server_time=now.isoformat(timespec="seconds"),
    )


if __name__ == "__main__":
    # Development server only. Docker uses Gunicorn instead (see Dockerfile).
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
