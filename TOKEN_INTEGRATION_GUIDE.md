# AI项目与全栈项目Token整合方案

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    用户操作流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 用户访问全栈项目 (localhost:5173)                       │
│     └→ 登录 → Token存入Cookie (Admin-Token)                │
│                                                             │
│  2. 用户点击"AI客服"按钮                                    │
│     └→ 获取Token → 拼接到URL                               │
│     └→ 跳转: http://localhost:8000?token=eyJhbGci...      │
│                                                             │
│  3. AI项目加载 (localhost:8000)                             │
│     └→ 从URL提取Token → 存入localStorage                   │
│                                                             │
│  4. 用户在AI项目提问                                        │
│     └→ AI项目调用全栈API时携带Token                         │
│     └→ 全栈API验证Token → 返回用户相关数据                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 需要修改的文件

### 全栈项目 (D:\damai\vue3)

| 文件 | 修改内容 |
|------|----------|
| src/components/header/index.vue | 添加"AI客服"按钮和openAIChat函数 |

### AI项目 (D:\ClaudeCodeProjects\CCAIAgent\damai-smart-ticket)

| 文件 | 修改内容 |
|------|----------|
| frontend/src/views/ChatView.vue | 在onMounted中接收Token |
| frontend/src/api/chat.ts | 调用API时携带Token |
| app/utils/java_api_client.py | 调用Java API时携带Token |
| app/api/agent.py | 从请求头提取Token并传递 |

## 实现步骤

### 步骤1: 全栈项目前端修改

在 header/index.vue 中添加：

```vue
<template>
  <!-- 在 loginInfo 列表中添加 -->
  <li @click="openAIChat" v-if="isHasToken">
    <span class="aiChat">AI客服</span>
  </li>
</template>

<script setup>
import { getToken } from "../../utils/auth"

function openAIChat() {
  const token = getToken()
  if (token) {
    window.open(`http://localhost:8000?token=${token}`)
  }
}
</script>

<style scoped>
.aiChat {
  cursor: pointer;
  color: #409eff;
}
.aiChat:hover {
  color: #66b1ff;
}
</style>
```

### 步骤2: AI项目前端修改

在 ChatView.vue 的 onMounted 中添加：

```typescript
onMounted(() => {
  // 从URL参数中获取Token
  const urlParams = new URLSearchParams(window.location.search)
  const token = urlParams.get('token')
  
  if (token) {
    localStorage.setItem('damai_token', token)
    
    // 清除URL中的token参数
    const url = new URL(window.location.href)
    url.searchParams.delete('token')
    window.history.replaceState({}, '', url.toString())
  }
})
```

### 步骤3: AI项目后端修改

在 app/api/agent.py 中添加Token传递：

```python
@router.post("/agent")
async def agent_chat(request: Request):
    # 从请求头获取Token
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    # 设置Token到Java API客户端
    java_api.set_token(token)
    
    # 后续调用会携带Token
    ...
```

## 功能实现对照表

| 功能 | 需要Token | 实现状态 |
|------|----------|----------|
| 搜索节目 | ❌ | ✅ 已实现 |
| 节目详情 | ❌ | ✅ 已实现 |
| 票档查询 | ❌ | ✅ 已实现 |
| 推荐列表 | ❌ | ✅ 已实现 |
| 创建订单 | ✅ | ⏳ 待实现 |
| 查询订单 | ✅ | ⏳ 待实现 |
| 订单支付 | ✅ | ⏳ 待实现 |

## 测试验证

### 测试步骤

1. 启动全栈项目 (localhost:5173)
2. 启动AI项目 (localhost:8000)
3. 在全栈项目登录
4. 点击"AI客服"按钮
5. 验证Token是否传递成功
6. 在AI项目测试"查询我的订单"

### 预期结果

- Token正确传递到AI项目
- AI项目可以调用需要认证的API
- 用户可以查询自己的订单
