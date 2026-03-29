from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import urlparse


def normalize_origin(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".lower()


class BotRegistryStore:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def init_schema(self) -> None:
        path = Path(self._db_path)
        if path.parent and str(path.parent) not in {".", ""}:
            path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bots (
                    bot_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_allowed_origins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(bot_id, origin),
                    FOREIGN KEY(bot_id) REFERENCES bots(bot_id)
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def is_bot_active(self, bot_id: str) -> bool:
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT status FROM bots WHERE bot_id = ?",
                (bot_id,),
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return False
        status = row[0]
        return isinstance(status, str) and status == "active"

    def is_origin_allowed(self, bot_id: str, origin: str | None) -> bool:
        normalized = normalize_origin(origin)
        if not normalized:
            return False

        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                """
                SELECT 1
                FROM bot_allowed_origins o
                JOIN bots b ON b.bot_id = o.bot_id
                WHERE o.bot_id = ?
                  AND o.origin = ?
                  AND o.status = 'active'
                  AND b.status = 'active'
                LIMIT 1
                """,
                (bot_id, normalized),
            ).fetchone()
        finally:
            conn.close()

        return bool(row)
