import os
from typing import Any

import httpx
from mcp.server.fastmcp import Context, FastMCP


BASE_URL = os.getenv("REMEMBER_ITEM_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
TOKEN = os.getenv("REMEMBER_ITEM_TOKEN", "")
TIMEOUT = float(os.getenv("REMEMBER_ITEM_MCP_TIMEOUT", "20"))

mcp = FastMCP(
    "RememberItem",
    instructions=(
        "RememberItem MCP server. Use it to search, list, create, update, "
        "and delete the authenticated user's remembered items."
    ),
    host="0.0.0.0",
    streamable_http_path="/",
)


def _token_from_context(ctx: Context | None) -> str:
    if ctx is None:
        return ""

    try:
        request = ctx.request_context.request
    except ValueError:
        return ""

    if request is None:
        return ""

    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return ""


def _headers(ctx: Context | None = None) -> dict[str, str]:
    token = _token_from_context(ctx) or TOKEN
    if not token:
        raise RuntimeError("REMEMBER_ITEM_TOKEN is not configured")
    return {"Authorization": f"Bearer {token}"}


def _request(method: str, path: str, ctx: Context | None = None, **kwargs) -> Any:
    url = f"{BASE_URL}{path}"
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.request(method, url, headers=_headers(ctx), **kwargs)

    if response.status_code == 204:
        return None

    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text}

    if response.is_error:
        detail = data.get("detail") if isinstance(data, dict) else data
        raise RuntimeError(f"RememberItem API error {response.status_code}: {detail}")

    return data


def _settings(ctx: Context | None = None) -> dict[str, Any]:
    return _request("GET", "/api/v1/settings", ctx=ctx)


def _require_mcp_enabled(ctx: Context | None = None) -> dict[str, Any]:
    settings = _settings(ctx)
    if not settings.get("mcp_enabled"):
        raise RuntimeError("RememberItem MCP is disabled in settings")
    return settings


def _require_read_enabled(ctx: Context | None = None) -> None:
    settings = _require_mcp_enabled(ctx)
    if not settings.get("mcp_read_enabled"):
        raise RuntimeError("RememberItem MCP read permission is disabled")


def _require_write_enabled(ctx: Context | None = None) -> None:
    settings = _require_mcp_enabled(ctx)
    if not settings.get("mcp_write_enabled"):
        raise RuntimeError("RememberItem MCP write permission is disabled")


@mcp.tool(description="Get current RememberItem MCP settings for the authenticated user.")
def remember_get_mcp_settings(ctx: Context) -> dict[str, Any]:
    return _settings(ctx)


@mcp.tool(description="List remembered items. Optionally filter by item name keyword.")
def remember_list_items(ctx: Context, keyword: str = "", limit: int = 50) -> list[dict[str, Any]]:
    _require_read_enabled(ctx)
    params: dict[str, Any] = {"limit": max(1, min(limit, 100))}
    if keyword.strip():
        params["keyword"] = keyword.strip()
    return _request("GET", "/api/v1/items", ctx=ctx, params=params)


@mcp.tool(description="Get a remembered item by id.")
def remember_get_item(ctx: Context, item_id: int) -> dict[str, Any]:
    _require_read_enabled(ctx)
    return _request("GET", f"/api/v1/items/{item_id}", ctx=ctx)


@mcp.tool(description="Create a remembered item.")
def remember_create_item(
    ctx: Context,
    name: str,
    description: str | None = None,
    image_url: str | None = None,
) -> dict[str, Any]:
    _require_write_enabled(ctx)
    return _request(
        "POST",
        "/api/v1/items",
        ctx=ctx,
        json={
            "name": name,
            "description": description,
            "image_url": image_url,
        },
    )


@mcp.tool(description="Update a remembered item by id.")
def remember_update_item(
    ctx: Context,
    item_id: int,
    name: str | None = None,
    description: str | None = None,
    image_url: str | None = None,
) -> dict[str, Any]:
    _require_write_enabled()
    payload = {
        key: value
        for key, value in {
            "name": name,
            "description": description,
            "image_url": image_url,
        }.items()
        if value is not None
    }
    if not payload:
        raise RuntimeError("At least one field must be provided")
    _require_write_enabled(ctx)
    return _request("PATCH", f"/api/v1/items/{item_id}", ctx=ctx, json=payload)


@mcp.tool(description="Delete a remembered item by id.")
def remember_delete_item(ctx: Context, item_id: int) -> dict[str, Any]:
    _require_write_enabled(ctx)
    _request("DELETE", f"/api/v1/items/{item_id}", ctx=ctx)
    return {"success": True, "item_id": item_id}


if __name__ == "__main__":
    mcp.run("stdio")
