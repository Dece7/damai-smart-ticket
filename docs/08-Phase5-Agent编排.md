# Phase 5：Agent 编排

> LangGraph ReAct Agent、自动工具选择、多工具协作的技术细节和面试准备。

---

## 做了什么

💥用 LangGraph 构建 ReAct Agent，将 Function Calling 工具和 RAG 检索工具统一注册，Agent 自动判断用户意图并选择合适工具。

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
- 💥ReAct 模式💥：Reasoning（推理）+ Acting（行动）循环
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

**多种用途：**

| 用途 | 用到的事件 | 详细文档 |
|------|-----------|---------|
| 流式输出文字 | `on_chat_model_stream` | 本节 |
| 推理过程可视化 | `on_tool_start/end` | 10-Phase7 |
| Token 统计 | `on_chat_model_end` + `usage_metadata` | 10-Phase7 |
| 节点进入提示 | `node_enter`（多 Agent） | 10-Phase7 |

**面试要点：**
- `astream_events` 是 LangChain 的流式事件 API，用途不止可视化
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

## 四种模式对比

| 模式 | 技术实现 | 本项目对应 |
|------|---------|-----------|
| **规则助手** | RAG 固定管线，无工具调用 | Phase 3 |
| **贴心助手** | Function Calling，代码控制循环 | Phase 2 |
| **Agent** | LangGraph ReAct，LLM 自主决策 | Phase 5 |
| **多 Agent** | 6 节点结构化编排 | Phase 5 |

详细流程对比见 `02-DST开发记录.md`。

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

详见 `10-Phase7-优化增强.md` 第 5 节，包含四种事件类型（node_enter/reasoning/tool_start/tool_end）和四种模式的可视化差异。

---

## 多 Agent 协作（Supervisor 模式）

6 节点结构化编排：intent_classifier → router → 子 Agent → answer_generator → fallback。

详细架构、状态设计、通信模式见 `08a-多Agent通信与协作.md`。

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
