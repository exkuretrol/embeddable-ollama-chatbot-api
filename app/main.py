import csv
import hashlib
import io
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from time import perf_counter

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
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

_CSV_FIELDS = ["timestamp", "ip", "bot_id", "model", "auth_method",
               "message", "reply", "history_len", "latency_ms", "user_agent"]


def _build_chat_csv_logger() -> logging.Logger:
    path = Path(__file__).parent.parent / "logs" / "chat.csv"
    path.parent.mkdir(parents=True, exist_ok=True)

    write_header = not path.exists() or path.stat().st_size == 0

    handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(path),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=False,
    )
    handler.suffix = "%Y-%m-%d"
    handler.setFormatter(logging.Formatter("%(message)s"))

    chat_logger = logging.getLogger("app.chat_csv")
    chat_logger.setLevel(logging.INFO)
    chat_logger.propagate = False
    chat_logger.addHandler(handler)

    if write_header:
        buf = io.StringIO()
        csv.writer(buf).writerow(_CSV_FIELDS)
        chat_logger.info(buf.getvalue().rstrip())

    return chat_logger


def _csv_row(**kwargs: object) -> str:
    buf = io.StringIO()
    csv.writer(buf).writerow([kwargs.get(f, "") for f in _CSV_FIELDS])
    return buf.getvalue().rstrip()


def _get_user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "")


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def create_app() -> FastAPI:
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-5s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    content_max = settings.log_content_max_chars
    is_dev = settings.app_env == "dev"

    chat_csv_logger = _build_chat_csv_logger() if settings.chat_log_enabled else None

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
        ip = get_client_ip(request)
        ua = _get_user_agent(request)

        if not origin or origin not in {normalize_origin(o) for o in merged_origins}:
            logger.warning(
                "embed_token_denied ip=%s origin=%s bot_id=%s ua=%s",
                ip, origin, payload.chatbot_id, ua,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin is not allowed for embed token issuance",
            )

        if not bot_registry.is_origin_allowed(payload.chatbot_id, origin):
            logger.warning(
                "embed_token_denied_bot_policy ip=%s origin=%s bot_id=%s ua=%s",
                ip, origin, payload.chatbot_id, ua,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="chatbot_id or origin is not allowed",
            )

        token, ttl = token_manager.issue(chatbot_id=payload.chatbot_id, origin=origin)
        logger.info(
            "embed_token_issued ip=%s origin=%s bot_id=%s ttl=%s ua=%s",
            ip, origin, payload.chatbot_id, ttl, ua,
        )
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
        client_ip = get_client_ip(request)
        ua = _get_user_agent(request)
        bot_id = auth.chatbot_id or ""

        bot_model: str | None = None
        if auth.method == "embed_token":
            if not auth.chatbot_id or not bot_registry.is_origin_allowed(auth.chatbot_id, auth.origin):
                logger.warning(
                    "chat_denied_bot_policy ip=%s origin=%s bot_id=%s ua=%s",
                    client_ip, auth.origin, bot_id, ua,
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
            logger.warning(
                "chat_upstream_timeout ip=%s origin=%s bot_id=%s ua=%s",
                client_ip, get_request_origin(request), bot_id, ua,
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"{runtime_settings.llm_provider} request timed out",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "chat_upstream_http_error status=%s ip=%s origin=%s bot_id=%s ua=%s",
                exc.response.status_code, client_ip, get_request_origin(request), bot_id, ua,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"{runtime_settings.llm_provider} returned HTTP {exc.response.status_code}",
            ) from exc
        except Exception as exc:
            logger.exception(
                "chat_unexpected_error ip=%s origin=%s bot_id=%s ua=%s",
                client_ip, get_request_origin(request), bot_id, ua,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unexpected {runtime_settings.llm_provider} error: {type(exc).__name__}",
            ) from exc

        latency_ms = int((perf_counter() - started) * 1000)
        effective_model = bot_model or runtime_settings.selected_model

        logger.info(
            "chat_ok ip=%s origin=%s bot_id=%s model=%s auth=%s latency_ms=%s ua=%s",
            client_ip, get_request_origin(request), bot_id, effective_model,
            auth.method, latency_ms, ua,
        )
        if is_dev:
            logger.debug(
                "chat_detail ip=%s bot_id=%s message=%s reply=%s history_len=%s",
                client_ip, bot_id,
                _truncate(payload.message, content_max),
                _truncate(reply, content_max),
                len(payload.history),
            )
            if chat_csv_logger:
                chat_csv_logger.info(_csv_row(
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    ip=client_ip,
                    bot_id=bot_id,
                    model=effective_model,
                    auth_method=auth.method,
                    message=payload.message,
                    reply=reply,
                    history_len=len(payload.history),
                    latency_ms=latency_ms,
                    user_agent=ua,
                ))

        return ChatResponse(reply=reply, model=effective_model, latency_ms=latency_ms)

    _embed_js_path = Path(settings.embed_js_path)
    if not _embed_js_path.is_absolute():
        _embed_js_path = Path(__file__).parent.parent / _embed_js_path

    # Cache content+ETag at startup in prod; re-read on every request in dev
    _embed_js_cache: dict[str, bytes | str] = {}

    def _load_embed_js() -> tuple[bytes, str]:
        content = _embed_js_path.read_bytes()
        etag = '"' + hashlib.sha256(content).hexdigest()[:16] + '"'
        return content, etag

    if not is_dev:
        _content, _etag = _load_embed_js()
        _embed_js_cache["content"] = _content
        _embed_js_cache["etag"] = _etag

    @app.get("/embed/v1/embed.js", include_in_schema=False)
    async def serve_embed_js(request: Request) -> Response:
        if is_dev:
            content, etag = _load_embed_js()
        else:
            content = _embed_js_cache["content"]
            etag = _embed_js_cache["etag"]

        cache_control = "no-cache" if is_dev else "public, max-age=300, must-revalidate"

        if request.headers.get("if-none-match") == etag:
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": cache_control},
            )

        return Response(
            content=content,
            media_type="application/javascript; charset=utf-8",
            headers={
                "ETag": etag,
                "Cache-Control": cache_control,
                "X-Content-Type-Options": "nosniff",
            },
        )

    return app


app = create_app()
