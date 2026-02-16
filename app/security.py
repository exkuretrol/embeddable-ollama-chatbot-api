from collections import defaultdict, deque
from time import monotonic

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings


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


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first = forwarded_for.split(",", maxsplit=1)[0].strip()
        if first:
            return first

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def require_api_key(request: Request, settings: Settings = Depends(get_settings)) -> None:
    provided = request.headers.get("x-api-key")
    if provided != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: missing or invalid API key",
        )
