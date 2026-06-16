# Phase 2：Function Calling — 知识点与面试要点

> 工具定义、AI 自动调用、多轮工具链的技术细节和面试准备。

---

## 做了什么

用 LangChain 的 `@tool` 装饰器定义业务工具（查节目、查票档、生成订单），AI 自动识别用户意图并调用对应工具，支持多轮工具调用。

---

## 核心知识点

### 1. Function Calling 原理

```
用户: "帮我买周杰伦北京演唱会1280的票"
         │
         ▼
   LLM 分析意图
   → 需要调用 search_program（查节目）
   → 需要调用 get_ticket_info（查票档）
   → 需要调用 create_order（下单）
         │
         ▼
   返回 tool_calls（JSON 格式的函数调用请求）
         │
         ▼
   应用层执行函数，返回结果
         │
         ▼
   LLM 基于结果生成最终回答
```

**面试要点：**
- Function Calling 不是 LLM 直接执行代码，而是 LLM 返回"我想调用什么函数、传什么参数"
- 应用层负责真正执行函数，把结果喂回 LLM
- LLM 基于工具结果生成自然语言回答
- 这是 **AI Agent 的核心能力**：感知 → 决策 → 行动

**面试问：** Function Calling 和直接让 LLM 写代码执行有什么区别？
**答：** Function Calling 更安全（限定工具范围）、更可控（参数有类型校验）、更可靠（不会生成恶意代码）。

---

### 2. @tool 装饰器定义工具

```python
from langchain_core.tools import tool

@tool
def search_program(city: str = "", category: str = "", actor: str = "") -> list[dict]:
    """根据城市、类型或艺人查询推荐的节目。至少提供一个查询条件。

    Args:
        city: 城市名，如"北京"、"上海"
        category: 节目类型，如"演唱会"、"音乐节"
        actor: 艺人名，如"周杰伦"
    """
    results = PROGRAMS
    if city:
        results = [p for p in results if city in p["city"]]
    return results
```

**面试要点：**
- `@tool` 装饰器将普通函数转为 LangChain 工具
- **函数名**就是工具名（LLM 通过名字识别工具）
- **docstring** 就是工具描述（LLM 通过描述判断何时调用）
- **类型注解** 就是参数定义（LLM 根据类型生成正确格式的参数）
- **docstring 非常重要**：写得越清晰，LLM 调用越准确

**面试问：** 工具的 docstring 为什么这么重要？
**答：** LLM 通过 docstring 理解工具的用途和参数含义。如果描述不清，LLM 可能在错误的场景调用工具，或传错参数。

---

### 3. bind_tools 绑定工具

```python
llm = ChatOpenAI(...).bind_tools([search_program, get_ticket_info, create_order])
```

**面试要点：**
- `bind_tools()` 将工具列表绑定到 LLM
- 调用时，LLM 的 system prompt 会自动注入工具的描述信息
- LLM 根据用户消息和工具描述，决定是否调用工具、调用哪个、传什么参数
- 工具描述会被序列化为 JSON Schema 格式传给模型

---

### 4. 多轮工具调用（Agent 循环）

```python
for round_num in range(MAX_TOOL_ROUNDS):
    response = await self.llm.ainvoke(messages)
    messages.append(response)

    if not response.tool_calls:
        break

    for tool_call in response.tool_calls:
        result = tool_func.invoke(tool_call["args"])
        messages.append(ToolMessage(content=json.dumps(result), tool_call_id=tool_call["id"]))
```

**面试要点：**
- 单轮工具调用：用户提问 → LLM 调用工具 → LLM 生成回答
- 多轮工具调用：用户提问 → LLM 调用工具 A → LLM 调用工具 B → ... → LLM 生成回答
- `MAX_TOOL_ROUNDS = 5` 防止无限循环
- 每轮工具结果都追加到 messages，LLM 有完整上下文

**面试问：** 什么是 ReAct 模式？
**答：** Reasoning + Acting。LLM 先推理（思考需要什么信息），再行动（调用工具获取信息），然后观察结果，继续推理...循环直到得到最终答案。

---

### 5. ToolMessage 工具结果

```python
from langchain_core.messages import ToolMessage

messages.append(ToolMessage(
    content=json.dumps(result, ensure_ascii=False),
    tool_call_id=tool_call["id"],
))
```

**面试要点：**
- `ToolMessage` 是 LangChain 的消息类型，表示工具执行结果
- `tool_call_id` 关联到具体的工具调用请求（一个消息可能有多个工具调用）
- 工具结果必须是字符串，所以用 `json.dumps()` 序列化

---

### 6. 消息类型体系

```python
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

messages = [
    SystemMessage(content="你是一个助手"),    # 系统指令
    HumanMessage(content="你好"),             # 用户消息
    AIMessage(content="你好呀"),              # AI 回复
    AIMessage(tool_calls=[...]),              # AI 请求调用工具
    ToolMessage(content="...", tool_call_id="xxx"),  # 工具执行结果
]
```

**面试要点：**
- LangChain 用消息列表管理对话上下文
- 不同消息类型对应不同角色：system / human / ai / tool
- 工具调用流程：AIMessage(tool_calls) → ToolMessage → AIMessage(回答)

---

## 完整工具调用流程

```
1. 用户消息 → messages = [SystemMessage, HumanMessage]

2. LLM 分析 → 返回 AIMessage(tool_calls=[{name, args, id}])

3. 执行工具 → for tool_call in response.tool_calls:
                  result = TOOLS_MAP[tool_call["name"]].invoke(tool_call["args"])
                  messages.append(ToolMessage(result, tool_call_id))

4. 判断是否继续 → 如果还有 tool_calls，回到步骤 2

5. 生成回答 → LLM 基于完整 messages 流式生成最终回答
```

---

## 面试高频问题

| 问题 | 回答要点 |
|------|---------|
| 什么是 Function Calling？ | LLM 返回函数调用请求，应用层执行，结果回传 LLM |
| @tool 装饰器的作用？ | 将普通函数转为 LangChain 工具，自动生成 JSON Schema |
| docstring 为什么重要？ | LLM 通过描述判断何时调用、如何传参 |
| 什么是多轮工具调用？ | LLM 可以连续调用多个工具，逐步获取信息 |
| 怎么防止工具调用死循环？ | 设置 MAX_TOOL_ROUNDS 上限 |
| ToolMessage 的作用？ | 将工具执行结果回传给 LLM，作为下一轮推理的上下文 |

---

## 与原项目（Spring AI）对比

| 原项目 (Spring AI) | Python 版 (LangChain) | 知识点 |
|-------------------|----------------------|--------|
| `@Tool(description="...")` | `@tool` + docstring | 工具定义 |
| `@ToolParam(description="...")` | 类型注解 + Args 描述 | 参数定义 |
| `defaultTools(aiProgram)` | `bind_tools([tools])` | 工具绑定 |
| Advisor 链拦截 | 多轮 for 循环 | 工具执行编排 |
| `ChatClient.prompt().user(msg).call()` | `llm.ainvoke(messages)` | 模型调用 |

---

## 代码模式总结

```python
# 模式 1：定义工具
@tool
def my_tool(param: str) -> dict:
    """工具描述，告诉 LLM 这个工具干什么"""
    return {"result": "..."}

# 模式 2：绑定工具
llm = ChatOpenAI(...).bind_tools([my_tool])

# 模式 3：工具调用循环
for _ in range(max_rounds):
    response = await llm.ainvoke(messages)
    if not response.tool_calls:
        break
    for tc in response.tool_calls:
        result = TOOLS_MAP[tc["name"]].invoke(tc["args"])
        messages.append(ToolMessage(content=json.dumps(result), tool_call_id=tc["id"]))

# 模式 4：最终生成
async for chunk in llm.astream(messages):
    yield chunk.content
```
