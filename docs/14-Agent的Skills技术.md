# Agent 的 Skills 技术

> Skills 是**按需加载的行为指令**，解决的是 Agent 能力扩展和 Token 消耗的平衡问题。RAG 提供知识，Function Calling 提供工具，Skills 提供行为指导，三者互补。

---

## 一、Skills 是什么

**面试提问**：什么是 Agent 的 Skills？

💥**优质回答**💥：
> Skills 是**预定义的能力模块**，根据用户意图动态加载到 Agent 的上下文中。核心思想是"按需加载"——不把所有能力都塞进去，而是用到什么加载什么。

用 Claude Code 举例：

```
你输入 /review    → 触发 review skill       → 把"代码审查"的详细指令注入到上下文
你输入 /fix       → 触发 fix skill          → 把"修复 Bug"的详细指令注入到上下文
你写 Java 代码    → 触发 java-dev skill     → 把"Java 开发规范"注入到上下文
```

这些 skill 的内容**不是每次都加载的**，只有匹配到意图时才注入。

---



## 二、为什么需要 Skills

**核心矛盾**：Agent 需要很多能力，但上下文窗口有限。

```
没有 Skills 的情况：
  System Prompt = 通用指令(500) + Java规范(800) + Python规范(800) + 代码审查规范(600) + 测试规范(600) + ...
  总计: 3000+ tokens，每次请求都带着，不管你写什么语言

有 Skills 的情况：
  System Prompt = 通用指令(500) + 当前需要的 skill(800)
  总计: 1300 tokens，只加载当前需要的
```

**面试话术**：

> "Skills 解决的是**❇️能力扩展和 Token 消耗的平衡问题❇️**。Agent 需要很多能力，但不能每次都把所有能力塞进上下文。通过意图分类，只加载当前场景需要的指令，既保证了 Agent 的专业性，又控制了 Token 消耗。"

---



## 三、Skills 与 RAG、Function Calling 的关系

**面试提问**：Skills 和 RAG、Function Calling 有什么区别？

**优质回答**：
> 三个技术解决的是不同层面的问题。RAG 解决"我知道什么"（知识检索），Function Calling 解决"我能做什么"（工具调用），Skills 解决"我怎么做"（行为指导）。三者是互补关系，不是替代关系。

### 三者对比

| 维度 | RAG | Function Calling | Skills |
|------|-----|-----------------|--------|
| 解决什么 | Agent 缺少领域知识 | Agent 缺少执行能力 | Agent 缺少行为指导 |
| 加载什么 | 文档片段 | 工具定义（函数签名） | 指令/规范/模板 |
| 加载时机 | 每次对话都检索 | 每次对话都带上工具定义 | 按需动态加载 |
| 对模型的影响 | 提供参考信息 | 提供可调用的函数 | 改变模型的行为方式 |
| Token 消耗 | 中（检索结果 1-3k） | 高（工具定义 3-5k） | 低（按需加载 0.5-1.5k） |

### 一个具体例子

用户问："帮我写一个 Java 的用户注册接口"

```
RAG 的作用：
  检索知识库 → 找到"Java 接口开发规范"文档 → 注入上下文
  → Agent 知道项目的代码规范、命名约定、异常处理方式

Function Calling 的作用：
  提供 tools: [create_file, run_tests, check_style]
  → Agent 能实际创建文件、运行测试、检查代码风格

Skills 的作用：
  匹配到 java-dev skill → 注入"Java 开发规范"指令
  → Agent 知道要用 Spring Boot、要写接口文档、要加参数校验
```

**面试话术**：

> "**❇️RAG 提供知识，❇️Function Calling 提供工具，❇️Skills 提供行为指导**。比如用户问 Java 接口开发，RAG 检索项目规范文档，Function Calling 提供创建文件和运行测试的工具，Skills 注入 Java 开发的最佳实践指令。三者配合，Agent 才能既懂知识、又能执行、还做得专业。"

---



## 四、Skills 的实现方式

### 1. Skill 文件结构

Skills 本质是带 frontmatter 的 markdown 文件：

```markdown
---
name: go-dev
description: "Use this skill when the user is writing Go code, asking about Go patterns, or working with Go projects"
---

# Go 开发规范

## 代码风格
- 使用 gofmt 格式化
- 错误处理用 if err != nil
...
```

**关键字段**：

| 字段 | 作用 |
|------|------|
| `name` | Skill 的唯一标识，也是 `/skill-name` 的触发词 |
| `description` | **决定自动触发的核心字段**，系统用它判断"该不该加载这个 skill" |

**description 为什么这么重要**：系统拿到用户输入后，会和所有 skill 的 description 做匹配。description 写得好不好，直接决定 skill 能不能被触发。

### 2. 触发方式（四种）

#### 方式一：💥显式触发（用户主动）

用户直接输入 `/skill-name`：

```
/review    → 触发 code-review skill
/fix       → 触发 fix-bug skill
```

这是**最可靠**的触发方式，100% 命中，不依赖 description 匹配。

#### 方式二：💥自动触发（系统匹配 description）

系统根据用户输入，自动匹配所有 skill 的 description：

```
用户输入："帮我写一个 Go 的 HTTP 接口"

系统扫描所有 skill 的 description：
  go-dev: "Use this skill when the user is writing Go code..."      ← 匹配 ✅
  python-dev: "Use this skill when writing Python code..."          ← 不匹配
  code-review: "Use this skill when reviewing code..."              ← 不匹配

→ 加载 go-dev skill
```

这是**最常用**的触发方式，但依赖 description 的质量。

#### 方式三：💥上下文触发（基于环境）

不看用户输入，看当前的环境状态：

```
检测到当前目录有 pom.xml         →   加载 java-dev skill
检测到当前目录有 package.json    →   加载 frontend-dev skill
检测到有 .py 文件               →   加载 python-dev skill
```

不需要用户说话，根据环境自动判断。

#### 方式四：💥组合触发（多条件）

```
用户输入包含"review" + 当前有 .ts 文件
  → 同时触发 code-review skill 和 typescript-dev skill
```

**触发方式总结**：

| 方式 | 触发条件 | 可靠性 | 适用场景 |
|------|---------|--------|---------|
| 显式触发 | 用户输入 `/skill-name` | ⭐⭐⭐⭐⭐ | 用户明确知道要用什么 skill |
| 自动触发 | 匹配 description | ⭐⭐⭐ | 用户自然语言描述需求 |
| 上下文触发 | 检测环境状态 | ⭐⭐⭐⭐ | 根据项目类型自动适配 |
| 组合触发 | 多条件同时满足 | ⭐⭐⭐⭐ | 复杂场景，多 skill 协作 |

### 3. description 编写技巧

| 技巧 | 说明 | 示例 |
|------|------|------|
| 列举触发场景 | 把所有可能的触发情况都写上 | "writing, debugging, reviewing, optimizing Go code" |
| 包含关键词 | 用户可能用到的关键词 | "Go, golang, Gin, goroutine" |
| 排除条件 | 明确什么情况不该触发 | "NOT when the user is writing Python" |
| 保持简洁 | 太长反而匹配不准 | 1-2 句话足够 |

### 4. 实现代码示例

```python
# 用户输入后，先做意图分类
intent = classify_intent(user_input)

# 根据意图加载对应的 skill
skill_map = {
    "java_dev": "skills/java-dev.md",
    "code_review": "skills/code-review.md",
    "debug": "skills/fix-bug.md",
}

if intent in skill_map:
    skill_content = load_skill(skill_map[intent])
    system_prompt = base_prompt + skill_content  # 动态拼接
```

**面试话术**：

> "Skills 的触发机制本质是**意图分类**。每个 skill 文件有一个 description 字段，系统拿到用户输入后，和所有 skill 的 description 做匹配，命中的就加载到上下文中。description 写得好不好直接决定触发准确率。触发方式有四种：用户显式调用 `/skill-name`、系统自动匹配 description、基于环境上下文触发、多条件组合触发。生产中通常组合使用。"

**面试话术**：

> "Skills 的实现有三种方式：静态文件（最简单，按文件名加载）、意图路由（先分类再加载）、上下文自动触发（检测用户行为自动匹配）。Claude Code 就是第三种——检测到你在写 Java，就自动加载 Java 开发规范的 skill。"

---



## 五、生产项目中的应用

### 为什么需要 Skills — 退款 vs 查票的例子

**核心价值**：同一个 Agent，在不同场景下表现不同。而不是把所有场景的规范都堆在 System Prompt 里。

```
没有 Skills：
  System Prompt = 通用指令(500) + 退款规范(400) + 查票规范(400) + 投诉规范(400) + 销售规范(400)
  总计: 2000+ tokens，每次请求都带着，不管你问什么

有 Skills：
  System Prompt = 通用指令(500) + 当前场景的 skill(400)
  总计: 900 tokens，只加载需要的
  → 省了 55% 的 token
```

**不同场景的语气差异**：

```markdown
# Skill: 退款/投诉场景
## 语气
- 诚恳、歉意、耐心
- 先道歉，再解决问题
- 不要推卸责任

## 话术
- "非常抱歉给您带来不好的体验..."
- "我理解您的心情，我来帮您处理..."
```

```markdown
# Skill: 查票/销售场景
## 语气
- 活泼、热情、有亲和力
- 主动推荐，制造期待感
- 适当用 emoji

## 话术
- "哇，这场演出超赞的！🎶"
- "我帮您看看还有哪些好位置～"
```

**没有 Skills 的话**，只能在 System Prompt 里写"根据用户问题类型切换语气"，但 LLM 不一定切换得好。有了 Skills，直接注入对应场景的完整指令，效果更稳定。

### 典型架构

```
用户请求
  │
  ▼
意图分类（小模型或规则）
  │
  ├─ 查询类 → 加载 knowledge-qa skill + RAG 检索
  ├─ 操作类 → 加载 ticket-booking skill + Function Calling
  ├─ 售后类 → 加载 refund-policy skill + Function Calling（诚恳语气）
  ├─ 投诉类 → 加载 complaint skill + Function Calling（道歉语气）
  └─ 闲聊类 → 不加载 skill，纯对话
  │
  ▼
System Prompt = 基础指令 + 动态 skill + RAG 结果 + 工具定义
  │
  ▼
Agent 执行
```

### Skills 的内容设计

一个好的 skill 文件通常包含：

```markdown
# Skill: 退票流程指导

## 角色
你是大麦网的退票客服，负责处理用户的退票请求。

## 语气
- 诚恳、歉意、耐心
- 先道歉，再解决问题

## 流程
1. 确认用户的订单号
2. 查询订单状态和退票资格
3. 告知退票政策（演出前48小时可退，扣10%手续费）
4. 引导用户完成退票操作

## 约束
- 不要承诺"一定能退"，要看具体订单状态
- 已出票的订单需要到现场退
- 退款到账时间是3-7个工作日

## 话术模板
- "非常抱歉给您带来不好的体验，我来帮您处理退票。"
- "您的订单符合退票条件，退票需扣除10%手续费..."
```

### 你项目的 Skills 设计

```
你项目的 Agent 有 9 个工具，覆盖订票、查票、知识库等场景。

Skills 方案：
  skills/
  ├── ticket-booking.md    # 订票场景：活泼热情，主动推荐
  ├── refund-policy.md     # 退票场景：诚恳歉意，耐心处理
  ├── complaint.md         # 投诉场景：先道歉，再解决
  ├── knowledge-qa.md      # 知识库问答：专业准确，引用来源
  └── general-chat.md      # 闲聊场景：友好自然，适当引导

  用户问退票   →   加载 refund-policy skill        →    Agent 用诚恳语气回答
  用户问演出   →   加载 knowledge-qa skill + RAG   →    Agent 用专业语气回答
  用户要买票   →   加载 ticket-booking skill       →    Agent 用热情语气回答
```

---



## 六、Skills 的优势与注意事项

### 优势

| 优势 | 说明 |
|------|------|
| Token 节省 | 只加载当前需要的指令，不浪费上下文窗口 |
| 能力隔离 | 不同场景的专业能力互不干扰 |
| 易于维护 | 每个 skill 独立文件，修改不影响其他场景 |
| 可扩展 | 新增场景只需加一个 skill 文件 |
| 一致性 | 同一场景的回答风格和流程统一 |

### 注意事项

| 注意点 | 说明 |
|--------|------|
| 意图分类要准 | 分类错了加载错 skill，效果反而更差 |
| Skill 内容要精简 | 太长的 skill 本身也消耗 token，失去按需加载的意义 |
| 冲突处理 | 多个 skill 匹配时要有优先级规则 |
| 兜底机制 | 没有匹配到 skill 时要有默认行为 |
| Skill 和 RAG 的边界 | Skill 是行为指导，RAG 是知识补充，不要混在一起 |

---

## 七、面试高频问题

| 问题 | 回答要点 |
|------|---------|
| 什么是 Agent 的 Skills？ | 预定义的能力模块，根据用户意图动态加载到上下文，核心是"按需加载" |
| Skills 解决什么问题？ | 能力扩展和 Token 消耗的平衡——不需要每次都加载所有能力 |
| Skills 和 RAG 的区别？ | RAG 提供知识（我知道什么），Skills 提供行为指导（我怎么做） |
| Skills 和 Function Calling 的区别？ | Function Calling 提供工具（我能做什么），Skills 提供行为规范（我怎么做） |
| 三者是什么关系？ | 互补关系：RAG 是知识层，Function Calling 是能力层，Skills 是行为层 |
| Skills 怎么实现？ | 三种方式：静态文件、意图路由、上下文自动触发 |
| 生产项目怎么用 Skills？ | 意图分类 → 动态加载对应 skill → 拼接到 System Prompt → Agent 执行 |
| Skills 的 Token 消耗？ | 按需加载 0.5-1.5k token，比全量加载 3k+ 省 50%+ |
| Skills 的注意事项？ | 意图分类要准、内容要精简、要有兜底机制、注意和 RAG 的边界 |

---

## 八、本项目 Skills 应用现状

| 维度 | 状态 | 说明 |
|------|------|------|
| 静态 Skill 文件 | ❌ 未做 | 没有独立的 skill 文件 |
| 意图分类 | ✅ 有 | Multi-Agent 模式有 intent_classifier 节点 |
| 动态 Prompt 加载 | ⚠️ 部分 | System Prompt 按模式切换，但不是按 skill 动态拼接 |
| 场景化行为指导 | ❌ 未做 | 没有退票、订票等场景的专属行为规范 |

**当前实现**：通过 Multi-Agent 的意图分类路由到不同的 Agent 节点（ticket_agent / knowledge_agent），每个节点有不同的 System Prompt。这本质上是 Skills 的雏形，但没有拆成独立的 skill 文件。

**面试话术**：
> "**项目通过 Multi-Agent 的意图分类实现了 Skills 的雏形。intent_classifier 节点判断用户意图后，路由到不同的 Agent 节点，每个节点有专属的 System Prompt 和工具集。本质上就是按需加载行为指令，只是没有拆成独立的 skill 文件。后续可以抽成独立的 skill 模块，支持更灵活的动态加载。**"
