# Phase 4：会话记忆管理 — 知识点与面试要点

> 多轮对话上下文、会话持久化、对话管理的技术细节和面试准备。

---

## 做了什么

用 SQLite 数据库存储对话和消息，支持多轮对话上下文记忆、多会话管理、对话历史持久化。

---

## 核心知识点

### 1. 会话记忆的作用

```
无记忆：                        有记忆：
用户: 北京有什么演唱会            用户: 北京有什么演唱会
AI: 周杰伦、林俊杰...            AI: 周杰伦、林俊杰...
用户: 第一个多少钱               用户: 第一个多少钱
AI: ??? 第一个是什么？           AI: 周杰伦演唱会票档价格是...
```

**面试要点：**
- LLM 本身是**无状态**的，每次请求都是独立的
- 会话记忆通过**消息列表**实现：把历史消息一起发给 LLM
- `max_messages=20` 滑动窗口：只保留最近 20 条，防止 token 超限

---

### 2. SQLAlchemy ORM 模型

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), default="新对话")
    chat_type = Column(String(20), default="assistant")
    messages = relationship("Message", back_populates="conversation")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String(20))  # user / assistant
    content = Column(Text)
    sources = Column(JSON, nullable=True)  # RAG 引用来源
```

**面试要点：**
- `relationship` 定义表之间的关联（一对多）
- `cascade="all, delete-orphan"` 删除对话时自动删除关联消息
- `JSON` 类型字段存储结构化数据（RAG 引用来源）

---

### 3. 消息加载与上下文构建

```python
# 加载历史消息
history = memory_service.get_history(conversation_id, max_messages=20)

# 构建消息列表
messages = [SystemMessage(content=SYSTEM_PROMPT)]
for h in history:
    if h["role"] == "user":
        messages.append(HumanMessage(content=h["content"]))
    elif h["role"] == "assistant":
        messages.append(AIMessage(content=h["content"]))
```

**面试要点：**
- 历史消息 + 系统提示 + 当前用户消息 = 完整的 LLM 输入
- `max_messages=20` 是滑动窗口，只保留最近的对话
- 对话太长时需要**截断**或**摘要**，防止超出 token 限制

**面试问：** 对话历史太长怎么办？
**答：** 三种策略：1）滑动窗口（只保留最近 N 条）；2）摘要压缩（让 LLM 总结历史）；3）混合方式（近期保留原文，远期用摘要）。

---

### 4. 对话管理 API

```
GET    /api/conversations              # 对话列表
GET    /api/conversations/{id}/messages # 历史消息
PUT    /api/conversations/{id}/title    # 修改标题
DELETE /api/conversations/{id}          # 删除对话
```

**面试要点：**
- 对话管理是 AI 应用的标配功能
- 前端需要对话列表、切换对话、新建对话、删除对话
- 消息分页加载（大量历史消息时）

---

### 5. 自动创建对话

```python
# chat 接口中自动创建对话
if not conversation_id:
    conv = memory_service.create_conversation(chat_type)
    conversation_id = str(conv.id)
    yield f'data: {{"type": "conversation_id", "content": "{conversation_id}"}}\n\n'
```

**面试要点：**
- 前端首次对话时不传 `conversation_id`，后端自动创建
- 创建后返回 `conversation_id`，前端保存，后续请求带上
- SSE 流中返回 `conversation_id`，前端实时获取

---

## 面试高频问题

| 问题 | 回答要点 |
|------|---------|
| LLM 怎么记住上下文？ | 把历史消息一起发给 LLM，LLM 本身无状态 |
| 对话历史太长怎么办？ | 滑动窗口、摘要压缩、混合策略 |
| 怎么实现多会话？ | conversation_id 区分不同对话，消息表关联 conversation_id |
| 会话持久化用什么？ | SQLite（轻量）/ MySQL（生产）/ Redis（缓存） |
| 消息类型有哪些？ | system（系统提示）、user（用户）、assistant（AI）、tool（工具结果） |

---

## 与原项目（Spring AI）对比

| 原项目 (Spring AI) | Python 版 | 知识点 |
|-------------------|-----------|--------|
| `MessageWindowChatMemory` | `max_messages=20` 滑动窗口 | 上下文窗口 |
| `JDBC Chat Memory` | SQLAlchemy + SQLite | 持久化存储 |
| `ChatTypeHistoryAdvisor` | `memory_service.save_message()` | 消息保存 |
| `ChatTypeTitleAdvisor` | `update_title()` | 标题生成 |
| `conversation_id` 参数 | 同样设计 | 多会话管理 |
