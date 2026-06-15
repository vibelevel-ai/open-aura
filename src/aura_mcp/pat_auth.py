"""VibeLevel Aura — Personal Access Token auth (mint, hash, verify, middleware).

Agents (Claude Code / Cursor / Claude Desktop) call the Aura MCP server as a
separate local process with NO browser cookie, so the monolith's only existing
auth — header-trust from the Next.js proxy (``src/core/auth.py``) — is unusable
here. PAT auth is therefore net-new.

Design (decision #9 one-click PAT, §7 of the connector spec) mirrors the proven
PFG pattern (``project_pfg/src/auth/pat.py`` + ``middleware.py``), adapted to:
  - our ``"AuraPersonalAccessToken"`` table (migrations/add_aura_tables.sql),
  - the ``aura_`` token prefix,
  - the repo's SYNCHRONOUS psycopg2 pool (``src/core/database_sync.py``) rather
    than PFG's async SQLAlchemy,
  - a ``current_user_id()`` contextvar the MCP tools read to resolve the caller.

Token format: ``aura_<43-char-base62-random>``. We store HMAC-SHA256 (hex) of
the raw token, keyed by an env secret — plain sha256 would also work but HMAC
prevents lookup-by-rainbow-table even if ``token_hash`` leaks. The raw token is
shown to the user exactly ONCE (at mint) and never persisted.

Lifecycle:
    generate_pat(user_id, name)  -> {"raw", "prefix", "id"}   # mint + persist
    hash_token(raw)              -> hex str (stored in token_hash)
    verify_pat(raw)              -> user_id str | None         # active-token lookup
    PATAuthMiddleware            -> verifies bearer on POST, sets contextvar
"""
from __future__ import annotations

import contextvars
import hashlib
import hmac
import logging
import os
import secrets
import string
import uuid
from typing import Awaitable, Callable, Optional

from psycopg2.extras import RealDictCursor
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from ..core.config import config
from ..core.database_sync import get_conn_with_retry, get_pool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config / constants
# ---------------------------------------------------------------------------

PAT_PREFIX = "aura_"
_RAW_TAIL_LEN = 43                       # base62 random tail length
_ALPHABET = string.ascii_letters + string.digits   # base62
_TABLE = '"AuraPersonalAccessToken"'

# Local mode (Open Aura self-host): no login / no PAT — bind a single fixed local
# user so the MCP works offline with zero auth setup. Default OFF so the hosted
# (multi-tenant) deployment keeps PAT auth; OSS opts in via AURA_LOCAL_MODE=true.
LOCAL_MODE = os.environ.get("AURA_LOCAL_MODE", "false").strip().lower() in (
    "1", "true", "yes", "on",
)
LOCAL_USER_ID = os.environ.get("AURA_LOCAL_USER_ID", "local")


def _hash_secret() -> bytes:
    """The HMAC key for hashing PATs.

    Read from the env (mirrors ``config.py``'s ``os.environ`` idiom so we don't
    have to edit the shared ``Config`` class). MUST be set and identical for
    every Aura MCP process so a token minted on one machine verifies on another.
    Falls back to ``POSTGRES_URL`` ONLY as a last resort for local dev, with a
    loud warning — never rely on that in production.
    """
    secret = os.environ.get("AURA_PAT_HASH_SECRET")
    if not secret:
        # Last-resort dev fallback: derive a stable-but-private key so local
        # runs work without extra setup. Production MUST set the env var.
        secret = config.get_database_url()
        logger.warning(
            "[AuraPAT] AURA_PAT_HASH_SECRET not set — falling back to a derived "
            "dev key. Set AURA_PAT_HASH_SECRET in production or all tokens break "
            "if the database URL changes."
        )
    return secret.encode("utf-8")


# ---------------------------------------------------------------------------
# Caller identity (contextvar) — set by the middleware, read by the MCP tools
# ---------------------------------------------------------------------------

_current_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "aura_current_user_id", default=None
)


def set_current_user_id(user_id: str) -> contextvars.Token:
    """Bind the resolved caller for the duration of one request. Returns a
    token the middleware resets in a ``finally`` so concurrent requests on the
    same event loop don't bleed identity."""
    return _current_user_id.set(user_id)


def reset_current_user_id(token: contextvars.Token) -> None:
    _current_user_id.reset(token)


def current_user_id() -> str:
    """Return the authenticated caller's ``"User".id`` for the current request.

    Raises ``RuntimeError`` if called outside an authenticated request — every
    MCP tool relies on this, so an unset value is a programming/auth error, not
    a recoverable state.
    """
    uid = _current_user_id.get()
    if uid is None:
        raise RuntimeError(
            "No Aura auth context — the request was not authenticated by "
            "PATAuthMiddleware (or a tool was invoked outside a request)."
        )
    return uid


def current_user_id_optional() -> Optional[str]:
    return _current_user_id.get()


# ---------------------------------------------------------------------------
# Mint / hash
# ---------------------------------------------------------------------------

def _random_tail(n: int = _RAW_TAIL_LEN) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def hash_token(raw: str) -> str:
    """HMAC-SHA256 of the raw token, hex-encoded. Stable across processes
    given the same ``AURA_PAT_HASH_SECRET``."""
    return hmac.new(_hash_secret(), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_pat(user_id: str, name: str = "Default") -> dict:
    """Mint a fresh PAT for ``user_id`` and persist its hash.

    Returns ``{"raw", "prefix", "id"}``:
      - ``raw``    — the full ``aura_...`` token. Show to the user ONCE; it is
                     never stored and cannot be recovered.
      - ``prefix`` — ``aura_`` + first 6 chars of the random tail, for UI
                     display in the token list (matches the migration's example
                     ``'aura_ab12cd'`` and the ``VARCHAR(16)`` prefix column).
      - ``id``     — the ``"AuraPersonalAccessToken".id`` (UUID) for rename/revoke.

    The DB stores only the HMAC hash + prefix + metadata, never the raw token.
    This is the one-click-Connect mint path (decision #9): the web "Connect your
    agent" card calls this, embeds ``raw`` in a copy-paste MCP config, and shows
    the prefix thereafter.
    """
    raw = f"{PAT_PREFIX}{_random_tail()}"
    token_hash = hash_token(raw)
    prefix = raw[: len(PAT_PREFIX) + 6]   # e.g. 'aura_ab12cd' -> fits VARCHAR(16)
    token_id = str(uuid.uuid4())

    pool, conn = get_conn_with_retry()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                INSERT INTO {_TABLE} (id, user_id, name, token_hash, prefix)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, prefix
                """,
                (token_id, user_id, name, token_hash, prefix),
            )
            row = cur.fetchone()
            conn.commit()
            logger.info(
                "[AuraPAT] minted token id=%s prefix=%s for user=%s name=%r",
                row["id"], row["prefix"], user_id, name,
            )
            return {"raw": raw, "prefix": row["prefix"], "id": str(row["id"])}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("[AuraPAT] failed to mint token for user=%s", user_id)
        raise
    finally:
        pool.putconn(conn)


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def verify_pat(raw: str) -> Optional[str]:
    """Resolve a raw PAT to its ``"User".id``, or ``None`` if invalid.

    Active token = a row whose ``token_hash`` matches, that is NOT revoked
    (``revoked_at IS NULL``) and NOT expired (``expires_at IS NULL OR
    expires_at > now()``). On a successful lookup we best-effort touch
    ``last_used_at`` (a failed touch does NOT fail the auth).
    """
    if not raw or not raw.startswith(PAT_PREFIX):
        return None

    digest = hash_token(raw)
    pool, conn = get_conn_with_retry()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT id, user_id
                FROM {_TABLE}
                WHERE token_hash = %s
                  AND revoked_at IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                LIMIT 1
                """,
                (digest,),
            )
            row = cur.fetchone()
            if row is None:
                conn.commit()  # release any read snapshot
                return None

            # Best-effort touch of last_used_at; never fail auth on this.
            try:
                cur.execute(
                    f'UPDATE {_TABLE} SET last_used_at = NOW() WHERE id = %s',
                    (row["id"],),
                )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.debug("[AuraPAT] last_used_at touch failed (non-fatal)", exc_info=True)

            return str(row["user_id"])
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("[AuraPAT] verify_pat lookup failed")
        return None
    finally:
        pool.putconn(conn)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class PATAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware on the mounted Aura MCP app (mirrors PFG's
    ``MCPPATAuthMiddleware``).

    - GET is allowed UNAUTHENTICATED so MCP clients can do server/capability
      discovery before a token is configured (matches PFG behaviour).
    - POST (every JSON-RPC tool invocation) REQUIRES a valid bearer PAT. On
      success we set ``current_user_id()`` for the request and reset it after.

    Notes:
      - ``verify_pat`` is synchronous (psycopg2). Calls are short and infrequent
        relative to the LLM-bound scoring work, so we call it inline; if it ever
        becomes hot, wrap it in ``anyio.to_thread.run_sync``.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable],
    ):
        # Discovery (GET) is open; tool calls (POST/others with a body) need auth.
        if request.method == "GET":
            return await call_next(request)

        # Local mode (Open Aura self-host): no PAT — bind the single local user.
        if LOCAL_MODE:
            ctx_token = set_current_user_id(LOCAL_USER_ID)
            try:
                return await call_next(request)
            finally:
                reset_current_user_id(ctx_token)

        authz = request.headers.get("authorization", "").strip()
        if not authz.lower().startswith("bearer ") or not authz[7:].strip():
            return JSONResponse(
                {
                    "error": "auth_required",
                    "message": (
                        "A VibeLevel Aura Personal Access Token (PAT) is required. "
                        "Create one from the 'Connect your agent' card in your "
                        "VibeLevel account, then pass it as: "
                        "Authorization: Bearer aura_..."
                    ),
                },
                status_code=401,
            )

        raw = authz[7:].strip()
        user_id = verify_pat(raw)
        if user_id is None:
            return JSONResponse(
                {
                    "error": "invalid_token",
                    "message": (
                        "The provided PAT is invalid, expired, or revoked. "
                        "Generate a new one from your VibeLevel account."
                    ),
                },
                status_code=401,
            )

        ctx_token = set_current_user_id(user_id)
        try:
            return await call_next(request)
        finally:
            reset_current_user_id(ctx_token)
