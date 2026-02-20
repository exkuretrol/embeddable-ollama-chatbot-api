.PHONY: help setup backend frontend dev test health token chat

help:
	@printf "\nTargets:\n"
	@printf "  make setup    - sync dependencies\n"
	@printf "  make backend  - start FastAPI backend (reload)\n"
	@printf "  make frontend - serve examples on :3000\n"
	@printf "  make dev      - run backend + frontend together\n"
	@printf "  make test     - run test suite\n"
	@printf "  make health   - call /health\n"
	@printf "  make token    - request embed token\n"
	@printf "  make chat     - send chat request with API key\n\n"

setup:
	uv sync --python 3.13

backend:
	uv run uvicorn app.main:app --reload

frontend:
	python3 -m http.server 3000 --directory examples

dev:
	sh -c 'trap "kill 0" INT TERM EXIT; uv run uvicorn app.main:app --reload & python3 -m http.server 3000 --directory examples & wait'

test:
	uv run python -m pytest

health:
	curl -sS http://127.0.0.1:8000/health

token:
	curl -sS -X POST http://127.0.0.1:8000/api/embed/token \
		-H "Content-Type: application/json" \
		-H "Origin: http://127.0.0.1:3000" \
		-d '{"chatbot_id":"demo"}'

chat:
	curl -sS -X POST http://127.0.0.1:8000/api/chat \
		-H "Content-Type: application/json" \
		-H "X-API-Key: dev-local-key" \
		-d '{"message":"hello","history":[]}'
