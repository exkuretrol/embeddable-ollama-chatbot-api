## Embeddable Ollama Chatbot API

FastAPI backend that proxies chat requests to Ollama, plus an embeddable website widget snippet.

Architecture:
- Embeddable widget -> FastAPI backend -> Ollama
- Session-only memory (`history[]` sent by frontend)

## Requirements

- Python `>=3.13,<3.15`
- `uv`
- Ollama running locally or remotely

## Quick Start

1. Copy env template:

```bash
cp .env.example .env
```

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
uv run pytest
```

## Chat API Test

```bash
curl -sS -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-a-strong-key" \
  -d '{
    "message": "用繁體中文介紹你自己",
    "history": []
  }'
```

## Environment Variables

- `APP_ENV`: `dev` or `prod`
- `OLLAMA_BASE_URL`: e.g. `http://127.0.0.1:11434`
- `OLLAMA_MODEL`: e.g. `qwen2.5:3b`
- `API_KEY`: required for `/api/chat`
- `ALLOWED_ORIGINS`: comma-separated origins
- `REQUEST_TIMEOUT`: Ollama upstream timeout seconds
- `HEALTH_TIMEOUT`: Ollama health check timeout seconds
- `RATE_LIMIT_PER_MIN`: requests per IP per minute
- `MAX_MESSAGE_CHARS`: per-message length limit
- `MAX_HISTORY_ITEMS`: max history items accepted

## Embed Example

Use `examples/embed-snippet.html`:
- paste into any website HTML block/page
- update `CONFIG.API_BASE_URL`
- update `CONFIG.API_KEY`

## Minified Embed Approach

- Ship a versioned loader script such as `https://cdn.example.com/embed/v1/embed.min.js`.
- Keep host-site integration to a single line: `<script ... data-chatbot-id="...">`.
- Keep server secrets on backend; browser embed should use short-lived public tokens, not master API keys.

## Production Notes

- Serve API behind HTTPS reverse proxy.
- Set strict `ALLOWED_ORIGINS` to your embed host domain(s).
- Keep Ollama private to the backend host/network when possible.
- Rotate `API_KEY` regularly.
