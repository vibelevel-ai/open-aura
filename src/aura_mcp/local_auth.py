"""Open Aura — local single-user binding for the MCP server.

Open Aura is local-first: one user, no login, no tokens. A tiny Starlette
middleware binds a fixed local user id into a contextvar for each request, and
the MCP tools read it via ``current_user_id()``.
"""
from __future__ import annotations

import contextvars
import os
from typing import Awaitable, Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

# The single local user — matches the default row seeded by schema.sql.
LOCAL_USER_ID = os.environ.get("AURA_LOCAL_USER_ID", "local")


# ---------------------------------------------------------------------------
# Caller identity (contextvar) — set by the middleware, read by the MCP tools
# ---------------------------------------------------------------------------

_current_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "aura_current_user_id", default=None
)


def set_current_user_id(user_id: str) -> contextvars.Token:
    """Bind the caller for the duration of one request. Returns a token the
    middleware resets in a ``finally`` so concurrent requests don't bleed
    identity."""
    return _current_user_id.set(user_id)


def reset_current_user_id(token: contextvars.Token) -> None:
    _current_user_id.reset(token)


def current_user_id() -> str:
    """Return the local user's ``"User".id`` for the current request.

    Raises ``RuntimeError`` if called outside a request bound by
    ``LocalUserMiddleware`` — an unset value is a programming error.
    """
    uid = _current_user_id.get()
    if uid is None:
        raise RuntimeError(
            "No Aura user context — the request was not bound by "
            "LocalUserMiddleware (or a tool was invoked outside a request)."
        )
    return uid


def current_user_id_optional() -> Optional[str]:
    return _current_user_id.get()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class LocalUserMiddleware(BaseHTTPMiddleware):
    """Bind the single local user for each request. GET (capability discovery)
    is open and needs no bound user; tool calls (POST) run as the local user."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable],
    ):
        if request.method == "GET":
            return await call_next(request)
        ctx_token = set_current_user_id(LOCAL_USER_ID)
        try:
            return await call_next(request)
        finally:
            reset_current_user_id(ctx_token)
