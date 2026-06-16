# Phase 6：前端与部署 — 知识点与面试要点

> Vue 前端对接 SSE 流式输出、Markdown 渲染、Docker 部署的技术细节和面试准备。

---

## 做了什么

前端用 Vue 3（CDN 引入）实现聊天界面，通过 `fetch + ReadableStream` 接收 SSE 流式消息，Markdown 实时渲染为 HTML。Docker 一键部署后端 + 前端。

---

## 核心知识点

### 1. SSE 前端对接

```javascript
const resp = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message, conversation_id, chat_type }),
})

const reader = resp.body.getReader()
const decoder = new TextDecoder()

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  const text = decoder.decode(value, { stream: true })
  // 解析 SSE 事件
  for (const line of text.split('\n')) {
    if (!line.startsWith('data: ')) continue
    const data = JSON.parse(line.slice(6))
    if (data.type === 'token') streamingText.value += data.content
  }
}
```

**面试要点：**
- SSE 用 `fetch + ReadableStream` 而非 `EventSource`，因为需要 POST 请求和自定义 Header
- `stream: true` 参数确保中文等多字节字符不会被截断
- 每个 `data:` 行是一个 JSON 事件，前端根据 `type` 字段分发处理

**面试问：** 为什么用 SSE 而不是 WebSocket？
**答：** SSE 是单向推送（服务端→客户端），聊天场景足够；协议简单、浏览器原生支持、自动重连；WebSocket 是双向通信，协议复杂，适合游戏、协同编辑等场景。

---

### 2. Markdown 实时渲染

```javascript
import { marked } from 'marked'

function renderMd(text) {
  let html = marked.parse(text)
  // 去掉外层 <p> 包裹，避免气泡底部多一行空白
  if (html.startsWith('<p>') && html.endsWith('</p>')) {
    html = html.slice(3, -4)
  }
  return html
}
```

```html
<!-- AI 消息用 v-html 渲染 Markdown -->
<div v-if="message.role === 'assistant'" v-html="renderMd(message.content)" />
<!-- 用户消息用纯文本，避免 XSS -->
<div v-else>{{ message.content }}</div>
```

**面试要点：**
- AI 输出是 Markdown 格式，需要实时渲染为 HTML 才能显示表格、代码块、列表等
- 用户输入用 `{{ }}` 纯文本渲染，不用 `v-html`，防止 XSS 注入
- `marked.parse()` 会包 `<p>` 标签，需要去掉避免多余空白

**面试问：** `v-html` 有什么安全风险？
**答：** `v-html` 会执行 HTML 中的脚本标签，如果用户输入包含 `<script>` 或 `<img onerror>` 会造成 XSS 攻击。所以只对 AI 生成的内容用 `v-html`（内容可信），用户输入用 `{{ }}` 转义。

---

### 3. 三模式对话设计

```
┌─────────────────────────────────────────────────────────┐
│                    用户输入问题                           │
└──────────────────────┬──────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    ┌─────────┐  ┌──────────┐  ┌─────────┐
    │  Agent   │  │ 贴心助手  │  │ 规则助手 │
    │ LangGraph│  │ FC 直接  │  │ RAG 检索 │
    │ 自动选工具│  │ 调用工具  │  │ 知识库   │
    └─────────┘  └──────────┘  └─────────┘
```

| 模式 | 技术实现 | 适用场景 | 接口 |
|------|---------|---------|------|
| Agent | LangGraph ReAct，自动判断意图选工具 | 不确定用哪个模式 | POST /api/agent |
| 贴心助手 | Function Calling，直接调业务工具 | 查节目、查票档、下单 | POST /api/chat |
| 规则助手 | RAG 检索知识库，基于文档回答 | 退票政策、订票流程 | POST /api/chat |

**面试要点：**
- RAG 封装为 `search_knowledge_base` 工具，与 Function Calling 工具统一注册到 Agent
- Agent 模式下用户说"帮我查演唱会，顺便告诉我退票政策"，会同时调用两个工具
- 保留独立模式满足明确场景下的精确调用

**面试问：** 为什么要有三个模式而不是只用 Agent？
**答：** Agent 模式最智能但最慢（需要 LLM 判断意图），明确场景下直接调用更快；规则助手只检索知识库不调工具，适合纯政策问答，避免不必要的工具调用。

---

### 4. Docker 部署

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data           # SQLite 持久化
      - ./chroma_db:/app/chroma_db # 向量数据库持久化
```

**面试要点：**
- 用 `python:3.11-slim` 而非完整镜像，减小镜像体积
- Volume 挂载确保数据持久化，容器重建不丢数据
- ChromaDB 和 SQLite 都是文件存储，不需要额外数据库容器

---

### 面试高频问题

| 问题 | 回答要点 |
|------|---------|
| 前端怎么接收流式消息？ | fetch + ReadableStream，逐 chunk 解码，按 SSE 格式解析 data 行 |
| Markdown 渲染用什么库？ | marked.js，流式时逐 token 追加并重新 parse |
| 为什么用 CDN 而不是 npm？ | 学习项目追求简单，无需构建步骤；生产项目应该用 Vite 工程化 |
| Docker 部署要注意什么？ | 数据持久化（Volume）、镜像瘦身（slim 基础镜像）、环境变量配置 |
