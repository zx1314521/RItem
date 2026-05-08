import os
import sqlite3
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


def init_items_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL,
                description TEXT,
                image_url TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(items)").fetchall()
        }
        if "user_id" not in columns:
            connection.execute(
                "ALTER TABLE items ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_items_name ON items(name)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_items_user_id ON items(user_id)"
        )


def _row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "description": row["description"],
        "image_url": row["image_url"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_item(
    user_id: int,
    name: str,
    description: str | None = None,
    image_url: str | None = None,
) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise ValueError("name is required")

    now = _utc_now()
    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO items (user_id, name, description, image_url, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, name, description, image_url, now, now),
        )
        row = connection.execute(
            "SELECT * FROM items WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    logger.info("Item created: user_id=%s item_id=%s", user_id, row["id"])
    return _row_to_item(row)


def list_items(
    user_id: int,
    keyword: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    with _connect() as connection:
        if keyword:
            pattern = f"%{keyword.strip()}%"
            rows = connection.execute(
                """
                SELECT * FROM items
                WHERE user_id = ? AND name LIKE ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, pattern, limit),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM items
                WHERE user_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
    return [_row_to_item(row) for row in rows]


def get_item(user_id: int, item_id: int) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM items WHERE user_id = ? AND id = ?",
            (user_id, item_id),
        ).fetchone()
    return _row_to_item(row) if row else None


def update_item(
    user_id: int,
    item_id: int,
    name: str | None = None,
    description: str | None = None,
    image_url: str | None = None,
) -> dict[str, Any] | None:
    current = get_item(user_id, item_id)
    if not current:
        logger.info("Item update missed: user_id=%s item_id=%s", user_id, item_id)
        return None

    next_name = current["name"] if name is None else name.strip()
    if not next_name:
        raise ValueError("name cannot be empty")

    next_description = current["description"] if description is None else description
    next_image_url = current["image_url"] if image_url is None else image_url
    now = _utc_now()

    with _connect() as connection:
        connection.execute(
            """
            UPDATE items
            SET name = ?, description = ?, image_url = ?, updated_at = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (next_name, next_description, next_image_url, now, item_id, user_id),
        )
        row = connection.execute(
            "SELECT * FROM items WHERE user_id = ? AND id = ?",
            (user_id, item_id),
        ).fetchone()
    logger.info("Item updated: user_id=%s item_id=%s", user_id, item_id)
    return _row_to_item(row)


def delete_item(user_id: int, item_id: int) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM items WHERE user_id = ? AND id = ?",
            (user_id, item_id),
        )
    logger.info(
        "Item deleted: user_id=%s item_id=%s deleted=%s",
        user_id,
        item_id,
        cursor.rowcount > 0,
    )
    return cursor.rowcount > 0


init_items_db()
