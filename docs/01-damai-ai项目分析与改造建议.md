# 大麦 AI 智能客服项目分析与 Python 改造建议

> 基于 `D:\ClaudeCodeProjects\CCdamai\damai-ai` 源码分析

---

## 一、项目现状总览

### 1.1 技术架构

| 层级 | 技术 | 说明 |
|------|------|------|
| 框架 | Spring Boot 3.5 + Spring AI 1.0 | Java AI 应用框架 |
| 模型 | DeepSeek + OpenAI (阿里 DashScope) + Ollama | 三模型并行 |
| 向量存储 | SimpleVectorStore（内存） | 开发级，非生产级 |
| 全文检索 | Elasticsearch 7.17 + Easy-ES | 节目搜索用 |
| 数据库 | MySQL + MyBatis-Plus | 元数据 + 会话历史 |
| 前端 | Vue 3 | 对话界面 |

### 1.2 两大 AI 角色

```
┌─────────────────────────────────────────────────────────┐
│                    大麦 AI 智能客服                       │
│                                                         │
│  ┌─────────────────────┐  ┌─────────────────────────┐   │
│  │    贴心助手（麦小蜜）  │  │      规则助手            │   │
│  │                     │  │                         │   │
│  │  Function Calling   │  │  RAG 检索增强生成         │   │
│  │  ├─ 查节目推荐        │  │  ├─ Markdown 文档加载    │   │
│  │  ├─ 查节目详情        │  │  ├─ Embedding 向量化     │   │
│  │  ├─ 查票档信息        │  │  ├─ 语义检索             │   │
│  │  └─ 生成订单         │   │  └─ 问答生成             │   │
│  │                     │  │                         │   │
│  │  业务系统对接         │  │  购票/退票规则问答         │   │
│  └─────────────────────┘  └─────────────────────────┘   │
│                                                         │
│  共享能力：                                               │
│  ├─ Advisor 链（日志/历史/标题/记忆）                       │
│  ├─ JDBC 会话持久化                                       │
│  ├─ 多模型切换                                            │
│  └─ 提示词工程                                            │
└─────────────────────────────────────────────────────────┘
```

### 1.3 核心代码结构

| 包路径 | 职责 | 关键类 |
|--------|------|--------|
| `config/` | 自动装配 | `DaMaiAiAutoConfiguration`、`DaMaiRagAiAutoConfiguration` |
| `ai/function/` | Function Calling | `AiProgram`（@Tool 定义）、`ProgramCall`、`OrderCall` |
| `ai/rag/` | RAG 能力 | `MarkdownLoader`、`QueryRewriter` |
| `advisor/` | 自定义拦截器 | `ChatTypeHistoryAdvisor`、`ChatTypeTitleAdvisor` |
| `controller/` | API 接口 | `SimpleChatController`、`ProgramController` |
| `service/` | 业务逻辑 | `ChatTypeHistoryService` |

---

## 二、项目评价

### 2.1 优点

| 优点 | 说明 |
|------|------|
| **完整的业务闭环** | 不是 demo 级别，有真实业务场景（节目查询 → 下单 → 支付跳转） |
| **Function Calling 实现规范** | 使用 @Tool 注解定义工具，参数描述清晰，AI 能正确调用业务接口 |
| **Prompt 工程做得不错** | 系统提示词定义了角色、规则、安全防护、输出约束，有实际生产意识 |
| **多模型支持** | 同时接入 DeepSeek / OpenAI / Ollama，通过配置切换 |
| **自定义 Advisor 链** | 理解 Spring AI 的拦截器模式，实现了日志、历史保存、标题生成等可插拔扩展 |
| **会话持久化** | JDBC Chat Memory，支持多会话管理 |
| **RAG 基础流程完整** | 文档加载 → Embedding → 向量存储 → 检索 → 问答 |

### 2.2 不足（与主流 AI 应用开发岗位要求对比）

| 不足 | 严重程度 | 说明 |
|------|:--------:|------|
| **Spring AI 生态认可度低** | ★★★★★ | 招聘 JD 90% 要求 Python/LangChain，Spring AI 几乎不被提及 |
| **向量数据库太弱** | ★★★★☆ | SimpleVectorStore 是内存存储，重启丢失，非生产方案 |
| **RAG 实现过于基础** | ★★★★☆ | 无分块策略、无重排序、无混合检索、无引用溯源 |
| **无 Agent 编排** | ★★★☆☆ | Function Calling 是单轮工具调用，缺少 ReAct 循环、任务规划 |
| **无流式输出** | ★★★☆☆ | 贴心助手未实现 SSE 流式返回，用户体验差 |
| **无 Docker 部署** | ★★☆☆☆ | 缺少容器化，部署不方便 |
| **无测试** | ★★☆☆☆ | 没有单元测试和集成测试 |
| **硬编码较多** | ★★☆☆☆ | 外部 URL 写死在常量类中，不够灵活 |
| **ES 与向量库割裂** | ★★☆☆☆ | 节目检索用 ES 全文搜索，RAG 用内存向量库，未统一 |

### 2.3 与招聘要求的匹配度

```
招聘要求关键词匹配：

✅ Function Calling         — 有，实现完整
✅ RAG                      — 有，但基础
✅ Prompt Engineering       — 有，做得不错
✅ 会话记忆管理              — 有，JDBC 持久化
✅ 多模型支持                — 有，三模型切换
❌ Python / LangChain       — 无，使用 Spring AI
❌ 向量数据库（Milvus等）     — 无，使用内存存储
❌ LangGraph / Agent 编排    — 无
❌ 重排序 / 混合检索          — 无
❌ 引用溯源                  — 无
❌ 流式输出（SSE）            — 无
❌ Docker 部署               — 无
```

**结论：项目能体现你理解 AI 应用开发的核心概念，但技术栈与市场主流需求不匹配。**

---

## 三、改造建议：Python 技术栈迁移

### 3.1 为什么值得改造

| 理由 | 说明 |
|------|------|
| **对齐市场主流** | Python + LangChain 是 AI 应用开发的通用语言，面试直接能聊 |
| **已有业务逻辑** | 不需要重新设计业务，只需要技术栈替换 |
| **深化理解** | 改造过程中你会对比两种实现，理解更深 |
| **简历升级** | "基于 Spring AI 实现" vs "基于 LangChain + LangGraph 实现"，后者含金量更高 |
| **学习曲线可控** | 你已理解 Function Calling、RAG、Advisor 等概念，只需要学 Python 实现方式 |

### 3.2 技术栈映射

| 大麦项目 (Spring AI) | 改造后 (Python) | 说明 |
|----------------------|-----------------|------|
| Spring Boot | FastAPI | Python Web 框架 |
| Spring AI ChatClient | LangChain ChatModel | 模型抽象层 |
| @Tool 注解 | LangChain Tools / @tool | 工具定义 |
| Advisor 链 | LangChain Callbacks / Middleware | 拦截器机制 |
| QuestionAnswerAdvisor | LangChain RAG Chain | RAG 检索问答 |
| SimpleVectorStore | ChromaDB | 向量数据库 |
| MarkdownLoader | LangChain DocumentLoader | 文档加载 |
| QueryRewriter | LangChain QueryTransform | 查询改写 |
| JDBC Chat Memory | Redis / SQLite | 会话持久化 |
| OpenAiEmbeddingModel | sentence-transformers / OpenAI Embedding | Embedding |
| Easy-ES (节目检索) | Elasticsearch DSL / 保留 | 全文检索 |

### 3.3 改造后的架构

```
┌──────────────────────────────────────────────────────────────┐
│                   SmartKB (Python 版大麦客服)                  │
│                                                              │
│  ┌──────────────────┐   ┌──────────────────────────────────┐ │
│  │   FastAPI 后端    │   │          Vue 3 前端（复用）        │ │
│  └────────┬─────────┘   └──────────────────────────────────┘ │
│           │                                                  │
│  ┌────────┴──────────────────────────────────────────────┐   │
│  │                   服务层                               │   │
│  │                                                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐   │   │
│  │  │ ChatService │  │ DocService  │  │ AgentService │   │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘   │   │
│  └─────────┼────────────────┼────────────────┼───────────┘   │
│            │                │                │               │
│  ┌─────────┴────────┐  ┌────┴─────┐   ┌──────┴───────────┐   │
│  │  RAG Pipeline    │  │ Document │   │  Agent Pipeline  │   │
│  │                  │  │ Pipeline │   │                  │   │
│  │  检索+重排序+生成  │  │ 解析+分块  │   │  LangGraph Agent │   │
│  │  + 引用溯源       │  │ +Embed   │   │   + 多工具调用     │   │
│  └──────────┬───────┘  └────┬─────┘   └──────┬───────────┘   │
│             │               │                │               │
│  ┌──────────┴───────────────┴────────────────┴──────────┐    │
│  │                    基础设施                           │    │
│  │  ChromaDB  │  MySQL  │  Redis  │  DeepSeek/GPT API   │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 3.4 改造后新增能力（原项目缺失的）

| 新增能力 | 说明 | 面试价值 | 实现状态 |
|----------|------|----------|:--------:|
| **ChromaDB 向量数据库** | 替换 SimpleVectorStore，数据持久化 | ★★★★★ | ✅ |
| **智能分块策略** | Markdown 标题感知切分 + Parent-Child 分块 | ★★★★★ | ✅ |
| **混合检索** | BM25 + 向量，RRF 融合排序 | ★★★★★ | ✅ |
| **Reranker 重排序** | FlashRank（ms-marco-TinyBERT-L-2-v2）精排 | ★★★★☆ | ✅（Phase 8） |
| **引用溯源** | 回答标注来源文档和段落，端到端持久化 | ★★★★★ | ✅ |
| **LangGraph Agent** | ReAct 循环 + 多工具编排 | ★★★★★ | ✅ |
| **SSE 流式输出** | 实时流式返回 | ★★★★☆ | ✅ |
| **Docker 部署** | 一键启动 | ★★★☆☆ | ✅ |
| **Prompt 注入防护** | 正则检测 + 输入清理 | ★★★★☆ | ✅ |
| **Token 消耗统计** | 流式返回 + 持久化 + 管理仪表盘 | ★★★★☆ | ✅ |
| **Agent 推理可视化** | 推理过程时间线展示 + 持久化 | ★★★★★ | ✅ |
| **多轮意图追踪（DST）** | 结构化输出维护对话状态，减少重复追问 | ★★★★★ | ✅（Phase 8） |
| **离线评估体系** | 65 条测试用例 + LLM Judge，量化 Recall/Precision/MRR/回答质量 | ★★★★☆ | ✅（Phase 8） |
| **前端工程化** | Vite + Element Plus + TypeScript | ★★★★☆ | ✅（Phase 8） |
| **Function Calling 扩展** | 新增查询、计算、推荐等操作类工具 | ★★★★☆ | ✅（Phase 8） |

---

## 四、改造方案选择

### 方案 A：完全重写（推荐）

从零用 Python + LangChain 搭建，但复用原项目的业务逻辑和 Prompt 设计。

| 维度 | 说明 |
|------|------|
| 周期 | 3-4 周 |
| 优点 | 代码干净、架构合理、技术栈主流 |
| 缺点 | 工作量较大 |
| 适合 | 时间充裕，想打牢 Python AI 基础 |

### 方案 B：混合架构

保留 Java 后端业务服务，新增 Python AI 网关层处理 RAG 和 Agent。

| 维度 | 说明 |
|------|------|
| 周期 | 2-3 周 |
| 优点 | 复用现有业务代码，学习 AI 层即可 |
| 缺点 | 架构复杂，部署麻烦 |
| 适合 | 想保留 Java 能力展示 |

### 方案 C：基于原项目增强（不推荐）

继续用 Spring AI 增强 RAG、加 Agent 能力。

| 维度 | 说明 |
|------|------|
| 周期 | 2-3 周 |
| 优点 | 改动最小 |
| 缺点 | 技术栈仍不主流，面试认可度低 |
| 适合 | 不打算投 AI 岗，只是了解 |

---

## 五、改造后简历话术对比

### 改造前（Spring AI 版）

> 基于 Spring AI 构建智能票务助手，实现 Function Calling 对接业务系统、RAG 购票规则问答、自定义 Advisor 链、JDBC 会话记忆。

**面试官内心：** Spring AI？没用过，不好评价深度。

### 改造后（Python + LangChain 版）

> 基于 LangChain + LangGraph 构建智能票务助手系统。
> - 实现 RAG 全流程：Markdown 文档解析 → 标题感知分块 → DashScope Embedding → ChromaDB 向量存储 → 混合检索（BM25 + 向量）→ LLM 生成，支持引用溯源
> - 基于 LangGraph 构建 6 节点多 Agent 系统，通过 Function Calling 实现节目查询、票档查询、订单生成等多工具自动调用
> - 实现 SSE 流式输出 + 多轮对话记忆 + Prompt 注入防护
> - Docker Compose 一键部署，支持 DeepSeek / GPT-4o 多模型切换

**面试官内心：** 技术栈主流，RAG 链路完整，Agent 有深度，可以聊聊。

---

## 六、从原项目中可以复用的内容

| 内容 | 复用方式 |
|------|----------|
| **系统提示词** | 直接翻译为 Python 版本，Prompt 设计思路不变 |
| **业务逻辑** | 节目查询、订单创建的业务流程可以直接参考 |
| **Function 定义** | @Tool 的参数描述和业务逻辑直接迁移 |
| **Advisor 设计思路** | 日志、历史保存、标题生成的拦截器模式对应 LangChain Callbacks |
| **Vue 前端** | 基本可以复用，只改 API 对接 |
| **MySQL 表结构** | 会话历史表设计可以直接复用 |

---

## 七、总结

| 结论 | 说明 |
|------|------|
| **项目本身** | 作为一个学习项目，完成度不错，体现了 AI 应用开发的核心概念 |
| **求职价值** | Spring AI 技术栈在招聘市场认可度低，简历竞争力不足 |
| **建议** | 用 Python + LangChain 重写 AI 层，复用原项目的业务逻辑和 Prompt 设计 |
| **改造周期** | 3-4 周（方案 A 完全重写） |
| **最终效果** | 一个技术栈主流、架构完整、能讲出深度的 AI 应用项目 |
