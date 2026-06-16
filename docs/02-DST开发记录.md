# DST 开发记录

> 大麦智能票务助手（Python 版）开发过程中的关键信息记录。
> 持续更新。

---

## 项目基本信息

| 项 | 值 |
|----|-----|
| 项目名 | damai-smart-ticket |
| 路径 | `D:\ClaudeCodeProjects\CCAIAgent\damai-smart-ticket` |
| 定位 | 基于 Python + LangChain 重构大麦 AI 智能客服 |
| 原项目 | `D:\ClaudeCodeProjects\CCdamai\damai-ai`（Spring AI 版） |
| Python 版本 | 3.11.2 |
| 虚拟环境 | `.venv`（uv 创建，306MB，109 个包） |

---

## 模型配置

### 主力模型：Mimo（小米）

| 项 | 值 |
|----|-----|
| API Key | `tp-cyg8uoab7h9881dea5ld1mycvl70uavsoumhwm8nhlm55spv` |
| Base URL | `https://token-plan-cn.xiaomimimo.com/v1` |
| 模型名 | `mimo-v2.5` |
| 协议 | OpenAI 兼容 |
| 来源 | CC 订阅管理页面 |

**能力验证（2026-06-01）：**

| 能力 | 状态 | 说明 |
|------|:----:|------|
| 基础对话 | ✅ PASS | |
| 流式输出 | ✅ PASS | 最后一个 chunk choices 为空，需代码处理 |
| Function Calling | ✅ PASS | 支持 @tool 工具调用 |
| Embedding | ❌ FAIL | 返回 404，不支持 |

### Embedding 模型：阿里云 DashScope

| 项 | 值 |
|----|-----|
| API Key | `sk-940aa79541cb44cb87471fb503600c43` |
| 模型名 | `tongyi-embedding-vision-plus`（多模态，1024 维） |
| 备选 | `text-embedding-v3`（纯文本，1024 维） |
| 用途 | 文本向量化（Embedding） |

### 模型分工

| 功能 | 模型 | 原因 |
|------|------|------|
| 对话 / Function Calling / 查询改写 | Mimo v2.5 | 免费额度，统一模型 |
| Embedding 向量化 | DashScope | Mimo 不支持 Embedding，阿里云免费额度 |

---

## 技术栈

| 包 | 版本 | 用途 |
|---|------|------|
| langchain | 1.3.4 | AI 应用框架 |
| langchain-openai | 1.2.2 | OpenAI/DeepSeek/Mimo 模型对接 |
| langchain-community | 0.4.2 | 社区集成（MarkdownLoader 等） |
| langchain-text-splitters | 1.1.2 | 文档分块 |
| langgraph | 1.2.4 | Agent 编排 |
| chromadb | 1.5.9 | 向量数据库 |
| openai | 2.41.0 | Mimo/DeepSeek SDK |
| fastapi | 0.136.3 | Web 框架 |
| sqlalchemy | 2.0.50 | ORM |
| tiktoken | 0.13.0 | Token 计数 |

---

## 环境注意事项

- PowerShell 激活虚拟环境：`.venv\Scripts\Activate.ps1`（不是 `source`）
- `.env` 文件已配置好，不提交 git
- Embedding 使用阿里云 DashScope（`tongyi-embedding-vision-plus-2026-03-06`），HashEmbedding 仅作 demo 验证
- API 文档用 Scalar 替代 Swagger，地址 `/scalar`（包：scalar-fastapi）
- Windows 下 `pkill` 不可靠，清理进程用 `taskkill //F //PID xxx` 或 PowerShell

---

## 开发进度

- [x] 项目初始化 + 虚拟环境
- [x] 依赖安装（109 个包）
- [x] Mimo API 能力验证
- [x] Phase 1: 基础对话跑通（FastAPI + Mimo 流式） ✅ 2026-06-07
- [x] Phase 2: Function Calling（仿原项目工具定义） ✅ 2026-06-07
  - 4 个工具：search_program / get_program_detail / get_ticket_info / create_order
  - 支持多轮工具调用（最多 5 轮）
  - 用模拟数据，项目可独立运行
- [x] Phase 3: RAG 知识库（Markdown + ChromaDB + 检索问答） ✅ 2026-06-07
  - 2 个规则文档（退票政策 + 订票指南）
  - ChromaDB 向量存储 + HashEmbedding（demo 用）
  - RAG 检索问答链（LangChain LCEL）
- [x] Phase 4: 会话记忆管理 ✅ 2026-06-07
  - SQLite 数据库存储对话和消息
  - SQLAlchemy ORM 模型
  - 对话 CRUD 接口（列表、历史、删除、改标题）
- [x] Phase 5: Agent 编排（LangGraph） ✅ 2026-06-07
  - LangGraph ReAct Agent
  - 5 个工具：4 个 FC + 1 个 RAG 检索
  - Agent 自动判断意图选择工具
- [x] Phase 6: 前端对接 + 部署 ✅ 2026-06-07
  - Vue 3 单页面（CDN 引入，无需 npm）
  - SSE 流式对话界面
  - Dockerfile + docker-compose.yml
  - README.md
- [x] Phase 7: 优化增强 ✅ 2026-06-08
  - RAG 引用溯源
  - Prompt 注入防护
  - Token 消耗统计 + 管理仪表盘
  - Agent 推理可视化
  - 混合检索（BM25 + 向量）
- [x] Phase 8: 功能扩展与深度优化 ✅ 2026-06-09
  - [x] 知识库扩充（15 份文档） ✅ 2026-06-09
  - [x] Reranker 精排（FlashRank） ✅ 2026-06-09
  - [x] 离线评估体系（65 条测试用例 + 评估脚本 + LLM Judge） ✅ 2026-06-09
  - [x] 三模式功能统一 ✅ 2026-06-09
    - Agent 模式：来源解析支持 ToolMessage 对象
    - 贴心助手：加入 search_knowledge_base 工具，统一 step 事件格式
    - 规则助手：保持原有功能
    - 三个模式都能检索知识库并展示参考来源（含摘要）
  - [x] Function Calling 扩展 ✅ 2026-06-09
    - 新增 4 个工具：query_ticket_status、check_order_status、calculate_price、get_recommendations
    - 扩展 mock_data.py：新增 ORDERS、MEMBERS、MEMBER_DISCOUNTS 数据
    - create_order 工具支持会员折扣
  - [x] 推荐能力 ✅ 2026-06-09
    - get_recommendations 工具支持按城市、类型、预算筛选
    - 返回推荐理由和最低票价
  - [x] 前端工程化（Vite + Element Plus） ✅ 2026-06-09
    - Vue 3 + TypeScript + Vite 6 + Element Plus + Pinia + Vue Router
    - 组件化重构：ChatMessage / ReasoningTimeline / SourceCard
    - SSE 流式对话对接、消息入场动画、流式光标
    - 响应式适配：移动端侧边栏折叠、汉堡菜单
    - 管理仪表盘：ECharts 替代 Chart.js，骨架屏加载
    - 侧边栏宽度持久化、快捷问题折叠
  - [x] 知识库管理 API ✅ 2026-06-09
    - GET /api/knowledge/documents — 文档列表
    - POST /api/knowledge/upload — 上传 .md 文件
    - DELETE /api/knowledge/documents/{name} — 删除文档
    - POST /api/knowledge/rebuild — 重建向量索引 + BM25 索引
- [x] Phase 9: 深度优化 ✅ 2026-06-14
  - [x] 查询改写（Query Rewriting） ✅ 2026-06-09
    - DeepSeek Flash 模型改写，~100ms 延迟
    - 集成到 search_knowledge_base 工具和 RAG 规则助手
    - 评估脚本支持 --rewrite 和 --compare 模式
    - HashEmbedding 下效果不明显（预期），真实 Embedding 下效果会更好
  - [x] 多 Agent 协作 ✅ 2026-06-10
    - LangGraph Supervisor 模式：编排 Agent → 票务 Agent / 知识 Agent
    - 票务 Agent：8 个工具（search_program、get_program_detail、get_ticket_info、create_order、query_ticket_status、check_order_status、calculate_price、get_recommendations）
    - 知识 Agent：1 个工具（search_knowledge_base）
    - Supervisor 分析意图自动路由，支持单 Agent 或双 Agent 协作
    - 推理时间线显示 Agent 标签（[调度中心]、[票务专家]、[知识库专家]）
    - API：POST /api/agent/multi
    - 前端新增「多Agent」模式选项
  - [x] MCP 协议集成 ✅ 2026-06-10
    - MCP Server 封装 9 个工具（search_program、get_program_detail、get_ticket_info、create_order、query_ticket_status、check_order_status、calculate_price、get_recommendations、search_knowledge_base）
    - 支持 stdio 模式（本地客户端）和 HTTP/SSE 模式（远程客户端）
    - API：GET /api/mcp/tools — 列出所有 MCP 工具
    - API：GET /api/mcp/info — 获取 MCP Server 信息
    - 启动方式：python -m app.mcp.server（stdio）或 python app/mcp/server.py --http（HTTP）

---

## 架构创新：四模式对话设计

项目提供四种对话模式，用户可根据场景选择。

### 模式对比

| 模式 | 技术实现 | 工具 | 适用场景 | 后端接口 |
|-----------|---------|------|---------|----|
| **规则助手** | RAG 检索知识库，基于文档回答 | 1 个（search_knowledge_base） | 退票政策、订票流程、入场规则 | POST /api/chat (chat_type=rag) |
| **贴心助手** | Function Calling，代码控制工具调用循环 | 8 个业务工具 | 查节目、查票档、下单 | POST /api/chat (chat_type=assistant) |
| **Agent** | LangGraph ReAct Agent，LLM 自主决策 | 全部 9 个工具 | 不确定用哪个模式时，最智能 | POST /api/agent |
| **多 Agent** | 6 节点结构化编排，分工协作 | 按需分配（ticket 8 个 / knowledge 1 个） | 跨领域复杂问题 | POST /api/agent/multi |

### 四种模式的本质区别

```
规则助手：    用户 → 查询改写 → BM25+向量检索 → LLM 生成回答（不调工具）
贴心助手：    用户 → LLM 判断 → 代码控制调工具 → LLM 生成回答（手动循环，最多 5 轮）
Agent 模式： 用户 → LLM 自主决策 → 自动调工具 → 自动判断停止（ReAct 循环）
多 Agent：   用户 → 意图分类 → 路由 → 专业子 Agent → 整合回答（6 节点结构化）
```

| 维度 | 规则助手 | 贴心助手 | Agent | 多 Agent |
|------|---------|---------|-------|---------|
| 工具调用 | ❌ | ✅ 代码控制 | ✅ LLM 自主 | ✅ 按分工 |
| LLM 自主决策 | ❌ | ❌ | ✅ | ✅ |
| 查询改写 | ✅ | ❌ | ❌ | ❌ |
| 可观测性 | 来源展示 | 工具步骤 | 工具步骤 | 节点进度 |
| 响应速度 | 最快 | 中等 | 中等 | 最慢 |

### 设计思路

1. **规则助手**：纯 RAG，不调工具，最稳定的问答模式
2. **贴心助手**：Function Calling，代码控制工具调用循环，可控性强
3. **Agent 模式**：LangGraph ReAct，LLM 全权决策，最灵活
4. **多 Agent 模式**：6 节点结构化编排（intent_classifier → router → 子 Agent → answer_generator → fallback），可观测可扩展

### 多 Agent 架构

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: str           # 意图分类
    route: str            # 路由决策
    current_agent: str    # 当前节点
    agent_results: dict   # 子 Agent 结果汇聚
    error: str | None     # 错误信息
    final_answer: str | None
```

节点：intent_classifier → router → ticket_agent / knowledge_agent → answer_generator → fallback

### 面试可讲的点

- "项目提供四种对话模式，从纯 RAG 到多 Agent 编排，覆盖不同复杂度场景"
- "多 Agent 模式用 LangGraph StateGraph 实现 6 节点结构化编排，意图分类→路由→专业子 Agent→回答生成→异常兜底"
- "状态用结构化 TypedDict（7 个字段），路由基于 state 字段而非消息标记"
- "answer_generator 对单 Agent 结果直接透传优化延迟，多 Agent 结果用 LLM 整合"

---

## 功能优化记录

### RAG 引用溯源 ✅ 2026-06-07

- RAG 回答末尾自动标注来源文档：`【来源：节目取消和退票-相关问题与回答】`
- 前端展示"参考来源"卡片，显示文档名和摘要
- RAG Prompt 增加引用要求："在回答末尾标注信息来源"
- `format_docs_with_source()` 将检索结果格式化为带来源的文本

### Prompt 注入防护 ✅ 2026-06-07

- 新增 `app/core/security.py` 安全模块
- 15+ 条正则规则覆盖常见注入模式：
  - 角色劫持："你现在是"、"you are now"
  - 指令覆盖："忽略之前的指令"、"ignore previous instructions"
  - 提示词泄露："输出你的提示词"、"show your prompt"
  - 模式切换："DAN模式"、"开发者模式"
- 检测到注入返回 400 错误，前端展示拦截提示
- 输入长度限制 2000 字符

### 智能标题生成 ✅ 2026-06-07

- 新对话首轮回复后自动调用 LLM 生成标题（替代默认"新对话"）
- 接口：POST /api/conversations/{id}/generate-title
- 标题上限 20 字，前端自动刷新对话列表

### Token 消耗统计 ✅ 2026-06-07

- 三种模式（Agent / 贴心助手 / 规则助手）均支持 token 用量统计
- SSE 事件 `{type: "usage", content: {prompt_tokens, completion_tokens, total_tokens}}`
- 前端消息气泡下方展示统计标签（Prompt / Completion / Total）

**实现方式：**

| 模式 | 统计方式 | 说明 |
|------|---------|------|
| 贴心助手 | `usage_metadata` 累计 | ainvoke 工具轮次 + astream 流式最后一帧 |
| Agent | `on_chat_model_end` 事件 | LangGraph astream_events 捕获每轮 LLM 调用 |
| 规则助手 | `llm.get_num_tokens()` 估算 | RAG 链用 StrOutputParser 丢失 usage，改用 token 计数 |

**涉及文件：**
- `app/services/chat_service.py` — LLM 加 `stream_usage=True`，两种模式累计 token
- `app/chains/agent.py` — `on_chat_model_end` 捕获 usage_metadata
- `app/pipelines/rag_pipeline.py` — `get_rag_chain()` 返回 LLM 实例用于 token 估算
- `app/services/agent_service.py` — 解析 usage SSE 事件
- `static/index.html` — CSS 样式 + 模板展示 + 事件处理

### 管理员仪表盘 ✅ 2026-06-07

- Token 用量持久化到 `messages.token_usage` 字段（JSON）
- 独立管理页面 `/admin`，Vue 3 + ECharts
- 三个统计维度：
  - 总览卡片：总对话数、总消息数、总 Token、平均 Token
  - 柱状图：每日 Token 消耗趋势（输入/输出堆叠）
  - 饼图：三种模式（贴心助手/规则助手/Agent）Token 占比
- SQLite 增量迁移：启动时自动检测并添加 `token_usage` 列

**涉及文件：**
- `app/models/conversation.py` — Message 模型加 `token_usage` JSON 列
- `app/core/database.py` — `migrate_db()` 启动时自动迁移
- `app/services/memory_service.py` — `save_message()` 加 `token_usage` 参数
- `app/services/chat_service.py` — 捕获 usage 事件并持久化
- `app/services/agent_service.py` — 传递 `token_usage` 给 `save_message()`
- `app/api/admin.py` — 3 个统计接口（summary / trend / by_mode）
- `app/main.py` — 注册 admin 路由 + `/admin` 页面
- `static/admin.html` — 管理员仪表盘页面

### Agent 思考过程可视化 ✅ 2026-06-08

- Agent 模式下展示推理过程时间线（可折叠）
- 三类步骤事件：reasoning（选择工具）→ tool_start（执行工具）→ tool_end（工具返回）
- 流式输出时实时显示推理步骤，完成后折叠保存
- 步骤圆点颜色区分：黄色=推理、蓝色=执行、绿色=完成

**涉及文件：**
- `app/chains/agent.py` — 发射 `step` 类型 SSE 事件（reasoning/tool_start/tool_end）
- `static/index.html` — 新增 `.thinking-steps` CSS 样式 + 步骤模板 + SSE 解析

**SSE 事件格式：**
```json
{"type": "step", "step": 1, "action": "reasoning", "content": "分析意图，选择工具: search_program({\"city\": \"北京\"})"}
{"type": "step", "step": 1, "action": "tool_start", "tool": "search_program", "content": "执行工具: search_program"}
{"type": "step", "step": 1, "action": "tool_end", "tool": "search_program", "content": "工具返回: ..."}
```

### 混合检索（BM25 + 向量） ✅ 2026-06-08

- RAG 检索从纯向量升级为 BM25 + 向量混合检索
- RRF（Reciprocal Rank Fusion）融合排序，BM25 权重 0.9，向量权重 0.1（因 DashScope Embedding 精度有限，BM25 字面匹配更可靠）
- BM25 索引持久化到 `data/bm25_index.pkl`，随 `build_rag.py` 一起构建
- 中文字符级分词（`list(text)`），适合短文档精确匹配

**涉及文件：**
- `app/pipelines/rag_pipeline.py` — 新增 `build_bm25_index()`、`load_bm25_index()`、`hybrid_retrieve()`、`get_hybrid_retriever()`
- `app/services/chat_service.py` — `_rag_chat()` 改用 `get_hybrid_retriever()`
- `build_rag.py` — 构建向量库时同步构建 BM25 索引

**依赖：**
- `rank_bm25==0.2.2`（8.6kB，纯 Python）

### Reranker 精排 ✅ 2026-06-09

- 在混合检索（BM25 + 向量 RRF）之后加 Reranker 精排
- 粗排取 20 个候选 → FlashRank Reranker 精排 → 取 Top-5
- 来源命中率从 23.6% 提升到 32.7%（+9.1%）
- 单次推理延迟约 80ms（CPU）

**涉及文件：**
- `app/pipelines/rag_pipeline.py` — 新增 `get_ranker()`、`rerank()`，修改 `hybrid_retrieve()` 接入 Reranker
- `app/chains/tools.py` — `search_knowledge_base` 改用混合检索 + Reranker
- `app/core/config.py` — 新增 `reranker_model`、`reranker_top_n`、`reranker_candidate_count` 配置
- `.env` / `.env.example` — 新增 Reranker 环境变量

**依赖：**
- `flashrank==0.2.10`（极轻量 Reranker，~30MB，CPU 友好）

**模型：**
- `ms-marco-TinyBERT-L-2-v2`（FlashRank 默认模型，~3MB）
- 模型缓存到 `models/` 目录，避免重复下载

**检索流程变更：**
```
现有：query → BM25+向量 RRF → Top-4 → LLM
增强：query → BM25+向量 RRF → Top-20 → Reranker 精排 → Top-5 → LLM
```

### 知识库扩充 ✅ 2026-06-09

- 从 2 份文档扩充到 12 份，覆盖完整票务业务场景
- 新增文档：选座指南、支付方式、会员权益、优惠活动、各城市场馆信息、入场须知、无障碍服务、儿童票政策、演出变更与延期、取票与配送
- 分块数从 6 个增加到 26 个

### 离线评估体系 ✅ 2026-06-09（2026-06-14 扩展至 65 条 + LLM Judge）

- 65 条标准问答对（55 knowledge + 5 ticket + 5 both，覆盖所有 15 份文档）
- 评估脚本支持：单次评估、对比模式（有/无 Reranker）
- 评估指标：来源命中率 @K、关键词命中率、端到端延迟

**涉及文件：**
- `eval/eval_dataset.json` — 65 条测试用例
- `eval/llm_judge.py` — LLM Judge 评估脚本
- `eval/evaluate.py` — 评估脚本
- `eval/results/eval_report.json` — 评估结果

**评估结果（2026-06-09）：**

| 指标 | 无 Reranker | 有 Reranker | 变化 |
|------|------------|------------|------|
| 来源命中率 @5 | 23.6% | 32.7% | **+9.1%** |
| 关键词命中率 | 38.2% | 32.7% | -5.5% |
| 平均延迟 | 3ms | 80ms | +77ms |

**备注：** 基线命中率偏低是因为当前用的是 HashEmbedding（demo 用，精度低）。后续换真实 Embedding 模型（如 DashScope tongyi-embedding-vision-plus）可进一步提升。

**评估结果（2026-06-14，Parent-Child 分块 + DashScope Embedding）：**

| 指标 | HashEmbedding 基线 | DashScope 基线 | Parent-Child 优化后 |
|------|-------------------|---------------|-------------------|
| 来源命中率 @5 | 23.6% | 56.4% | **100%** |
| 关键词命中率 | 38.2% | — | **100%** |
| 平均延迟 | 3ms | — | 313ms |

**关键发现：**
- 英文 Reranker（ms-marco-TinyBERT-L-2-v2）在中文内容上效果反而变差（100% → 81.8%），已默认关闭
- Parent-Child 分块 + 标题注入是命中率提升的主要原因
- 65 条测试用例全部命中来源和关键词

### 三模式功能统一 ✅ 2026-06-09

**问题背景：**
- Agent 模式：有分析过程，但参考来源为空
- 贴心助手：无法检索知识库，只能调用业务工具
- 规则助手：有参考来源，但没有分析过程

**修复内容：**

| 模式 | 修复前 | 修复后 |
|------|--------|--------|
| Agent | 来源解析不支持 ToolMessage | 支持 `output.content` 解析 |
| 贴心助手 | TOOLS 不含知识库工具 | 加入 `search_knowledge_base` |
| 贴心助手 | 发送 `thinking`/`tool_result` 事件 | 统一为 `step` 事件格式 |
| 贴心助手 | 不提取知识库来源 | 自动提取 `[来源：xxx]` 标记 |
| 贴心助手 | 参考来源无摘要 | 提取来源标记后的内容作为摘要 |
| 贴心助手 | 可能无限调用工具 | 限制最多 2 轮工具调用 |

**涉及文件：**
- `app/chains/agent.py` — 来源解析支持 ToolMessage 对象
- `app/services/chat_service.py` — 贴心助手加入知识库工具、统一事件格式、来源提取
- `app/chains/tools.py` — `search_knowledge_base` 返回包含 `[来源：xxx]` 标记

**三模式对比（修复后）：**

| 模式 | 分析过程 | 参考来源 | 业务工具 | 知识库检索 | 响应速度 |
|------|:--------:|:--------:|:--------:|:----------:|:--------:|
| Agent | ✅ | ✅ | ✅ | ✅ | 慢 |
| 贴心助手 | ✅ | ✅ | ✅ | ✅ | 中 |
| 规则助手 | ❌ | ✅ | ❌ | ✅ | 快 |

### Function Calling 扩展 ✅ 2026-06-09

**新增工具：**

| 工具 | 功能 | 参数 | 返回 |
|------|------|------|------|
| `query_ticket_status` | 查询实时余票 | program_id | 各票档余票状态 |
| `check_order_status` | 查询订单状态 | order_number | 订单详情 |
| `calculate_price` | 计算票价含折扣 | program_id, ticket_price, ticket_count, mobile | 原价、折扣、实付 |
| `get_recommendations` | 推荐演出 | city, category, budget | 推荐列表 |

**数据扩展：**

| 数据 | 说明 |
|------|------|
| `ORDERS` | 订单存储字典，create_order 自动写入 |
| `MEMBERS` | 会员信息（手机号 → 等级、积分、折扣） |
| `MEMBER_DISCOUNTS` | 会员折扣规则（普通 1.0、银卡 0.95、金卡 0.9、钻石 0.85） |

**涉及文件：**
- `app/services/mock_data.py` — 新增 ORDERS、MEMBERS、MEMBER_DISCOUNTS
- `app/chains/tools.py` — 新增 4 个工具，create_order 支持会员折扣
- `app/chains/agent.py` — 更新 ALL_TOOLS 列表
- `app/services/chat_service.py` — 更新 TOOLS 列表

**工具总数：** 9 个（原有 5 个 + 新增 4 个）
