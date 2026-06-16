# DST 开发计划

> 大麦智能票务助手（Python 版）分阶段开发计划。
> 对标原项目 `D:\ClaudeCodeProjects\CCdamai\damai-ai`（Spring AI 版）功能逐步迁移。

---

## 总览

```
Phase 1  基础对话           1-2 天    FastAPI + Mimo 流式对话               ✅
Phase 2  Function Calling   2-3 天    工具定义 + AI 自动调用                ✅
Phase 3  RAG 知识库问答      2-3 天    Markdown + ChromaDB + 检索生成       ✅
Phase 4  会话记忆管理        1-2 天    多轮对话 + 多会话 + 数据库持久化         ✅
Phase 5  Agent 编排          2-3 天    LangGraph ReAct Agent              ✅
Phase 6  前端对接 + 部署     2-3 天    Vue 前端 + Docker                    ✅
Phase 7  优化增强            2-3 天    P0/P1 功能补齐                       ✅
Phase 8  功能扩展与深度优化   3 周     Reranker + 评估 + FC扩展 + 前端工程化   ✅
Phase 9  深度优化             1 周     查询改写 + 多Agent + MCP协议          ✅

总计：约 12-19 天（Phase 1-7）+ 3 周（Phase 8）+ 1 周（Phase 9）
```

---

## Phase 1：基础对话（1-2 天）

**目标：** FastAPI 启动 → 调 Mimo API → SSE 流式返回 → 浏览器能看到逐字输出

**要写的文件：**

| 文件 | 职责 |
|------|------|
| `app/core/config.py` | 配置读取（已有，微调） |
| `app/services/chat_service.py` | Mimo 对话服务 |
| `app/api/chat.py` | POST /api/chat 接口（SSE 流式） |
| `app/main.py` | FastAPI 入口 |

**技术要点：**
- LangChain `ChatOpenAI` 对接 Mimo（OpenAI 兼容协议）
- `astream()` 异步流式生成
- SSE（Server-Sent Events）实时返回
- FastAPI `StreamingResponse`

**对应原项目：**
- `SimpleChatController.java` → `chat.py`
- `DaMaiAiAutoConfiguration.chatClient()` → `chat_service.py`

**验证标准：**
1. `python run.py` 启动成功
2. 浏览器访问 `http://localhost:8000/docs` 看到 Swagger 文档
3. POST `/api/chat` 发送消息 → 流式返回 AI 回复

---

## Phase 2：Function Calling（2-3 天）

**目标：** AI 能自动识别用户意图并调用工具（查节目、查票档、生成订单）

**要写的文件：**

| 文件 | 职责 |
|------|------|
| `app/chains/tools.py` | 用 `@tool` 定义工具函数 |
| `app/services/chat_service.py` | 升级为支持工具调用的对话链 |
| `app/services/program_service.py` | 节目业务逻辑（对应 ProgramCall.java） |
| `app/services/order_service.py` | 订单业务逻辑（对应 OrderCall.java） |
| `app/utils/http_client.py` | HTTP 请求封装（对应 Hutool HttpRequest） |

**技术要点：**
- LangChain `@tool` 装饰器定义工具
- `ChatOpenAI.bind_tools()` 绑定工具
- Function Calling 响应解析
- 工具执行 + 结果回传 LLM

**对应原项目：**
- `AiProgram.java`（5 个 @Tool）→ `tools.py`（@tool 装饰器）
- `ProgramCall.java` → `program_service.py`
- `OrderCall.java` → `order_service.py`
- `DaMaiConstant.DA_MAI_SYSTEM_PROMPT` → 系统提示词迁移

**工具清单（对应原项目）：**

| 原项目 @Tool | Python 版工具 | 说明 |
|-------------|--------------|------|
| `selectProgramRecommendList` | `search_program` | 根据地区/类型查节目 |
| `selectProgramList` | `search_program_by_condition` | 按条件查节目 |
| `detail` | `get_program_detail` | 查节目详情 |
| `selectTicketCategory` | `get_ticket_info` | 查票档信息 |
| `createOrder` | `create_order` | 生成订单 |

**验证标准：**
1. 用户说"北京有什么演唱会" → AI 调用 `search_program` → 返回节目列表
2. 用户说"帮我买一张580的票" → AI 调用 `create_order` → 返回订单号
3. 工具调用日志可追踪

---

## Phase 3：RAG 知识库问答（2-3 天）

**目标：** 加载 Markdown 规则文档 → AI 基于文档内容回答购票/退票政策问题

**要写的文件：**

| 文件 | 职责 |
|------|------|
| `app/pipelines/document_pipeline.py` | 文档加载 + 分块 + Embedding |
| `app/pipelines/rag_pipeline.py` | 检索 + 重排序 + 生成 |
| `app/services/rag_service.py` | RAG 问答服务 |
| `app/utils/embedding.py` | Embedding 封装（DeepSeek API） |
| `docs/` | Markdown 规则文档（从原项目复制） |

**技术要点：**
- LangChain `MarkdownDocumentReader` 加载文档
- `RecursiveCharacterTextSplitter` 智能分块
- DashScope Embedding API 向量化
- ChromaDB 向量存储 + 语义检索
- Reranker 重排序（可选）
- Prompt 模板 + 引用溯源

**对应原项目：**
- `MarkdownLoader.java` → `document_pipeline.py`
- `DaMaiRagAiAutoConfiguration` → `rag_pipeline.py`
- `QuestionAnswerAdvisor` → RAG Chain
- `QueryRewriter.java` → 查询改写（可选）
- `DaMaiConstant.MARK_DOWN_SYSTEM_PROMPT` → RAG 提示词

**RAG 流程：**

```
文档入库：Markdown → 分块 → DashScope Embedding → ChromaDB
查询流程：用户问题 → Embedding → 语义检索 Top-K → 组装 Prompt → Mimo 生成回答
```

**验证标准：**
1. 加载规则文档后，ChromaDB 中有向量数据
2. 问"怎么退票" → AI 基于文档回答，不是瞎编
3. 回答附带引用来源（哪个文档、哪个段落）

---

## Phase 4：会话记忆管理（1-2 天）

**目标：** 多轮对话带上下文，支持多会话管理，历史持久化到数据库

**要写的文件：**

| 文件 | 职责 |
|------|------|
| `app/models/conversation.py` | 对话 + 消息 SQLAlchemy 模型 |
| `app/services/memory_service.py` | 会话记忆服务 |
| `app/api/conversation.py` | 对话管理接口（列表、历史、切换） |
| `sql/init.sql` | 建表 SQL |

**技术要点：**
- SQLAlchemy ORM 定义数据模型
- LangChain `ConversationBufferWindowMemory` 滑动窗口
- 会话历史持久化到 MySQL
- 对话标题自动生成

**对应原项目：**
- `ChatTypeHistory.java` + `ChatHistoryMapper.java` → SQLAlchemy 模型
- `ChatTypeHistoryAdvisor.java` → 记忆服务
- `ChatTypeTitleAdvisor.java` → 标题生成
- `MessageChatMemoryAdvisor` → 会话窗口管理
- JDBC Chat Memory → MySQL 持久化

**数据库表设计：**

```sql
-- 对话表
CREATE TABLE conversations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(200),
    chat_type VARCHAR(20),  -- assistant / rag
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 消息表
CREATE TABLE messages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL,
    role VARCHAR(20) NOT NULL,  -- user / assistant
    content TEXT NOT NULL,
    sources JSON,               -- RAG 引用来源
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**验证标准：**
1. 连续问两个相关问题 → AI 能记住上下文
2. 创建多个对话 → 切换对话 → 上下文不串
3. 重启服务 → 对话历史还在

---

## Phase 5：Agent 编排（2-3 天）

**目标：** 用 LangGraph 构建 ReAct Agent，自动选择 RAG 或 Function Calling

**要写的文件：**

| 文件 | 职责 |
|------|------|
| `app/chains/agent.py` | LangGraph ReAct Agent 定义 |
| `app/services/agent_service.py` | Agent 服务 |
| `app/api/agent.py` | Agent 对话接口 |

**技术要点：**
- LangGraph `create_react_agent` 构建 Agent
- 工具注册：Function Calling 工具 + RAG 检索工具
- Agent 自动判断：该查文档还是该调业务接口
- 工具调用过程可追踪可展示

**对应原项目：**
- 原项目用 Spring AI Advisor 链实现 → 用 LangGraph 状态图替代
- 原项目贴心助手和规则助手分开 → Agent 统一调度

**Agent 决策流程：**

```
用户输入
   │
   ▼
Agent（LLM 判断意图）
   │
   ├─ 需要查业务数据 → 调用 Function Calling 工具
   │                    ├─ search_program
   │                    ├─ get_ticket_info
   │                    └─ create_order
   │
   ├─ 需要查政策规则 → 调用 RAG 检索工具
   │                    └─ search_knowledge_base
   │
   └─ 简单闲聊 → 直接回答
```

**验证标准：**
1. "北京有什么演唱会" → Agent 选择 Function Calling 工具
2. "怎么退票" → Agent 选择 RAG 检索工具
3. "帮我查北京的演唱会，顺便告诉我退票政策" → Agent 同时调用两个工具

---

## Phase 6：前端对接 + 部署（2-3 天）

**目标：** Vue 前端对接、Docker 一键部署

**要做的事：**

| 任务 | 说明 |
|------|------|
| 复用原项目 Vue 前端 | 改 API 地址指向 Python 后端 |
| SSE 前端对接 | EventSource 接收流式返回 |
| 工具调用展示 | 前端展示 Agent 的工具调用过程 |
| Dockerfile | Python 后端容器化 |
| docker-compose.yml | 一键启动（后端 + MySQL + ChromaDB） |
| README.md | 项目说明、启动方式、架构图 |

**验证标准：**
1. `docker-compose up` 一键启动
2. 浏览器打开前端 → 对话功能正常
3. README 包含项目介绍、架构图、启动方式

---

## Phase 7：优化增强 ✅ 2026-06-08

**目标：** 补齐生产级能力，提升面试竞争力

| 优先级 | 功能 | 说明 | 状态 |
|--------|------|------|:----:|
| P0 | RAG 引用溯源 | sources 字段端到端持久化，前端展示来源卡片 | ✅ |
| P0 | Prompt 注入防护 | 15+ 条正则规则，chat/agent 双入口拦截 | ✅ |
| P1 | Token 消耗统计 | 流式返回 usage 事件 + messages 表持久化 + 管理仪表盘 | ✅ |
| P1 | Agent 推理可视化 | reasoning/tool_start/tool_end 三类 step 事件，可折叠时间线 | ✅ |
| P1 | 混合检索 | BM25 + 向量，RRF 融合排序 | ✅ |

**新增文件：**
- `app/core/security.py` — Prompt 注入检测模块
- `app/api/admin.py` — 管理统计接口（summary / trend / by_mode）
- `static/admin.html` — 管理员仪表盘页面（Vue 3 + ECharts）
- `data/bm25_index.pkl` — BM25 索引持久化

**依赖新增：**
- `rank_bm25==0.2.2`（8.6kB，BM25 检索）

---

## Phase 8：功能扩展与深度优化（3 周）

**目标：** 扩展核心功能、提升检索质量、完善前端工程化，从"能跑的 demo"升级为"有技术深度的完整产品"

### Week 1：Reranker + 评估体系 + 知识库扩充 ✅

| 任务 | 时间 | 说明 | 状态 |
|------|------|------|------|
| Reranker 集成 | 1 天 | FlashRank 精排，粗排 Top-20 → 精排 Top-5 | ✅ |
| 评估体系搭建 | 1 天 | 65 条测试用例 + 评估脚本（Recall/Precision/MRR/LLM Judge） | ✅ |
| Reranker 效果对比 | 0.5 天 | 来源命中率 +9.1%（23.6% → 32.7%） | ✅ |
| 知识库扩充 | 1 天 | 从 2 份扩充到 15 份，覆盖完整票务场景 | ✅ |
| build_rag 重建索引 | 0.5 天 | 重建向量库 + BM25 索引 | ✅ |
| 三模式功能统一 | 1 天 | Agent/贴心助手/规则助手都能检索知识库并展示来源 | ✅ |

**新增文件：**
- `app/pipelines/rag_pipeline.py` — 新增 `get_ranker()`、`rerank()`
- `eval/eval_dataset.json` — 65 条测试用例
- `eval/evaluate.py` — 评估脚本
- `docs/rag/` — 新增 10 份知识库文档

**依赖新增：**
- `flashrank==0.2.10`（极轻量 Reranker，~30MB）

### Week 2：Function Calling 扩展 + 推荐 ✅

| 任务 | 时间 | 说明 | 状态 |
|------|------|------|------|
| Function Calling 扩展 | 1.5 天 | 新增 4 个工具 | ✅ |
| 推荐能力 | 0.5 天 | 基于城市/类型/预算推荐演出 | ✅ |

**新增工具（总计 9 个）：**
- `query_ticket_status` — 查询实时余票状态
- `check_order_status` — 查询订单状态
- `calculate_price` — 计算票价含会员折扣
- `get_recommendations` — 推荐演出

**新增文件：**
- `app/chains/tools.py` — 新增 4 个工具函数
- `app/services/mock_data.py` — 新增 ORDERS、MEMBERS、MEMBER_DISCOUNTS

**技术要点：**
- 工具链自动编排：Agent 自动判断需要调用哪些工具并按顺序执行
- 会员折扣系统：银卡95折、金卡9折、钻石85折
- 订单生命周期：创建 → 保存 → 可查询

### Week 3：前端工程化 ✅

| 任务 | 时间 | 说明 | 状态 |
|------|------|------|:----:|
| Vite + Element Plus 项目初始化 | 0.5 天 | Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router | ✅ |
| 对话界面重构 | 1 天 | 流式消息 + 引用卡片 + Agent 推理时间线 | ✅ |
| 知识库管理页面 | 1 天 | 文档列表、上传、删除、重建索引 | ✅ |
| 管理仪表盘重构 | 1 天 | ECharts 替代 Chart.js，三个统计维度 | ✅ |
| 会话管理完善 | 0.5 天 | 左侧会话列表、置顶、重命名、删除 | ✅ |
| 知识库管理 API | 0.5 天 | 后端接口：文档列表/上传/删除/重建索引 | ✅ |

**新增目录：**
```
frontend/
├── src/
│   ├── views/
│   │   ├── ChatView.vue
│   │   ├── KnowledgeView.vue
│   │   └── AdminView.vue
│   ├── components/
│   │   ├── ChatMessage.vue
│   │   ├── ReasoningTimeline.vue
│   │   ├── SourceCard.vue
│   │   └── FileUpload.vue
│   ├── api/
│   ├── stores/
│   └── router/
├── package.json
└── vite.config.ts
```

---

## 各 Phase 对应原项目代码

| Phase | 原项目 Java 文件 | Python 版文件 |
|-------|-----------------|--------------|
| 1 | `SimpleChatController.java` | `api/chat.py` |
| 1 | `DaMaiAiAutoConfiguration.chatClient()` | `services/chat_service.py` |
| 2 | `AiProgram.java` | `chains/tools.py` |
| 2 | `ProgramCall.java` | `services/program_service.py` |
| 2 | `OrderCall.java` | `services/order_service.py` |
| 2 | `DaMaiConstant.DA_MAI_SYSTEM_PROMPT` | 配置文件中的系统提示词 |
| 3 | `MarkdownLoader.java` | `pipelines/document_pipeline.py` |
| 3 | `DaMaiRagAiAutoConfiguration` | `pipelines/rag_pipeline.py` |
| 3 | `QueryRewriter.java` | `pipelines/rag_pipeline.py`（可选） |
| 4 | `ChatTypeHistory.java` | `models/conversation.py` |
| 4 | `ChatTypeHistoryAdvisor.java` | `services/memory_service.py` |
| 4 | `ChatTypeTitleAdvisor.java` | `services/memory_service.py` |
| 5 | Advisor 链编排 | `chains/agent.py`（LangGraph） |
| 6 | `vue/` 目录 | 复用前端，改 API 地址 |

---

## 技术栈学习对照

| 原项目 (Spring AI) | Python 版 | 学到什么 |
|-------------------|-----------|---------|
| `ChatClient` | `ChatOpenAI` | 模型抽象层、统一接口 |
| `@Tool` | `@tool` | Function Calling 工具定义 |
| `Advisor` 链 | LangChain Callbacks / LangGraph | 拦截器模式、流程编排 |
| `QuestionAnswerAdvisor` | RAG Chain | 检索增强生成全流程 |
| `SimpleVectorStore` | ChromaDB | 向量数据库选型与使用 |
| `MarkdownLoader` | LangChain DocumentLoader | 文档解析与分块 |
| `JDBC Chat Memory` | SQLAlchemy + Memory | 会话持久化方案 |
| `@Autowired` | Python 依赖注入 | 配置管理、服务初始化 |
