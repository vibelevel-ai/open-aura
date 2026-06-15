"""Slim Postgres connection-pool primitives for Open Aura.

Vendored from the VibeLevel backend — ONLY the pool management the Aura MCP +
scoring/profile services need: get_pool · get_conn_with_retry · close_pool ·
test_database_connection. Backed by a psycopg2 SimpleConnectionPool over
``config.get_database_url()`` (set POSTGRES_URL in your .env; see .env.example).
"""
from __future__ import annotations

import logging
from typing import Optional

import psycopg2
from psycopg2.pool import SimpleConnectionPool

from .config import config

logger = logging.getLogger(__name__)

POSTGRES_URL = config.get_database_url()
logger.info("[Database] Using %s environment", config.environment)

_pool: Optional[SimpleConnectionPool] = None


def _create_pool() -> None:
    """Create (or recreate) the connection pool."""
    global _pool
    if _pool:
        try:
            _pool.closeall()
        except Exception:
            pass
    logger.info("[Database] Creating connection pool")
    _pool = SimpleConnectionPool(1, 20, POSTGRES_URL)
    logger.info("[Database] Connection pool created")


def get_pool() -> SimpleConnectionPool:
    """Get or lazily create the pool."""
    global _pool
    if _pool is None or _pool.closed:
        _create_pool()
    return _pool


def get_conn_with_retry():
    """Return ``(pool, conn)`` — caller MUST ``pool.putconn(conn)`` when done.

    Retries once on a stale connection (Neon/managed Postgres drop idle SSL
    connections); validates with a lightweight ``SELECT 1`` and recreates the
    pool if the connection is dead.
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return pool, conn
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        logger.warning("[Database] Stale connection detected; recreating pool")
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        _create_pool()
        pool = get_pool()
        return pool, pool.getconn()


def test_database_connection() -> bool:
    """True if a trivial query succeeds — used by the app's startup check."""
    try:
        pool = get_pool()
        conn = pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        pool.putconn(conn)
        logger.info("[Database] connection OK")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("[Database] connection FAILED: %s", e)
        return False


def close_pool() -> None:
    """Close the pool (app shutdown)."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        logger.info("[Database] pool closed")
