from collections import deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

_WINDOW_SECONDS = 60.0
_MAX_REQUESTS = 12
_MAX_TRACKED_CLIENTS = 4096
_requests: dict[str, deque[float]] = {}
_lock = Lock()


def _client_key(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if peer in {"127.0.0.1", "::1", "testclient"}:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded
    return peer


def require_public_ai_capacity(request: Request) -> None:
    now = monotonic()
    cutoff = now - _WINDOW_SECONDS
    key = _client_key(request)

    with _lock:
        bucket = _requests.setdefault(key, deque())
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= _MAX_REQUESTS:
            retry_after = max(1, ceil(_WINDOW_SECONDS - (now - bucket[0])))
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many questions. Please wait before trying again.",
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        if len(_requests) > _MAX_TRACKED_CLIENTS:
            stale_keys = [
                client_key
                for client_key, attempts in _requests.items()
                if not attempts or attempts[-1] <= cutoff
            ]
            for stale_key in stale_keys:
                _requests.pop(stale_key, None)
