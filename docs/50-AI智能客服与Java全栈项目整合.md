# AI智能客服与Java全栈项目整合方案

> AI智能客服项目与Java高并发票务系统的整合开发过程记录。

---

## 项目背景

| 项 | 值 |
|----|-----|
| AI项目 | damai-smart-ticket（Python + LangChain） |
| 全栈项目 | D:\damai（Java + Spring Cloud 微服务） |
| 整合目标 | 实现AI客服调用真实业务数据，完成传统项目AI智能化升级 |
| 开发时间 | 2026-07-12 |

---

## 一、整合目标

### 1.1 核心目标

| 目标 | 说明 |
|------|------|
| 数据整合 | AI客服通过API调用获取全栈项目的真实业务数据 |
| 用户隔离 | 不同用户的聊天记录相互隔离 |
| 功能完整 | 支持查询节目、查询订单、创建订单等功能 |
| 生产级设计 | 符合微服务架构和安全规范 |

### 1.2 技术挑战

| 挑战 | 说明 |
|------|------|
| 异构系统整合 | Python AI项目 + Java微服务项目 |
| 认证机制 | Token传递和用户身份验证 |
| 数据隔离 | 不同用户的对话记录隔离 |
| API设计 | 复用现有API vs 新建API |

---

## 二、技术方案

### 2.1 整合架构

```
┌─────────────────────────────────────────────────────────────┐
│                      整合架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户 → 全栈项目前端 (localhost:5173)                       │
│         └→ 登录 → 获取JWT Token                            │
│         └→ 点击"AI客服"按钮                                │
│                                                             │
│  用户 → AI项目前端 (localhost:8000)                         │
│         └→ 接收Token → 存储到localStorage                  │
│         └→ 调用API时携带Token                              │
│                                                             │
│  AI项目后端 → 调用Java API                                  │
│               ├→ 节目服务 (localhost:6086)                  │
│               └→ 订单服务 (localhost:8081)                  │
│                                                             │
│  Java服务 → 验证Token → 返回用户相关数据                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 数据流转

```
1. 用户在全栈项目登录 → 获取JWT Token
2. 点击"AI客服"按钮 → Token通过URL参数传递给AI项目
3. AI项目前端存储Token到localStorage
4. 用户提问时，前端携带Token调用后端API
5. AI后端解析Token获取userId
6. 调用Java API时携带Token
7. Java服务验证Token，返回用户相关数据
8. AI生成回复，保存对话记录（关联userId）
```

---

## 三、实现过程

### 3.1 阶段一：API调用基础实现

**目标**：实现AI项目调用Java API获取业务数据

**实现**：
- 修改 `java_api_client.py`，使用 `/program/page` 代替 `/program/search`
- 解决ES索引前缀配置问题
- 实现节目查询、详情查询、票档查询等功能

**关键代码**：
```python
# java_api_client.py
def search_program(self, content, city, ...):
    # 使用 /program/page 代替 /program/search（有数据库回退机制）
    data = {"content": content, "timeType": 0, "pageNumber": 1, "pageSize": 10}
    return self._request("POST", "/program/page", data, base_url=self.program_url)
```

**问题与解决**：
| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 搜索返回空数据 | `/program/search`依赖ES，ES无数据 | 改用`/program/page`（有数据库回退） |
| ES索引前缀不匹配 | 配置文件与实际索引不一致 | 修改配置文件添加prefix |

---

### 3.2 阶段二：用户认证整合

**目标**：实现Token传递和用户身份验证

**实现**：
- 创建 `token_util.py` 解析JWT Token
- 修改 `agent.py`、`chat.py` 添加登录验证
- 修改 `java_api_client.py` 支持Token传递

**关键代码**：
```python
# token_util.py
def get_user_id_from_token(token: str) -> Optional[int]:
    """从Token中获取用户ID"""
    user_info = parse_token(token)
    if user_info:
        return user_info.get('userId')
    return None

# agent.py
@router.post("")
async def agent_chat(request: AgentRequest, req: Request):
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return JSONResponse(status_code=401, content={"detail": "请先登录"})
    
    java_api.set_token(token)
    user_id = java_api.get_user_id()
    # ...
```

**问题与解决**：
| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Token解析失败 | JWT格式理解错误 | 实现Base64解码解析payload |
| 全局单例污染 | java_api是全局实例，user_id未重置 | 每次请求前重置token |

---

### 3.3 阶段三：用户对话隔离

**目标**：实现不同用户的对话记录相互隔离

**实现**：
- 修改 `Conversation` 模型，添加 `user_id` 字段
- 修改 `memory_service.py`，创建对话时保存user_id
- 修改 `get_conversations()` 方法，根据user_id过滤

**关键代码**：
```python
# conversation.py
class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)  # 用户ID
    title = Column(String(200), default="新对话")
    # ...

# memory_service.py
def get_conversations(self, user_id: int = None) -> list[dict]:
    query = db.query(Conversation)
    if user_id is not None:
        query = query.filter(Conversation.user_id == user_id)
    # ...
```

**问题与解决**：
| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 换账号后看到旧记录 | localStorage中的Token未更新 | 检测Token变化，更新localStorage |
| 对话列表不显示 | API请求未携带Token | 添加axios请求拦截器 |

---

### 3.4 阶段四：前端整合

**目标**：实现全栈项目跳转到AI客服，并正确传递Token

**实现**：
- 全栈项目header组件添加"AI客服"按钮
- AI项目前端接收URL参数中的Token
- API请求自动携带Token

**关键代码**：
```javascript
// 全栈项目 header/index.vue
function openAIChat() {
    const token = getToken()
    if (token) {
        window.open(`http://localhost:8000?token=${token}`)
    }
}

// AI项目 frontend/src/api/index.ts
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('damai_token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})
```

---

## 四、API整合清单

### 4.1 已整合的API

| API | 功能 | 状态 |
|-----|------|------|
| `/program/page` | 搜索节目 | ✅ 可用 |
| `/program/detail` | 节目详情 | ✅ 可用 |
| `/ticket/category/select/list/by/program` | 票档查询 | ✅ 可用 |
| `/program/recommend/list` | 推荐列表 | ✅ 可用 |
| `/program/order/create/v1` | 创建订单 | ✅ 可用 |
| `/order/get` | 查询订单详情 | ✅ 可用 |
| `/order/select/list` | 查询订单列表 | ✅ 可用 |

### 4.2 工具函数映射

| 工具函数 | 调用的Java API | 说明 |
|----------|---------------|------|
| `search_program` | `/program/page` | 搜索节目 |
| `get_program_detail` | `/program/detail` | 节目详情 |
| `get_ticket_info` | `/ticket/category/select/list/by/program` | 票档查询 |
| `create_order` | `/program/order/create/v1` | 创建订单 |
| `get_order_list` | `/order/select/list` | 订单列表 |
| `check_order_status` | `/order/get` | 订单详情 |
| `get_recommendations` | `/program/recommend/list` | 推荐列表 |

---

## 五、关键发现与解决方案

### 5.1 ES索引问题

**问题**：Java项目的搜索API使用Elasticsearch，但ES中没有数据

**原因**：
- 节目搜索API (`/program/search`) 依赖ES
- ES索引前缀配置不一致
- ES数据初始化可能失败

**解决方案**：
- 使用 `/program/page` 代替 `/program/search`（有数据库回退机制）
- 修改配置文件确保索引前缀正确

### 5.2 用户认证问题

**问题**：AI项目无法获取用户身份信息

**原因**：
- 全栈项目使用JWT Token认证
- AI项目没有Token解析机制

**解决方案**：
- 实现JWT Token解析工具
- 添加登录验证中间件
- 自动携带Token调用API

### 5.3 数据隔离问题

**问题**：不同用户的对话记录混在一起

**原因**：
- 对话表没有user_id字段
- 查询时没有过滤用户

**解决方案**：
- 添加user_id字段
- 创建对话时保存user_id
- 查询时根据user_id过滤

---

## 六、测试验证

### 6.1 功能测试

| 测试项 | 结果 | 说明 |
|--------|------|------|
| 搜索节目 | ✅ 通过 | 返回真实业务数据 |
| 节目详情 | ✅ 通过 | 返回完整节目信息 |
| 票档查询 | ✅ 通过 | 返回价格和余票 |
| 创建订单 | ✅ 通过 | 可以创建订单 |
| 查询订单列表 | ✅ 通过 | 返回用户的订单 |
| 用户隔离 | ✅ 通过 | 不同用户只能看到自己的对话 |

### 6.2 集成测试

| 测试项 | 结果 | 说明 |
|--------|------|------|
| 全栈项目登录 | ✅ 正常 | 获取JWT Token |
| 跳转AI客服 | ✅ 正常 | Token正确传递 |
| AI对话 | ✅ 正常 | 可以正常提问和回答 |
| 对话记录保存 | ✅ 正常 | 消息正确保存到数据库 |
| 对话列表显示 | ✅ 正常 | 显示用户的对话列表 |
| 用户切换 | ✅ 正常 | 不同用户看到不同的对话 |

---

## 七、修改的文件清单

### 7.1 AI项目

| 文件 | 修改内容 |
|------|----------|
| `app/utils/token_util.py` | 新增：JWT Token解析工具 |
| `app/utils/java_api_client.py` | 修改：添加Token支持、修复API路径 |
| `app/api/agent.py` | 修改：添加登录验证、Token传递 |
| `app/api/chat.py` | 修改：添加登录验证 |
| `app/api/conversation.py` | 修改：添加登录验证、用户过滤 |
| `app/chains/tools.py` | 修改：添加get_order_list工具 |
| `app/chains/agent.py` | 修改：注册新工具 |
| `app/core/prompts.py` | 修改：添加订单查询规则 |
| `app/models/conversation.py` | 修改：添加user_id字段 |
| `app/services/memory_service.py` | 修改：支持用户过滤 |
| `app/services/agent_service.py` | 修改：支持user_id参数 |
| `app/services/chat_service.py` | 修改：支持user_id参数 |
| `frontend/src/api/index.ts` | 修改：添加Token请求拦截器 |
| `frontend/src/api/chat.ts` | 修改：携带Token调用API |
| `frontend/src/views/ChatView.vue` | 修改：Token接收和对话列表加载 |

### 7.2 全栈项目

| 文件 | 修改内容 |
|------|----------|
| `vue3/src/components/header/index.vue` | 修改：添加"AI客服"按钮 |

---

## 八、面试话术

### 8.1 项目介绍

> "我做了一个传统票务系统的AI智能化升级。原系统是Java微服务架构（Spring Cloud + Redis + Kafka + ES），处理高并发购票场景。我基于Python + LangChain + LangGraph构建了AI智能客服系统，通过HTTP API与原系统整合，实现了自然语言查询节目、智能下单、规则问答等功能。"

### 8.2 技术亮点

> "整合过程中的关键设计：
> 1. **异构系统整合**：Python AI项目 + Java微服务，通过HTTP API通信
> 2. **用户认证共享**：JWT Token跨系统传递，实现统一身份认证
> 3. **数据隔离**：基于user_id的对话记录隔离，保证用户隐私
> 4. **API复用**：复用现有Java API，不修改原有业务代码
> 5. **自动回退**：API不可用时自动回退到模拟数据"

### 8.3 问题解决

> "遇到了几个关键问题：
> 1. **ES索引问题**：搜索API依赖ES但数据未同步，改用有数据库回退的API
> 2. **Token传递**：实现JWT解析和跨系统Token传递机制
> 3. **用户隔离**：添加user_id字段，实现对话记录按用户隔离
> 4. **全局状态污染**：Java API客户端是单例，需要在每次请求时重置状态"

---

## 九、项目价值

### 9.1 技术价值

| 价值 | 说明 |
|------|------|
| AI落地能力 | 展示传统业务AI赋能的完整流程 |
| 架构设计 | 异构系统整合的架构设计能力 |
| 问题解决 | 实际开发中遇到问题的解决能力 |
| 全栈能力 | 前后端 + AI + Java 的全栈能力 |

### 9.2 面试价值

| 亮点 | 说明 |
|------|------|
| 业务理解 | 理解票务场景和用户需求 |
| 技术深度 | RAG、Agent、Function Calling等AI技术 |
| 工程能力 | 用户认证、数据隔离、API设计 |
| 实战经验 | 真实项目的开发和整合经验 |

---

## 十、后续优化

### 10.1 短期优化

| 优化项 | 说明 |
|--------|------|
| 单元测试 | 添加核心功能的单元测试 |
| 错误处理 | 完善异常处理和用户提示 |
| 日志优化 | 添加结构化日志便于排查 |

### 10.2 中期优化

| 优化项 | 说明 |
|--------|------|
| 部署上线 | Docker Compose打包部署 |
| 监控告警 | 添加性能监控和异常告警 |
| 缓存优化 | Redis缓存热门查询结果 |

### 10.3 长期优化

| 优化项 | 说明 |
|--------|------|
| 微前端 | 使用qiankun实现独立部署 |
| 多租户 | 支持多租户隔离 |
| 性能优化 | 流式RAG、异步处理 |

---

## 附录：数据库结构

### conversations表

```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,           -- 用户ID，用于用户隔离
    title VARCHAR(200) DEFAULT '新对话',
    chat_type VARCHAR(20) DEFAULT 'assistant',
    pinned INTEGER DEFAULT 0,
    created_at DATETIME,
    updated_at DATETIME
);
```

### messages表

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    sources JSON,
    steps JSON,
    token_usage JSON,
    created_at DATETIME,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

