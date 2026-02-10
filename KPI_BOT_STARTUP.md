# KPI Bot 启动说明

本文档说明如何在本仓库中启动并访问 **KPI Bot**（后端 Bottun 应用 + 前端页面）。

## 1) 后端启动（包含 KPI Bot API）

后端服务会在 `http://0.0.0.0:8081` 启动，并挂载 KPI Bot 的 OpenAI 兼容接口：`/bottun/v1/*`。

在项目根目录执行：

```bash
./run_bottun_backend.sh
```

常用检查：

```bash
curl -sS http://localhost:8081/bottun/v1/models | python -m json.tool
curl -sS http://localhost:8081/api/version
```

### KPI 配置与数据库配置

KPI Bot 使用的配置文件在：

- `backend/open_webui/apps/bottun/config/kpi_config.yaml`
- `backend/open_webui/apps/bottun/config/ui_mappings.yaml`
- `backend/open_webui/apps/bottun/config/db_config.yaml`
- `backend/open_webui/apps/bottun/config/bot_config.yaml`

修改配置后，重启后端即可生效。

## 2) 前端启动（用 IP + 端口访问，支持其他机器访问）

前端开发服务器固定监听 `0.0.0.0:5173`，因此局域网内其他机器可通过 `http://<你的机器IP>:5173` 访问。

在项目根目录执行：

```bash
npm install
npm run dev
```

### 获取本机 IP（macOS）

```bash
ipconfig getifaddr en0
```

然后在其他机器浏览器中打开：

`http://<你的机器IP>:5173`

## 3) 访问 KPI Bot

### WebUI 页面

前端页面路由：

- `http://<你的机器IP>:5173/bottun`

### OpenAI 兼容接口（供其他服务调用）

其他服务可直接调用 KPI Bot 的 OpenAI 兼容接口：

- Base URL：`http://<你的机器IP>:8081/bottun/v1`
- Chat Completions：`POST /chat/completions`
- Models：`GET /models`

示例：

```bash
curl -sS -X POST 'http://<你的机器IP>:8081/bottun/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{"model":"bottun-rule-bot","messages":[{"role":"user","content":"25年Q4的su hour per tool"}],"stream":false}' \
  | python -m json.tool
```

