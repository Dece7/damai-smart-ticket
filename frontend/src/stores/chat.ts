import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Conversation, Message, Source, Step, TokenUsage } from '../api/conversation'
import {
  getConversations,
  getMessages,
  deleteConversation,
  updateTitle,
  togglePin as apiTogglePin,
  generateTitle,
} from '../api/conversation'
import { sendMessage, type ChatMode } from '../api/chat'

export const useChatStore = defineStore('chat', () => {
  // --- State ---
  const conversations = ref<Conversation[]>([])
  const currentConvId = ref<number | null>(null)
  const messages = ref<(Message & { _showSteps?: boolean; _showSources?: boolean })[]>([])
  const loading = ref(false)
  const streamingText = ref('')
  const currentSteps = ref<Step[]>([])
  const streamingSources = ref<Source[]>([])
  const showStreamingSteps = ref(true)
  const mode = ref<ChatMode>('agent')

  // --- Computed ---
  const currentConv = computed(() =>
    conversations.value.find((c) => c.id === currentConvId.value),
  )

  // --- Actions ---
  async function loadConversations() {
    conversations.value = await getConversations()
  }

  async function switchChat(id: number) {
    currentConvId.value = id
    const msgs = await getMessages(id)
    messages.value = msgs.map((m) => ({
      ...m,
      _showSteps: false,
      _showSources: false,
    }))
  }

  function newChat() {
    messages.value = []
    currentConvId.value = null
  }

  async function removeConversation(id: number) {
    await deleteConversation(id)
    if (currentConvId.value === id) {
      messages.value = []
      currentConvId.value = null
    }
    await loadConversations()
  }

  async function renameConversation(id: number, title: string) {
    await updateTitle(id, title)
    await loadConversations()
  }

  async function pinConversation(id: number) {
    const data = await apiTogglePin(id)
    await loadConversations()
    return data.pinned
  }

  async function send(text: string) {
    if (!text.trim() || loading.value) return

    const userMsg = text.trim()
    messages.value.push({ role: 'user', content: userMsg })
    loading.value = true
    streamingText.value = ''
    currentSteps.value = []
    streamingSources.value = []
    showStreamingSteps.value = true

    const isNewChat = !currentConvId.value

    await sendMessage(mode.value, userMsg, currentConvId.value, {
      onConversationId(id) {
        currentConvId.value = id
      },
      onStep(step) {
        currentSteps.value.push(step)
      },
      onSources(sources) {
        const existing = new Set(streamingSources.value.map((s) => s.doc))
        for (const s of sources) {
          if (!existing.has(s.doc)) {
            streamingSources.value.push(s)
            existing.add(s.doc)
          }
        }
      },
      onToken(text) {
        streamingText.value += text
      },
      onUsage(usage) {
        // 保存到当前消息
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.token_usage = usage
        }
      },
      onError(error) {
        messages.value.push({ role: 'assistant', content: '', error })
      },
      onDone() {
        if (streamingText.value || streamingSources.value.length) {
          messages.value.push({
            role: 'assistant',
            content: streamingText.value,
            sources: streamingSources.value.length ? [...streamingSources.value] : undefined,
            steps: currentSteps.value.length ? [...currentSteps.value] : undefined,
            _showSteps: false,
            _showSources: false,
          })
        }
        streamingText.value = ''
        currentSteps.value = []
        streamingSources.value = []
        loading.value = false
        loadConversations()

        // 新对话自动生成标题
        if (isNewChat && currentConvId.value) {
          generateTitle(currentConvId.value).then(() => loadConversations())
        }
      },
    })
  }

  return {
    conversations,
    currentConvId,
    currentConv,
    messages,
    loading,
    streamingText,
    currentSteps,
    streamingSources,
    showStreamingSteps,
    mode,
    loadConversations,
    switchChat,
    newChat,
    removeConversation,
    renameConversation,
    pinConversation,
    send,
  }
})
