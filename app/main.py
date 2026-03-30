import logging
from time import perf_counter

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from app.bot_registry import BotRegistryStore
from app.config import Settings, get_settings
from app.llm_provider import build_llm_client
from app.schemas import ChatMessage, ChatRequest, ChatResponse, EmbedTokenRequest, EmbedTokenResponse, ErrorResponse
from app.security import (
    ChatAuthContext,
    EmbedTokenManager,
    RateLimiter,
    get_client_ip,
    get_request_origin,
    normalize_origin,
    require_chat_auth,
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Ollama Chatbot API", version="0.1.0")

    limiter = RateLimiter(limit_per_minute=settings.rate_limit_per_min)
    llm_client = build_llm_client(settings=settings)
    token_manager = EmbedTokenManager(settings.embed_token_secret, settings.embed_token_ttl_seconds)
    bot_registry = BotRegistryStore(settings.bot_registry_db_path)
    bot_registry.init_schema()

    bot_origins = bot_registry.get_all_active_origins()
    merged_origins = list({*settings.allowed_origins, *bot_origins})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=merged_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "X-Embed-Token"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        try:
            model_available = await llm_client.health_check()
            ollama_status = "ok" if model_available else "model-missing"
            service_status = "ok" if model_available else "degraded"
            return {
                "status": service_status,
                "ollama": ollama_status,
                "provider": settings.llm_provider,
                "model": settings.selected_model,
                "env": settings.app_env,
            }
        except Exception:
            return {
                "status": "degraded",
                "ollama": "unreachable",
                "provider": settings.llm_provider,
                "model": settings.selected_model,
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
    ) -> EmbedTokenResponse:
        origin = get_request_origin(request)
        if not origin or origin not in {normalize_origin(o) for o in merged_origins}:
            logger.warning("embed_token_denied origin=%s chatbot_id=%s", origin, payload.chatbot_id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin is not allowed for embed token issuance",
            )

        if not bot_registry.is_origin_allowed(payload.chatbot_id, origin):
            logger.warning("embed_token_denied_bot_policy origin=%s chatbot_id=%s", origin, payload.chatbot_id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="chatbot_id or origin is not allowed",
            )

        token, ttl = token_manager.issue(chatbot_id=payload.chatbot_id, origin=origin)
        logger.info("embed_token_issued origin=%s chatbot_id=%s ttl=%s", origin, payload.chatbot_id, ttl)
        return EmbedTokenResponse(token=token, expires_in=ttl)

    @app.post(
        "/api/chat",
        response_model=ChatResponse,
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
    )
    async def chat(
        payload: ChatRequest,
        request: Request,
        auth: ChatAuthContext = Depends(require_chat_auth),
        runtime_settings: Settings = Depends(get_settings),
    ) -> ChatResponse:
        bot_model: str | None = None
        if auth.method == "embed_token":
            if not auth.chatbot_id or not bot_registry.is_origin_allowed(auth.chatbot_id, auth.origin):
                logger.warning(
                    "chat_denied_bot_policy origin=%s chatbot_id=%s",
                    auth.origin,
                    auth.chatbot_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="chatbot_id or origin is not allowed",
                )
            bot_model = bot_registry.get_bot_model(auth.chatbot_id)

        if len(payload.message) > runtime_settings.max_message_chars:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"message exceeds MAX_MESSAGE_CHARS={runtime_settings.max_message_chars}",
            )

        if len(payload.history) > runtime_settings.max_history_items:
            payload.history = payload.history[-runtime_settings.max_history_items:]

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
            reply = await llm_client.chat(messages=messages, model_override=bot_model)
        except httpx.TimeoutException as exc:
            logger.warning("chat_upstream_timeout origin=%s", get_request_origin(request))
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"{runtime_settings.llm_provider} request timed out",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "chat_upstream_http_error status=%s origin=%s",
                exc.response.status_code,
                get_request_origin(request),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"{runtime_settings.llm_provider} returned HTTP {exc.response.status_code}",
            ) from exc
        except Exception as exc:
            logger.exception("chat_unexpected_error origin=%s", get_request_origin(request))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unexpected {runtime_settings.llm_provider} error: {type(exc).__name__}",
            ) from exc

        latency_ms = int((perf_counter() - started) * 1000)
        effective_model = bot_model or runtime_settings.selected_model
        return ChatResponse(reply=reply, model=effective_model, latency_ms=latency_ms)

    return app


app = create_app()
