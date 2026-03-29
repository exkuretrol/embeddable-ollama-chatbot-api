from pathlib import Path

import pytest

from app.config import Settings
from app.schemas import ChatMessage


def test_defaults_to_ollama_provider(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("APP_ENV=dev\nAPI_KEY=test-key\n", encoding="utf-8")

    settings = Settings(_env_file=str(env_path))
    assert settings.llm_provider == "ollama"


def test_openwebui_provider_requires_required_settings(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "APP_ENV=dev",
                "API_KEY=test-key",
                "LLM_PROVIDER=openwebui",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        Settings(_env_file=str(env_path))


def test_provider_factory_selects_openwebui(tmp_path: Path):
    from app.llm_provider import OpenWebUIClient, build_llm_client

    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "APP_ENV=dev",
                "API_KEY=test-key",
                "LLM_PROVIDER=openwebui",
                "OPENWEBUI_BASE_URL=http://127.0.0.1:3001",
                "OPENWEBUI_API_KEY=secret",
                "OPENWEBUI_MODEL=my-rag-model",
            ]
        ),
        encoding="utf-8",
    )
    settings = Settings(_env_file=str(env_path))

    client = build_llm_client(settings)
    assert isinstance(client, OpenWebUIClient)


@pytest.mark.anyio
async def test_openwebui_chat_response_mapping(monkeypatch, tmp_path: Path):
    from app.llm_provider import OpenWebUIClient

    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "APP_ENV=dev",
                "API_KEY=test-key",
                "LLM_PROVIDER=openwebui",
                "OPENWEBUI_BASE_URL=http://127.0.0.1:3001",
                "OPENWEBUI_API_KEY=secret",
                "OPENWEBUI_MODEL=my-rag-model",
            ]
        ),
        encoding="utf-8",
    )
    settings = Settings(_env_file=str(env_path))
    client = OpenWebUIClient(settings)

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "您好，這是 RAG 回覆。",
                        }
                    }
                ]
            }

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            return DummyResponse()

    monkeypatch.setattr("httpx.AsyncClient", DummyAsyncClient)

    reply = await client.chat([ChatMessage(role="user", content="hi")])
    assert reply == "您好，這是 RAG 回覆。"
