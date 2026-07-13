import type { Source, Step, TokenUsage } from './conversation'

export type ChatMode = 'agent' | 'multi' | 'assistant' | 'rag' | 'router-skill'

export interface StreamCallbacks {
  onConversationId?: (id: number) => void
  onStep?: (step: Step) => void
  onSources?: (sources: Source[]) => void
  onToken?: (text: string) => void
  onUsage?: (usage: TokenUsage) => void
  onError?: (error: string) => void
  onDone?: () => void
}

/**
 * 发送消息（SSE 流式）
 */
export async function sendMessage(
  mode: ChatMode,
  message: string,
  conversationId: number | null,
  callbacks: StreamCallbacks,
) {
  let url: string
  if (mode === 'agent') url = '/api/agent'
  else if (mode === 'multi') url = '/api/agent/multi'
  else if (mode === 'router-skill') url = '/api/router-skill'
  else url = '/api/chat'
  const body: Record<string, unknown> = {
    message,
    conversation_id: conversationId ? String(conversationId) : null,
  }
  if (mode !== 'agent') {
    body.chat_type = mode
  }

  // 获取Token
  const token = localStorage.getItem('damai_token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const resp = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })

  // 安全拦截
  if (resp.status === 400) {
    const err = await resp.json()
    callbacks.onError?.(err.detail || '输入被拒绝')
    callbacks.onDone?.()
    return
  }

  if (!resp.ok) {
    callbacks.onError?.(`请求失败: ${resp.status}`)
    callbacks.onDone?.()
    return
  }

  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()!

    for (const line of lines) {
      if (!line.startsWith('data: ') || line === 'data: [DONE]') continue
      try {
        const d = JSON.parse(line.slice(6))
        if (d.type === 'conversation_id') {
          callbacks.onConversationId?.(d.content)
        } else if (d.type === 'step') {
          callbacks.onStep?.(d)
        } else if (d.type === 'sources') {
          callbacks.onSources?.(d.content)
        } else if (d.type === 'token') {
          callbacks.onToken?.(d.content)
        } else if (d.type === 'usage') {
          callbacks.onUsage?.(d.content)
        }
      } catch {
        // ignore parse errors
      }
    }
  }

  callbacks.onDone?.()
}


