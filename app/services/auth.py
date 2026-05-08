import hashlib
import hmac
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.common.logger import logger


DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")
DB_PATH = os.path.join(DB_DIR, "remember_item.db")
TOKEN_EXPIRE_DAYS = 30


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_text() -> str:
    return _utc_now().isoformat()


def _connect() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _hash_password(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120_000,
    )
    return f"{salt.hex()}:{password_hash.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, _ = stored_hash.split(":", 1)
        expected = _hash_password(password, bytes.fromhex(salt_hex))
    except ValueError:
        return False
    return hmac.compare_digest(expected, stored_hash)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def init_auth_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                phone TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                mcp_enabled INTEGER NOT NULL DEFAULT 0,
                mcp_read_enabled INTEGER NOT NULL DEFAULT 1,
                mcp_write_enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )


def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "phone": row["phone"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def register_user(
    username: str,
    password: str,
    phone: str | None = None,
) -> dict[str, Any]:
    username = username.strip()
    phone = phone.strip() if phone else None

    if not username:
        raise ValueError("username is required")
    if len(password) < 6:
        raise ValueError("password must be at least 6 characters")

    now = _utc_now_text()
    try:
        with _connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (username, phone, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, phone, _hash_password(password), now, now),
            )
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
    except sqlite3.IntegrityError as exc:
        message = str(exc).lower()
        if "users.phone" in message:
            logger.info("Register rejected: duplicated phone")
            raise ValueError("phone already exists") from exc
        logger.info("Register rejected: duplicated username")
        raise ValueError("username already exists") from exc

    logger.info("User registered: user_id=%s", row["id"])
    return _row_to_user(row)


def authenticate_user(account: str, password: str) -> dict[str, Any] | None:
    account = account.strip()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM users
            WHERE username = ? OR phone = ?
            LIMIT 1
            """,
            (account, account),
        ).fetchone()

    if not row or not _verify_password(password, row["password_hash"]):
        logger.info("Login failed: invalid account or password")
        return None
    logger.info("Login succeeded: user_id=%s", row["id"])
    return _row_to_user(row)


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    if old_password == new_password:
        raise ValueError("new password must be different from old password")

    with _connect() as connection:
        row = connection.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if not row or not _verify_password(old_password, row["password_hash"]):
            logger.info("Password change failed: user_id=%s reason=invalid_old_password", user_id)
            return False

        connection.execute(
            """
            UPDATE users
            SET password_hash = ?, updated_at = ?
            WHERE id = ?
            """,
            (_hash_password(new_password), _utc_now_text(), user_id),
        )

    logger.info("Password changed: user_id=%s", user_id)
    return True


def create_session(user_id: int) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    now = _utc_now()
    expires_at = now + timedelta(days=TOKEN_EXPIRE_DAYS)
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO auth_sessions (user_id, token_hash, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, _hash_token(token), now.isoformat(), expires_at.isoformat()),
        )
    logger.info("Session created: user_id=%s expires_at=%s", user_id, expires_at.isoformat())
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at.isoformat(),
    }


def get_user_by_token(token: str) -> dict[str, Any] | None:
    token_hash = _hash_token(token)
    now = _utc_now_text()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT users.*
            FROM auth_sessions
            JOIN users ON users.id = auth_sessions.user_id
            WHERE auth_sessions.token_hash = ?
              AND auth_sessions.expires_at > ?
            LIMIT 1
            """,
            (token_hash, now),
        ).fetchone()
    return _row_to_user(row) if row else None


def delete_session(token: str) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM auth_sessions WHERE token_hash = ?",
            (_hash_token(token),),
        )
    logger.info("Session deleted: deleted=%s", cursor.rowcount > 0)
    return cursor.rowcount > 0


def _mcp_server_command() -> str:
    configured_command = os.getenv("REMEMBER_ITEM_MCP_CLIENT_COMMAND")
    if configured_command:
        return configured_command

    if os.getenv("REMEMBER_ITEM_MCP_CONFIG_MODE") == "published":
        return "rememberitem-mcp"

    project_root = Path(__file__).resolve().parents[2]
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _mcp_server_args() -> list[str]:
    raw_args = os.getenv("REMEMBER_ITEM_MCP_CLIENT_ARGS", "")
    if raw_args.strip():
        return [arg for arg in raw_args.split("||") if arg]

    if os.getenv("REMEMBER_ITEM_MCP_CONFIG_MODE") == "published":
        return []

    project_root = Path(__file__).resolve().parents[2]
    return [str(project_root / "app" / "mcp_server.py")]


def _mcp_client_config(mcp_base_url: str) -> dict[str, Any]:
    if os.getenv("REMEMBER_ITEM_MCP_CONFIG_MODE") == "published":
        return {
            "mcpServers": {
                "remember-item": {
                    "type": "streamable-http",
                    "url": f"{mcp_base_url.rstrip('/')}/mcp/",
                    "headers": {
                        "Authorization": "Bearer <access_token>",
                    },
                }
            }
        }

    return {
        "mcpServers": {
            "remember-item": {
                "command": _mcp_server_command(),
                "args": _mcp_server_args(),
                "env": {
                    "REMEMBER_ITEM_BASE_URL": mcp_base_url,
                    "REMEMBER_ITEM_TOKEN": "<access_token>",
                },
            }
        }
    }


def _row_to_settings(row: sqlite3.Row, mcp_base_url: str) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "mcp_enabled": bool(row["mcp_enabled"]),
        "mcp_read_enabled": bool(row["mcp_read_enabled"]),
        "mcp_write_enabled": bool(row["mcp_write_enabled"]),
        "mcp_base_url": mcp_base_url,
        "mcp_server_command": _mcp_server_command(),
        "mcp_server_args": _mcp_server_args(),
        "mcp_client_config": _mcp_client_config(mcp_base_url),
        "mcp_note": (
            "本地开发默认展示 stdio MCP 配置。发布应用时设置 "
            "REMEMBER_ITEM_MCP_CONFIG_MODE=published，设置页会展示远程 HTTP MCP 配置。"
        ),
        "updated_at": row["updated_at"],
    }


def get_settings(user_id: int, mcp_base_url: str) -> dict[str, Any]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            now = _utc_now_text()
            connection.execute(
                """
                INSERT INTO user_settings
                    (user_id, mcp_enabled, mcp_read_enabled, mcp_write_enabled, updated_at)
                VALUES (?, 0, 1, 0, ?)
                """,
                (user_id, now),
            )
            row = connection.execute(
                "SELECT * FROM user_settings WHERE user_id = ?",
                (user_id,),
            ).fetchone()
    return _row_to_settings(row, mcp_base_url)


def update_settings(
    user_id: int,
    mcp_base_url: str,
    mcp_enabled: bool | None = None,
    mcp_read_enabled: bool | None = None,
    mcp_write_enabled: bool | None = None,
) -> dict[str, Any]:
    current = get_settings(user_id, mcp_base_url)
    next_enabled = current["mcp_enabled"] if mcp_enabled is None else mcp_enabled
    next_read = current["mcp_read_enabled"] if mcp_read_enabled is None else mcp_read_enabled
    next_write = current["mcp_write_enabled"] if mcp_write_enabled is None else mcp_write_enabled
    now = _utc_now_text()

    with _connect() as connection:
        connection.execute(
            """
            UPDATE user_settings
            SET mcp_enabled = ?,
                mcp_read_enabled = ?,
                mcp_write_enabled = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                int(next_enabled),
                int(next_read),
                int(next_write),
                now,
                user_id,
            ),
        )
        row = connection.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    logger.info("Settings updated: user_id=%s mcp_enabled=%s", user_id, next_enabled)
    return _row_to_settings(row, mcp_base_url)


init_auth_db()
