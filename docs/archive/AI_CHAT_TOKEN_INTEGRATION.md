# AI项目前端修改方案

## 文件位置
D:\ClaudeCodeProjects\CCAIAgent\damai-smart-ticket\frontend\src\views\ChatView.vue

## 修改内容

### 1. 在 onMounted 中添加 Token 接收逻辑

```typescript
onMounted(() => {
  // 从URL参数中获取Token
  const urlParams = new URLSearchParams(window.location.search)
  const token = urlParams.get('token')
  
  if (token) {
    // 存储Token到localStorage
    localStorage.setItem('damai_token', token)
    console.log('Token已保存')
    
    // 清除URL中的token参数（避免刷新时重复处理）
    const url = new URL(window.location.href)
    url.searchParams.delete('token')
    window.history.replaceState({}, '', url.toString())
  }
})
```

### 2. 修改 API 调用，携带Token

在 api/chat.ts 中添加 Token 请求头：

```typescript
// 获取Token
function getToken(): string | null {
  return localStorage.getItem('damai_token')
}

// 调用Agent API时携带Token
export async function sendMessage(message: string, mode: ChatMode) {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  const response = await fetch('/api/agent', {
    method: 'POST',
    headers,
    body: JSON.stringify({ message, mode })
  })
  
  return response
}
```

### 3. 显示用户登录状态（可选）

在侧边栏或顶部显示用户登录状态：

```vue
<template>
  <div class="user-status" v-if="isLoggedIn">
    <span>已登录</span>
    <button @click="logout">退出</button>
  </div>
</template>

<script setup>
const isLoggedIn = computed(() => !!localStorage.getItem('damai_token'))

function logout() {
  localStorage.removeItem('damai_token')
}
</script>
```
