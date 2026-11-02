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
    for section in ["Application health", "Deployment status", "Last deployment",
                    "Monitoring", "Deployment pipeline", "Technology stack"]:
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


def test_homepage_shows_local_mode_when_not_on_render(client, monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    page = client.get("/").get_data(as_text=True)
    assert "Running locally" in page


def test_homepage_shows_render_details_when_on_render(client, monkeypatch):
    # Pretend to be on Render by setting the variables Render provides.
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc1234def5678")
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    page = client.get("/").get_data(as_text=True)
    assert "Deployed on Render" in page
    assert "abc1234" in page          # short commit hash
    assert "abc1234def5678" not in page  # full hash is not shown
    assert "Production" in page
