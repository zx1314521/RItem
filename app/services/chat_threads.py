import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from app.common.logger import logger


DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")
DB_PATH = os.path.join(DB_DIR, "remember_item.db")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_chat_threads_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                thread_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, thread_id)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_threads_user_updated
            ON chat_threads(user_id, updated_at)
            """
        )


def _row_to_thread(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "thread_id": row["thread_id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _normalize_title(title: str | None) -> str:
    if not title:
        return "新对话"
    cleaned = " ".join(title.strip().split())
    if not cleaned:
        return "新对话"
    return cleaned[:80]


def title_from_message(message: str, image_url: str | None = None) -> str:
    if message and message.strip():
        return _normalize_title(message)[:32]
    if image_url:
        return "图片对话"
    return "新对话"


def create_thread(user_id: int, title: str | None = None) -> dict[str, Any]:
    thread_id = uuid.uuid4().hex
    now = _utc_now()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO chat_threads (user_id, thread_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, thread_id, _normalize_title(title), now, now),
        )
        row = connection.execute(
            """
            SELECT * FROM chat_threads
            WHERE user_id = ? AND thread_id = ?
            """,
            (user_id, thread_id),
        ).fetchone()
    logger.info("Chat thread created: user_id=%s thread_id=%s", user_id, thread_id)
    return _row_to_thread(row)


def ensure_thread(
    user_id: int,
    thread_id: str,
    title: str | None = None,
) -> dict[str, Any]:
    now = _utc_now()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM chat_threads
            WHERE user_id = ? AND thread_id = ?
            """,
            (user_id, thread_id),
        ).fetchone()
        if row:
            next_title = row["title"]
            if row["title"] == "新对话" and title:
                next_title = _normalize_title(title)
            connection.execute(
                """
                UPDATE chat_threads
                SET title = ?, updated_at = ?
                WHERE user_id = ? AND thread_id = ?
                """,
                (next_title, now, user_id, thread_id),
            )
        else:
            connection.execute(
                """
                INSERT INTO chat_threads (user_id, thread_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, thread_id, _normalize_title(title), now, now),
            )
        row = connection.execute(
            """
            SELECT * FROM chat_threads
            WHERE user_id = ? AND thread_id = ?
            """,
            (user_id, thread_id),
        ).fetchone()
    return _row_to_thread(row)


def list_threads(user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM chat_threads
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [_row_to_thread(row) for row in rows]


def delete_thread(user_id: int, thread_id: str) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            """
            DELETE FROM chat_threads
            WHERE user_id = ? AND thread_id = ?
            """,
            (user_id, thread_id),
        )
    deleted = cursor.rowcount > 0
    logger.info(
        "Chat thread deleted: user_id=%s thread_id=%s deleted=%s",
        user_id,
        thread_id,
        deleted,
    )
    return deleted


init_chat_threads_db()
