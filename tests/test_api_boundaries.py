import sqlite3
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import auth as auth_service


class ApiBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        suffix = str(time.time_ns())
        self.username = f"user_{suffix}"
        self.phone = f"138{suffix[-8:]}"
        self.password = "secret123"

    def _register_and_login(self, username=None, phone=None):
        username = username or self.username
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "password": self.password,
                "phone": phone,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)

        login = self.client.post(
            "/api/v1/auth/login",
            json={"account": username, "password": self.password},
        )
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, response.json()

    def test_auth_boundaries_and_password_storage(self):
        short_username = self.client.post(
            "/api/v1/auth/register",
            json={"username": "ab", "password": self.password},
        )
        self.assertEqual(short_username.status_code, 422)

        short_password = self.client.post(
            "/api/v1/auth/register",
            json={"username": f"{self.username}_short", "password": "123"},
        )
        self.assertEqual(short_password.status_code, 422)

        headers, user = self._register_and_login(phone=self.phone)
        self.assertEqual(user["username"], self.username)

        with sqlite3.connect(auth_service.DB_PATH) as connection:
            stored_hash = connection.execute(
                "SELECT password_hash FROM users WHERE id = ?",
                (user["id"],),
            ).fetchone()[0]
        self.assertNotEqual(stored_hash, self.password)
        self.assertIn(":", stored_hash)

        duplicate_username = self.client.post(
            "/api/v1/auth/register",
            json={"username": self.username, "password": self.password},
        )
        self.assertEqual(duplicate_username.status_code, 400)

        duplicate_phone = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": f"{self.username}_phone",
                "password": self.password,
                "phone": self.phone,
            },
        )
        self.assertEqual(duplicate_phone.status_code, 400)

        bad_login = self.client.post(
            "/api/v1/auth/login",
            json={"account": self.username, "password": "wrong123"},
        )
        self.assertEqual(bad_login.status_code, 401)

        me = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)

        wrong_change = self.client.post(
            "/api/v1/auth/password",
            headers=headers,
            json={"old_password": "wrong123", "new_password": "secret456"},
        )
        self.assertEqual(wrong_change.status_code, 400)

        same_password = self.client.post(
            "/api/v1/auth/password",
            headers=headers,
            json={"old_password": self.password, "new_password": self.password},
        )
        self.assertEqual(same_password.status_code, 400)

        changed = self.client.post(
            "/api/v1/auth/password",
            headers=headers,
            json={"old_password": self.password, "new_password": "secret456"},
        )
        self.assertEqual(changed.status_code, 200)

        old_login = self.client.post(
            "/api/v1/auth/login",
            json={"account": self.username, "password": self.password},
        )
        self.assertEqual(old_login.status_code, 401)

        new_login = self.client.post(
            "/api/v1/auth/login",
            json={"account": self.username, "password": "secret456"},
        )
        self.assertEqual(new_login.status_code, 200)

        logout = self.client.post("/api/v1/auth/logout", headers=headers)
        self.assertEqual(logout.status_code, 200)

        after_logout = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(after_logout.status_code, 401)

    def test_item_boundaries_and_user_isolation(self):
        owner_headers, _ = self._register_and_login(phone=self.phone)
        other_headers, _ = self._register_and_login(
            username=f"{self.username}_other",
            phone=f"139{self.phone[-8:]}",
        )

        without_token = self.client.get("/api/v1/items")
        self.assertEqual(without_token.status_code, 401)

        invalid_limit = self.client.get(
            "/api/v1/items",
            headers=owner_headers,
            params={"limit": 0},
        )
        self.assertEqual(invalid_limit.status_code, 422)

        blank_name = self.client.post(
            "/api/v1/items",
            headers=owner_headers,
            json={"name": "   "},
        )
        self.assertEqual(blank_name.status_code, 400)

        created = self.client.post(
            "/api/v1/items",
            headers=owner_headers,
            json={
                "name": "test-key",
                "description": "near door",
                "image_url": "https://example.com/key.jpg",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        item_id = created.json()["id"]

        owner_list = self.client.get(
            "/api/v1/items",
            headers=owner_headers,
            params={"keyword": "key"},
        )
        self.assertEqual(owner_list.status_code, 200)
        self.assertEqual(len(owner_list.json()), 1)

        other_get = self.client.get(f"/api/v1/items/{item_id}", headers=other_headers)
        self.assertEqual(other_get.status_code, 404)

        other_list = self.client.get(
            "/api/v1/items",
            headers=other_headers,
            params={"keyword": "key"},
        )
        self.assertEqual(other_list.status_code, 200)
        self.assertEqual(other_list.json(), [])

        invalid_update = self.client.patch(
            f"/api/v1/items/{item_id}",
            headers=owner_headers,
            json={"name": "   "},
        )
        self.assertEqual(invalid_update.status_code, 400)

        updated = self.client.patch(
            f"/api/v1/items/{item_id}",
            headers=owner_headers,
            json={"description": "box near door"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["description"], "box near door")

        other_delete = self.client.delete(
            f"/api/v1/items/{item_id}",
            headers=other_headers,
        )
        self.assertEqual(other_delete.status_code, 404)

        owner_delete = self.client.delete(
            f"/api/v1/items/{item_id}",
            headers=owner_headers,
        )
        self.assertEqual(owner_delete.status_code, 204)

    def test_settings_boundaries(self):
        headers, user = self._register_and_login(phone=self.phone)

        settings = self.client.get("/api/v1/settings", headers=headers)
        self.assertEqual(settings.status_code, 200)
        settings_body = settings.json()
        self.assertEqual(settings_body["user_id"], user["id"])
        self.assertFalse(settings_body["mcp_enabled"])
        self.assertTrue(settings_body["mcp_read_enabled"])
        self.assertFalse(settings_body["mcp_write_enabled"])
        self.assertIn("mcpServers", settings_body["mcp_client_config"])
        remember_server = settings_body["mcp_client_config"]["mcpServers"]["remember-item"]
        self.assertTrue(remember_server["command"].endswith("python.exe"))
        self.assertTrue(remember_server["args"][0].endswith("app\\mcp_server.py"))

        with patch.dict("os.environ", {"REMEMBER_ITEM_MCP_CONFIG_MODE": "published"}):
            published_settings = self.client.get("/api/v1/settings", headers=headers)
        self.assertEqual(published_settings.status_code, 200)
        published_server = published_settings.json()["mcp_client_config"]["mcpServers"][
            "remember-item"
        ]
        self.assertEqual(published_server["command"], "rememberitem-mcp")
        self.assertEqual(published_server["args"], [])
        self.assertNotIn("C:\\", str(published_server))

        updated = self.client.patch(
            "/api/v1/settings",
            headers=headers,
            json={
                "mcp_enabled": True,
                "mcp_read_enabled": True,
                "mcp_write_enabled": True,
            },
        )
        self.assertEqual(updated.status_code, 200)
        updated_body = updated.json()
        self.assertTrue(updated_body["mcp_enabled"])
        self.assertTrue(updated_body["mcp_read_enabled"])
        self.assertTrue(updated_body["mcp_write_enabled"])

        without_token = self.client.get("/api/v1/settings")
        self.assertEqual(without_token.status_code, 401)

    def test_chat_thread_boundaries(self):
        headers, _ = self._register_and_login(phone=self.phone)

        without_token = self.client.get("/api/v1/chat/threads")
        self.assertEqual(without_token.status_code, 401)

        created = self.client.post(
            "/api/v1/chat/threads",
            headers=headers,
            json={"title": "测试对话"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        thread = created.json()
        self.assertEqual(thread["title"], "测试对话")

        listed = self.client.get("/api/v1/chat/threads", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(
            any(item["thread_id"] == thread["thread_id"] for item in listed.json())
        )

        messages = self.client.get(
            "/api/v1/chat/messages",
            headers=headers,
            params={"thread_id": thread["thread_id"]},
        )
        self.assertEqual(messages.status_code, 200)
        self.assertEqual(messages.json(), {"messages": []})

        deleted = self.client.delete(
            f"/api/v1/chat/threads/{thread['thread_id']}",
            headers=headers,
        )
        self.assertEqual(deleted.status_code, 204)

        deleted_again = self.client.delete(
            f"/api/v1/chat/threads/{thread['thread_id']}",
            headers=headers,
        )
        self.assertEqual(deleted_again.status_code, 404)


if __name__ == "__main__":
    unittest.main()
