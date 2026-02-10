# API 文档与 Agentic RAG 重构规划

本文档整理了 Open WebUI 的前后端 API 结构，并为未来使用 Agentic RAG 重构后端提供了规划建议。

## 1. 架构概览

Open WebUI 采用前后端分离架构：
- **前端 (Frontend)**: SvelteKit 应用，位于 `src/`。
- **后端 (Backend)**: FastAPI 应用，位于 `backend/open_webui/`。

### 目录结构对应关系

| 功能模块 | 前端 API (`src/lib/apis/`) | 后端路由 (`backend/open_webui/routers/`) |
| :--- | :--- | :--- |
| **认证 (Auth)** | `auths/index.ts` | `auths.py` |
| **用户 (Users)** | `users/index.ts` | `users.py` |
| **聊天 (Chats)** | `chats/index.ts` | `chats.py` |
| **检索 (Retrieval)** | `retrieval/index.ts` | `retrieval.py` |
| **Ollama 集成** | `ollama/index.ts` | `ollama.py` |
| **OpenAI 集成** | `openai/index.ts` | `openai.py` |
| **文件 (Files)** | `files/index.ts` | `files.py` |
| **工具 (Tools)** | `tools/index.ts` | `tools.py` |
| **函数 (Functions)** | `functions/index.ts` | `functions.py` |

## 2. 核心 API 整理

### 2.1 认证 (Auth)
- `POST /api/v1/auths/signin`: 用户登录
- `POST /api/v1/auths/signup`: 用户注册
- `GET /api/v1/auths/user`: 获取当前用户信息

### 2.2 检索 (Retrieval / RAG)
这是 RAG 重构的核心区域。
- `GET /api/v1/retrieval/`: 获取 RAG 配置状态
- `POST /api/v1/retrieval/process/url`: 处理 URL 并存入向量库
- `POST /api/v1/retrieval/process/file`: 处理文件并存入向量库
- `POST /api/v1/retrieval/query/collection`: 查询向量集合
- `POST /api/v1/retrieval/query/doc`: 查询特定文档

### 2.3 聊天 (Chats)
- `POST /api/v1/chats/new`: 创建新对话
- `GET /api/v1/chats/`: 获取对话列表
- `GET /api/v1/chats/{id}`: 获取特定对话详情
- `POST /api/v1/chats/{id}/completion`: 发送消息并获取回复 (核心交互)

### 2.4 工具与函数 (Tools & Functions)
- `GET /api/v1/tools/`: 获取可用工具列表
- `POST /api/v1/tools/`: 创建/注册新工具
- `GET /api/v1/functions/`: 获取可用函数列表

## 3. Agentic RAG 重构规划

目前的 RAG 实现 (`retrieval.py`) 主要是线性的：接收查询 -> 检索向量库 -> 生成回答。
**Agentic RAG (代理式 RAG)** 将引入“代理 (Agent)”概念，使其能够动态决策。

### 3.1 核心变更点

1.  **引入 Agent Router**:
    - 在 `backend/open_webui/routers/` 下新建 `agent.py` 或改造 `retrieval.py`。
    - Agent 不再只是简单的检索，而是可以执行多步推理。

2.  **工具化 (Tool-use)**:
    - 将现有的检索功能 (`query_collection`, `web_search`) 封装为 Agent 可调用的 **Tools**。
    - 前端 `src/lib/apis/tools/index.ts` 需要配合后端更新，支持动态工具定义。

3.  **决策循环 (Reasoning Loop)**:
    - 后端需要引入 ReAct (Reasoning + Acting) 或类似的循环机制。
    - 流程：用户提问 -> Agent 分析 -> **决定**使用搜索工具/向量库/计算器 -> 获取结果 -> 生成最终回答。

### 3.2 建议重构步骤

1.  **后端改造**:
    - 定义 `Agent` 类，支持绑定多个 `Tool`。
    - 将 `backend/open_webui/retrieval/vector/main.py` 中的向量检索逻辑封装为标准 Tool。
    - 将 `backend/open_webui/retrieval/web/main.py` 中的联网搜索封装为标准 Tool。
    - 使用 LangChain 或 LlamaIndex 的 Agent 框架重写 `/api/v1/chat/completion` 的处理逻辑，使其支持 "Agentic" 模式。

2.  **前端适配**:
    - 在聊天界面增加 "Agent 思考过程" 的展示 (Thought Chain)。
    - 更新 API 调用方式，支持流式传输 Agent 的中间步骤 (Status/Reasoning steps)。

3.  **API 扩展**:
    - 新增 `/api/v1/agents/`: 管理不同的 Agent 配置（如“搜索专家”、“文档分析师”）。

### 3.3 示例：Agentic 后端逻辑伪代码

```python
# 伪代码：未来的 Agentic 处理流程
class AgenticRAG:
    def __init__(self, tools):
        self.tools = tools  # [VectorSearchTool, WebSearchTool, Calculator]
        self.llm = LLM(...)

    async def run(self, query):
        # 1. 思考 (Think)
        plan = await self.llm.plan(query, self.tools)
        
        # 2. 执行 (Act)
        if plan.action == "search_vector_db":
            result = self.tools.vector_search.run(plan.args)
        elif plan.action == "web_search":
            result = self.tools.web_search.run(plan.args)
            
        # 3. 观察 (Observe) & 生成 (Generate)
        response = await self.llm.generate(query, context=result)
        return response
```

通过这种方式，Open WebUI 将从简单的“文档问答”进化为能够处理复杂任务的“智能助手”。
