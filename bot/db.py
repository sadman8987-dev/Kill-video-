"""SQLite storage (stdlib only). Runs queries in a worker thread so the event loop never blocks."""
from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY,
  username TEXT,
  first_name TEXT,
  lang TEXT NOT NULL DEFAULT 'ar',
  default_quality TEXT NOT NULL DEFAULT 'ask',
  banned INTEGER NOT NULL DEFAULT 0,
  joined_at INTEGER NOT NULL,
  last_seen INTEGER NOT NULL,
  downloads INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS downloads(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  url TEXT, title TEXT, mode TEXT, quality TEXT, size INTEGER,
  ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_downloads_user_ts ON downloads(user_id, ts);
CREATE TABLE IF NOT EXISTS file_cache(
  key TEXT PRIMARY KEY,
  file_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  ts INTEGER NOT NULL
);
"""


def day_start(now: float | None = None) -> int:
    return int(now or time.time()) // 86400 * 86400


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    # ---- low level -------------------------------------------------
    def _exec(self, sql: str, params: tuple = (), fetch: str | None = None):
        with self._lock:
            cur = self._conn.execute(sql, params)
            result = None
            if fetch == "one":
                row = cur.fetchone()
                result = dict(row) if row else None
            elif fetch == "all":
                result = [dict(r) for r in cur.fetchall()]
            elif fetch == "scalar":
                row = cur.fetchone()
                result = row[0] if row else None
            self._conn.commit()
            return result

    async def _a(self, sql: str, params: tuple = (), fetch: str | None = None):
        return await asyncio.to_thread(self._exec, sql, params, fetch)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- users -----------------------------------------------------
    async def upsert_user(self, uid: int, username: str | None, first_name: str | None, default_lang: str) -> dict:
        now = int(time.time())
        await self._a(
            "INSERT INTO users(id, username, first_name, lang, joined_at, last_seen) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET username=excluded.username, "
            "first_name=excluded.first_name, last_seen=excluded.last_seen",
            (uid, username, first_name, default_lang, now, now),
        )
        return await self.get_user(uid)  # type: ignore[return-value]

    async def get_user(self, uid: int) -> dict | None:
        return await self._a("SELECT * FROM users WHERE id=?", (uid,), "one")

    async def set_lang(self, uid: int, lang: str) -> None:
        await self._a("UPDATE users SET lang=? WHERE id=?", (lang, uid))

    async def set_quality(self, uid: int, quality: str) -> None:
        await self._a("UPDATE users SET default_quality=? WHERE id=?", (quality, uid))

    async def set_banned(self, uid: int, banned: bool) -> bool:
        await self._a("UPDATE users SET banned=? WHERE id=?", (1 if banned else 0, uid))
        user = await self.get_user(uid)
        return bool(user)

    async def all_user_ids(self) -> list[int]:
        rows = await self._a("SELECT id FROM users WHERE banned=0", (), "all")
        return [r["id"] for r in rows]

    # ---- downloads -------------------------------------------------
    async def log_download(self, uid: int, url: str, title: str, mode: str, quality: str, size: int) -> None:
        await self._a(
            "INSERT INTO downloads(user_id, url, title, mode, quality, size, ts) VALUES(?,?,?,?,?,?,?)",
            (uid, url, title, mode, quality, size, int(time.time())),
        )
        await self._a("UPDATE users SET downloads=downloads+1 WHERE id=?", (uid,))

    async def count_downloads_today(self, uid: int) -> int:
        n = await self._a(
            "SELECT COUNT(*) FROM downloads WHERE user_id=? AND ts>=?", (uid, day_start()), "scalar"
        )
        return int(n or 0)

    # ---- file_id cache --------------------------------------------
    async def cache_get(self, key: str) -> dict | None:
        return await self._a("SELECT file_id, kind FROM file_cache WHERE key=?", (key,), "one")

    async def cache_put(self, key: str, file_id: str, kind: str) -> None:
        await self._a(
            "INSERT INTO file_cache(key, file_id, kind, ts) VALUES(?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET file_id=excluded.file_id, kind=excluded.kind, ts=excluded.ts",
            (key, file_id, kind, int(time.time())),
        )

    async def cache_delete(self, key: str) -> None:
        await self._a("DELETE FROM file_cache WHERE key=?", (key,))

    async def cache_clear(self) -> int:
        n = await self._a("SELECT COUNT(*) FROM file_cache", (), "scalar")
        await self._a("DELETE FROM file_cache")
        return int(n or 0)

    # ---- stats -----------------------------------------------------
    async def stats(self) -> dict:
        ds = day_start()
        q = {
            "users": "SELECT COUNT(*) FROM users",
            "banned": "SELECT COUNT(*) FROM users WHERE banned=1",
            "active_today": f"SELECT COUNT(*) FROM users WHERE last_seen>={ds}",
            "new_today": f"SELECT COUNT(*) FROM users WHERE joined_at>={ds}",
            "downloads": "SELECT COUNT(*) FROM downloads",
            "downloads_today": f"SELECT COUNT(*) FROM downloads WHERE ts>={ds}",
            "cached_files": "SELECT COUNT(*) FROM file_cache",
        }
        return {k: int(await self._a(sql, (), "scalar") or 0) for k, sql in q.items()}