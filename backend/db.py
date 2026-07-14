"""Async OceanBase (MySQL-wire) access via asyncmy. Use %s placeholders, never $1."""
from urllib.parse import unquote, urlparse

import asyncmy
from asyncmy.cursors import DictCursor

import config

_pool = None


def _dsn() -> dict:
    # DATABASE_URL looks like: mysql://user%40tenant:password@host:2881/dbname
    u = urlparse(config.DATABASE_URL)
    return {
        "host": u.hostname,
        "port": u.port or 2881,
        "user": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "db": (u.path or "/").lstrip("/"),
    }


async def init_pool():
    global _pool
    if config.DATABASE_URL and _pool is None:
        _pool = await asyncmy.create_pool(autocommit=True, **_dsn())
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


def available() -> bool:
    return _pool is not None


async def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    async with _pool.acquire() as conn, conn.cursor(cursor=DictCursor) as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    async with _pool.acquire() as conn, conn.cursor(cursor=DictCursor) as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def execute(sql: str, params: tuple = ()) -> int:
    """Run a write; return lastrowid (0 if none)."""
    async with _pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return cur.lastrowid or 0
