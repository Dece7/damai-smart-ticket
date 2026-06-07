# 小麦同学 智能AI客服

基于 Python + LangChain + LangGraph 的 AI 智能票务客服系统。

## 功能特性

- **三模式对话**：Agent 智能模式、贴心助手（Function Calling）、规则助手（RAG）
- **RAG 全流程**：Markdown 文档解析 → 语义分块 → ChromaDB 向量存储 → 混合检索（BM25 + 向量，RRF 融合排序）→ LLM 生成，支持引用溯源
- **Agent 编排**：LangGraph ReAct Agent，自动判断意图选择工具，支持多工具连续调用
- **推理可视化**：Agent 推理过程时间线展示，推理步骤持久化存储
- **安全防护**：Prompt 注入检测（15+ 条正则规则）
- **可观测性**：Token 消耗统计、管理员仪表盘（按天趋势、按模式对比）
- **会话管理**：多轮对话记忆、多会话切换、置顶、重命名、删除、标题自动生成
- **流式输出**：SSE 实时流式返回

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI |
| AI 框架 | LangChain + LangGraph |
| 模型 | Mimo (小米) / DeepSeek |
| 向量数据库 | ChromaDB |
| 全文检索 | rank_bm25 |
| 数据库 | SQLite |
| 前端 | Vue 3 (CDN) |
| 部署 | Docker |

## 快速启动

### 1. 安装依赖

```bash
uv venv .venv --python 3.11
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
uv pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

### 3. 构建 RAG 知识库

```bash
python build_rag.py
```

### 4. 启动服务

```bash
python run.py
```

访问 http://localhost:8000 查看前端界面，http://localhost:8000/admin 查看管理仪表盘。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 贴心助手/规则助手对话 |
| POST | `/api/agent` | Agent 对话 |
| GET | `/api/conversations` | 对话列表 |
| GET | `/api/conversations/{id}/messages` | 历史消息 |
| GET | `/api/admin/stats/summary` | 统计总览 |
| GET | `/api/admin/stats/trend` | Token 趋势 |
| GET | `/api/admin/stats/by_mode` | 模式对比 |
| GET | `/scalar` | API 文档 |

## 项目结构

```
damai-smart-ticket/
├── app/
│   ├── api/           # API 接口（chat / agent / conversation / admin）
│   ├── chains/        # LangChain 工具和 Agent
│   ├── core/          # 配置、数据库、提示词、安全防护
│   ├── models/        # SQLAlchemy 数据模型
│   ├── pipelines/     # RAG 管线（向量 + BM25 混合检索）
│   └── services/      # 业务服务（chat / agent / memory）
├── docs/rag/          # RAG 知识库文档
├── static/            # 前端页面（index.html + admin.html）
├── build_rag.py       # 构建向量数据库 + BM25 索引
├── run.py             # 启动脚本
└── docker-compose.yml
```

## Docker 部署

```bash
docker-compose up -d
```
