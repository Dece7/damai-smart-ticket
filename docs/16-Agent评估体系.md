# Agent 评估体系

> RAG 评估看"检索准不准、回答对不对"，Agent 评估看"任务完没完成、工具用得对不对、效率高不高"。两者的评估维度完全不同。

---

## 一、Agent 评估 vs RAG 评估

**面试提问**：Agent 项目怎么做评估？和 RAG 评估有什么区别？

💥**优质回答**💥：
> RAG 评估关注检索质量和生成质量，核心指标是 Recall、Precision、幻觉率。Agent 评估**❇️关注任务完成和工具使用**，核心指标是任务完成率、工具调用准确率、推理步数。RAG 评估是静态的（问一个问题看回答），Agent 评估是动态的（看整个执行过程）。

| 维度 | RAG 评估 | Agent 评估 |
|------|---------|-----------|
| 评估对象 | 检索结果 + 生成回答 | 整个执行过程（思考→工具调用→结果→回答） |
| 核心指标 | Recall、Precision、MRR、幻觉率 | 任务完成率、工具准确率、推理步数、延迟 |
| 评估方式 | 静态（问→答） | 动态（问→多轮执行→答） |
| 复杂度 | 低（单轮检索+生成） | 高（多轮工具调用，中间状态多） |

**面试话术**：
> "RAG 评估是静态的，看检索和生成两个环节。**Agent 评估是动态的**，要看整个执行过程——选对工具了吗？参数传对了吗？几步完成的？最终答案对不对？评估维度完全不同。"

---



## 二、Agent 评估五大维度

### 维度一：💥任务完成率

**定义**：用户的问题最终解决了吗？

```
用户问："帮我查周杰伦北京演唱会最便宜的票"

✅ 完成：Agent 调用 search_program → 找到演唱会 → 调用 get_ticket_info → 返回最便宜票档
❌ 未完成：Agent 调用 search_program → 没找到 → 告诉用户"没有相关演出"（实际有）
❌ 未完成：Agent 调用了错误的工具 → 最终回答答非所问
```

**评估方法**：

```python
# 测试用例格式
test_case = {
    "question": "帮我查周杰伦北京演唱会最便宜的票",
    "expected_answer_contains": ["周杰伦", "北京", "380"],  # 期望答案包含的关键词
    "expected_tool_calls": ["search_program", "get_ticket_info"],  # 期望的工具调用序列
    "expected_intent": "ticket"  # 期望的意图分类
}

# 评估逻辑
def evaluate_task_completion(question, actual_answer, expected):
    # 1. 关键词命中
    keyword_hit = all(kw in actual_answer for kw in expected["expected_answer_contains"])

    # 2. 语义正确性（用 LLM Judge）
    semantic_correct = llm_judge(question, actual_answer, expected)

    return keyword_hit and semantic_correct
```

**指标**：

```
任务完成率 = 成功完成的任务数 / 总任务数 × 100%
```

### 维度二：💥工具调用准确率

**定义**：Agent 选对工具了吗？参数传对了吗？

```
用户问："帮我查退票政策"

✅ 工具选择正确：调用 search_knowledge_base("退票政策")
❌ 工具选择错误：调用 search_program("退票")  ← 应该用知识库，不是搜索节目
❌ 参数错误：调用 search_knowledge_base()  ← 没传参数
❌ 多余调用：调用了 search_program + get_ticket_info + search_knowledge_base  ← 不需要前两个
```

**评估方法**：

```python
test_case = {
    "question": "帮我查退票政策",
    "expected_tool_calls": [
        {"name": "search_knowledge_base", "args_contains": {"query": "退票"}}
    ],
    "unexpected_tool_calls": ["search_program", "get_ticket_info"]
}

def evaluate_tool_accuracy(actual_tool_calls, expected):
    # 1. 工具选择准确率
    expected_names = {tc["name"] for tc in expected["expected_tool_calls"]}
    actual_names = {tc["name"] for tc in actual_tool_calls}
    tool_selection_correct = expected_names == actual_names

    # 2. 参数准确率
    param_correct = True
    for expected_tc in expected["expected_tool_calls"]:
        actual_tc = find_matching_call(actual_tool_calls, expected_tc["name"])
        if actual_tc:
            for key, value in expected_tc["args_contains"].items():
                if key not in actual_tc["args"] or value not in str(actual_tc["args"][key]):
                    param_correct = False

    # 3. 是否有多余调用
    unexpected = set(expected.get("unexpected_tool_calls", []))
    no_unexpected = not (actual_names & unexpected)

    return tool_selection_correct, param_correct, no_unexpected
```

**指标**：

```
工具选择准确率 = 选对工具的任务数 / 总任务数 × 100%
参数准确率 = 参数传对的任务数 / 总任务数 × 100%
无冗余调用率 = 没有多余工具调用的任务数 / 总任务数 × 100%
```

### 维度三：💥推理效率（推理步数）

**定义**：完成任务用了几轮工具调用？越少越好。

```
用户问："帮我查周杰伦北京演唱会最便宜的票"

高效路径（2 步）：
  第 1 步：search_program(actor="周杰伦", city="北京") → 找到演唱会
  第 2 步：get_ticket_info(program_id=123) → 返回票档价格
  → 推理步数 = 2 ✅

低效路径（4 步）：
  第 1 步：search_program(actor="周杰伦") → 返回所有城市的演唱会
  第 2 步：search_program(actor="周杰伦", city="北京") → 北京的演唱会
  第 3 步：get_program_detail(program_id=123) → 演唱会详情（不需要）
  第 4 步：get_ticket_info(program_id=123) → 返回票档价格
  → 推理步数 = 4 ❌（多了 2 步无效调用）
```

**指标**：

```
平均推理步数 = 所有任务的推理步数之和 / 任务数
推理步数分布：最好/最差/中位数
冗余调用率 = 无效工具调用数 / 总工具调用数 × 100%
```

### 维度四：💥端到端延迟

**定义**：从用户提问到最终回答，总耗时多少？

```
延迟分解：
  意图分类 LLM:  ~500ms
  工具调用 1:    ~300ms（数据库查询）
  LLM 生成:     ~1000ms
  工具调用 2:    ~200ms
  最终回答 LLM:  ~800ms
  ─────────────────────
  总延迟:        ~2800ms
```

**指标**：

```
TTFT（Time to First Token）：第一个 token 的延迟
总延迟：从请求到完整回答的延迟
延迟分布：P50 / P95 / P99
```

**你项目数据**：优化前 17.5s → 优化后 10.5s（-40%）

### 维度五：💥幻觉率

**定义**：Agent 的回答中有多少内容是工具返回数据中没有的。

```
工具返回："周杰伦演唱会，看台票 380 元，内场票 1280 元"

Agent 回答："周杰伦演唱会看台票 380 元，内场票 1280 元，VIP 区 2880 元"
→ "VIP 区 2880 元"是幻觉，工具返回里没有这个信息
```

**评估方法**：和 RAG 评估一样，用 LLM Judge 从忠实度维度打分。

---



## 三、评估方法论

### 方法一：构建测试用例集

```python
# 测试用例格式
test_cases = [
    {
        "id": "TC001",
        "question": "帮我查周杰伦北京演唱会最便宜的票",
        "category": "ticket",                    # 任务类别
        "difficulty": "medium",                  # 难度：easy / medium / hard
        "expected_tool_calls": [                 # 期望的工具调用
            {"name": "search_program", "args_contains": {"actor": "周杰伦"}},
            {"name": "get_ticket_info"}
        ],
        "expected_answer_contains": ["周杰伦", "380"],  # 期望答案包含
        "expected_intent": "ticket",             # 期望意图
        "max_steps": 3                           # 最大允许步数
    },
    {
        "id": "TC002",
        "question": "退票政策是什么",
        "category": "knowledge",
        "difficulty": "easy",
        "expected_tool_calls": [
            {"name": "search_knowledge_base"}
        ],
        "expected_answer_contains": ["退票", "48小时"],
        "expected_intent": "knowledge",
        "max_steps": 2
    },
    {
        "id": "TC003",
        "question": "帮我查北京周杰伦的演唱会，选最便宜的票，帮我下单",
        "category": "complex",
        "difficulty": "hard",
        "expected_tool_calls": [
            {"name": "search_program"},
            {"name": "get_ticket_info"},
            {"name": "create_order"}
        ],
        "expected_answer_contains": ["订单"],
        "expected_intent": "both",
        "max_steps": 5
    }
]
```

**测试用例设计原则**：

| 类别 | 覆盖场景 | 数量建议 |
|------|---------|---------|
| 单工具调用 | 只需要一个工具就能完成 | 20+ |
| 多工具协作 | 需要 2-3 个工具配合 | 15+ |
| 知识库问答 | 需要 RAG 检索 | 15+ |
| 复杂任务 | 需要多步推理 + 多工具 | 10+ |
| 边界情况 | 无法完成的任务、模糊问题 | 10+ |

### 方法二：自动化评估脚本

```python
async def evaluate_agent(test_cases):
    results = []
    for tc in test_cases:
        # 执行 Agent
        response = await agent.run(tc["question"])

        # 评估
        task_result = evaluate_task_completion(tc["question"], response.answer, tc)
        tool_result = evaluate_tool_accuracy(response.tool_calls, tc)
        efficiency = evaluate_efficiency(response.tool_calls, tc["max_steps"])
        latency = response.total_latency

        results.append({
            "id": tc["id"],
            "task_complete": task_result,
            "tool_correct": tool_result,
            "steps": len(response.tool_calls),
            "latency": latency,
            "pass": task_result and tool_result[0] and efficiency
        })

    # 汇总
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r["pass"]),
        "task_completion_rate": sum(1 for r in results if r["task_complete"]) / len(results),
        "tool_accuracy": sum(1 for r in results if r["tool_correct"][0]) / len(results),
        "avg_steps": sum(r["steps"] for r in results) / len(results),
        "avg_latency": sum(r["latency"] for r in results) / len(results)
    }
```

### 方法三：LLM Judge（和 RAG 评估类似）

```python
AGENT_JUDGE_PROMPT = """你是一个 Agent 评估专家。请从以下维度对 Agent 的回答打分（1-5分）：

1. 任务完成度：用户的问题是否被完全解决？
2. 工具使用合理性：是否选择了正确的工具？参数是否正确？
3. 回答准确性：回答内容是否基于工具返回的数据？有无幻觉？
4. 效率：推理步骤是否合理？有无冗余调用？

用户问题：{question}
Agent 执行过程：{tool_calls}
Agent 最终回答：{answer}

请返回 JSON 格式：
{{"task_completion": N, "tool_usage": N, "accuracy": N, "efficiency": N, "overall": N, "reasoning": "..."}}
"""
```

---

## 四、评估结果示例

```
Agent 评估报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
测试用例总数：65
通过：60 / 65（92.3%）

维度统计：
  任务完成率：93.8%（61/65）
  工具选择准确率：95.4%（62/65）
  参数准确率：92.3%（60/65）
  无冗余调用率：89.2%（58/65）
  平均推理步数：2.3 步
  平均延迟：2.8s
  LLM Judge 综合：4.6/5

失败用例分析：
  TC012：工具选择错误（应用 search_knowledge_base，实际用了 search_program）
  TC023：参数错误（query 传了空字符串）
  TC034：推理步数超限（5 步未完成）
  TC045：幻觉（回答了工具返回中没有的信息）
  TC056：延迟过高（>10s）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 五、本项目评估现状

| 评估维度 | 状态 | 说明 |
|---------|------|------|
| RAG 评估 | ✅ 有 | 65 条用例，Recall@5=100%，LLM Judge=4.9/5 |
| Agent 任务完成率 | ❌ 没有 | 没有 Agent 专用测试用例 |
| 工具调用准确率 | ❌ 没有 | 没有工具调用序列的对比评估 |
| 推理效率 | ⚠️ 部分 | 有推理步骤记录，但没有自动化评估 |
| 端到端延迟 | ✅ 有 | 优化前 17.5s → 优化后 10.5s |
| 幻觉率 | ⚠️ 部分 | RAG 模式有（0%），Agent 模式没有 |

**为什么没做**：当前重点在 RAG 评估，Agent 模式的评估需要构建专门的测试用例（期望的工具调用序列），开发成本较高。

**面试话术**：
> "**项目有完整的 RAG 评估体系（65 条用例，Recall@5=100%，LLM Judge=4.9/5）。Agent 评估目前有推理步骤记录和延迟统计，但还没有自动化评估框架。生产环境我会构建 Agent 专用测试用例，每个用例定义期望的工具调用序列和答案关键词，自动化评估任务完成率、工具准确率、推理步数三个维度。**"

---

## 六、面试高频问题

| 问题 | 回答要点 |
|------|---------|
| Agent 怎么评估？ | 五个维度：任务完成率、工具调用准确率、推理效率、端到端延迟、幻觉率 |
| Agent 评估和 RAG 评估有什么区别？ | RAG 评估是静态的（检索+生成），Agent 评估是动态的（整个执行过程） |
| 任务完成率怎么评估？ | 构建测试用例，定义期望答案关键词 + LLM Judge 语义判断 |
| 工具调用准确率怎么评估？ | 对比实际工具调用序列和期望序列，检查工具选择+参数+是否有冗余调用 |
| 推理效率怎么衡量？ | 平均推理步数、冗余调用率，步数越少效率越高 |
| 测试用例怎么设计？ | 按场景分类：单工具、多工具、知识库、复杂任务、边界情况 |
| LLM Judge 怎么用于 Agent 评估？ | 从任务完成度、工具使用合理性、回答准确性、效率四个维度打分 |
| 你项目做了 Agent 评估吗？ | RAG 评估完整，Agent 有推理步骤记录和延迟统计，生产环境会加自动化评估 |

---

## 七、面试综合话术

> "**Agent 评估和 RAG 评估的维度完全不同。RAG 评估看检索质量和生成质量，Agent 评估看任务完成和工具使用。我从五个维度评估：任务完成率（用户问题解决了吗）、工具调用准确率（选对工具了吗、参数对吗）、推理效率（几步完成的）、端到端延迟（多久出结果）、幻觉率（有没有编造信息）。评估方法是构建测试用例集，每个用例定义期望的工具调用序列和答案关键词，用自动化脚本对比实际执行和期望执行，再用 LLM Judge 做语义层面的质量打分。当前项目有完整的 RAG 评估体系，Agent 评估有推理步骤记录和延迟统计，生产环境会补齐自动化评估框架。**"
