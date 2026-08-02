"""VibeLevel Aura — standalone MCP sidecar entrypoint.

This is the OWN process for the Aura MCP connector. It is deployed as a
standalone app with its own FastMCP session-manager lifespan wiring.

Run it with uvicorn:

    uvicorn aura_mcp_app:app --host 0.0.0.0 --port 8090

(or ``python aura_mcp_app.py`` which calls uvicorn for you).

What this wires:
  - builds the FastMCP streamable-HTTP sub-app (``mcp.streamable_http_app()``),
  - applies ``PATAuthMiddleware`` to it (bearer-PAT on POST; GET open for
    discovery),
  - starts ``mcp.session_manager`` in the FastAPI lifespan — mounting a
    Starlette sub-app onto FastAPI does NOT propagate the sub-app's lifespan,
    so the session manager must be started here or every ``/mcp/`` request 500s,
  - exposes ``/health`` for health checks,
  - mounts the MCP app at ``/mcp`` (so the JSON-RPC endpoint is ``/mcp/``),
  - rewrites ``/mcp`` -> ``/mcp/`` so Starlette's mount 307-redirect doesn't
    strip the POST body from MCP clients.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv

# Load .env.<APP_ENV> BEFORE importing src.* (config reads env at import time).
# Production injects env vars directly; this loads them for local dev so
# `python aura_mcp_app.py` sees POSTGRES_URL / AURA_PAT_HASH_SECRET.
_env = os.getenv("APP_ENV", "local")
_env_file = {"local": ".env.local", "preview": ".env.preview",
             "production": ".env.prod", "prod": ".env.prod"}.get(_env, ".env")
_env_path = Path(__file__).parent / _env_file
if _env_path.exists():
    load_dotenv(_env_path, override=False)

from src.aura_mcp.pat_auth import PATAuthMiddleware
from src.aura_mcp.server import mcp as mcp_server
from src.core.config import config
from src.core.database_sync import close_pool, get_pool, test_database_connection
from src.core.model_config import init_model_config
from src.services.aura.pfg_client import pfg_status

# Backend version (keep in sync with package.json) + a build label so you can tell
# WHICH build is running. Override the label per build/branch via AURA_BUILD.
__version__ = "0.1.0"
_BUILD = os.getenv("AURA_BUILD", "pfg-insights-poc")

def _configure_logging() -> None:
    """Central log-verbosity control for the sidecar.

    All knobs are optional env vars taking a standard level name
    (DEBUG/INFO/WARNING/ERROR). Framework noise is quieted by DEFAULT; turn an
    individual source back up when you need it:

      AURA_LOG_LEVEL          root level                              (default INFO)
      AURA_APP_LOG_LEVEL      our own ``[AURA-*]`` logs (``src.*``)   (default INFO;
                              set DEBUG to see the per-session scoring trace)
      AURA_MCP_SDK_LOG_LEVEL  MCP SDK chatter ("Processing request",
                              "Terminating session")                  (default WARNING)
      AURA_HTTPX_LOG_LEVEL    httpx "HTTP Request: POST ..." lines    (default WARNING)
      AURA_ACCESS_LOG_LEVEL   uvicorn per-request access log          (default WARNING = off)
      AURA_SSE_LOG_LEVEL      sse_starlette keep-alive "ping:" spam   (default WARNING)

    Prefer raising AURA_APP_LOG_LEVEL (our `src.*` trace) over AURA_LOG_LEVEL:
    root=DEBUG turns on EVERY third-party library's DEBUG (sse_starlette pings,
    anyio, etc.), whereas app=DEBUG gives just our scoring trace. Our `src`
    logger is set explicitly, and basicConfig's handler is unfiltered, so the
    app trace still emits even with root at INFO.
    """
    def lvl(env: str, default: str) -> str:
        return os.environ.get(env, default).upper()

    root = lvl("AURA_LOG_LEVEL", "INFO")
    logging.basicConfig(level=root)
    # basicConfig no-ops if a handler already exists (e.g. uvicorn installed one
    # first), so set the root level explicitly too.
    logging.getLogger().setLevel(root)

    # Quiet third-party / framework loggers by default. These have NO explicit
    # level otherwise, so they'd inherit root — and at root=DEBUG, sse_starlette
    # floods the log with a keep-alive ping every ~15s. Pin them independently so
    # they stay quiet regardless of the root level.
    logging.getLogger("mcp").setLevel(lvl("AURA_MCP_SDK_LOG_LEVEL", "WARNING"))
    logging.getLogger("httpx").setLevel(lvl("AURA_HTTPX_LOG_LEVEL", "WARNING"))
    logging.getLogger("uvicorn.access").setLevel(lvl("AURA_ACCESS_LOG_LEVEL", "WARNING"))
    logging.getLogger("sse_starlette").setLevel(lvl("AURA_SSE_LOG_LEVEL", "WARNING"))

    # Our own Aura logs live under the `src` package; independent knob.
    logging.getLogger("src").setLevel(lvl("AURA_APP_LOG_LEVEL", "INFO"))


_configure_logging()
logger = logging.getLogger(__name__)

# Path the MCP app is mounted at (so JSON-RPC lives at f"/{MOUNT}/").
MCP_MOUNT = os.environ.get("AURA_MCP_MOUNT", "mcp").strip("/")
_MOUNT_PATH = f"/{MCP_MOUNT}"


def create_app() -> FastAPI:
    # Fail fast if the PAT hashing secret is missing in production. Otherwise
    # pat_auth._hash_secret() silently falls back to the DB URL, and EVERY token
    # breaks if that URL ever rotates. Local/preview keep the dev fallback.
    if config.environment in ("production", "prod") and not os.environ.get(
        "AURA_PAT_HASH_SECRET"
    ):
        raise RuntimeError(
            "AURA_PAT_HASH_SECRET must be set in production (refusing to fall "
            "back to the database URL for PAT hashing)."
        )

    # Initialize the model-config registry (provider routing for the SHARED LLM
    # client). Without this the registry is empty and EVERY model falls back to
    # the OpenAI provider — which is why a Groq-namespaced scoring model like
    # ``openai/gpt-oss-120b`` 400s against api.openai.com. The main API does this
    # in app.py startup; the sidecar is a separate process and must do it too.
    _cfg = Path(__file__).parent / "model_config.json"
    if not _cfg.exists():
        raise FileNotFoundError(f"Required model configuration file not found: {_cfg}")
    init_model_config(str(_cfg))
    logger.info("[AuraMCP] model configuration initialized (%s)", _cfg.name)

    # Build the MCP sub-app FIRST — ``streamable_http_app()`` lazily creates
    # ``mcp_server.session_manager``, which the lifespan below must start.
    mcp_app = mcp_server.streamable_http_app()
    mcp_app.add_middleware(PATAuthMiddleware)

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        logger.info("[AuraMCP] starting (env=%s, mount=%s)", config.environment, _MOUNT_PATH)
        logger.info("[Open Aura] backend v%s · build=%s", __version__, _BUILD)
        # PFG operational insights — surface ON/OFF + reachability so the user
        # knows at a glance whether grounding is wired. Best-effort; never blocks.
        try:
            ps = pfg_status(probe=True)
            if not ps["enabled"]:
                logger.info("[Open Aura] PFG insights: OFF "
                            "(set PFG_GROUNDING_ENABLED=true to enable)")
            elif not ps["configured"]:
                logger.warning("[Open Aura] PFG insights: ON but NOT configured "
                               "— PFG_MCP_URL is empty")
            else:
                reach = ("reachable ✓" if ps["reachable"]
                         else "UNREACHABLE ✗ (check PFG_MCP_URL/PFG_MCP_TOKEN)")
                logger.info("[Open Aura] PFG insights: ON · %s · ws=%s · %s · "
                            "extract-LLM=%s", ps["host"], ps["workspace"], reach,
                            "on" if ps["extract_llm"] else "off")
        except Exception as exc:
            logger.debug("[Open Aura] PFG status line skipped: %s", exc)
        # Warm the shared psycopg2 pool and fail fast if the DB is unreachable.
        get_pool()
        if not test_database_connection():
            logger.error("[AuraMCP] database connection check FAILED at startup")
        try:
            # Start the FastMCP streamable-HTTP session manager for this process.
            async with mcp_server.session_manager.run():
                yield
        finally:
            logger.info("[AuraMCP] shutting down")
            close_pool()

    app = FastAPI(
        title="VibeLevel Aura MCP",
        description=(
            "Standalone MCP connector for Open Aura. Agents score real local "
            "AI work sessions — single local user, no login."
        ),
        version="0.1.0",
        lifespan=_lifespan,
    )

    # CORS: reuse the env-driven origins from the shared config. Browser clients
    # aren't the primary caller (agents are), but the one-click Connect card and
    # any web discovery benefit from correct CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"ok": True, "service": "vibelevel-aura-mcp", "env": config.environment}

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {
            "name": app.title,
            "version": app.version,
            "mcp": _MOUNT_PATH,
            "health": "/health",
            "api": "/api/aura",
        }

    # REST endpoints for the web viewer (profile / session / leaderboard). Same
    # contract the hosted SaaS serves; the shared Aura UI consumes it.
    from src.api.aura_endpoints import router as aura_router

    app.include_router(aura_router, prefix="/api/aura")

    # Header-config clients like Claude Code / Cursor send the PAT directly, and
    # local mode needs no auth.

    # Mount the MCP HTTP transport. ``mcp_app`` was built above so the session
    # manager exists in time for ``_lifespan`` to start it.
    app.mount(_MOUNT_PATH, mcp_app)

    # Starlette's mount() 307-redirects "/mcp" -> "/mcp/", which makes MCP
    # clients lose the POST body on redirect. Rewrite the path before the
    # router sees it.
    class _MCPSlashRewrite:
        def __init__(self, asgi_app):
            self.app = asgi_app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http" and scope.get("path") == _MOUNT_PATH:
                scope = dict(scope, path=_MOUNT_PATH + "/")
            await self.app(scope, receive, send)

    app.add_middleware(_MCPSlashRewrite)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    # Access log follows AURA_ACCESS_LOG_LEVEL (default WARNING => off). uvicorn
    # reconfigures its own loggers on start, so the access log is controlled here
    # rather than via setLevel (which it would override on this path).
    _access_on = os.environ.get("AURA_ACCESS_LOG_LEVEL", "WARNING").upper() in (
        "INFO", "DEBUG", "NOTSET",
    )
    uvicorn.run(
        "aura_mcp_app:app",
        host=os.environ.get("AURA_MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("AURA_MCP_PORT", "8090")),
        reload=bool(os.environ.get("AURA_MCP_RELOAD")),
        access_log=_access_on,
    )
