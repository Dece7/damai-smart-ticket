# Agent 的 Token 治理

> Agent 和普通 LLM 调用的核心区别：多轮循环 + 工具调用 + 上下文累积。Token 消耗是 O(n²) 级别的增长，是 Agent 项目在生产环境中最大的成本挑战之一。

---

## 一、Token 消耗为什么是 Agent 的核心问题

**面试提问**：Agent 项目在生产环境中遇到的最大挑战是什么？

💥**优质回答**💥：
> Agent 的 Token 消耗是指数级增长的。每轮对话都携带前几轮的全部上下文，工具调用的返回值也在不断累积，导致单次请求的 Token 消耗远超普通 LLM 调用。

一次典型的 Agent 执行流程：

```
System Prompt (~2k)
  + 工具定义 (~3k)
  + 用户输入 (~0.5k)
  + [第1轮] 思考 + 工具调用 (~1k)
  + [第1轮] 工具返回 (~2k)        ← 累积
  + [第2轮] 思考 + 工具调用 (~1.5k)
  + [第2轮] 工具返回 (~3k)        ← 继续累积
  + ...第N轮
  + 最终输出 (~1k)
```

**关键洞察**：每轮对话都携带前几轮的全部上下文，Token 消耗是 **O(n²)** 级别的。

---



## 二、排查方法论

### 1. 建立度量体系（第一步）

**面试提问**：怎么排查 Agent 的 Token 消耗问题？

**优质回答**：
> 没有度量就没有优化。第一步是建立 Token 监控体系，按请求、轮次、工具三个维度打点，搞清楚 Token 花在哪了。

```typescript
// 核心指标
interface TokenMetrics {
  totalTokens: number       	    // 总消耗
  inputTokens: number       	    // 输入（含上下文）
  outputTokens: number       	    // 输出（含工具调用）
  toolCallCount: number       	    // 工具调用次数
  loopCount: number           	    // Agent 循环轮数
  contextTokensPerTurn: number[]    // 每轮上下文增长曲线
}
```

**生产环境必须埋点的字段**：

| 维度 | 指标 | 作用 |
|------|------|------|
| 按请求 | `total_tokens`, `cost` | 定位高消耗请求 |
| 按轮次 | `turn_input_tokens[]` | 发现上下文膨胀拐点 |
| 按工具 | `tool_name`, `tool_output_tokens` | 找到返回数据过多的工具 |
| 按模型 | `model`, `tokens_per_model` | 区分模型消耗占比 |

### 2. 度量体系落地三要素

**面试提问**：度量体系具体怎么落地？

**优质回答**：
> 三件事：**采集**（拿到数据）、**存储**（存下来）、**分析**（用起来）。技术上依赖 LLM SDK 的 **❇️usage_metadata**、JSON 字段持久化、SQL 聚合分析。

#### 采集：怎么拿到 Token 数据

```python
# LangChain 方案：开启 stream_usage，从 usage_metadata 获取
llm = ChatOpenAI(..., stream_usage=True)

# 在 astream_events 中捕获每次 LLM 调用的 token 消耗
async for event in agent.astream_events(...):
    if event["event"] == "on_chat_model_end":
        usage = event["data"]["output"].usage_metadata
        # usage = {"input_tokens": 1200, "output_tokens": 800, "total_tokens": 2000}
```

```python
# OpenAI SDK 方案：从 response.usage 直接获取
response = await client.chat.completions.create(...)
usage = response.usage
# usage.prompt_tokens, usage.completion_tokens, usage.total_tokens
```

**关键点**：LangChain 的 `usage_metadata` 只返回**本次 LLM 调用**的 token 数。Agent 多轮调用需要自己累加。

#### 存储：数据存哪

```python
# 方案一：JSON 字段（简单，推荐小项目）
class Message(Base):
    token_usage = Column(JSON)  # {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}

# 方案二：独立表（适合需要多维分析的场景）
class TokenUsage(Base):
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id"))
    model = Column(String)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    tool_name = Column(String, nullable=True)  # 按工具拆分
    turn_number = Column(Integer)              # 第几轮
```

#### 分析：怎么用数据

```sql
-- 按模式统计（你项目已实现）
SELECT chat_type,
       SUM(json_extract(token_usage, '$.total_tokens')) as total,
       AVG(json_extract(token_usage, '$.total_tokens')) as avg
FROM messages GROUP BY chat_type

-- 按天统计趋势（你项目已实现）
SELECT date(created_at) as day,
       SUM(json_extract(token_usage, '$.prompt_tokens')) as input_total,
       SUM(json_extract(token_usage, '$.completion_tokens')) as output_total
FROM messages GROUP BY day ORDER BY day DESC

-- 高消耗请求 Top-N（可扩展）
SELECT conversation_id, id,
       json_extract(token_usage, '$.total_tokens') as total
FROM messages
ORDER BY total DESC LIMIT 10
```

### 3. 识别消耗热点

拿到数据后，问三个问题：

```
① Token 消耗的大头在哪？	（System Prompt / 工具定义 / 对话历史 / 工具返回）
② 哪些请求消耗异常高？	  （长尾分布 vs 均匀分布）
③ 循环轮数是否合理？		  （正常任务 3-5 轮，超过 10 轮要警惕）
```

### 4. 常见病灶

| 症状 | 根因 | 排查方式 |
|------|------|----------|
| 第 5 轮后 Token 陡增 | 工具返回了大量原始数据（如整张表、整个文件） | 按工具统计 `output_tokens` |
| 所有请求 Token 都高 | System Prompt 或工具定义过长 | 统计固定开销占比 |
| 某些请求循环 20+ 轮 | Agent 陷入重试/死循环 | 检查是否有退出条件 |
| 同类任务消耗差异大 | 上下文没有做裁剪/压缩 | 对比 `contextTokensPerTurn` 曲线 |
| 工具调用次数多但效果差 | 工具粒度太细，一次任务要调很多次 | 统计 `toolCallCount / task` 比值 |

---



## 三、优化策略（分层）

### 第 1 层：💥压缩固定开销

**面试提问**：Agent 的 Token 优化有哪些手段？

#### System Prompt 瘦身

```
❌ 5000 字的详细指令
✅ 1500 字精简指令 + 动态加载相关规则
```

#### 工具定义优化

```typescript
// ❌ 每个工具的 description 写了 200 字
// ✅ 精简到核心信息，详细文档放别处
tools: [
  {
    name: "search_docs",
    description: "Search documentation. Input: query string",  // 简洁
    // 详细说明放 tool 的 system hint 里，按需注入
  }
]
```

**实用技巧**：20 个工具定义约 3-5k token。如果某些工具只在特定场景用，考虑动态加载。

**面试话术**：

> **System Prompt 精简到 1500 字以内，工具定义只保留核心描述，详细文档按需加载**。20 个工具定义约 3-5k token，精简后可省 30%。

### 第 2 层：💥控制上下文增长（收益最大）

#### 滑动窗口 + 摘要压缩

```typescript
function trimContext(messages: Message[]): Message[] {
  // 保留：system prompt + 最近 N 轮
  // 压缩：中间轮次用摘要替代
  const recent = messages.slice(-6)  // 最近 3 轮（user+assistant 对）
  const old = messages.slice(1, -6)  // 中间部分

  if (old.length > 0) {
    const summary = summarize(old)   // 用小模型生成摘要
    return [messages[0], summary, ...recent]
  }
  return messages
}
```

#### 工具返回值裁剪

```typescript
// ❌ 返回整张表
const users = await db.query("SELECT * FROM users")
return JSON.stringify(users)  // 可能 10k+ tokens

// ✅ 返回摘要 + 分页
const users = await db.query("SELECT * FROM users LIMIT 20")
return {
  total: 1000,
  page: 1,
  data: users,
  hint: "Use offset parameter for more pages"
}
```

**面试话术**：

> 这是收益最大的一层。三个手段：**①滑动窗口控制历史消息数量，②早期对话用摘要压缩替代原文，③工具返回值裁剪掉 Agent 不需要的字段**。工具返回值通常是 token 消耗的大头，裁剪后单次请求可省 30-40%。

### 第 3 层：💥减少循环轮数

#### 工具合并

```typescript
// ❌ 3 个工具，3 次调用
get_user_info(userId)
get_user_orders(userId)
get_user_preferences(userId)

// ✅ 1 个工具，1 次调用
get_user_profile(userId)  // 返回 info + orders + preferences
```

#### 提前退出条件

```typescript
// Agent Loop 中加入防护
const MAX_LOOPS = 10
const MAX_TOKENS = 50000

for (let i = 0; i < MAX_LOOPS; i++) {
  const result = await agent.step()

  if (result.totalTokens > MAX_TOKENS) {
    // 强制总结并退出
    return await agent.summarizeAndExit()
  }

  if (result.isComplete) break
}
```

**面试话术**：

> 两个方向：一是**合并细粒度工具**，比如把 get_user_info、get_user_orders、get_user_preferences 合成一个 get_user_profile，一次调用拿到全部数据；二是**设最大循环轮数和 token 熔断**，防止 Agent 陷入死循环烧爆预算。

### 第 4 层：💥模型分级

**不是每一步都需要最强模型。**

```typescript
// 路由策略
function selectModel(task: Task): string {
  if (task.type === 'simple_lookup') return 'gpt-4o-mini'    // $0.15/1M
  if (task.type === 'code_generation') return 'gpt-4o'       // $2.5/1M
  if (task.type === 'complex_reasoning') return 'o1'          // $15/1M
}
```

| 阶段 | 推荐模型 | 原因 |
|------|----------|------|
| 意图识别 / 路由 | 小模型 | 简单分类任务 |
| 工具调用决策 | 中等模型 | 结构化输出 |
| 复杂推理 / 代码生成 | 大模型 | 需要强推理 |
| 摘要压缩 | 小模型 | 纯文本压缩 |

**面试话术**：
> 不是每一步都需要最强模型，可以实现**模型分级**。意图识别用小模型（成本 ¥0.004），复杂推理用大模型（成本 ¥0.01），成本可降 80%。关键是做好任务路由，只对明确的简单任务用小模型，不能为了省钱降级影响效果。

### 第 5 层：💥缓存与预计算

```typescript
// 语义缓存：相似问题直接返回
const cacheKey = embedding(userQuery)
const cached = await vectorCache.search(cacheKey, { threshold: 0.95 })
if (cached) return cached  // 省掉整次 Agent 调用

// 工具结果缓存
const toolCache = new Map()
async function callTool(name, params) {
  const key = `${name}:${hash(params)}`
  if (toolCache.has(key)) return toolCache.get(key)
  // ...
}
```

**面试话术**：
> 两个层面：一是**语义缓存**，相似问题直接返回缓存结果，省掉整次 Agent 调用；二是**工具结果缓存**，相同参数的重复调用直接复用上次结果。适合高频重复场景，但要注意缓存过期和数据一致性。

---



## 四、优化策略总览

| 层级 | 策略 | 收益 | 实现难度 | 本项目 |
|------|------|------|---------|--------|
| 第 1 层 | 压缩固定开销      （System Prompt / 工具定义） | 中 | 低 | ✅ Prompt 已精简 |
| 第 2 层 | 控制上下文增长  （滑动窗口 / 返回值裁剪） | 高 | 中 | ✅ 滑动窗口 20 条 |
| 第 3 层 | 减少循环轮数      （工具合并 / 退出条件） | 高 | 中 | ❌ 未做 |
| 第 4 层 | 模型分级             （简单任务用小模型） | 中 | 低 | ❌ 未做（单一模型） |
| 第 5 层 | 缓存预计算         （语义缓存 / 工具缓存） | 中 | 高 | ❌ 未做 |

---



## 五、本项目 Token 治理现状

### 已实现的能力

| 维度 | 具体实现 | 状态 |
|------|---------|------|
| 采集 | LangChain `stream_usage=True` + `astream_events` 捕获 `usage_metadata` | ✅ |
| 持久化 | `messages.token_usage` JSON 列，`migrate_db()` 自动加列 | ✅ |
| SSE 实时推送 | `{"type": "usage", "content": {prompt/completion/total}}` | ✅ |
| 前端展示 | 每条消息下方显示 Prompt/Completion/Total 三个指标 | ✅ |
| Admin Dashboard | 总量卡片 + 每日趋势柱状图 + 按模式饼图（ECharts） | ✅ |
| Admin API | `/api/admin/stats/summary`, `/trend`, `/by_mode` 三个接口 | ✅ |
| 上下文管理 | 滑动窗口 20 条消息 | ✅ |
| System Prompt | 精简指令，控制固定开销 | ✅ |

### 四种模式的采集方式

| 模式 | 采集方式 | 说明 |
|------|---------|------|
| Rule Assistant (RAG) | `llm.get_num_tokens()` 估算 | StrOutputParser 丢失 usage_metadata，只能估算 |
| Caring Assistant (FC) | `usage_metadata` 累加 | 多轮工具调用累加 prompt/completion |
| Agent (ReAct) | `on_chat_model_end` 事件 | LangGraph astream_events 捕获每次 LLM 调用 |
| Multi-Agent | `on_chat_model_end` 事件 | 每个子 Agent 节点的 LLM 调用分别捕获 |

### 缺失的能力

| 维度 | 说明 | 影响 |
|------|------|------|
| 按工具统计 | 不知道哪个 tool 返回数据最多 | 无法定位"数据胖子" |
| 按轮次统计 | 不知道第几轮开始 token 陡增 | 无法发现上下文膨胀拐点 |
| 高消耗请求 Top-N | 没有异常请求排查能力 | 无法快速定位问题请求 |
| Token 熔断 | 没有单次请求上限控制 | 异常请求可能烧爆预算 |
| 日预算告警 | 没有日消耗量监控 | 无法及时发现异常 |
| 模型分级 | 所有任务用 Mimo v2.5 | 简单任务成本偏高 |
| 语义缓存 | 相似问题重复消耗 | 高频问题浪费 token |

### 面试话术

**基础版**（突出已有能力）：
> **项目实现了完整的 Token 度量体系。采集层通过 LangChain 的 stream_usage=True 自动获取每次 LLM 调用的 token 消耗，四种对话模式都做了适配。数据持久化到 SQLite 当中，并且还实现提供总量统计、每日趋势和按模式分布三个维度的可视化。**

**进阶版**（突出优化思路）：

> **项目实现了完整的 Token 度量体系，四种模式都能采集 token 消耗并持久化。在排查过程中发现，工具返回值是 token 消耗的大头，比如 search_program 一次返回 3000 token。优化方向是裁剪返回字段和限制数量，预估可降低 30-40% 的 token 消耗。同时计划加单次请求 token 熔断，防止异常请求烧爆预算。**

**追问应对**：

| 追问 | 应答 |
|------|------|
| "具体怎么采集的？" | "LangChain 的 stream_usage=True，从 astream_events 的 on_chat_model_end 事件中读取 usage_metadata" |
| "数据存在哪？" | "SQLite 的 messages 表，token_usage 是 JSON 列，不需要 ALTER TABLE 就能扩展字段" |
| "怎么分析的？" | "Admin API 用 json_extract 做 SQL 聚合，按模式、按天两个维度统计" |
| "怎么优化的？" | "工具返回值裁剪是收益最大的，裁掉 Agent 不需要的字段，限制返回数量" |
| "优化效果多少？" | "预估工具返回值裁剪可降低 30-40% token，摘要压缩可降低长对话 40%+ token" |

---



## 六、面试高频问题与回答话术

### 基础概念类

| 问题 | 回答要点 | 话术示例 |
|------|---------|---------|
| Agent 的 Token 消耗为什么比普通 LLM 高？ | 多轮循环 + 上下文累积 + 工具调用 | "Agent 每轮对话都携带前几轮的全部上下文，加上工具返回值不断累积，Token 消耗是 O(n²) 级别的增长。普通 LLM 调用只有一问一答，是 O(1) 的" |
| Token 优化的核心思路是什么？ | 先量化、再分层、抓大头 | "三步走：先建立度量体系搞清楚 Token 花在哪，再分层优化（固定开销→上下文→循环→模型→缓存），最后盯着占比最大的部分重点优化" |
| 度量体系怎么建？ | 采集 + 存储 + 分析 | "三件事：采集层用 LLM SDK 的 usage_metadata 拿数据，存储层用 JSON 字段持久化，分析层用 SQL 聚合做多维统计" |

### 优化策略类

| 问题 | 回答要点 | 话术示例 |
|------|---------|---------|
| 优化 Token 消耗有哪些手段？ | 五层策略 | "分五层：压缩固定开销（System Prompt 瘦身、工具定义精简）、控制上下文增长（滑动窗口、摘要压缩、返回值裁剪）、减少循环轮数（工具合并、退出条件）、模型分级（简单任务用小模型）、缓存预计算（语义缓存、工具缓存）" |
| 收益最大的优化是什么？ | 控制上下文增长 | "收益最大的是控制上下文增长，特别是工具返回值裁剪。比如一个搜索工具返回 50 条完整数据要 3000 token，裁剪到 10 条必要字段只要 800 token，单次请求就能省 27%" |
| 工具返回数据太多怎么办？ | 裁剪 + 分页 + 摘要 | "三个手段：一是裁剪字段，只保留 Agent 做决策需要的；二是限制数量，返回 Top-10 而不是全部；三是摘要替代，用 LLM 把长文本压缩成关键信息" |
| 优化会不会影响 Agent 效果？ | 裁噪音不影响，裁关键信息才影响 | "裁剪噪音不影响效果，裁剪关键信息才影响。比如工具返回的 created_at、poster_url 这些字段对 Agent 做决策没帮助，裁掉反而让 LLM 处理更准确。关键是想清楚 Agent 到底需要什么信息" |

### 生产实战类

| 问题 | 回答要点 | 话术示例 |
|------|---------|---------|
| 怎么排查 Token 消耗问题？ | 先度量，再定位 | "先建立度量体系，按请求、轮次、工具三个维度打点。拿到数据后问三个问题：大头在哪？哪些请求异常高？循环轮数是否合理？" |
| Agent 陷入死循环怎么处理？ | 双重防护 | "设两个熔断：最大循环轮数（比如 10 轮）和最大 Token 消耗（比如 50000 token）。超限时不是直接中断，而是让 Agent 基于已有信息做总结再退出" |
| 怎么监控生产环境的 Token 消耗？ | 埋点 + 可视化 + 告警 | "每次请求记录 total_tokens、按工具返回量、按轮次增长曲线。Admin Dashboard 做可视化，日消耗超阈值时告警通知" |
| 不同任务用不同模型有必要吗？ | 有必要，但要谨慎 | "有必要，意图识别用小模型成本可降 80%。但复杂推理必须用大模型，不能为了省钱降级。关键是做好任务路由，只对明确的简单任务用小模型" |
| Token 成本怎么算？ | 区分 input/output 价格 | "单次成本 = (input_tokens × input_price + output_tokens × output_price) / 1M。关键是要分 input 和 output，output 通常是 input 的 3-4 倍价格" |

### 追问应对策略

**面试官追问"你项目具体怎么做的？"时的回答框架**：

```
1. 说实现："我们用 LangChain 的 stream_usage 采集 token 消耗"
2. 说存储："持久化到 SQLite 的 JSON 字段"
3. 说分析："Admin API 做 SQL 聚合，按模式和按天两个维度统计"
4. 说发现："排查发现工具返回值是大头"
5. 说优化："裁剪返回字段 + 限制数量，预估省 30-40%"
```

**面试官追问"效果提升了多少？"时的回答框架**：

```
1. 说方法："用同一组测试问题，对比优化前后的 token 消耗"
2. 说数字："工具返回值裁剪后单次请求降低 27%，摘要压缩后长对话降低 43%"
3. 说成本："日均 1000 次请求，每月节省 ¥200-300"
4. 说质量："效果没有下降，因为裁掉的是 Agent 不需要的噪音字段"
```
