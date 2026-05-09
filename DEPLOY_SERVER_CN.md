# RememberItem 服务器部署说明

这份文档按当前项目状态编写，适合“暂时没有域名，只有一台服务器 IP”的部署方式。

当前项目结构重点：

- 后端：FastAPI，入口是 `app.main:app`。
- 前端：Vue3 + Vite，源码在 `frontend/`。
- 前端构建产物：输出到 `app/static/`，由 FastAPI 直接托管。
- 数据库：当前使用 SQLite，文件会生成在 `app/db/` 下。
- MCP Server：`app/mcp_server.py`，本地开发可用，正式发布时还需要再设计安装命令或远程 MCP。

## 一、上线前需要注意和可能要改的地方

### 1. Python 版本

当前 `pyproject.toml` 里写的是：

```toml
requires-python = ">=3.14"
```

服务器必须能安装或运行 Python 3.14。

如果服务器装 Python 3.14 很麻烦，可以之后把它改成：

```toml
requires-python = ">=3.12"
```

但改完后必须重新测试后端依赖和单元测试。

### 2. 不要上传 `.env`

真实密钥只能放服务器本地的 `.env` 文件里，不能提交到 GitHub。

项目已经有 `.env.example`，服务器上用它复制一份：

```bash
cp .env.example .env
```

然后自己填写真实配置。

### 3. 当前没有域名时的访问方式

没有域名时，前端和 API 可以先用服务器 IP 访问：

```text
http://服务器IP
```

如果不用 Nginx，也可以临时直接访问：

```text
http://服务器IP:8002
```

正式长期运行更建议用 Nginx，把公网 `80` 端口转发到本机 `127.0.0.1:8002`。

### 4. 安卓 App 后面不能写 `127.0.0.1`

安卓 App 请求服务器时，不能写：

```text
http://127.0.0.1:8002
```

因为手机里的 `127.0.0.1` 代表手机自己，不是你的服务器。

没有域名时，安卓端应该写：

```text
http://服务器IP/api/v1
```

有域名和 HTTPS 后再改成：

```text
https://你的域名/api/v1
```

### 5. HTTP 和 HTTPS

现在没有域名，短期可以先用 HTTP。

但安卓正式打包 APK 时要注意：

- Android 9 以后默认不允许明文 HTTP。
- 如果暂时只用 HTTP，需要在安卓工程里配置允许明文请求。
- 最终上线建议买域名并配置 HTTPS。

### 6. CORS 配置

当前 `app/main.py` 里 CORS 是：

```python
allow_origins=["*"]
```

开发阶段可以这样。

正式上线后，建议改成你的前端访问地址，例如：

```python
allow_origins=[
    "http://服务器IP",
    "https://你的域名",
]
```

如果安卓 App 直接请求 API，CORS 对原生 App 影响不大，但网页端会受影响。

### 7. SQLite 数据库备份

当前数据库是 SQLite，生成目录大概是：

```text
app/db/
```

服务器上一定要定期备份这个目录，否则服务器重装或误删会丢数据。

建议以后用户多了之后迁移到 PostgreSQL 或 MySQL。

## 二、服务器基础准备

以下以 Ubuntu 22.04 / 24.04 为例。

更新系统：

```bash
sudo apt update
sudo apt upgrade -y
```

安装基础工具：

```bash
sudo apt install -y git curl nginx
```

安装 Node.js，建议 Node 20 以上。

可以使用 NodeSource，或者服务器已有 Node 也可以：

```bash
node -v
npm -v
```

安装 `uv`：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

## 三、拉取项目

建议放到 `/opt/rememberitem`：

```bash
sudo mkdir -p /opt/rememberitem
sudo chown -R $USER:$USER /opt/rememberitem
cd /opt/rememberitem
```

如果服务器能正常连 GitHub SSH：

```bash
git clone git@github.com:zx1314521/RItem.git .
```

如果服务器的 22 端口连 GitHub 被拦，可以用 GitHub SSH 443：

```bash
git clone ssh://git@ssh.github.com:443/zx1314521/RItem.git .
```

## 四、配置环境变量

```bash
cd /opt/rememberitem
cp .env.example .env
nano .env
```

按需填写：

```env
DASHSCOPE_BASE_URL=
DASHSCOPE_API_KEY=
DASHSCOPE_IMAGE_MODEL=qwen-image-2.0-pro
DASHSCOPE_IMAGE_SIZE=1024*1024
REMEMBER_ITEM_MODEL=qwen3.6-35b-a3b
REMEMBER_ITEM_GENERATE_IMAGES=true
TAVILY_API_KEY=

LANGSMITH_API_KEY=
LANGSMITH_TRACING=false
LANGSMITH_PROJECT=RememberItem

OSS_ACCESS_KEY_ID=
OSS_ACCESS_KEY_SECRET=
OSS_BUCKET=
OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com
OSS_REGION=cn-beijing
```

如果暂时不用图片上传，OSS 可以先不填。

如果要用 AI 对话，必须配置对应的大模型 API Key。

当前默认对话模型是 `qwen3.6-35b-a3b`。如果用户没有上传图片，但 AI 判断是在新增物品，后端会尝试用 `qwen-image-2.0-pro` 生成一张参考图，并复制到 OSS 后保存长期可访问的图片 URL。

如果不想让新增物品时自动生成图片，可以设置：

```env
REMEMBER_ITEM_GENERATE_IMAGES=false
```

## 五、安装后端依赖

```bash
cd /opt/rememberitem
uv sync
```

如果这里因为 Python 3.14 失败，需要先解决 Python 版本问题，或者调整 `pyproject.toml` 的 Python 要求后重新测试。

## 六、构建前端

正式部署不用运行 `npm run dev`。

服务器上构建一次即可：

```bash
cd /opt/rememberitem/frontend
npm install
npm run build
```

构建后会生成：

```text
/opt/rememberitem/app/static/
```

FastAPI 会直接托管这个目录。

## 七、手动测试后端

先手动运行：

```bash
cd /opt/rememberitem
uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

另开一个终端测试：

```bash
curl http://127.0.0.1:8002/openapi.json
```

如果返回 JSON，说明后端能跑。

也可以临时用服务器 IP 测试：

```bash
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

然后浏览器访问：

```text
http://服务器IP:8002
```

这个方式只建议临时测试。长期运行建议用 Nginx。

## 八、配置 systemd 长期运行

创建服务文件：

```bash
sudo nano /etc/systemd/system/rememberitem.service
```

写入：

```ini
[Unit]
Description=RememberItem FastAPI Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/rememberitem
EnvironmentFile=/opt/rememberitem/.env
ExecStart=/root/.local/bin/uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

注意：`ExecStart` 里的 `uv` 路径要按服务器实际情况修改。

查看 `uv` 路径：

```bash
which uv
```

如果输出是：

```text
/home/ubuntu/.local/bin/uv
```

那就把服务文件改成：

```ini
ExecStart=/home/ubuntu/.local/bin/uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable rememberitem
sudo systemctl start rememberitem
sudo systemctl status rememberitem
```

查看日志：

```bash
journalctl -u rememberitem -f
```

## 九、配置 Nginx，通过服务器 IP 访问

没有域名时，Nginx 可以直接监听 IP 的 80 端口。

创建配置：

```bash
sudo nano /etc/nginx/sites-available/rememberitem
```

写入：

```nginx
server {
    listen 80 default_server;
    server_name _;

    client_max_body_size 20m;

    location /api/v1/chat/stream {
        proxy_pass http://127.0.0.1:8002;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

如果要给外部 AI 客户端使用远程 MCP，建议额外加一个更明确的 `/mcp/` 配置，放在 `location /` 前面：

```nginx
location /mcp/ {
    proxy_pass http://127.0.0.1:8002;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_buffering off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/rememberitem /etc/nginx/sites-enabled/rememberitem
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

然后访问：

```text
http://服务器IP
```

### 如果访问公网 IP 仍然显示 Welcome to nginx

如果看到的是：

```text
Welcome to nginx!
```

通常说明 Nginx 默认站点还在生效，或者 Nginx 没有重新加载你的 RememberItem 配置。

先删除默认站点：

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

确认 RememberItem 配置已经启用：

```bash
ls -l /etc/nginx/sites-enabled/
```

应该能看到：

```text
rememberitem -> /etc/nginx/sites-available/rememberitem
```

再测试并重启 Nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl restart nginx
```

在服务器本机测试 80 端口是否已经转发到 RememberItem：

```bash
curl -I http://127.0.0.1
curl http://127.0.0.1 | head
```

如果这里还是 `Welcome to nginx`，说明还有别的默认配置在生效。

查看 Nginx 实际加载了哪些配置：

```bash
sudo nginx -T | grep -n "server_name\|root\|proxy_pass\|listen"
```

重点检查是否有：

```nginx
proxy_pass http://127.0.0.1:8002;
```

以及是否还有：

```nginx
root /var/www/html;
```

继续搜索默认页相关配置：

```bash
sudo grep -R "Welcome to nginx\|/var/www/html\|default_server\|server_name _" /etc/nginx
```

如果发现类似：

```text
/etc/nginx/conf.d/default.conf
```

可以先备份移走：

```bash
sudo mv /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.bak
sudo nginx -t
sudo systemctl restart nginx
```

最后用浏览器访问公网 IP 时，建议强制刷新：

```text
Ctrl + F5
```

或者换无痕窗口/手机流量访问，排除浏览器缓存。

## 十、防火墙和云服务器安全组

云服务器控制台里放行：

```text
22/tcp
80/tcp
443/tcp
```

如果你临时直接访问 `8002`，还需要放行：

```text
8002/tcp
```

但长期建议不要开放 `8002`，只开放 `80/443`，让 Nginx 转发。

Ubuntu 防火墙如果启用了 `ufw`：

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

## 十一、MCP 在服务器上的注意点

当前 MCP 文件是：

```text
app/mcp_server.py
```

本地开发时，设置页会给出类似：

```json
{
  "command": "C:\\Repo\\PythonProject\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Repo\\PythonProject\\app\\mcp_server.py"]
}
```

这只适合本地开发。

服务器发布给别人时不要暴露服务器路径。当前项目已经支持远程 MCP，优先使用：

```text
http://服务器IP/mcp/
```

如果后端 systemd 里设置了：

```ini
Environment=REMEMBER_ITEM_MCP_CONFIG_MODE=published
```

网页设置页会显示远程 HTTP MCP 配置，而不是 `command + args`。

### 远程 MCP 配置

当前项目已经支持远程 Streamable HTTP MCP，服务器端点是：

```text
http://服务器IP/mcp/
```

例如：

```text
http://115.191.21.161/mcp/
```

注意最后的 `/` 建议保留。

远程 MCP 客户端不要再使用服务器内部路径：

```json
{
  "command": "/opt/rememberitem/.venv/bin/python3",
  "args": ["/opt/rememberitem/app/mcp_server.py"]
}
```

这种 `command + args` 是 stdio MCP，只适合在服务器本机启动脚本，不适合远程客户端。

远程客户端应该选择 `Streamable HTTP` 或类似 HTTP MCP 类型。

常见配置：

```json
{
  "mcpServers": {
    "remember-item": {
      "type": "streamable-http",
      "url": "http://服务器IP/mcp/",
      "headers": {
        "Authorization": "Bearer 你的access_token"
      }
    }
  }
}
```

有些客户端可能不是这个 JSON 结构，而是界面字段：

```text
类型：Streamable HTTP / HTTP
URL：http://服务器IP/mcp/
Header：Authorization = Bearer 你的access_token
```

如果客户端只有“标准输入 / stdio”类型，没有 HTTP 类型，就不能直接连接远程 MCP。

使用前要在 RememberItem 设置页打开：

- 启用 MCP
- 允许读取物品
- 如果需要新增、修改、删除，再打开允许写入物品

`access_token` 是敏感信息，不要公开发给别人。

## 十二、安卓端后续开发注意

安卓 App 后面调用接口时，基础地址先写：

```text
http://服务器IP/api/v1
```

登录成功后保存：

```text
access_token
```

后续请求统一带：

```http
Authorization: Bearer <access_token>
```

主要接口：

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/auth/logout
POST /api/v1/auth/password

GET    /api/v1/items
POST   /api/v1/items
GET    /api/v1/items/{item_id}
PATCH  /api/v1/items/{item_id}
DELETE /api/v1/items/{item_id}

GET    /api/v1/chat/threads
POST   /api/v1/chat/threads
DELETE /api/v1/chat/threads/{thread_id}
GET    /api/v1/chat/messages
POST   /api/v1/chat/stream

GET   /api/v1/settings
PATCH /api/v1/settings
```

如果暂时没有 HTTPS，安卓需要允许 HTTP 明文请求。

## 十三、以后更新服务器代码

每次本地开发完成并 push 到 GitHub 后，服务器执行：

```bash
cd /opt/rememberitem
git pull
uv sync

cd frontend
npm install
npm run build

cd ..
sudo systemctl restart rememberitem
sudo systemctl status rememberitem
```

查看日志：

```bash
journalctl -u rememberitem -n 100
```

## 十四、上线检查清单

上线前检查：

- `.env` 已在服务器创建，并且没有提交到 GitHub。
- `uv sync` 成功。
- `frontend/npm run build` 成功。
- `curl http://127.0.0.1:8002/openapi.json` 成功。
- `sudo systemctl status rememberitem` 是 running。
- `sudo nginx -t` 成功。
- 浏览器能打开 `http://服务器IP`。
- 手机网络能访问 `http://服务器IP/api/v1`。
- 云服务器安全组已放行 `80` 和 `22`。
- `app/db/` 有备份计划。

## 十五、建议的下一步

短期：

- 先用服务器 IP 部署跑通。
- 安卓 App 先用 HTTP + 服务器 IP 调接口。
- 等功能稳定后再买域名。

中期：

- 配置域名。
- 配置 HTTPS。
- 安卓 App 改成 HTTPS 地址。

长期：

- SQLite 迁移到 PostgreSQL 或 MySQL。
- MCP 做成正式发布形态。
- 增加日志轮转、数据库备份、错误监控。
