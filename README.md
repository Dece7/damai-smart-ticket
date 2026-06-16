# 小麦同学 智能AI客服

基于 Python + LangChain + LangGraph 的 AI 智能票务客服系统，支持四模式对话、RAG 知识库问答、多 Agent 协作、Java 微服务整合。

## 功能特性

- **四模式对话**：规则助手（RAG）、贴心助手（Function Calling）、Agent（ReAct）、多 Agent（6 节点结构化编排）
- **RAG 全流程**：Markdown 标题感知切分 → Parent-Child 分块 → DashScope Embedding → ChromaDB 向量存储 → BM25 + 向量混合检索 → LLM 生成，支持引用溯源
- **多 Agent 编排**：LangGraph StateGraph，6 节点（intent_classifier → router → 子 Agent → answer_generator → fallback），7 字段结构化状态
- **Java 微服务整合**：MySQL 直连 + HTTP API 双模式，对接真实业务数据（节目、票档、订单）
- **推理可视化**：Agent 推理过程时间线展示，节点步骤实时推送
- **安全防护**：Prompt 注入检测（15+ 条正则规则）
- **可观测性**：Token 消耗统计、管理员仪表盘（按天趋势、按模式对比）
- **会话管理**：多轮对话记忆、多会话切换、置顶、重命名、删除、标题自动生成
- **流式输出**：SSE 实时流式返回
- **主题切换**：白天模式（纸质感米黄）/ 黑夜模式（暖棕深色）

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI |
| AI 框架 | LangChain + LangGraph |
| 模型 | Mimo (小米) / DeepSeek |
| Embedding | DashScope tongyi-embedding-vision-plus (1024 维) |
| 向量数据库 | ChromaDB |
| 全文检索 | rank_bm25 |
| 数据库 | SQLite（会话）+ MySQL（业务数据） |
| 前端 | Vue 3 + Vite + Element Plus + ECharts |
| 部署 | Docker |

## 快速启动

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
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
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 查看前端界面，http://localhost:8000/admin 查看管理仪表盘。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 贴心助手/规则助手对话 |
| POST | `/api/agent` | Agent 对话（单 Agent） |
| POST | `/api/agent/multi` | 多 Agent 协作对话 |
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
│   ├── api/           # API 接口（chat / agent / conversation / admin / knowledge）
│   ├── chains/        # LangChain 工具、Agent、多 Agent 编排
│   ├── core/          # 配置、数据库、提示词、安全防护
│   ├── models/        # SQLAlchemy 数据模型
│   ├── pipelines/     # RAG 管线（向量 + BM25 混合检索）
│   ├── services/      # 业务服务（chat / agent / multi_agent / memory）
│   └── utils/         # 工具类（Java API 客户端、Embedding）
├── docs/              # 项目文档 + RAG 知识库（15 份）
├── eval/              # 离线评估体系（65 条测试用例 + LLM Judge）
├── frontend/          # Vue 3 前端源码
├── static/            # 前端构建产物
├── build_rag.py       # 构建向量数据库 + BM25 索引
├── test_langgraph.py  # LangGraph 功能测试（10/10）
└── test_quantitative.py  # 量化测试（意图分类/端到端/延迟）
```

## 评估指标

| 指标 | 值 |
|------|-----|
| 意图分类准确率 | 100%（25/25） |
| Recall@5 | 100%（65 条用例） |
| Precision@5 | 55.7% |
| MRR | 0.992 |
| LLM Judge 综合 | 4.9/5 |
| 端到端成功率 | 100%（10/10） |
