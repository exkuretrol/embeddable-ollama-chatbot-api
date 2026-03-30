from __future__ import annotations

import secrets
import sqlite3
import sys
from datetime import datetime, timezone

from app.bot_registry import BotRegistryStore, normalize_origin
from app.config import get_settings


def _db_path() -> str:
    return get_settings().bot_registry_db_path


def _ensure_schema() -> str:
    path = _db_path()
    store = BotRegistryStore(path)
    store.init_schema()
    return path


def _generate_bot_id() -> str:
    return f"bot_{secrets.token_hex(4)}"


def _parse_origins(raw: str) -> list[str]:
    results = []
    for part in raw.split(","):
        normalized = normalize_origin(part.strip())
        if normalized:
            results.append(normalized)
        elif part.strip():
            print(f"  警告：忽略無效 origin「{part.strip()}」（需要 scheme://host 格式）")
    return results


def _prompt(label: str, default: str = "", required: bool = False) -> str:
    hint = f" [{default}]" if default else ""
    while True:
        value = input(f"  {label}{hint}: ").strip()
        if not value:
            if default:
                return default
            if required:
                print(f"  ✗ {label} 為必填")
                continue
        return value


def _fetch_bot(conn: sqlite3.Connection, bot_id: str) -> dict | None:
    row = conn.execute(
        "SELECT bot_id, name, status, model, created_at FROM bots WHERE bot_id = ?",
        (bot_id,),
    ).fetchone()
    if not row:
        return None
    origins = [
        r[0]
        for r in conn.execute(
            "SELECT origin FROM bot_allowed_origins WHERE bot_id = ? AND status = 'active' ORDER BY origin",
            (bot_id,),
        ).fetchall()
    ]
    return {
        "bot_id": row[0],
        "name": row[1],
        "status": row[2],
        "model": row[3] or "",
        "created_at": row[4],
        "origins": origins,
    }


def _print_bot(bot: dict) -> None:
    model_display = bot["model"] or "(env 預設)"
    origins_display = ", ".join(bot["origins"]) if bot["origins"] else "(無)"
    print(f"  Bot ID  : {bot['bot_id']}")
    print(f"  名稱    : {bot['name']}")
    print(f"  狀態    : {bot['status']}")
    print(f"  模型    : {model_display}")
    print(f"  Origins : {origins_display}")
    print(f"  建立時間: {bot['created_at']}")


# ── Commands ────────────────────────────────────────────────────────────────

def cmd_add() -> None:
    print("\n[ 新增 Bot ]\n")
    db = _ensure_schema()

    bot_id = _generate_bot_id()
    print(f"  自動產生 Bot ID：{bot_id}\n")

    name = _prompt("名稱", required=True)
    model = _prompt("模型（留空使用 env 預設）")
    origins_raw = _prompt("Allowed origins（逗號分隔，至少一個）", required=True)
    origins = _parse_origins(origins_raw)

    if not origins:
        print("\n  ✗ 未提供任何有效 origin，操作取消。")
        return

    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT INTO bots (bot_id, name, status, model) VALUES (?, ?, 'active', ?)",
            (bot_id, name, model or None),
        )
        for origin in origins:
            conn.execute(
                "INSERT INTO bot_allowed_origins (bot_id, origin, status) VALUES (?, ?, 'active')",
                (bot_id, origin),
            )
        conn.commit()
    finally:
        conn.close()

    print(f"\n  ✓ Bot 已新增\n")
    bot = _fetch_bot(sqlite3.connect(db), bot_id)
    if bot:
        _print_bot(bot)


def cmd_update() -> None:
    print("\n[ 修改 Bot ]\n")
    db = _ensure_schema()

    bot_id = _prompt("Bot ID", required=True)
    conn = sqlite3.connect(db)
    bot = _fetch_bot(conn, bot_id)
    conn.close()

    if not bot:
        print(f"\n  ✗ 找不到 Bot「{bot_id}」")
        return

    print("\n  目前資料：")
    _print_bot(bot)
    print("\n  （直接按 Enter 保留原值）\n")

    name = _prompt("名稱", default=bot["name"])
    model = _prompt("模型（留空清除覆寫，使用 env 預設）", default=bot["model"])
    status = _prompt("狀態（active / disabled）", default=bot["status"])
    origins_raw = _prompt(
        "Allowed origins（逗號分隔，留空保留原值）",
        default=",".join(bot["origins"]),
    )

    origins = _parse_origins(origins_raw) if origins_raw else bot["origins"]
    if not origins:
        print("\n  ✗ 未提供任何有效 origin，操作取消。")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "UPDATE bots SET name=?, status=?, model=?, updated_at=? WHERE bot_id=?",
            (name, status, model or None, now, bot_id),
        )
        conn.execute(
            "DELETE FROM bot_allowed_origins WHERE bot_id=?",
            (bot_id,),
        )
        for origin in origins:
            conn.execute(
                "INSERT INTO bot_allowed_origins (bot_id, origin, status) VALUES (?, ?, 'active')",
                (bot_id, origin),
            )
        conn.commit()
    finally:
        conn.close()

    print(f"\n  ✓ Bot 已更新\n")
    updated = _fetch_bot(sqlite3.connect(db), bot_id)
    if updated:
        _print_bot(updated)


def cmd_remove() -> None:
    print("\n[ 移除 Bot ]\n")
    db = _ensure_schema()

    bot_id = _prompt("Bot ID", required=True)
    conn = sqlite3.connect(db)
    bot = _fetch_bot(conn, bot_id)
    conn.close()

    if not bot:
        print(f"\n  ✗ 找不到 Bot「{bot_id}」")
        return

    print("\n  將刪除以下 Bot：")
    _print_bot(bot)
    confirm = input("\n  確認刪除？(y/N): ").strip().lower()
    if confirm != "y":
        print("  取消。")
        return

    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM bot_allowed_origins WHERE bot_id=?", (bot_id,))
        conn.execute("DELETE FROM bots WHERE bot_id=?", (bot_id,))
        conn.commit()
    finally:
        conn.close()

    print(f"\n  ✓ Bot「{bot_id}」已刪除。")


def cmd_list() -> None:
    db = _ensure_schema()

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            """
            SELECT b.bot_id, b.name, b.status, b.model, b.created_at,
                   GROUP_CONCAT(o.origin, ', ') AS origins
            FROM bots b
            LEFT JOIN bot_allowed_origins o
                   ON o.bot_id = b.bot_id AND o.status = 'active'
            GROUP BY b.bot_id
            ORDER BY b.created_at DESC
            """
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("\n  （資料庫中尚無 Bot）\n")
        return

    col_id     = max(len(r[0]) for r in rows)
    col_name   = max(len(r[1]) for r in rows)
    col_status = max(len(r[2]) for r in rows)
    col_model  = max(len(r[3] or "") for r in rows)

    col_id     = max(col_id, 6)
    col_name   = max(col_name, 4)
    col_status = max(col_status, 6)
    col_model  = max(col_model, 5)

    header = (
        f"  {'Bot ID':<{col_id}}  {'名稱':<{col_name}}  {'狀態':<{col_status}}"
        f"  {'模型':<{col_model}}  Origins"
    )
    print(f"\n{header}")
    print("  " + "-" * (len(header) - 2))

    for row in rows:
        bot_id, name, status, model, created_at, origins = row
        print(
            f"  {bot_id:<{col_id}}  {name:<{col_name}}  {status:<{col_status}}"
            f"  {(model or ''):<{col_model}}  {origins or '(無)'}"
        )
    print()


# ── Entry point ──────────────────────────────────────────────────────────────

COMMANDS = {
    "add": cmd_add,
    "update": cmd_update,
    "remove": cmd_remove,
    "list": cmd_list,
}

USAGE = """\
使用方式：manage-bots <指令>

指令：
  add      新增 Bot（自動產生 bot_id）
  update   修改現有 Bot
  remove   移除 Bot
  list     列出所有 Bot
"""


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in COMMANDS:
        print(USAGE)
        sys.exit(0 if not args else 1)
    try:
        COMMANDS[args[0]]()
    except (KeyboardInterrupt, EOFError):
        print("\n  中止。")
        sys.exit(0)
