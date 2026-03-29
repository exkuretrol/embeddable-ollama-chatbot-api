## Embeddable Ollama Chatbot API

FastAPI backend that proxies chat requests to Ollama, plus an embeddable website widget snippet.

Architecture:
- Embeddable widget -> FastAPI backend -> Ollama
- Session-only memory (`history[]` sent by frontend)

Upstream provider is selected with `.env` `LLM_PROVIDER`:
- `ollama` (default)
- `openwebui`

## Requirements

- Python `>=3.13,<3.15`
- `uv`
- Ollama running locally or remotely

## Quick Start

1. Copy env template:

```bash
cp .env.example .env
```

Set `API_KEY` and `EMBED_TOKEN_SECRET` in `.env`.

If `LLM_PROVIDER=openwebui`, also set `OPENWEBUI_BASE_URL`, `OPENWEBUI_API_KEY`, and `OPENWEBUI_MODEL`.

Set `BOT_REGISTRY_DB_PATH` to a writable SQLite file path.

2. Install dependencies with Python 3.13:

```bash
uv sync --python 3.13
```

3. Make sure Ollama is running and model exists:

```bash
ollama list
```

4. Run API:

```bash
uv run uvicorn app.main:app --reload
```

5. Health check:

```bash
curl -sS http://127.0.0.1:8000/health
```

`/health` reports:
- `status=ok` and `ollama=ok` when Ollama is reachable and the configured model is present.
- `status=degraded` when Ollama is unreachable or model is missing.

## Run Tests

```bash
uv run python -m pytest
```

## Make Targets

```bash
make setup
make backend
make frontend
make dev
make test
make health
make token
make chat
```

## Chat API Test

```bash
curl -sS -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key>" \
  -d '{
    "message": "用繁體中文介紹你自己",
    "history": []
  }'
```

## Embed Token Test

```bash
curl -sS -X POST http://127.0.0.1:8000/api/embed/token \
  -H "Content-Type: application/json" \
  -H "Origin: http://127.0.0.1:3000" \
  -d '{"chatbot_id":"demo"}'
```

Note: token issuance requires `chatbot_id` to exist in the bot registry and request origin to match an allowed origin for that bot.

## Bot Registry (SQLite)

The backend enforces exact-origin policy per `chatbot_id` using SQLite.

Create a bot and allow one origin:

```bash
sqlite3 ./data/bots.sqlite3 "INSERT INTO bots (bot_id,name,status) VALUES ('bot_demo_123','Demo Bot','active');"
sqlite3 ./data/bots.sqlite3 "INSERT INTO bot_allowed_origins (bot_id,origin,status) VALUES ('bot_demo_123','http://127.0.0.1:3000','active');"
```

Use that same `bot_id` in embed snippet `data-chatbot-id`.

## Provider Switch Examples

Use Ollama:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
```

Use Open WebUI:

```env
LLM_PROVIDER=openwebui
OPENWEBUI_BASE_URL=http://127.0.0.1:3000
OPENWEBUI_API_KEY=replace-with-openwebui-token
OPENWEBUI_MODEL=your-custom-rag-model
OPENWEBUI_CHAT_PATH=/api/chat/completions
```

## Environment Variables

- `APP_ENV`: `dev` or `prod`
- `LLM_PROVIDER`: `ollama` or `openwebui`
- `OLLAMA_BASE_URL`: e.g. `http://127.0.0.1:11434`
- `OLLAMA_MODEL`: e.g. `qwen2.5:3b`
- `OPENWEBUI_BASE_URL`: e.g. `http://127.0.0.1:3000`
- `OPENWEBUI_API_KEY`: Open WebUI bearer token
- `OPENWEBUI_MODEL`: model id/alias in Open WebUI
- `OPENWEBUI_CHAT_PATH`: endpoint path, default `/api/chat/completions`
- `API_KEY`: required for `/api/chat`
- `ALLOWED_ORIGINS`: comma-separated origins
- `REQUEST_TIMEOUT`: Ollama upstream timeout seconds
- `HEALTH_TIMEOUT`: Ollama health check timeout seconds
- `RATE_LIMIT_PER_MIN`: requests per IP per minute
- `MAX_MESSAGE_CHARS`: per-message length limit
- `MAX_HISTORY_ITEMS`: max history items accepted
- `EMBED_TOKEN_SECRET`: HMAC secret for browser embed tokens
- `EMBED_TOKEN_TTL_SECONDS`: embed token lifetime in seconds
- `BOT_REGISTRY_DB_PATH`: SQLite path for bot and allowed-origin policies

## Embed Example

`examples/embed-playground.html` is the combined runtime preview + snippet builder page:
- previews real `embed.js` behavior on a host page
- explains every `data-*` argument
- updates snippet code immediately; use Reload Preview to apply runtime changes
- includes copy-ready snippet generation

Widget options supported by generated snippet:
- floating launcher opens chat window by default; users can minimize it
- desktop supports drag-to-move (mobile drag is disabled)
- optional: set `data-locale` for fixed language
- optional: set `data-locale-query-param` to customize URL locale key (default: `locale`)
- optional: set `data-start-open` (`true` or `false`)
- optional: set `data-draggable` (`true` or `false`)
- optional: set `data-persist-history` (`true` or `false`, default `true`)
- optional: set `data-history-ttl-seconds` (default `86400`)
- optional: set `data-history-storage-key` (custom localStorage key)
- optional: set `data-launcher-icon` with text/emoji or image URL
- locale supports `en` and `zh-TW`; `zh-Hant*` auto-maps to `zh-TW`
- history persistence uses browser localStorage; add a clear option in UI for shared devices

For local preview:

```bash
python3 -m http.server 3000 --directory examples
```

Then open `http://127.0.0.1:3000/embed-playground.html`.

## Minified Embed Approach

- Ship a versioned loader script such as `https://cdn.example.com/embed/v1/embed.min.js`.
- Keep host-site integration to a single line: `<script ... data-chatbot-id="...">`.
- Keep server secrets on backend; browser embed should use short-lived public tokens, not master API keys.

Current local starter files:
- `examples/embed.js` (loader-style widget script)
- `examples/embed-playground.html` (combined preview + snippet builder)

## Production Notes

- Serve API behind HTTPS reverse proxy.
- Set strict `ALLOWED_ORIGINS` to your embed host domain(s).
- Keep Ollama private to the backend host/network when possible.
- Rotate `API_KEY` regularly.
