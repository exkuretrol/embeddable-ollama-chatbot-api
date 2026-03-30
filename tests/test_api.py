import sys
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.main import create_app


def build_client(monkeypatch, **env: str) -> TestClient:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    return TestClient(create_app())


def seed_bot_policy(
    db_path: str,
    bot_id: str,
    origin: str,
    bot_status: str = "active",
    model: str | None = None,
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bots (
                bot_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                model TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_allowed_origins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id TEXT NOT NULL,
                origin TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(bot_id, origin),
                FOREIGN KEY(bot_id) REFERENCES bots(bot_id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO bots (bot_id, name, status, model)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(bot_id) DO UPDATE SET
                name=excluded.name,
                status=excluded.status,
                model=excluded.model,
                updated_at=CURRENT_TIMESTAMP
            """,
            (bot_id, f"bot-{bot_id}", bot_status, model),
        )
        conn.execute(
            """
            INSERT INTO bot_allowed_origins (bot_id, origin, status)
            VALUES (?, ?, 'active')
            ON CONFLICT(bot_id, origin) DO UPDATE SET
                status='active',
                updated_at=CURRENT_TIMESTAMP
            """,
            (bot_id, origin),
        )
        conn.commit()
    finally:
        conn.close()


def set_bot_status(db_path: str, bot_id: str, status: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE bots SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE bot_id = ?",
            (status, bot_id),
        )
        conn.commit()
    finally:
        conn.close()


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


def test_health_includes_provider(monkeypatch):
    async def fake_health(self):
        return True

    monkeypatch.setattr("app.ollama_client.OllamaClient.health_check", fake_health)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        LLM_PROVIDER="ollama",
    )

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["provider"] == "ollama"


def test_chat_requires_api_key(monkeypatch):
    async def fake_chat(self, messages, model_override=None):
        return "hello"

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        OLLAMA_MODEL="qwen2.5:3b",
    )

    response = client.post("/api/chat", json={"message": "hi", "history": []})
    assert response.status_code == 401


def test_chat_success(monkeypatch):
    async def fake_chat(self, messages, model_override=None):
        return "您好"

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        OLLAMA_MODEL="qwen2.5:3b",
    )

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
    async def fake_chat(self, messages, model_override=None):
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


def test_chat_truncates_history_exceeding_limit(monkeypatch):
    captured_messages = {}

    async def fake_chat(self, messages, model_override=None):
        captured_messages["value"] = messages
        return "ok"

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        MAX_HISTORY_ITEMS="2",
    )

    history = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
        {"role": "assistant", "content": "d"},
    ]

    response = client.post(
        "/api/chat",
        headers={"X-API-Key": "test-key"},
        json={"message": "e", "history": history},
    )

    assert response.status_code == 200
    # history truncated to last 2 items + current message = 3 messages total
    assert len(captured_messages["value"]) == 3
    assert captured_messages["value"][0].content == "c"
    assert captured_messages["value"][1].content == "d"
    assert captured_messages["value"][2].content == "e"


def test_chat_rate_limit(monkeypatch):
    async def fake_chat(self, messages, model_override=None):
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


def test_embed_token_issued_via_bot_origin_without_env_allowed_origins(monkeypatch, tmp_path: Path):
    """Bot's allowed origin in SQLite is enough — no need to duplicate in ALLOWED_ORIGINS env."""
    db_path = str(tmp_path / "bots.sqlite3")
    seed_bot_policy(db_path, bot_id="demo", origin="http://localhost:3000")

    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        EMBED_TOKEN_SECRET="embed-secret",
        ALLOWED_ORIGINS="",
        BOT_REGISTRY_DB_PATH=db_path,
    )

    response = client.post(
        "/api/embed/token",
        headers={"Origin": "http://localhost:3000"},
        json={"chatbot_id": "demo"},
    )

    assert response.status_code == 200
    assert response.json()["token"]


def test_embed_token_issued_for_allowed_origin(monkeypatch, tmp_path: Path):
    db_path = str(tmp_path / "bots.sqlite3")
    seed_bot_policy(db_path, bot_id="demo", origin="http://localhost:3000")

    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        EMBED_TOKEN_SECRET="embed-secret",
        ALLOWED_ORIGINS="http://localhost:3000",
        BOT_REGISTRY_DB_PATH=db_path,
    )

    response = client.post(
        "/api/embed/token",
        headers={"Origin": "http://localhost:3000"},
        json={"chatbot_id": "demo"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token"]
    assert payload["expires_in"] > 0

def test_embed_token_rejected_for_disallowed_origin(monkeypatch, tmp_path: Path):
    db_path = str(tmp_path / "bots.sqlite3")
    seed_bot_policy(db_path, bot_id="demo", origin="http://localhost:3000")

    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        EMBED_TOKEN_SECRET="embed-secret",
        ALLOWED_ORIGINS="http://localhost:3000",
        BOT_REGISTRY_DB_PATH=db_path,
    )

    response = client.post(
        "/api/embed/token",
        headers={"Origin": "http://evil.local:3000"},
        json={"chatbot_id": "demo"},
    )

    assert response.status_code == 403


def test_embed_token_rejected_for_unknown_bot(monkeypatch, tmp_path: Path):
    db_path = str(tmp_path / "bots.sqlite3")
    seed_bot_policy(db_path, bot_id="demo", origin="http://localhost:3000")

    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        EMBED_TOKEN_SECRET="embed-secret",
        ALLOWED_ORIGINS="http://localhost:3000",
        BOT_REGISTRY_DB_PATH=db_path,
    )

    response = client.post(
        "/api/embed/token",
        headers={"Origin": "http://localhost:3000"},
        json={"chatbot_id": "missing-bot"},
    )

    assert response.status_code == 403


def test_chat_accepts_embed_token(monkeypatch, tmp_path: Path):
    async def fake_chat(self, messages, model_override=None):
        return "token-auth-ok"

    db_path = str(tmp_path / "bots.sqlite3")
    seed_bot_policy(db_path, bot_id="demo", origin="http://localhost:3000")

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        EMBED_TOKEN_SECRET="embed-secret",
        ALLOWED_ORIGINS="http://localhost:3000",
        BOT_REGISTRY_DB_PATH=db_path,
    )

    token_response = client.post(
        "/api/embed/token",
        headers={"Origin": "http://localhost:3000"},
        json={"chatbot_id": "demo"},
    )
    token = token_response.json()["token"]

    response = client.post(
        "/api/chat",
        headers={
            "Origin": "http://localhost:3000",
            "X-Embed-Token": token,
        },
        json={"message": "hello", "history": []},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "token-auth-ok"


def test_chat_rejects_invalid_embed_token(monkeypatch, tmp_path: Path):
    async def fake_chat(self, messages, model_override=None):
        return "should-not-pass"

    db_path = str(tmp_path / "bots.sqlite3")
    seed_bot_policy(db_path, bot_id="demo", origin="http://localhost:3000")

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        EMBED_TOKEN_SECRET="embed-secret",
        ALLOWED_ORIGINS="http://localhost:3000",
        BOT_REGISTRY_DB_PATH=db_path,
    )

    response = client.post(
        "/api/chat",
        headers={
            "Origin": "http://localhost:3000",
            "X-Embed-Token": "invalid.token",
        },
        json={"message": "hello", "history": []},
    )

    assert response.status_code == 401


def test_chat_rejects_expired_embed_token(monkeypatch, tmp_path: Path):
    now = {"value": 1_700_000_000}

    def fake_time():
        return now["value"]

    db_path = str(tmp_path / "bots.sqlite3")
    seed_bot_policy(db_path, bot_id="demo", origin="http://localhost:3000")

    monkeypatch.setattr("app.security.time", fake_time)

    async def fake_chat(self, messages, model_override=None):
        return "should-not-pass"

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        EMBED_TOKEN_SECRET="embed-secret",
        EMBED_TOKEN_TTL_SECONDS="60",
        ALLOWED_ORIGINS="http://localhost:3000",
        BOT_REGISTRY_DB_PATH=db_path,
    )

    token_response = client.post(
        "/api/embed/token",
        headers={"Origin": "http://localhost:3000"},
        json={"chatbot_id": "demo"},
    )
    token = token_response.json()["token"]

    now["value"] += 61
    response = client.post(
        "/api/chat",
        headers={
            "Origin": "http://localhost:3000",
            "X-Embed-Token": token,
        },
        json={"message": "hello", "history": []},
    )

    assert response.status_code == 401


def test_chat_rejects_token_when_bot_disabled_after_issue(monkeypatch, tmp_path: Path):
    async def fake_chat(self, messages, model_override=None):
        return "should-not-pass"

    db_path = str(tmp_path / "bots.sqlite3")
    seed_bot_policy(db_path, bot_id="demo", origin="http://localhost:3000")

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        EMBED_TOKEN_SECRET="embed-secret",
        ALLOWED_ORIGINS="http://localhost:3000",
        BOT_REGISTRY_DB_PATH=db_path,
    )

    token_response = client.post(
        "/api/embed/token",
        headers={"Origin": "http://localhost:3000"},
        json={"chatbot_id": "demo"},
    )
    token = token_response.json()["token"]

    set_bot_status(db_path, bot_id="demo", status="disabled")

    response = client.post(
        "/api/chat",
        headers={
            "Origin": "http://localhost:3000",
            "X-Embed-Token": token,
        },
        json={"message": "hello", "history": []},
    )

    assert response.status_code == 403


def test_chat_uses_bot_model_when_set(monkeypatch, tmp_path: Path):
    captured_model = {}

    async def fake_chat(self, messages, model_override=None):
        captured_model["value"] = model_override
        return "bot-model-reply"

    db_path = str(tmp_path / "bots.sqlite3")
    seed_bot_policy(db_path, bot_id="demo", origin="http://localhost:3000", model="llama3:8b")

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        EMBED_TOKEN_SECRET="embed-secret",
        ALLOWED_ORIGINS="http://localhost:3000",
        BOT_REGISTRY_DB_PATH=db_path,
        OLLAMA_MODEL="qwen2.5:3b",
    )

    token_response = client.post(
        "/api/embed/token",
        headers={"Origin": "http://localhost:3000"},
        json={"chatbot_id": "demo"},
    )
    token = token_response.json()["token"]

    response = client.post(
        "/api/chat",
        headers={
            "Origin": "http://localhost:3000",
            "X-Embed-Token": token,
        },
        json={"message": "hello", "history": []},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "bot-model-reply"
    assert response.json()["model"] == "llama3:8b"
    assert captured_model["value"] == "llama3:8b"


def test_chat_uses_env_model_when_bot_has_no_model(monkeypatch, tmp_path: Path):
    captured_model = {}

    async def fake_chat(self, messages, model_override=None):
        captured_model["value"] = model_override
        return "env-model-reply"

    db_path = str(tmp_path / "bots.sqlite3")
    seed_bot_policy(db_path, bot_id="demo", origin="http://localhost:3000", model=None)

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        EMBED_TOKEN_SECRET="embed-secret",
        ALLOWED_ORIGINS="http://localhost:3000",
        BOT_REGISTRY_DB_PATH=db_path,
        OLLAMA_MODEL="qwen2.5:3b",
    )

    token_response = client.post(
        "/api/embed/token",
        headers={"Origin": "http://localhost:3000"},
        json={"chatbot_id": "demo"},
    )
    token = token_response.json()["token"]

    response = client.post(
        "/api/chat",
        headers={
            "Origin": "http://localhost:3000",
            "X-Embed-Token": token,
        },
        json={"message": "hello", "history": []},
    )

    assert response.status_code == 200
    assert response.json()["model"] == "qwen2.5:3b"
    assert captured_model["value"] is None


def test_chat_api_key_auth_uses_env_model(monkeypatch):
    captured_model = {}

    async def fake_chat(self, messages, model_override=None):
        captured_model["value"] = model_override
        return "api-key-reply"

    monkeypatch.setattr("app.ollama_client.OllamaClient.chat", fake_chat)
    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        OLLAMA_MODEL="qwen2.5:3b",
    )

    response = client.post(
        "/api/chat",
        headers={"X-API-Key": "test-key"},
        json={"message": "hello", "history": []},
    )

    assert response.status_code == 200
    assert response.json()["model"] == "qwen2.5:3b"
    assert captured_model["value"] is None


def test_chat_openwebui_provider_returns_openwebui_model(monkeypatch):
    async def fake_chat(self, messages, model_override=None):
        return "from-openwebui"

    async def fake_health(self):
        return True

    monkeypatch.setattr("app.llm_provider.OpenWebUIClient.chat", fake_chat)
    monkeypatch.setattr("app.llm_provider.OpenWebUIClient.health_check", fake_health)

    client = build_client(
        monkeypatch,
        APP_ENV="dev",
        API_KEY="test-key",
        LLM_PROVIDER="openwebui",
        OPENWEBUI_BASE_URL="http://127.0.0.1:3000",
        OPENWEBUI_API_KEY="owui-key",
        OPENWEBUI_MODEL="custom-rag",
    )

    response = client.post(
        "/api/chat",
        headers={"X-API-Key": "test-key"},
        json={"message": "hello", "history": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"] == "from-openwebui"
    assert payload["model"] == "custom-rag"
