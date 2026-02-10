# 本地部署指南

本指南总结了如何在本地运行 Open WebUI，涵盖后端和前端的操作。

## 先决条件

- **Node.js**: v18.13.0 或更高版本
- **Python**: 推荐 v3.11

## 后端设置 (Backend)

1.  **环境设置**:
    推荐使用名为 `open-webui` 的 Conda 环境。

    ```bash
    # 如果环境不存在，则创建该环境
    conda create -n open-webui python=3.11 -y
    
    # 激活环境
    conda activate open-webui
    ```

2.  **安装依赖**:
    ```bash
    pip install -r backend/requirements.txt
    ```

3.  **启动后端**:
    ```bash
    PORT=8081 bash backend/start.sh
    ```
    后端运行在 `http://localhost:8081`。

    **故障排除**:
    - 如果遇到 "bad substitution" 错误，请确保使用的是现代 Bash 或更新后的 `start.sh` 脚本。
    - 确保 `conda` 在你的 PATH 环境变量中。
    - 端口 8080 经常被其他服务（如 Docker）占用。我们使用 8081 以避免冲突。
    - 前端已配置为代理请求到 `http://localhost:8081`。

### 4. 远程访问

应用程序配置为监听所有网络接口 (`0.0.0.0`)。你可以使用计算机的 IP 地址从同一网络上的其他设备访问它。

1.  **查找你的 IP 地址**:
    ```bash
    ifconfig | grep "inet " | grep -v 127.0.0.1
    ```
    (例如：`192.168.31.241`)

2.  **访问 URL**:
    -   **前端 (浏览器)**: `http://<YOUR_IP>:5173`
    -   **后端 (API)**: `http://<YOUR_IP>:8081`

3.  **防火墙**:
    确保你的防火墙允许端口 `5173` 和 `8081` 的传入流量。

## 前端设置 (Frontend)

前端是一个位于根目录的 SvelteKit 应用程序。

1.  **安装 Node 依赖**
    在项目根目录运行：

    ```bash
    npm install
    ```

2.  **配置**
    确保根目录下有 `.env` 文件。
    - 如果缺失，复制示例文件：`cp .env.example .env`
    - 默认配置期望后端位于 `http://localhost:8080`（或 `http://0.0.0.0:8080`）。
    - **开发模式**：运行 `npm run dev` 时，前端连接到 `http://localhost:8080` 的后端。
    - **CORS**：确保 `.env` 中的 `CORS_ALLOW_ORIGIN` 包含 `http://localhost:5173` 或设置为 `*`。
    - **离线模式**：为防止连接到 Hugging Face，在 `.env` 中设置 `OFFLINE_MODE=true`。
    - **Ollama Embedding**：要使用本地 Ollama 模型（例如 `qwen3-embedding:4b`），请将以下内容添加到 `.env`：
      ```env
      RAG_EMBEDDING_ENGINE=ollama
      RAG_EMBEDDING_MODEL=qwen3-embedding:4b
      RAG_OLLAMA_BASE_URL=http://localhost:11434
      ```

3.  **启动前端 (开发模式)**
    用于开发或需要热重载的情况。

    ```bash
    npm run dev
    ```
    - 在 `http://localhost:5173` 访问应用程序。

4.  **构建生产版本 (可选)**
    如果你更喜欢通过后端（单一端口 8080）提供前端服务：

    ```bash
    npm run build
    ```
    - 构建完成后，重启后端。
    - 后端将自动从 `build` 目录提供静态文件。
    - 在 `http://localhost:8080` 访问应用程序。

## 命令汇总

**终端 1 (后端):**
```bash
# 如果使用 venv 则激活
source backend/venv/bin/activate
# 或者使用 conda
conda activate open-webui

PORT=8081 bash backend/start.sh
```

**终端 2 (前端):**
```bash
npm install
npm run dev
```
