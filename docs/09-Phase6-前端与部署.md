# Phase 6：前端与部署

> Vue 前端对接 SSE 流式输出、Markdown 渲染、Docker 部署。

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

### 3. 四模式对话设计

```
┌─────────────────────────────────────────────────────────┐
│                       用户输入问题                        │
└────────────────────────┬────────────────────────────────┘
                         │
       ┌─────────┬───────┴───────┬──────────┐
       ▼         ▼               ▼          ▼
  ┌─────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐
  │ 规则助手  │ │ 贴心助手  │ │  Agent    │ │  多Agent │
  │ RAG 管线 │ │ FC 调工具 │ │ ReAct 循环 │ │ 6节点编排 │
  └─────────┘ └──────────┘ └───────────┘ └──────────┘
```

| 模式 | 技术实现 | 工具 | 适用场景 | 接口 |
|------|---------|------|---------|------|
| 规则助手 | RAG 固定管线 | 无（直接调 RAG） | 退票政策、订票流程 | POST /api/chat (chat_type=rag) |
| 贴心助手 | Function Calling，代码控制循环 | 8 个业务工具 | 查节目、查票档、下单 | POST /api/chat (chat_type=assistant) |
| Agent | LangGraph ReAct，LLM 自主决策 | 9 个（8 业务 + 知识库） | 不确定用哪个模式 | POST /api/agent |
| 多 Agent | 6 节点结构化编排 | 按需分配 | 跨领域复杂问题 | POST /api/agent/multi |

**面试要点：**
- 四种模式覆盖不同复杂度：固定管线 → 代码控制 → LLM 自主 → 多 Agent 协作
- 规则助手直接调 RAG 管线，不经过 tool 机制
- 贴心助手不含知识库工具，Agent 含全部 9 个工具
- 多 Agent 通过 intent_classifier 分类意图，router 路由到专业子 Agent

**面试问：** 为什么要有四个模式而不是只用 Agent？
**答：** 不同场景需要不同精度和速度。规则助手最快（固定管线），适合简单问答；Agent 最灵活但最慢（LLM 决策），适合复杂问题；多 Agent 最适合跨领域问题（分工协作）。用户可以根据场景选择，也可以直接用 Agent 模式让系统自动判断。

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
| 四个模式的前端怎么区分？ | 模式切换用 Tab 组件，不同模式调不同 API 端点，共享同一个消息渲染组件 |
| Docker 部署要注意什么？ | 数据持久化（Volume）、镜像瘦身（slim 基础镜像）、环境变量配置 |
