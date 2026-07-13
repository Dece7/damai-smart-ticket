# 用户隔离实现方案

## 1. 修改数据库结构

### 添加 user_id 字段

```python
# app/models/conversation.py
class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)  # 添加用户ID
    title = Column(String(200), default="新对话")
    chat_type = Column(String(20), default="assistant")
    pinned = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

## 2. 修改API接口

### 在创建对话时保存user_id

```python
# app/api/conversation.py
@router.post("/conversations")
async def create_conversation(request: Request):
    # 从Token中获取user_id
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user_id = get_user_id_from_token(token)
    
    # 创建对话时保存user_id
    conversation = Conversation(
        user_id=user_id,
        title="新对话"
    )
    # ...
```

### 查询对话时过滤user_id

```python
@router.get("/conversations")
async def list_conversations(request: Request):
    # 从Token中获取user_id
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user_id = get_user_id_from_token(token)
    
    # 只查询当前用户的对话
    conversations = db.query(Conversation).filter(
        Conversation.user_id == user_id
    ).all()
    # ...
```

## 3. 修改工具函数

### 自动使用当前用户的userId

```python
# app/chains/tools.py
@tool
def create_order(program_id: int, ticket_category_id: int, ticket_count: int) -> dict:
    """创建订单"""
    # 自动获取当前用户的userId
    user_id = java_api.get_user_id()
    if not user_id:
        return {"error": "用户未登录"}
    
    # 查询购票人信息
    ticket_users = java_api.get_ticket_users(user_id)
    if not ticket_users:
        return {"error": "请先添加购票人"}
    
    # 创建订单
    result = java_api.create_order(
        program_id=program_id,
        user_id=user_id,
        ticket_category_id=ticket_category_id,
        ticket_count=ticket_count,
        ticket_user_ids=[ticket_users[0]["id"]]
    )
    return result
```
