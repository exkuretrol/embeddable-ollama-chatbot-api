import base64
from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import hmac
import json
import logging
from time import monotonic
from time import time
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, limit_per_minute: int):
        self._limit = max(1, limit_per_minute)
        self._bucket: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = monotonic()
        window_start = now - 60.0
        timestamps = self._bucket[key]

        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        if len(timestamps) >= self._limit:
            return False

        timestamps.append(now)
        return True


class EmbedTokenManager:
    def __init__(self, secret: str, ttl_seconds: int):
        self._secret = secret.encode("utf-8")
        self._ttl = ttl_seconds

    def issue(self, chatbot_id: str, origin: str) -> tuple[str, int]:
        expires_at = int(time()) + self._ttl
        payload = {
            "sub": chatbot_id,
            "org": normalize_origin(origin),
            "exp": expires_at,
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        payload_b64 = self._b64_encode(payload_bytes)
        signature = self._sign(payload_b64)
        token = f"{payload_b64}.{signature}"
        return token, self._ttl

    def verify(self, token: str, request_origin: str | None) -> dict[str, str | int] | None:
        if not token or "." not in token:
            return None

        payload_b64, signature = token.split(".", maxsplit=1)
        expected_signature = self._sign(payload_b64)
        if not hmac.compare_digest(signature, expected_signature):
            return None

        try:
            payload_raw = self._b64_decode(payload_b64)
            payload = json.loads(payload_raw)
        except Exception:
            return None

        if not isinstance(payload, dict):
            return None

        exp = payload.get("exp")
        origin = payload.get("org")
        chatbot_id = payload.get("sub")
        if not isinstance(exp, int) or not isinstance(origin, str) or not isinstance(chatbot_id, str):
            return None

        if exp < int(time()):
            return None

        normalized_origin = normalize_origin(request_origin)
        if not normalized_origin or normalize_origin(origin) != normalized_origin:
            return None

        return {
            "sub": chatbot_id,
            "org": normalize_origin(origin) or "",
            "exp": exp,
        }

    def _sign(self, payload_b64: str) -> str:
        digest = hmac.new(self._secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
        return self._b64_encode(digest)

    @staticmethod
    def _b64_encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")

    @staticmethod
    def _b64_decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first = forwarded_for.split(",", maxsplit=1)[0].strip()
        if first:
            return first

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def normalize_origin(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".lower()


def get_request_origin(request: Request) -> str | None:
    return normalize_origin(request.headers.get("origin"))


def origin_allowed(origin: str | None, settings: Settings) -> bool:
    if not origin:
        return False
    allowed = {normalize_origin(item) for item in settings.allowed_origins}
    return origin in allowed


def require_api_key(request: Request, settings: Settings = Depends(get_settings)) -> None:
    provided = request.headers.get("x-api-key")
    if provided != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: missing or invalid API key",
        )


@dataclass
class ChatAuthContext:
    method: str
    chatbot_id: str | None = None
    origin: str | None = None


def require_chat_auth(request: Request, settings: Settings = Depends(get_settings)) -> ChatAuthContext:
    provided = request.headers.get("x-api-key")
    if provided == settings.api_key:
        return ChatAuthContext(method="api_key")

    token = request.headers.get("x-embed-token")
    origin = get_request_origin(request)
    manager = EmbedTokenManager(settings.embed_token_secret, settings.embed_token_ttl_seconds)
    if token:
        claims = manager.verify(token, origin)
        if claims:
            return ChatAuthContext(
                method="embed_token",
                chatbot_id=str(claims["sub"]),
                origin=str(claims["org"]),
            )

    logger.warning(
        "chat_auth_failed ip=%s origin=%s has_api_key=%s has_embed_token=%s",
        get_client_ip(request),
        origin,
        bool(provided),
        bool(token),
    )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: missing or invalid API key or embed token",
    )
