# RememberItem MCP Server 使用说明

RememberItem 已经内置了一个真正的 stdio MCP Server：

```text
app/mcp_server.py
```

它的作用是让外部 AI 客户端通过 MCP 调用 RememberItem 的物品能力，比如查询、添加、修改和删除物品。

## 可用工具

当前 MCP Server 暴露这些工具：

- `remember_get_mcp_settings`：读取当前 MCP 开关和权限配置。
- `remember_list_items`：查询物品列表，可按名称关键字过滤。
- `remember_get_item`：按 ID 获取单个物品。
- `remember_create_item`：新增物品。
- `remember_update_item`：修改物品。
- `remember_delete_item`：删除物品。

## 使用前提

MCP Server 本身会调用 RememberItem 后端接口，所以后端必须先运行。

本地开发时可以这样启动后端：

```powershell
cd C:\Repo\PythonProject
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

然后在网页端登录 RememberItem，进入“设置”页面，打开 MCP 开关。

如果只希望外部 AI 查询物品，打开“允许读取物品”即可。

如果希望外部 AI 可以新增、修改、删除物品，还需要打开“允许写入物品”。

## 本地开发配置

在当前源码开发阶段，设置页默认输出的是本地可直接运行的 stdio MCP 配置。

示例：

```json
{
  "mcpServers": {
    "remember-item": {
      "command": "C:\\Repo\\PythonProject\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Repo\\PythonProject\\app\\mcp_server.py"
      ],
      "env": {
        "REMEMBER_ITEM_BASE_URL": "http://127.0.0.1:8002",
        "REMEMBER_ITEM_TOKEN": "your-access-token"
      }
    }
  }
}
```

字段含义：

- `command`：启动 MCP Server 的 Python 解释器。
- `args`：传给 Python 的脚本路径，也就是 `app/mcp_server.py`。
- `REMEMBER_ITEM_BASE_URL`：RememberItem 后端地址，必须和实际运行端口一致。
- `REMEMBER_ITEM_TOKEN`：当前登录用户的访问令牌。

注意：如果后端跑在 `8002`，这里就必须是 `http://127.0.0.1:8002`。如果写成 `8001`，MCP Server 会连错后端。

## 发布应用时的配置

本地开发配置里会出现你电脑上的绝对路径，例如 `C:\Repo\PythonProject\...`。这对你自己调试没问题，但发布给别人时不应该暴露。

发布应用时，建议直接使用远程 HTTP MCP。先在后端运行环境里设置：

```powershell
$env:REMEMBER_ITEM_MCP_CONFIG_MODE = "published"
```

设置后，网页设置页会输出远程 MCP 配置：

```json
{
  "mcpServers": {
    "remember-item": {
      "type": "streamable-http",
      "url": "http://服务器IP/mcp/",
      "headers": {
        "Authorization": "Bearer your-access-token"
      }
    }
  }
}
```

这个配置不会暴露开发者电脑里的 `C:\Repo\...` 路径。

以后如果想支持不具备 HTTP MCP 能力的客户端，再额外打包 `rememberitem-mcp` 命令。

## 远程 MCP 配置

RememberItem 后端已经挂载了远程 Streamable HTTP MCP 端点：

```text
/mcp/
```

如果服务器公网 IP 是 `115.191.21.161`，远程 MCP 地址就是：

```text
http://115.191.21.161/mcp/
```

注意：这里最后的 `/` 建议保留。

远程 MCP 不需要配置服务器内部路径，也不需要配置：

```json
"command": "/opt/rememberitem/.venv/bin/python3"
```

或：

```json
"args": ["/opt/rememberitem/app/mcp_server.py"]
```

远程客户端应该选择 `Streamable HTTP` 或类似的 HTTP MCP 类型，然后填写 URL 和请求头。

常见配置格式如下：

```json
{
  "mcpServers": {
    "remember-item": {
      "type": "streamable-http",
      "url": "http://115.191.21.161/mcp/",
      "headers": {
        "Authorization": "Bearer your-access-token"
      }
    }
  }
}
```

有些客户端字段名可能不同，例如：

```json
{
  "name": "RememberItem",
  "url": "http://115.191.21.161/mcp/",
  "auth": "Bearer your-access-token"
}
```

核心不变：

- 类型选择 HTTP / Streamable HTTP MCP。
- URL 填 `http://服务器IP/mcp/`。
- 认证填 `Authorization: Bearer <access_token>`。

如果客户端只有“标准输入 / stdio”类型，没有 HTTP MCP 类型，那它不能直接连接远程 MCP，只能使用本地 `command + args` 的 stdio 配置。

## 权限开关

MCP Server 每次执行工具前都会读取 `/api/v1/settings` 检查权限。

- `mcp_enabled = false`：外部 MCP 物品工具全部禁止。
- `mcp_read_enabled = false`：禁止查询物品。
- `mcp_write_enabled = false`：禁止新增、修改、删除物品。

这些开关只控制外部 MCP 调用。

RememberItem 应用内部的 AI Agent 是另一套内部能力，它仍然会按当前登录用户的身份调用后端服务，不受“对外 MCP 开关”影响。

## 常见问题

### 为什么 `rememberitem-mcp` 会启动失败？

因为当前还没有真正发布或安装 `rememberitem-mcp` 这个命令。

在源码开发阶段，请使用设置页默认输出的 `python.exe + app/mcp_server.py` 配置。

如果已经部署到服务器，优先使用远程 HTTP MCP 配置，也就是 `http://服务器IP/mcp/`。

### 为什么以前能成功，现在连不上？

优先检查两个地方：

- `command` 和 `args` 是否指向当前电脑上真实存在的 Python 和 `app/mcp_server.py`。
- `REMEMBER_ITEM_BASE_URL` 的端口是否和后端实际端口一致，例如当前是 `8002` 就不能写成 `8001`。

### Token 能不能随便给别人？

不能。`REMEMBER_ITEM_TOKEN` 代表当前用户登录身份。

拿到这个 token 的外部 AI 客户端，可以在 MCP 开关允许的范围内访问你的物品数据。不要把包含真实 token 的配置公开发布。
