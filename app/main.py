from time import perf_counter

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.ollama_client import OllamaClient
from app.schemas import ChatMessage, ChatRequest, ChatResponse, EmbedTokenRequest, EmbedTokenResponse, ErrorResponse
from app.security import (
    EmbedTokenManager,
    RateLimiter,
    get_client_ip,
    get_request_origin,
    origin_allowed,
    require_chat_auth,
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Ollama Chatbot API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "X-Embed-Token"],
    )

    limiter = RateLimiter(limit_per_minute=settings.rate_limit_per_min)
    ollama = OllamaClient(settings=settings)
    token_manager = EmbedTokenManager(settings.embed_token_secret, settings.embed_token_ttl_seconds)

    @app.get("/health")
    async def health() -> dict[str, str]:
        try:
            model_available = await ollama.health_check()
            ollama_status = "ok" if model_available else "model-missing"
            service_status = "ok" if model_available else "degraded"
            return {
                "status": service_status,
                "ollama": ollama_status,
                "model": settings.ollama_model,
                "env": settings.app_env,
            }
        except Exception:
            return {
                "status": "degraded",
                "ollama": "unreachable",
                "model": settings.ollama_model,
                "env": settings.app_env,
            }

    @app.post(
        "/api/embed/token",
        response_model=EmbedTokenResponse,
        responses={
            403: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
    )
    async def issue_embed_token(
        payload: EmbedTokenRequest,
        request: Request,
        runtime_settings: Settings = Depends(get_settings),
    ) -> EmbedTokenResponse:
        origin = get_request_origin(request)
        if not origin_allowed(origin, runtime_settings):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin is not allowed for embed token issuance",
            )

        token, ttl = token_manager.issue(chatbot_id=payload.chatbot_id, origin=origin)
        return EmbedTokenResponse(token=token, expires_in=ttl)

    @app.post(
        "/api/chat",
        response_model=ChatResponse,
        responses={
            401: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
    )
    async def chat(
        payload: ChatRequest,
        request: Request,
        _: None = Depends(require_chat_auth),
        runtime_settings: Settings = Depends(get_settings),
    ) -> ChatResponse:
        if len(payload.message) > runtime_settings.max_message_chars:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"message exceeds MAX_MESSAGE_CHARS={runtime_settings.max_message_chars}",
            )

        if len(payload.history) > runtime_settings.max_history_items:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"history exceeds MAX_HISTORY_ITEMS={runtime_settings.max_history_items}",
            )

        for item in payload.history:
            if len(item.content) > runtime_settings.max_message_chars:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="a history message exceeds MAX_MESSAGE_CHARS",
                )

        client_ip = get_client_ip(request)
        if not limiter.allow(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests; please retry in a minute",
            )

        messages: list[ChatMessage] = [*payload.history, ChatMessage(role="user", content=payload.message)]
        started = perf_counter()

        try:
            reply = await ollama.chat(messages=messages)
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Ollama request timed out",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ollama returned HTTP {exc.response.status_code}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unexpected Ollama error: {type(exc).__name__}",
            ) from exc

        latency_ms = int((perf_counter() - started) * 1000)
        return ChatResponse(reply=reply, model=runtime_settings.ollama_model, latency_ms=latency_ms)

    return app


app = create_app()
