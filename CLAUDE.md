# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI backend that proxies chat requests to Ollama (or Open WebUI), with an embeddable browser widget. Session-only memory — the frontend sends `history[]` with each request. A SQLite bot registry enforces per-chatbot origin policies.

**Architecture:** Embeddable widget (plain JS) -> FastAPI API -> Ollama / Open WebUI

## Commands

```bash
make setup              # uv sync --python 3.13
make dev                # backend (:8000) + frontend (:3000) concurrently
make backend            # FastAPI with --reload
make backend-openwebui  # same, with LLM_PROVIDER=openwebui
make test               # uv run python -m pytest
make health             # curl /health
```

Run a single test:
```bash
uv run python -m pytest tests/test_api.py -k <keyword>
```

## Code Architecture

| Module | Role |
|---|---|
| `app/main.py` | App factory (`create_app()`), route handlers, CORS middleware |
| `app/config.py` | `Settings` (pydantic-settings), loads `.env` |
| `app/schemas.py` | Pydantic request/response models |
| `app/security.py` | RateLimiter, EmbedTokenManager (HMAC-SHA256), auth helpers |
| `app/llm_provider.py` | `LLMClient` protocol, `OllamaClient`, `OpenWebUIClient`, factory |
| `app/ollama_client.py` | Async httpx client for Ollama HTTP API |
| `app/bot_registry.py` | SQLite bot registry with origin policy checks |
| `examples/embed.js` | Widget loader with full chat UI, i18n (en, zh-TW) |
| `examples/embed-playground.html` | Interactive widget preview and snippet builder |

**Endpoints:** `GET /health`, `POST /api/embed/token`, `POST /api/chat`

**Auth:** `X-API-Key` header (server-to-server) or `X-Embed-Token` (browser clients, short-lived HMAC tokens).

## Development Rules

- **Strict TDD:** Red -> Green -> Refactor. No behavior changes without tests. Regression test every bug fix.
- **Conventional Commits v1.0.0** required (feat, fix, docs, test, refactor, etc.).
- **Do not alter API contract or security defaults** without explicit approval.
- Mock external services (Ollama/Open WebUI HTTP calls) in unit tests.
- Widget must remain framework-free (plain HTML/CSS/JS). CSS is scoped via Shadow DOM.
- Never expose backend secrets in browser code; use short-lived embed tokens.
- Provider is selected via `LLM_PROVIDER` env var (`ollama` or `openwebui`).

## Testing

Tests are in `tests/` using pytest with FastAPI's `TestClient`. External HTTP calls are monkeypatched. Tests cover auth flows, rate limiting, embed token lifecycle, bot registry policies, and both LLM providers.
