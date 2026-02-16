# AGENTS.md

## Project
Build a chatbot backend powered by Ollama, with a generic embeddable frontend snippet.

Architecture:
- Embeddable widget (HTML/CSS/JS) -> Python API (FastAPI) -> Ollama
- Session-only memory (frontend sends `history[]` per request)
- No database in v1

## Core Stack
- Python project manager: `uv`
- API framework: `FastAPI`
- HTTP client: `httpx`
- ASGI server: `uvicorn`
- Config: `pydantic-settings`
- LLM runtime: `Ollama`

## Development Strategy (TDD)
Use strict TDD by default for backend and embed logic changes.

Workflow:
1. Red: write or update a failing test for the target behavior.
2. Green: implement the minimal change required to pass.
3. Refactor: improve structure while keeping tests green.

Rules:
- Do not ship behavior changes without tests.
- Add regression tests for every bug fix.
- Prefer small, behavior-focused test cases.
- Mock external services (such as Ollama HTTP calls) in unit tests.
- Use smoke checks for real upstream verification.

Definition of done:
- Relevant tests were added or updated first.
- `uv run python -m pytest` passes locally.
- A manual smoke check was run for changed runtime paths.

## Agent Behavior Rules
1. Subagent usage is allowed.
2. Nested subagent calls are forbidden (a subagent must not invoke another subagent).
3. Keep orchestration single-level from the primary agent.
4. Do not introduce additional orchestration layers unless explicitly requested.

## API Contract (v1)
### `GET /health`
- Returns service health and Ollama connectivity status.

### `POST /api/chat`
Headers:
- `X-API-Key: <key>` (required in dev and prod)

Request JSON:
- `message: string`
- `history: [{ "role": "user" | "assistant" | "system", "content": string }]`

Response JSON:
- `reply: string`
- optional `latency_ms: number`

## Security Defaults
- Enforce `X-API-Key` on `/api/chat` in all environments.
- Restrict CORS via `ALLOWED_ORIGINS` allowlist.
- Apply basic in-memory per-IP rate limiting.
- Validate input sizes (message length, history length).
- Return normalized JSON errors for timeout/upstream failures.

## Environment Variables
- `APP_ENV` (`dev` or `prod`)
- `OLLAMA_BASE_URL` (default: `http://127.0.0.1:11434`)
- `OLLAMA_MODEL` (dev default: `qwen2.5:3b`)
- `API_KEY`
- `ALLOWED_ORIGINS` (comma-separated)
- `REQUEST_TIMEOUT`
- `HEALTH_TIMEOUT`
- `RATE_LIMIT_PER_MIN`

## Local Development
- Ollama runs locally with model pulled (e.g. `qwen2.5:3b`).
- Backend runs via `uv`.
- Embed snippet points to local backend endpoint.

## Commands
- Install deps: `uv sync` (or `uv add ...` during setup)
- Run API: `uv run uvicorn app.main:app --reload`
- Run tests: `uv run python -m pytest`
- Run specific tests: `uv run python -m pytest tests/test_api.py -k <keyword>`
- Health check: `curl http://127.0.0.1:8000/health`
- Chat test: `curl -X POST http://127.0.0.1:8000/api/chat ...`

## Embed Integration Rules
- Provide a paste-ready snippet under `examples/`.
- Scope CSS to avoid conflicts with host site styles.
- Keep frontend framework-free in v1 (plain HTML/CSS/JS).
- Keep memory session-only in browser runtime.

## Embed Delivery Strategy
- Prefer minified loader-based delivery for production embeds.
- Keep integration to a single script tag when possible.
- Never expose backend master secrets in browser code.

## Non-Goals (v1)
- No persistent chat storage.
- No user auth system beyond static API key.
- No streaming response protocol (non-streaming only).

## Change Control
- Do not alter API contract or security defaults without explicit approval.
- Do not add background workers, queues, or databases in v1 unless requested.

## Commit Message Convention
Use Conventional Commits v1.0.0 for all git commit messages.

Format:
- `<type>[optional scope]: <description>`
- optional body
- optional footer(s)

Rules:
- Use lowercase `type` and concise imperative description.
- Keep subject line short and focused on intent.
- Use `!` after type or scope for breaking changes, or include `BREAKING CHANGE:` in footer.
- Prefer separate commits for test-first progression when practical.

Allowed types:
- `feat`: a new feature
- `fix`: a bug fix
- `docs`: documentation-only changes
- `style`: formatting-only changes
- `refactor`: code change that is neither fix nor feature
- `perf`: performance improvement
- `test`: add or update tests
- `build`: build system or dependency changes
- `ci`: CI or CD changes
- `chore`: maintenance tasks
- `revert`: revert a previous commit
