<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'
import ChatMessage from '../components/ChatMessage.vue'
import ReasoningTimeline from '../components/ReasoningTimeline.vue'
import { marked } from 'marked'
import type { ChatMode } from '../api/chat'

const router = useRouter()
const store = useChatStore()

const input = ref('')
const msgBox = ref<HTMLElement>()
const sidebar = ref<HTMLElement>()
const renamingId = ref<number | null>(null)
const renameInput = ref<HTMLInputElement>()
const sidebarOpen = ref(true)
const isMobile = ref(false)
const showAllHints = ref(false)

// 模式标签
const modeLabels: Record<ChatMode, string> = {
  agent: 'Agent 智能模式',
  multi: '多 Agent 协作',
  assistant: '贴心助手',
  rag: '规则助手',
}

const modeOptions: { value: ChatMode; label: string }[] = [
  { value: 'agent', label: 'Agent' },
  { value: 'multi', label: '多Agent' },
  { value: 'assistant', label: '贴心助手' },
  { value: 'rag', label: '规则助手' },
]

// 快捷问题
const allHints = [
  { icon: ' ', text: '北京有什么演唱会' },
  { icon: ' ', text: '帮我买周杰伦演唱会的票' },
  { icon: ' ', text: '怎么退票？退票后多久退款？' },
  { icon: ' ', text: '怎么选座位？两个人可以选相邻的吗？' },
  { icon: ' ', text: '支持哪些支付方式？可以开发票吗？' },
  { icon: ' ', text: '会员有什么等级和折扣？积分怎么获得？' },
  { icon: ' ', text: '有什么优惠活动？早鸟票是什么？' },
  { icon: ' ️', text: '北京和上海有哪些演出场馆？' },
  { icon: ' ', text: '入场需要带什么证件？可以带相机吗？' },
  { icon: '♿', text: '轮椅用户怎么买票？有无障碍设施吗？' },
  { icon: ' ', text: '儿童需要买票吗？婴儿可以带入场吗？' },
  { icon: ' ', text: '演出取消或延期了怎么办？' },
  { icon: ' ', text: '电子票怎么使用？票丢了怎么办？' },
]

const hints = computed(() =>
  showAllHints.value ? allHints : allHints.slice(0, 6),
)

function scrollBottom() {
  nextTick(() => {
    if (msgBox.value) {
      msgBox.value.scrollTop = msgBox.value.scrollHeight
    }
  })
}

function renderMd(text: string): string {
  if (!text) return ''
  try {
    let html = marked.parse(text) as string
    if (html.startsWith('<p>') && html.endsWith('</p>\n')) {
      html = html.slice(3, -5)
    } else if (html.startsWith('<p>') && html.endsWith('</p>')) {
      html = html.slice(3, -4)
    }
    return html
  } catch {
    return text
  }
}

async function handleSend() {
  const text = input.value.trim()
  if (!text || store.loading) return
  input.value = ''
  await store.send(text)
  scrollBottom()
}

function quickSend(text: string) {
  input.value = text
  handleSend()
}

function switchMode(m: ChatMode) {
  store.mode = m
  ElMessage.success(`已切换至「${modeLabels[m]}」`)
}

async function handleSwitchChat(id: number) {
  await store.switchChat(id)
  scrollBottom()
  if (isMobile.value) sidebarOpen.value = false
}

function startRename(c: { id: number; title: string }) {
  renamingId.value = c.id
  nextTick(() => {
    renameInput.value?.focus()
  })
}

async function confirmRename(id: number, e: Event) {
  const title = (e.target as HTMLInputElement).value.trim()
  if (title) {
    await store.renameConversation(id, title)
  }
  renamingId.value = null
}

async function handleTogglePin(id: number) {
  const pinned = await store.pinConversation(id)
  ElMessage.success(pinned ? '已置顶' : '已取消置顶')
}

async function handleDelete(id: number) {
  await store.removeConversation(id)
  ElMessage.success('已删除对话')
}

// 侧边栏拖拽
function startResize(e: MouseEvent) {
  e.preventDefault()
  const handle = e.target as HTMLElement
  handle.classList.add('active')
  const startX = e.clientX
  const startWidth = sidebar.value!.offsetWidth

  const onMove = (ev: MouseEvent) => {
    const newWidth = Math.min(500, Math.max(180, startWidth + ev.clientX - startX))
    sidebar.value!.style.width = newWidth + 'px'
    localStorage.setItem('sidebar-width', String(newWidth))
  }
  const onUp = () => {
    handle.classList.remove('active')
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

// 响应式
function checkMobile() {
  isMobile.value = window.innerWidth < 768
  if (isMobile.value) sidebarOpen.value = false
}

// 监听消息变化自动滚动
watch(
  () => [store.messages.length, store.streamingText],
  () => scrollBottom(),
)

onMounted(() => {
  store.loadConversations()
  checkMobile()
  window.addEventListener('resize', checkMobile)
  // 恢复侧边栏宽度
  const saved = localStorage.getItem('sidebar-width')
  if (saved && sidebar.value) {
    sidebar.value.style.width = saved + 'px'
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<template>
  <div class="chat-layout">
    <!-- 移动端遮罩 -->
    <div
      v-if="isMobile && sidebarOpen"
      class="sidebar-overlay"
      @click="sidebarOpen = false"
    />

    <!-- 侧边栏 -->
    <aside
      class="sidebar"
      ref="sidebar"
      :class="{ collapsed: !sidebarOpen }"
    >
      <div v-if="!isMobile" class="resize-handle" @mousedown="startResize" />
      <div class="sidebar-header">
        <div class="logo" @click="store.newChat()">
          <div class="logo-icon">麦</div>
          <div>
            <div class="logo-text">大麦智能票务助手</div>
            <div class="logo-sub">AI Customer Service</div>
          </div>
        </div>
        <el-button type="primary" class="new-chat-btn" @click="store.newChat()">
          + 新建对话
        </el-button>
      </div>

      <div class="chat-list">
        <div
          v-for="c in store.conversations"
          :key="c.id"
          :class="['chat-item', { active: c.id === store.currentConvId }]"
          @click="handleSwitchChat(c.id)"
        >
          <span v-if="c.pinned" class="pin-icon">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="#e94560">
              <path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z" />
            </svg>
          </span>
          <input
            v-if="renamingId === c.id"
            class="rename-input"
            :value="c.title"
            @keyup.enter="confirmRename(c.id, $event)"
            @keyup.escape="renamingId = null"
            @blur="renamingId = null"
            ref="renameInput"
            @click.stop
          />
          <span v-else class="item-title">{{ c.title }}</span>
          <div class="item-actions" @click.stop>
            <button
              class="item-action"
              @click="handleTogglePin(c.id)"
              :title="c.pinned ? '取消置顶' : '置顶'"
            >
              <svg v-if="!c.pinned" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 17v5M9 3h6v8l3 3H6l3-3V3z" />
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
            <button class="item-action" @click="startRename(c)" title="重命名">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </button>
            <button class="item-action danger" @click="handleDelete(c.id)" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
              </svg>
            </button>
          </div>
        </div>
        <div v-if="store.conversations.length === 0" class="empty-list">
          暂无对话记录
        </div>
      </div>

      <div class="sidebar-footer">
        <p>Powered by LangChain + LangGraph</p>
      </div>
    </aside>

    <!-- 主区域 -->
    <main class="main">
      <header class="header">
        <button
          v-if="isMobile || !sidebarOpen"
          class="menu-btn"
          @click="sidebarOpen = !sidebarOpen"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <div class="header-title">智能客服</div>
        <div class="mode-tabs">
          <button
            v-for="opt in modeOptions"
            :key="opt.value"
            :class="['mode-tab', { active: store.mode === opt.value }]"
            @click="switchMode(opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
        <el-button
          text
          circle
          @click="router.push('/knowledge')"
          title="知识库管理"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
          </svg>
        </el-button>
        <el-button
          text
          circle
          @click="router.push('/admin')"
          title="管理后台"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 20V10M18 20V4M6 20v-4" />
          </svg>
        </el-button>
      </header>

      <!-- 消息区 -->
      <div class="messages" ref="msgBox">
        <!-- 欢迎页 -->
        <div v-if="store.messages.length === 0 && !store.loading" class="welcome">
          <div class="welcome-icon"> </div>
          <h2>你好，我是麦小蜜</h2>
          <p>我可以帮你查询演出信息、购买门票、解答退票政策等问题。试试下面的问题吧：</p>
          <div class="welcome-hints">
            <div
              v-for="h in hints"
              :key="h.text"
              class="hint-chip"
              @click="quickSend(h.text)"
            >
              {{ h.icon }} {{ h.text }}
            </div>
            <div
              v-if="!showAllHints && allHints.length > 6"
              class="hint-chip more"
              @click="showAllHints = true"
            >
              更多问题...
            </div>
          </div>
        </div>

        <!-- 消息列表（带入场动画） -->
        <transition-group name="msg">
          <ChatMessage
            v-for="(m, i) in store.messages"
            :key="i"
            :message="m"
          />
        </transition-group>

        <!-- 流式输出中 -->
        <div v-if="store.loading" class="msg-row assistant streaming-row">
          <div class="msg-avatar">AI</div>
          <div class="msg-body">
            <ReasoningTimeline
              v-if="store.currentSteps.length"
              :steps="store.currentSteps"
              :streaming="true"
            />
            <div class="msg-bubble assistant-bubble md-content">
              <span v-html="renderMd(store.streamingText)" /><span class="streaming-cursor" />
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="input-box">
          <el-input
            v-model="input"
            @keyup.enter="handleSend"
            placeholder="输入你的问题..."
            :disabled="store.loading"
            size="large"
          >
            <template #append>
              <el-button
                @click="handleSend"
                :disabled="store.loading || !input.trim()"
                type="primary"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </el-button>
            </template>
          </el-input>
        </div>
        <div class="input-hint">
          按 Enter 发送 · 当前模式：{{ modeLabels[store.mode] }}
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  position: relative;
}

/* ===== 移动端遮罩 ===== */
.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 99;
}

/* ===== 侧边栏 ===== */
.sidebar {
  width: 280px;
  min-width: 180px;
  max-width: 500px;
  background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: relative;
  transition: transform 0.3s ease;
}

.sidebar.collapsed {
  transform: translateX(-100%);
  position: absolute;
  z-index: 100;
  height: 100%;
}

.resize-handle {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 5px;
  cursor: col-resize;
  z-index: 10;
  transition: background 0.15s;
}

.resize-handle:hover,
.resize-handle:global(.active) {
  background: rgba(233, 69, 96, 0.5);
}

.sidebar-header {
  padding: 24px 20px 16px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  cursor: pointer;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #e94560, #ff6b6b);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.logo-text {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
}

.logo-sub {
  font-size: 11px;
  color: #8892b0;
  margin-top: 2px;
}

.new-chat-btn {
  width: 100%;
}

.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.chat-list::-webkit-scrollbar {
  width: 4px;
}

.chat-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
}

.chat-item {
  padding: 10px 14px;
  border-radius: 10px;
  cursor: pointer;
  margin-bottom: 4px;
  font-size: 13px;
  color: #8892b0;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: background 0.15s;
  position: relative;
}

.chat-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #ccd6f6;
}

.chat-item.active {
  background: rgba(233, 69, 96, 0.12);
  color: #e94560;
  font-weight: 500;
}

.pin-icon {
  flex-shrink: 0;
  width: 14px;
}

.item-title {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-actions {
  display: none;
  gap: 1px;
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(22, 33, 62, 0.95);
  border-radius: 6px;
  padding: 2px;
}

.chat-item:hover .item-actions {
  display: flex;
}

.item-action {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #8892b0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.item-action:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.item-action.danger:hover {
  background: rgba(233, 69, 96, 0.2);
  color: #e94560;
}

.rename-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(233, 69, 96, 0.4);
  border-radius: 6px;
  padding: 2px 6px;
  font-size: 13px;
  color: #fff;
  outline: none;
  min-width: 0;
}

.empty-list {
  text-align: center;
  color: #4a5568;
  font-size: 12px;
  padding: 20px;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.sidebar-footer p {
  font-size: 11px;
  color: #4a5568;
  text-align: center;
}

/* ===== 主区域 ===== */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.header {
  padding: 16px 28px;
  background: #fff;
  border-bottom: 1px solid #e8ecf0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.15s;
}

.menu-btn:hover {
  background: #f3f4f6;
  color: #e94560;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
}

.mode-tabs {
  display: flex;
  gap: 6px;
  margin-left: auto;
  background: #f5f7fa;
  padding: 4px;
  border-radius: 10px;
}

.mode-tab {
  padding: 7px 18px;
  border-radius: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
  transition: all 0.2s;
}

.mode-tab:hover {
  color: #374151;
}

.mode-tab.active {
  background: #fff;
  color: #e94560;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* ===== 消息区 ===== */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 28px 32px;
}

.welcome {
  text-align: center;
  padding: 80px 40px 40px;
}

.welcome-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.welcome h2 {
  font-size: 22px;
  font-weight: 600;
  color: #1a1a2e;
  margin-bottom: 8px;
}

.welcome p {
  font-size: 14px;
  color: #6b7280;
  line-height: 1.6;
  max-width: 400px;
  margin: 0 auto;
}

.welcome-hints {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 24px;
  flex-wrap: wrap;
}

.hint-chip {
  padding: 8px 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  transition: all 0.15s;
}

.hint-chip:hover {
  border-color: #e94560;
  color: #e94560;
  background: #fef2f2;
}

.hint-chip.more {
  color: #9ca3af;
  border-style: dashed;
}

.hint-chip.more:hover {
  color: #e94560;
  border-color: #e94560;
  background: #fef2f2;
}

.streaming-row {
  display: flex;
  margin-bottom: 20px;
  gap: 12px;
}

.streaming-row .msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
  background: linear-gradient(135deg, #0f3460, #16213e);
  color: #fff;
}

.streaming-row .msg-body {
  max-width: 70%;
  min-width: 60px;
}

.streaming-row .msg-bubble {
  padding: 12px 16px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
  background: #fff;
  color: #1a1a2e;
  border-bottom-left-radius: 4px;
  border-left: 3px solid #3b82f6;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

/* ===== 输入区 ===== */
.input-area {
  padding: 16px 28px 20px;
  background: #fff;
  border-top: 1px solid #e8ecf0;
  padding-bottom: calc(20px + env(safe-area-inset-bottom, 0px));
}

.input-box :deep(.el-input__wrapper) {
  border-radius: 14px;
  padding: 6px 6px 6px 18px;
}

.input-box :deep(.el-input-group__append) {
  border-radius: 14px;
  padding: 0;
}

.input-box :deep(.el-input-group__append .el-button) {
  border-radius: 14px;
  margin: 0;
  height: 40px;
  width: 50px;
}

.input-hint {
  text-align: center;
  margin-top: 8px;
  font-size: 11px;
  color: #9ca3af;
}

/* ===== 移动端适配 ===== */
@media (max-width: 767px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    width: 280px;
    max-width: 80vw;
  }

  .sidebar.collapsed {
    transform: translateX(-100%);
  }

  .messages {
    padding: 16px;
  }

  .header {
    padding: 12px 16px;
  }

  .mode-tab {
    padding: 6px 12px;
    font-size: 12px;
  }

  .input-area {
    padding: 12px 16px 16px;
  }

  .msg-body {
    max-width: 85%;
  }

  .welcome {
    padding: 40px 20px;
  }

  .welcome-icon {
    font-size: 36px;
  }

  .welcome h2 {
    font-size: 18px;
  }
}
</style>
