# RAG 知识库权限隔离

> 不给模型越权内容，才是最安全的权限隔离。权限必须在模型看到内容之前控制住。

---

## 一、核心原则

**面试提问**：RAG 知识库怎么做权限隔离？

💥**优质回答**💥：
> 企业级 RAG 的核心，不是让模型自觉保密，而是在模型看到内容之前就把权限控制住。大模型看到什么，才可能回答什么。不给它越权内容，才是最安全的权限隔离。

```
❌ 错误做法：先把所有文档都给 LLM，让 LLM 自己判断哪些能说
   → LLM 可能泄露，Prompt 注入可以绕过

✅ 正确做法：在 LLM 看到内容之前，就把无权限的文档过滤掉
   → LLM 根本看不到越权内容，自然不会泄露
```

---



## 二、五层权限隔离

### 第 1 层：💥租户隔离 — 按租户隔离数据

**做什么**：每个文档、每个 chunk、每条向量，都必须带租户 ID。检索时只允许在当前租户的数据范围内召回。

```python
# 每个 chunk 的 metadata 都带 tenant_id
chunk.metadata = {
    "tenant_id": "tenant_001",
    "source": "退票政策.md",
    "parent_id": "parent_001"
}

# 检索时限定租户范围
results = vectorstore.similarity_search(
    query,
    k=5,
    filter={"tenant_id": current_user.tenant_id}  # 只搜当前租户的数据
)
```

**隔离方式**：

| 方式 | 说明 | 优点 | 缺点 |
|------|------|------|------|
| 物理隔离 | 每个租户一个独立的向量库 | 完全隔离，安全性最高 | 资源浪费，运维复杂 |
| 逻辑隔离 | 共享向量库，用 metadata 过滤 | 资源利用率高 | 依赖过滤逻辑正确性 |

**面试话术**：
> "租户隔离是第一道边界。每个 chunk 都带 tenant_id，检索时用 metadata 过滤限定范围。小规模用逻辑隔离，大规模用物理隔离。"

### 第 2 层：💥文档级权限 — 精细到文档的访问控制

**做什么**：文档入库时，不只是存正文和向量，还要存**❇️权限元数据**。chunk 必须继承原始文档的权限。

```python
# 文档入库时绑定权限
doc.metadata = {
    "tenant_id": "tenant_001",
    "doc_id": "doc_0123",
    "permission": "internal",           # public / internal / vip / secret
    "allowed_roles": ["admin", "hr"],    # 允许访问的角色
    "allowed_users": ["user_001"],       # 允许访问的用户白名单
    "security_level": "confidential",   # 密级：public / internal / confidential / secret
}

# chunk 继承文档的权限
for chunk in chunks:
    chunk.metadata["permission"] = doc.metadata["permission"]
    chunk.metadata["allowed_roles"] = doc.metadata["allowed_roles"]
    chunk.metadata["security_level"] = doc.metadata["security_level"]
```

**权限模型**：

| 维度 | 说明 | 示例 |
|------|------|------|
| 角色 | 按角色控制 | admin 可看全部，user 只看 public |
| 用户白名单 | 指定用户 | 只有 user_001 和 user_003 能看 |
| 密级 | 按安全等级 | public < internal < confidential < secret |
| 部门 | 按组织架构 | 只有 HR 部门能看薪资文档 |

**面试话术**：
> "文档级权限要做两件事：一是**入库时绑定权限元数据**，二是 **chunk 必须继承原始文档的权限**。权限模型要支持角色、用户白名单、密级、部门多个维度，不能只按部门隔离。"

### 第 3 层：💥检索前过滤 — 企业级 RAG 的主防线

**做什么**：在检索阶段按权限过滤候选内容。**不是先检索再过滤，而是❇️先限定范围再检索。**

```
❌ 错误顺序：先检索全部 → 再过滤无权限的
   → 无权限文档已经进入了候选集，可能被泄露

✅ 正确顺序：先生成过滤条件 → 在过滤范围内检索
   → 无权限文档根本不会被检索到
```

```python
def generate_permission_filter(user):
    """根据用户信息生成权限过滤条件"""
    filters = {"tenant_id": user.tenant_id}

    # 角色过滤
    if user.role != "admin":
        filters["permission"] = {"$in": ["public", "internal"]}
        filters["allowed_roles"] = {"$contains": user.role}

    # 密级过滤
    max_level = get_max_security_level(user.role)
    filters["security_level"] = {"$lte": max_level}

    return filters

# 检索时先过滤再搜索
permission_filter = generate_permission_filter(current_user)
results = vectorstore.similarity_search(
    query,
    k=5,
    filter=permission_filter  # 先限定范围，再检索
)
```

**为什么这是主防线**：

```
五层防护中，第 3 层是唯一在"数据进入 LLM 之前"做大规模过滤的层。
  - 第 1 层（租户隔离）：划定大边界
  - 第 2 层（文档权限）：定义权限规则
  - 第 3 层（检索前过滤）：执行过滤，主防线
  - 第 4 层（生成前校验）：兜底检查
  - 第 5 层（输出审查）：最终兜底
```

**面试话术**：
> "检索前过滤是企业级 RAG 的主防线。核心原则是先限定范围再检索，不是先检索再过滤。根据用户的租户、角色、密级生成过滤条件，在向量检索时就限定范围，无权限文档根本不会进入候选集。"

### 第 4 层：💥生成前二次校验 — 兜底检查

**做什么**：对检索到的 chunk 再次校验，确保无越权内容进入 LLM。

```python
def validate_chunks(chunks, user):
    """生成前二次校验"""
    validated = []
    for chunk in chunks:
        # 校验租户
        if chunk.metadata["tenant_id"] != user.tenant_id:
            continue
        # 校验文档是否被撤权或删除
        if is_doc_revoked(chunk.metadata["doc_id"]):
            continue
        # 校验密级
        if chunk.metadata["security_level"] > get_max_level(user.role):
            continue
        # 校验用户白名单
        if not is_user_allowed(chunk.metadata, user):
            continue
        validated.append(chunk)
    return validated
```

**为什么需要二次校验**：

```
检索前过滤已经做了一次，为什么还要再校验？

原因一：权限可能在检索和生成之间发生变化
  用户 A 检索时有权限 → 文档被撤权 → 用户 A 看到了无权限内容

原因二：向量库的 metadata 过滤可能有 bug
  元数据写错了 → 过滤没拦住 → 二次校验兜底

原因三：企业级系统不能只靠一层防线
  向量库负责召回，权限服务负责最终确认
```

**面试话术**：
> "生成前二次校验是兜底防线。校验四件事：tenant_id 是否一致、doc_id 是否在可访问范围内、密级是否越权、文档是否被撤权或删除。企业级系统不能只靠一层防线，向量库负责召回，权限服务负责最终确认。"

### 第 5 层：💥答案级安全控制 — 输出审查与脱敏

**做什么**：对 LLM 的输出进行审查和脱敏，防止模型在回答中泄露敏感信息。

```python
def sanitize_output(answer: str, user) -> str:
    """输出审查与脱敏"""

    # 1. 引用来源校验
    sources = extract_sources(answer)
    for source in sources:
        if not check_source_permission(source, user):
            answer = remove_source(answer, source)

    # 2. 敏感信息脱敏
    answer = re.sub(r'1[3-9]\d{9}', '1**********', answer)      # 手机号
    answer = re.sub(r'\d{17}[\dXx]', '******************', answer) # 身份证
    answer = re.sub(r'\d{4}-\d{4}-\d{4}-\d{4}', '****-****-****-****', answer) # 银行卡

    # 3. 高敏感内容审查
    if contains_salary_info(answer) and user.role not in ["hr", "admin"]:
        answer = "抱歉，该信息需要 HR 权限才能查看。"

    return answer
```

**为什么需要输出审查**：

```
检索阶段防止拿错资料，生成阶段防止说错内容。

模型可能会融合多个 chunk 的信息，在融合过程中可能产生越权内容。
比如：chunk A 是用户有权限的，chunk B 也是用户有权限的，
但 A + B 组合起来推导出的信息可能是越权的。
```

**面试话术**：
> "答案级安全控制是最后一道防线。做三件事：一是**引用来源校验**，确保引用的文档用户有权限访问；二是**敏感信息脱敏**，手机号、身份证、银行卡自动替换；三是**高敏感内容审查**，薪资、合同金额等需要额外权限。检索阶段防止拿错资料，生成阶段防止说错内容。"

---



## 三、真实项目落地链路

```
用户登录
  │
  ▼
生成权限过滤条件（租户、角色、密级、白名单）
  │
  ▼
向量检索（在权限范围内检索）
  │
  ▼
二次校验（tenant_id、doc_id、密级、撤权状态）
  │
  ▼
合规 chunk 拼接 Prompt
  │
  ▼
大模型回答
  │
  ▼
输出审查与脱敏
  │
  ▼
返回用户 + 记录审计日志
```

**审计日志**：

```python
audit_log = {
    "user_id": "user_001",
    "tenant_id": "tenant_001",
    "question": "退票政策是什么",
    "retrieved_docs": ["doc_0123", "doc_0456"],
    "used_docs": ["doc_0123"],
    "timestamp": "2026-06-28 15:30:00",
    "ip_address": "192.168.1.100"
}
```

**审计日志记录什么**：谁问了什么、引用了哪些文档、命中文档是什么、什么时候发生的。用于审计追踪和问题排查。

**面试话术**：
> "真实项目的落地链路：用户登录后生成权限过滤条件，向量检索在权限范围内执行，检索结果做二次校验，合规 chunk 拼接 Prompt 给大模型，输出再过审查和脱敏，最后记录审计日志。审计日志记录谁问了什么、看了什么、什么时候发生的，用于追溯。"

---

## 四、常见坑

| 坑 | 说明 | 正确做法 |
|----|------|---------|
| 只按部门隔离 | 权限模型太简单，覆盖不了复杂场景 | 支持角色、用户白名单、密级、部门多维度 |
| 权限写死在向量里 | 权限变了要重算 embedding，成本高 | 权限存 metadata 或权限表，独立管理 |
| 相信大模型会保密 | Prompt 注入可以绕过 | 不给它无权限内容，才是最安全的 |
| 忽略审计日志 | 出了问题无法追溯 | 记录用户、问题、引用文档、时间 |
| 先检索再过滤 | 无权限文档已进入候选集 | 先限定范围再检索 |
| chunk 不继承文档权限 | 检索到的 chunk 可能越权 | chunk 入库时必须继承原始文档的权限 |

**面试话术**：
> "常见坑有四个：一是只按部门隔离，权限模型要支持多维度；二是权限写死在向量里，权限变了要重算 embedding，应该存 metadata 独立管理；三是相信大模型会保密，不给它无权限内容才是最安全的；四是忽略审计日志，谁问了什么、看了什么都要能追溯。"

---

## 五、总结

```
1. 租户隔离做边界        →    每个 chunk 带 tenant_id
2. 文档权限做颗粒度      →    chunk 继承文档权限
3. 检索前过滤做主防线     →    先限定范围再检索
4. 生成前校验做兜底      →    二次校验确保无越权
5. 输出审查做最终兜底     →    脱敏 + 来源校验
6. 审计日志做追踪        →    记录谁问了什么、看了什么
```

**金句**：
> "RAG 的权限控制，必须发生在模型看到内容之前。**不给它越权内容，才是最安全的权限隔离**。大模型看到什么，才可能回答什么。"

---

## 六、本项目权限隔离现状

| 层级 | 状态 | 说明 |
|------|------|------|
| 租户隔离 | ❌ 未做 | 单租户场景，不需要 |
| 文档级权限 | ❌ 未做 | 文档无权限元数据 |
| 检索前过滤 | ❌ 未做 | 无过滤条件 |
| 生成前校验 | ❌ 未做 | 无二次校验 |
| 输出审查 | ⚠️ 部分 | 有 Prompt 注入检测，无脱敏 |
| 审计日志 | ⚠️ 部分 | 有消息持久化，无审计专用表 |

**为什么没做**：当前是单用户 Demo 场景，不需要权限隔离。生产环境需要逐层补齐。

**面试话术**：
> "**当前项目是单用户 Demo 场景，没有做权限隔离。但架构上是支持扩展的——chunk 的 metadata 可以加 tenant_id 和 permission 字段，检索时用 ChromaDB 的 where 过滤即可。生产环境我会按五层来做：租户隔离、文档权限、检索前过滤、生成前校验、输出审查，核心原则是不给模型越权内容。**"

---

## 七、面试高频问题

| 问题 | 回答要点 |
|------|---------|
| RAG 知识库怎么做权限隔离？ | 五层：租户隔离、文档权限、检索前过滤、生成前校验、输出审查 |
| 权限隔离的核心原则是什么？ | 不给模型越权内容，在模型看到内容之前就把权限控制住 |
| 检索前过滤还是先检索再过滤？ | 先过滤再检索，无权限文档根本不会进入候选集 |
| 为什么需要生成前二次校验？ | 权限可能在检索和生成之间变化，向量库过滤可能有 bug，企业级需要多层防线 |
| chunk 的权限怎么管理？ | chunk 入库时继承原始文档的权限，存到 metadata 里 |
| 权限变了怎么办？ | 权限存 metadata 或权限表，独立管理，不用重算 embedding |
| 审计日志记什么？ | 谁问了什么、引用了哪些文档、命中文档、时间、IP |
| 你项目做了权限隔离吗？ | 没有，单用户场景不需要。但架构支持扩展，chunk metadata 可以加权限字段 |
