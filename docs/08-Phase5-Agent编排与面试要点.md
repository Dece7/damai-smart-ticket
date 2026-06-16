# Phase 5：Agent 编排 — 知识点与面试要点

> LangGraph ReAct Agent、自动工具选择、多工具协作的技术细节和面试准备。

---

## 做了什么

用 LangGraph 构建 ReAct Agent，将 Function Calling 工具和 RAG 检索工具统一注册，Agent 自动判断用户意图并选择合适的工具。

---

## 核心知识点

### 1. 什么是 Agent

```
传统 LLM：                    Agent：
用户提问 → LLM → 回答          用户提问 → LLM → 思考 → 调用工具 → 观察 → 思考 → 回答
                              （可以多轮循环，直到得到满意答案）
```

**面试要点：**
- Agent = LLM + 工具 + 规划能力
- Agent 能**自主决策**：该调什么工具、传什么参数、什么时候停止
- ReAct 模式：Reasoning（推理）+ Acting（行动）循环
- Agent 是 AI 应用的**高级形态**，比单纯的 RAG 或 Function Calling 更灵活

**面试问：** Agent 和 Function Calling 的区别？
**答：** Function Calling 是单轮工具调用（用户→LLM→工具→回答）；Agent 是多轮自主推理循环，可以连续调用多个工具、根据中间结果调整策略。

---

### 2. LangGraph ReAct Agent

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    model=llm,
    tools=[search_program, get_ticket_info, create_order, search_knowledge_base],
    prompt=SYSTEM_PROMPT,
)
```

**面试要点：**
- `create_react_agent` 是 LangGraph 提供的开箱即用的 ReAct Agent
- 内置了：工具调用循环、结果解析、停止条件判断
- `prompt` 参数设置 Agent 的系统指令
- Agent 会自动处理：调用工具 → 解析结果 → 继续推理 → 最终回答

---

### 3. 统一工具注册

```python
ALL_TOOLS = [
    search_program,          # Function Calling：查节目
    get_ticket_info,         # Function Calling：查票档
    create_order,            # Function Calling：下单
    search_knowledge_base,   # RAG：搜索知识库
]
```

**面试要点：**
- Function Calling 工具和 RAG 工具可以**统一注册**到同一个 Agent
- Agent 根据用户意图**自动选择**用哪个工具
- 工具的 `docstring` 是 Agent 决策的依据

---

### 4. RAG 封装为工具

```python
@tool
def search_knowledge_base(query: str) -> str:
    """搜索购票规则知识库，回答退票政策、订票流程、入场规则等问题。
    当用户询问规则、政策、流程相关问题时使用此工具。
    """
    vectorstore = load_vectorstore()
    docs = vectorstore.similarity_search(query, k=3)
    return "\n\n".join(doc.page_content for doc in docs)
```

**面试要点：**
- RAG 可以封装为一个工具，Agent 在需要时自动调用
- 好处：Agent 可以**混合使用**业务工具和知识库工具
- 比如："帮我查周杰伦演唱会的票，顺便告诉我退票政策" → Agent 同时调用 `search_program` 和 `search_knowledge_base`

---

### 5. 流式事件（astream_events）

```python
async for event in agent.astream_events({"messages": messages}, version="v2"):
    kind = event.get("event", "")

    if kind == "on_chat_model_stream":     # LLM 生成 token
        yield event["data"]["chunk"].content

    elif kind == "on_tool_start":           # 工具开始调用
        yield f"正在调用工具: {event['name']}"

    elif kind == "on_tool_end":             # 工具返回结果
        yield event["data"]["output"]
```

**面试要点：**
- `astream_events` 是 LangChain 的流式事件 API
- 可以追踪 Agent 的每一步：LLM 生成、工具调用、工具结果
- 适合做**前端可视化**：展示 Agent 的思考和行动过程

---

### 6. Agent 决策流程

```
用户: "帮我查周杰伦演唱会的票，顺便告诉我退票政策"
  │
  ▼
Agent 思考: 用户需要两件事 - 查票和退票政策
  │
  ├─→ 调用 search_program(actor="周杰伦")     → 返回演唱会列表
  ├─→ 调用 search_knowledge_base("退票政策")   → 返回退票规则
  │
  ▼
Agent 综合两个工具的结果，生成最终回答
```

---

## 三种模式对比

| 模式 | 适用场景 | 本项目对应 |
|------|---------|-----------|
| **直接对话** | 简单闲聊 | Phase 1 |
| **Function Calling** | 调用业务接口 | Phase 2 |
| **RAG** | 基于文档问答 | Phase 3 |
| **Agent** | 混合场景，自动选择 | Phase 5 |

---

## 面试高频问题

| 问题 | 回答要点 |
|------|---------|
| 什么是 ReAct？ | Reasoning + Acting 循环：思考→行动→观察→思考... |
| Agent 和 Chain 的区别？ | Chain 是固定流程；Agent 是动态决策，自主选择工具 |
| 怎么防止 Agent 死循环？ | 设置最大循环次数、超时机制 |
| 工具的 docstring 为什么重要？ | Agent 通过 docstring 判断何时调用哪个工具 |
| 怎么让 Agent 同时调用多个工具？ | LLM 可以在一次响应中返回多个 tool_calls |
| LangGraph 的优势？ | 状态图编排、支持复杂流程、内置 ReAct Agent |

---

## 推理过程可视化

### 为什么需要

Agent 是"黑盒"——用户只看到最终回答，不知道 Agent 为什么选这个工具、传了什么参数。可视化推理过程可以：
- 增加用户信任（"原来它查了知识库才回答的"）
- 便于调试（"它选错了工具"）
- 面试加分（"我做了 Agent 可观测性"）

### 实现方式

通过 `astream_events` 捕获三类事件，构造推理时间线：

| 事件 | 触发时机 | 内容 |
|------|---------|------|
| `reasoning` | `on_chat_model_end` + 有 tool_calls | "分析意图，选择工具: search_program({city: '北京'})" |
| `tool_start` | `on_tool_start` | "执行工具: search_program" |
| `tool_end` | `on_tool_end` | "工具返回: [{name: '周杰伦演唱会', ...}]" |

```python
# 捕获 LLM 的工具调用决策
elif kind == "on_chat_model_end":
    if output.tool_calls:
        step_num += 1
        for tc in output.tool_calls:
            yield {"type": "step", "step": step_num, "action": "reasoning",
                   "content": f"分析意图，选择工具: {tc['name']}({args})"}

# 捕获工具执行过程
elif kind == "on_tool_start":
    yield {"type": "step", "action": "tool_start", "tool": tool_name}
elif kind == "on_tool_end":
    yield {"type": "step", "action": "tool_end", "tool": tool_name}
```

### 持久化

推理步骤存储在 `messages.steps` JSON 字段，切换对话后仍可查看。

### 面试高频问题

| 问题 | 回答要点 |
|------|---------|
| 怎么展示 Agent 的思考过程？ | `astream_events` 捕获 `on_chat_model_end` 和 `on_tool_start/end` |
| LangGraph 的 ReAct 有显式 Thought 吗？ | 没有，推理通过 tool_calls 体现，不输出文字形式的"思考" |
| 推理数据需要持久化吗？ | 需要，便于回溯调试，存 JSON 字段即可 |
| 可视化对用户有什么用？ | 增加信任感，让用户知道 AI 不是在"瞎猜" |

---

## 多 Agent 协作（Supervisor 模式）

### 架构设计

单 Agent 模式下，一个 ReAct Agent 要同时处理票务查询、知识库检索、闲聊，职责不清。多 Agent 模式将职责拆分到专业子 Agent，由 Supervisor 统一调度。

```
用户输入
  ↓
intent_classifier（意图分类，输出结构化 intent）
  ↓
router（路由决策，读 state.intent）
  ├─ ticket → ticket_agent → answer_generator → END
  ├─ knowledge → knowledge_agent → answer_generator → END
  ├─ both → ticket_agent → knowledge_agent → answer_generator → END
  ├─ chat → answer_generator → END
  └─ error → fallback → END
```

### 6 个节点

| 节点 | 职责 | 是否调用 LLM |
|------|------|-------------|
| `intent_classifier` | 纯意图分类，输出 ticket/knowledge/both/chat | 是（非流式） |
| `router` | 读 state.intent 决定路由 | 否（纯逻辑） |
| `ticket_agent` | 票务操作（ReAct 子 Agent，8 个工具） | 是（流式） |
| `knowledge_agent` | 知识库检索（ReAct 子 Agent，1 个工具） | 是（流式） |
| `answer_generator` | 统一格式化最终回答 | 单 Agent 透传不调 LLM，多 Agent 整合才调 |
| `fallback` | 异常兜底，友好错误提示 | 否 |

### 结构化状态

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # 对话消息（reducer 自动追加）
    intent: str           # 意图分类
    route: str            # 路由决策
    current_agent: str    # 当前执行的 agent
    agent_results: dict   # {"ticket": "结果...", "knowledge": "结果..."}
    error: str | None     # 错误信息
    final_answer: str | None  # 最终回答
```

**面试要点：**
- 状态用结构化字段，不用消息体塞标记（反模式）
- `agent_results` 字典汇聚多 Agent 结果
- 路由决策读 `state.intent`，可观测、可恢复
- 启用 `MemorySaver` checkpoint，支持状态持久化

### 延迟优化

| 优化项 | 做了什么 | 效果 |
|--------|---------|------|
| answer_generator 透传 | 单 Agent 结果直接返回，不过 LLM | 总耗时 ↓40% |
| 节点步骤可视化 | 进入每个节点推送"正在分析..." | 感知延迟 ↓ |

### 面试高频问题

| 问题 | 回答要点 |
|------|---------|
| 多 Agent 怎么协作？ | Supervisor 模式：intent_classifier 分类 → router 路由 → 专业子 Agent 执行 → answer_generator 整合 |
| 状态怎么设计？ | 结构化 TypedDict，7 个字段（intent, route, agent_results 等），不用消息体标记 |
| 多 Agent 结果怎么汇聚？ | `agent_results` 字典，按 agent 名称存储，answer_generator 统一整合 |
| 怎么处理异常？ | fallback 节点兜底，所有异常路径都指向它，返回友好提示 |
| 怎么优化延迟？ | 单 Agent 结果透传（省一次 LLM）、步骤可视化（感知延迟） |
| checkpoint 有什么用？ | 状态持久化，支持从断点恢复、审计追踪 |

---

## 与原项目（Spring AI）对比

| 原项目 (Spring AI) | Python 版 (LangGraph) | 知识点 |
|-------------------|----------------------|--------|
| Advisor 链编排 | `create_react_agent` + StateGraph | Agent 编排 |
| 贴心助手 + 规则助手分开 | Supervisor 多 Agent 路由 | 工具路由 |
| `defaultTools(aiProgram)` | `tools=[...]` | 工具注册 |
| `QuestionAnswerAdvisor` | `search_knowledge_base` 工具 | RAG 集成 |
| 单轮工具调用 | 多轮 ReAct 循环 | Agent 能力 |
| 无状态管理 | 结构化 AgentState（7 字段） | 状态管理 |
| 无异常兜底 | fallback 节点 | 容错 |
| 无 checkpoint | MemorySaver | 持久化 |
