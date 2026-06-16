# Phase 1：基础对话 — 知识点与面试要点

> FastAPI + LangChain + Mimo 流式对话的技术细节和面试准备。

---

## 做了什么

用 Python FastAPI 搭建后端，通过 LangChain 的 `ChatOpenAI` 对接 Mimo 大模型，实现 SSE 流式对话。

---

## 核心知识点

### 1. LangChain ChatOpenAI 模型抽象

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    api_key="tp-xxx",
    base_url="https://token-plan-cn.xiaomimimo.com/v1",
    model="mimo-v2.5",
    streaming=True,
)
```

**面试要点：**
- `ChatOpenAI` 是 LangChain 对 OpenAI 协议的统一封装
- 任何兼容 OpenAI 协议的模型（DeepSeek、Mimo、通义千问）都可以用同一个类对接
- `streaming=True` 开启流式输出，调用 `astream()` 逐 chunk 返回
- 这体现了**策略模式**：换模型只改配置，不改业务代码

**面试问：** 为什么用 LangChain 而不是直接调 OpenAI SDK？
**答：** LangChain 提供统一抽象层，换模型不改代码；内置工具调用、RAG、Agent 等能力；社区生态丰富。

---

### 2. SSE 流式输出（Server-Sent Events）

```python
from fastapi.responses import StreamingResponse

@app.post("/api/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        chat_service.chat(message=request.message),
        media_type="text/event-stream",
    )
```

**SSE 协议格式：**
```
data: {"content": "你好"}
data: {"content": "呀！"}
data: [DONE]
```

**面试要点：**
- SSE 是 HTTP 单向推送协议，服务端 → 客户端
- 每条消息以 `data:` 前缀，以 `\n\n` 分隔
- `[DONE]` 表示流结束
- 相比 WebSocket：SSE 更轻量、基于 HTTP、天然支持跨域
- 相比轮询：实时性更好、延迟更低、节省带宽

**面试问：** SSE 和 WebSocket 的区别？
**答：** SSE 是单向（服务端→客户端），基于 HTTP，适合通知、流式输出；WebSocket 是双向，适合聊天、游戏等需要实时双向通信的场景。

---

### 3. 异步流式生成

```python
async for chunk in self.llm.astream(messages):
    if chunk.content:
        yield f"data: {json.dumps({'content': chunk.content})}\n\n"
```

**面试要点：**
- `astream()` 是 LangChain 的异步流式方法
- `async for` + `yield` 构成异步生成器
- FastAPI 的 `StreamingResponse` 接收异步生成器，逐块发送给客户端
- 每个 chunk 只包含一小段文本（通常几个字），实现"打字机效果"

---

### 4. Pydantic Settings 配置管理

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mimo_api_key: str = ""
    mimo_base_url: str = "https://token-plan-cn.xiaomimimo.com/v1"

    class Config:
        env_file = str(BASE_DIR / ".env")
```

**面试要点：**
- `pydantic-settings` 自动从环境变量 / `.env` 文件读取配置
- 类型校验：如果 `mimo_port` 定义为 `int`，传字符串会报错
- `@lru_cache` 缓存配置实例，避免重复读取文件
- `.env` 文件不提交 git（安全性），`.env.example` 提交（模板）

**面试问：** 配置管理的最佳实践？
**答：** 敏感信息用环境变量，不硬编码；用 pydantic-settings 做类型校验；`.env` 只用于开发，生产用环境变量注入。

---

### 5. FastAPI 中间件（CORS）

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**面试要点：**
- CORS（跨域资源共享）：浏览器安全策略，限制跨域请求
- 前端（localhost:5173）调后端（localhost:8000）属于跨域
- `allow_origins=["*"]` 允许所有来源（开发用，生产要限制）

---

### 6. Scalar API 文档

```python
from scalar_fastapi import get_scalar_api_reference

@app.get("/scalar")
async def scalar_docs():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)
```

**面试要点：**
- Scalar 是 Swagger UI 的现代替代品，界面更美观
- FastAPI 自动生成 OpenAPI 规范（基于类型注解和 Pydantic 模型）
- `/scalar` 页面可以直接测试 API，无需 Postman

---

## 项目结构（Phase 1）

```
app/
├── core/
│   ├── config.py       # 配置管理（pydantic-settings）
│   └── prompts.py      # 系统提示词
├── services/
│   └── chat_service.py # 对话服务（LangChain ChatOpenAI）
├── api/
│   └── chat.py         # API 接口（FastAPI Router）
├── main.py             # 应用入口
└── run.py              # 启动脚本
```

---

## 面试高频问题

| 问题 | 回答要点 |
|------|---------|
| 为什么选 FastAPI？ | 异步高性能、自动 API 文档、类型校验、Python 生态主流 |
| 流式输出怎么实现？ | SSE + async generator + StreamingResponse |
| LangChain 的作用？ | 统一模型抽象、工具调用、RAG、Agent 编排 |
| 怎么对接不同模型？ | ChatOpenAI + 不同的 base_url 和 api_key |
| 配置怎么管理？ | pydantic-settings + .env 文件 + 环境变量 |

---

## 与原项目（Spring AI）对比

| 原项目 (Spring AI) | Python 版 | 知识点 |
|-------------------|-----------|--------|
| `ChatClient.builder(model)` | `ChatOpenAI(...)` | 模型抽象层 |
| `Flux<String>` | `async for chunk in astream()` | 响应式流 vs 异步生成器 |
| `@Value("${key}")` | `pydantic-settings` | 配置管理 |
| `WebMvcConfigurer` | `CORSMiddleware` | 跨域配置 |
| Swagger UI | Scalar | API 文档 |
