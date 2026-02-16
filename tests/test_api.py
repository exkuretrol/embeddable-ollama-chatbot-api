import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.main import create_app


def build_client(monkeypatch, **env: str) -> TestClient:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    return TestClient(create_app())


def test_health_ok(monkeypatch):
    async def fake_health(self):
        return True

    monkeypatch.setattr("app.ollama_client.OllamaClient.health_check", fake_health)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        OLLAMA_MODEL="qwen2.5:3b",
    )

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["ollama"] == "ok"


def test_health_model_missing(monkeypatch):
    async def fake_health(self):
        return False

    monkeypatch.setattr("app.ollama_client.OllamaClient.health_check", fake_health)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        OLLAMA_MODEL="qwen2.5:3b",
    )

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["ollama"] == "model-missing"


def test_chat_requires_api_key(monkeypatch):
    async def fake_chat(self, messages):
        return "hello"

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(monkeypatch, APP_ENV="dev", API_KEY="test-key")

    response = client.post("/api/chat", json={"message": "hi", "history": []})
    assert response.status_code == 401


def test_chat_success(monkeypatch):
    async def fake_chat(self, messages):
        return "您好"

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(monkeypatch, APP_ENV="dev", API_KEY="test-key")

    response = client.post(
        "/api/chat",
        headers={"X-API-Key": "test-key"},
        json={"message": "請打招呼", "history": []},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"] == "您好"
    assert payload["model"] == "qwen2.5:3b"


def test_chat_respects_limits(monkeypatch):
    async def fake_chat(self, messages):
        return "ok"

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        MAX_MESSAGE_CHARS="3",
    )

    response = client.post(
        "/api/chat",
        headers={"X-API-Key": "test-key"},
        json={"message": "toolong", "history": []},
    )
    assert response.status_code == 422
    assert "MAX_MESSAGE_CHARS" in response.json()["detail"]


def test_chat_rate_limit(monkeypatch):
    async def fake_chat(self, messages):
        return "ok"

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        RATE_LIMIT_PER_MIN="1",
    )

    first = client.post(
        "/api/chat",
        headers={"X-API-Key": "test-key"},
        json={"message": "a", "history": []},
    )
    second = client.post(
        "/api/chat",
        headers={"X-API-Key": "test-key"},
        json={"message": "b", "history": []},
    )

    assert first.status_code == 200
    assert second.status_code == 429
