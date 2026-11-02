"""Automated tests for CloudDeploy Monitor. Run with:  pytest -v"""

import pytest

from app import app


@pytest.fixture
def client():
    # Flask's test client sends fake requests to the app without starting a real server.
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ---------- Homepage ----------

def test_homepage_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_homepage_is_html(client):
    response = client.get("/")
    assert response.content_type.startswith("text/html")


def test_homepage_shows_app_name_and_sections(client):
    page = client.get("/").get_data(as_text=True)
    assert "CloudDeploy Monitor" in page
    for section in ["Application health", "Deployment status", "Cloud infrastructure",
                    "Monitoring", "CI/CD pipeline", "Technology stack"]:
        assert section in page


def test_stylesheet_is_served(client):
    response = client.get("/static/style.css")
    assert response.status_code == 200
    assert "text/css" in response.content_type


# ---------- Health endpoint ----------

def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_json(client):
    response = client.get("/health")
    assert response.is_json


def test_health_json_matches_expected(client):
    response = client.get("/health")
    assert response.get_json() == {
        "status": "healthy",
        "application": "CloudDeploy Monitor",
    }


# ---------- Other application behaviour ----------

def test_unknown_page_returns_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404


def test_health_rejects_post(client):
    response = client.post("/health")
    assert response.status_code == 405  # Method Not Allowed


# Environment variables that only exist on the EC2 deployment.
EC2_ENV = {
    "CLOUD_PROVIDER": "AWS EC2",
    "CLOUD_REGION": "us-east-1",
    "CLOUD_ZONE": "us-east-1a",
    "CLOUD_INSTANCE_TYPE": "t3.micro",
    "GIT_COMMIT": "abc1234def5678",
    "GIT_BRANCH": "main",
    "DEPLOYED_BY": "GitHub Actions",
}


def test_homepage_shows_local_mode_by_default(client, monkeypatch):
    for name in EC2_ENV:
        monkeypatch.delenv(name, raising=False)
    page = client.get("/").get_data(as_text=True)
    assert "Running locally" in page
    assert "Development" in page


def test_homepage_shows_ec2_details_when_deployed(client, monkeypatch):
    for name, value in EC2_ENV.items():
        monkeypatch.setenv(name, value)
    page = client.get("/").get_data(as_text=True)
    assert "Deployed on AWS EC2" in page
    assert "Production" in page
    assert "us-east-1" in page and "t3.micro" in page
    assert "abc1234" in page             # short commit hash
    assert "abc1234def5678" not in page  # full hash is not shown


# ---------- Status API ----------

def test_status_api_returns_200_json(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.is_json


def test_status_api_has_expected_fields(client):
    data = client.get("/api/status").get_json()
    assert data["application"] == "CloudDeploy Monitor"
    assert data["status"] == "healthy"
    for key in ["platform", "region", "instance_type", "commit", "branch", "deployed_by"]:
        assert key in data["deployment"]
    assert data["runtime"]["uptime_seconds"] >= 0


def test_status_api_reports_ec2_deployment(client, monkeypatch):
    for name, value in EC2_ENV.items():
        monkeypatch.setenv(name, value)
    data = client.get("/api/status").get_json()
    assert data["environment"] == "Production"
    assert data["deployment"]["platform"] == "AWS EC2"
    assert data["deployment"]["commit"] == "abc1234"
    assert data["deployment"]["deployed_by"] == "GitHub Actions"


def test_status_api_does_not_leak_sensitive_values(client, monkeypatch):
    # Even if secrets exist in the environment, the API must never echo them.
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "super-secret-value")
    monkeypatch.setenv("EC2_SSH_KEY", "-----BEGIN OPENSSH PRIVATE KEY-----")
    body = client.get("/api/status").get_data(as_text=True)
    assert "super-secret-value" not in body
    assert "PRIVATE KEY" not in body
    for word in ["instance_id", "private_ip", "public_ip", "account"]:
        assert word not in body
