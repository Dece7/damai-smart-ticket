# Phase 9：深度优化

> 查询改写、多 Agent 协作、MCP 协议集成。

---

## 做了什么

三个方向的深度优化：① 检索质量（Query Rewriting 查询改写）、② Agent 架构（Supervisor 多 Agent 协作）、③ 协议标准化（MCP 工具封装）。

---

## 核心知识点

### 1. 查询改写（Query Rewriting）

用户提问往往模糊、简短、口语化，直接拿去检索效果差：

```
用户输入:  "怎么退"                       →   直接检索命中率低
改写后:    "退票政策和退款流程"             →   检索命中率高

用户输入:  "那个周杰伦的"                  →   直接检索命中率低
改写后:    "周杰伦演唱会门票价格和购票方式"   →   检索命中率高
```

```python
QUERY_REWRITE_PROMPT = """将用户的简短、模糊、口语化问题改写为适合知识库检索的完整查询。
规则：
1. 补充缺失的上下文
2. 口语化表达转为正式表述
3. 保留原始意图，不添加额外信息
4. 如果问题已经足够清晰，直接返回原问题

用户问题: {question}
改写后的查询:"""
```

**集成位置（仅规则助手）：**
```
规则助手：用户输入 → 查询改写 → BM25 + 向量检索 → RRF → LLM 生成
                     ↑
                  新增环节

其他模式：LLM 决定调 search_knowledge_base(query="退票政策") → 检索 → 返回
                                    ↑
                   LLM 的 query 已经足够精准，不需要二次改写
```

仅规则助手有查询改写，其他模式通过工具调用时不做改写。原因：LLM 调工具时的 query 已经是精准表述，再改写是重复劳动。

**技术方案对比：**

| 方案 | 实现 | 优点 | 缺点 |
|------|------|------|------|
| LLM 改写 | 用 LLM 将模糊问题改写为完整查询 | 效果最好 | 增加一次 LLM 调用延迟 |
| HyDE | LLM 生成假设性回答，用回答做检索 | 不需要标注数据 | 生成质量不稳定 |
| 多查询 | LLM 生成多个变体查询，合并结果 | 覆盖面广 | 检索次数翻倍 |

项目选择 **LLM 改写**，实现简单、效果稳定。

**实际评估结果（Parent-Child + DashScope）：**

| 指标 | 无改写 | 有改写 | 变化 |
|------|--------|--------|------|
| 来源命中率 @5 | 81.8% | 89.1% | **+7.3%** |
| 关键词命中率 | — | — | — |
| 平均延迟 | — | — | +100ms（LLM 改写耗时） |

查询改写在规则助手模式下提升来源命中率 7.3%，代价是增加约 100ms 延迟。

**面试要点：**
- 查询改写解决用户输入模糊导致检索命中率低的问题
- 用小模型做改写，~100ms 延迟，不影响整体响应速度
- 如果原始问题已经足够清晰，直接返回原问题，不强行改写
- 仅规则助手模式使用查询改写，其他模式 LLM 调工具时的 query 已经足够精准

**面试问：** 查询改写和 HyDE 的区别？
**答：** HyDE 生成假设性回答，用回答做检索；Query Rewriting 改写问题本身，更直接可控。HyDE 依赖生成质量，Query Rewriting 更稳定。

---

### 2. 多 Agent 协作（Supervisor 模式）

单个 Agent 处理所有请求，工具多了选择困难、上下文过长：

```
单 Agent：9 个工具混在一起，LLM 容易选错

多 Agent（6 节点结构化架构）：
  intent_classifier（意图分类）  →  router（路由决策）
                                    ├→ ticket_agent（票务专家，8 个工具）
                                    ├→ knowledge_agent（知识库专家，1 个工具）
                                    ├→ answer_generator（统一格式化回答）
                                    └→ fallback（异常兜底）
```

```python
# 结构化状态（7 个字段）
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: str           # 意图分类
    route: str            # 路由决策
    current_agent: str    # 当前节点
    agent_results: dict   # 子 Agent 结果汇聚
    error: str | None     # 错误信息
    final_answer: str | None

# 路由基于 state 字段，不用消息标记
def route_after_router(state):
    return {"ticket": "ticket_agent", "knowledge": "knowledge_agent",
            "both": "ticket_agent", "chat": "answer_generator"}[state["route"]]
```

**架构图：**
```
        用户输入
          │
          ▼
┌───────────────────┐
│ intent_classifier │  意图分类
└─────────┬─────────┘
          ▼
┌─────────────────────────────┐
│           router            │  路由决策（纯逻辑，无 LLM）
└────┬─────────┬─────────┬────┘
     │         │         │
     ▼         ▼         ▼
┌──────┐  ┌─────────┐  ┌────────────────┐
│ticket│  │knowledge│  │answer_generator│
│Agent │  │Agent    │  │（整合回答）      │
└──────┘  └─────────┘  └────────────────┘
             │
             ▼
    ┌────────────────┐
    │    fallback    │  异常兜底
    └────────────────┘
         │       │
         ▼       ▼
    ┌────────────────┐
    │    合并结果     │  汇总输出 
    └────────────────┘
```

**三种多 Agent 模式对比：**

| 模式 | 适用场景 | 实现复杂度 |
|------|---------|-----------|
| **Supervisor** | 一个编排 Agent 分派任务给子 Agent | ★★☆☆☆ |
| **Hierarchical** | 多层级 Agent 树状结构 | ★★★★☆ |
| **Swarm** | Agent 之间互相传递控制权 | ★★★★★ |

项目选择 **Supervisor 模式**，面试够用，实现可控。

**关键实现细节：**

| 问题 | 解决方案 |
|------|---------|
| 路由消息干扰子 Agent | 已重构为结构化 state 路由，不再需要过滤 |
| 意图分类器流式输出泄露 | intent_classifier 节点的 token 不推送给前端 |
| 子 Agent 暴露内部标识 | 提示词约束"不要提及 Agent 名称" |

**面试要点：**

- Supervisor 模式是最简单的多 Agent 架构，一个编排 Agent 分派任务给子 Agent
- 子 Agent 各有独立的 system prompt 和工具集，决策更精准
- 子 Agent 之间通过共享 State 传递消息，或通过 Supervisor 中转

**面试问：** 多 Agent 和单 Agent + 多工具的区别？
**答：** 多 Agent 有独立的 system prompt 和工具集，决策更精准；单 Agent 所有工具混在一起，容易选错。比如问"会员有什么等级"，单 Agent 可能调用 search_program（搜演出），多 Agent 的知识库 Agent 只会调用 search_knowledge_base。

---

### 3. MCP 协议集成（Model Context Protocol）

MCP 是 Anthropic 提出的标准化协议，让 AI 模型以统一方式连接外部工具和数据源。

```
传统方式：                          MCP 方式：
每个工具写自定义适配代码              统一协议，即插即用
┌────────┐                        ┌────────┐
│  AI    │── 自定义 API ──→ 工具A   │  AI    │── MCP 协议 ──→ MCP Server A
│  模型   │── 自定义 API ──→ 工具B  │  模型   │── MCP 协议 ──→ MCP Server B
└────────┘                        └────────┘
```

```python
from mcp.server import Server

server = Server("damai-ticket-server")

@server.tool()
async def search_program(city: str, keyword: str = None) -> str:
    """搜索演出信息"""
    # 现有逻辑
    ...

@server.tool()
async def get_ticket_info(program_id: int) -> str:
    """查询票档信息"""
    ...
```

**两种运行模式：**

| 模式 | 启动方式 | 适用场景 |
|------|---------|---------|
| stdio | `python -m app.mcp.server` | 本地客户端（Claude Desktop、Cursor） |
| HTTP/SSE | `python app/mcp/server.py --http` | 远程客户端、Web 应用 |

**适用场景说明：**

本项目将票务工具 MCP 化主要是**技术展示**，实际第三方客户端（Claude Desktop、Cursor）不会去查演唱会或下单。MCP 真正适合的是**通用型工具服务**：

| 适合 MCP 化的服务 | 工具示例 | 第三方客户端用途 |
|-----------------|---------|----------------|
| 数据库查询 | `query_sql`, `list_tables` | Claude 直接查数据库 |
| 文件管理 | `read_file`, `search_files` | Cursor 操作文件系统 |
| 日志查询 | `search_logs`, `get_error_trace` | Claude 分析系统日志 |
| 内部知识库 | `search_docs`, `get_api_spec` | Claude 查公司文档 |
| 监控系统 | `get_metrics`, `check_alerts` | Claude 查看系统状态 |

**面试要点：**
- MCP 解决工具适配碎片化问题，每个工具都要写自定义代码，MCP 提供统一协议
- 将现有工具封装为 MCP Server，第三方客户端即插即用
- MCP 和 Function Calling 互补：Function Calling 是 LLM 层面的工具调用机制，MCP 是传输层的标准化协议
- 本项目做 MCP 是技术展示，实际业务场景更适合通用型工具服务

**面试问：** MCP 和 Function Calling 的关系？
**答：** Function Calling 是 LLM 层面的机制，LLM 决定调用哪个工具、传什么参数；MCP 是传输层的标准化协议，定义工具怎么暴露、怎么连接、怎么调用。两者互补：Function Calling 负责"选哪个工具"，MCP 负责"工具怎么接入"。

**面试问：** 什么服务适合 MCP 化？
**答：** 通用型工具服务适合 MCP 化，比如数据库查询、文件管理、日志查询、内部知识库等，第三方 AI 客户端可以直接调用。业务型工具（如票务查询）做 MCP 主要是技术展示，实际使用场景有限。

---

### 面试高频问题

| 问题 | 回答要点 |
|------|---------|
| 查询改写怎么实现？ | LLM 将模糊问题改写为完整查询，用小模型（~100ms），原始问题足够清晰时不改写 |
| 多 Agent 有什么好处？ | 各司其职，独立 prompt 和工具集，决策更精准，可维护性更好 |
| Supervisor 怎么路由？ | LLM 分析意图，返回 Agent 名称，编排器根据名称分派任务 |
| MCP 解决什么问题？ | 工具适配碎片化，统一协议即插即用，第三方客户端标准化接入 |
| MCP 和 API 网关的区别？ | MCP 是 AI 领域的工具协议，包含工具发现、参数描述、调用语义；API 网关是通用的 HTTP 代理 |
