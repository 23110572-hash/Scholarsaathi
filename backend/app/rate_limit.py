from collections import deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

_AI_WINDOW_SECONDS = 60.0
_AI_MAX_REQUESTS = 12
_REGISTRATION_WINDOW_SECONDS = 900.0
_REGISTRATION_MAX_REQUESTS = 5
_MAX_TRACKED_CLIENTS = 4096
_ai_requests: dict[str, deque[float]] = {}
_registration_requests: dict[str, deque[float]] = {}
_lock = Lock()


def _client_key(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if peer in {"127.0.0.1", "::1", "testclient"}:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded
    return peer


def _require_capacity(
    request: Request,
    requests: dict[str, deque[float]],
    window_seconds: float,
    max_requests: int,
    message: str,
) -> None:
    now = monotonic()
    cutoff = now - window_seconds
    key = _client_key(request)

    with _lock:
        bucket = requests.setdefault(key, deque())
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= max_requests:
            retry_after = max(1, ceil(window_seconds - (now - bucket[0])))
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                message,
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        if len(requests) > _MAX_TRACKED_CLIENTS:
            stale_keys = [
                client_key
                for client_key, attempts in requests.items()
                if not attempts or attempts[-1] <= cutoff
            ]
            for stale_key in stale_keys:
                requests.pop(stale_key, None)


def require_public_ai_capacity(request: Request) -> None:
    _require_capacity(
        request,
        _ai_requests,
        _AI_WINDOW_SECONDS,
        _AI_MAX_REQUESTS,
        "Too many questions. Please wait before trying again.",
    )


def require_student_registration_capacity(request: Request) -> None:
    _require_capacity(
        request,
        _registration_requests,
        _REGISTRATION_WINDOW_SECONDS,
        _REGISTRATION_MAX_REQUESTS,
        "Too many account creation attempts. Please wait before trying again.",
    )
