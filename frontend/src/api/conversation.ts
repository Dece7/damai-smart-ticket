import api from './index'

export interface Conversation {
  id: number
  title: string
  chat_type: string
  pinned: boolean
  created_at: string
}

export interface Message {
  id?: number
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  steps?: Step[]
  token_usage?: TokenUsage
  error?: string
}

export interface Source {
  doc: string
  excerpt: string
}

export interface Step {
  step: number
  action: 'reasoning' | 'tool_start' | 'tool_end' | 'node_enter'
  content: string
  tool?: string
}

export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

/** 获取对话列表 */
export async function getConversations(): Promise<Conversation[]> {
  const { data } = await api.get('/conversations')
  return data
}

/** 获取对话消息 */
export async function getMessages(conversationId: number): Promise<Message[]> {
  const { data } = await api.get(`/conversations/${conversationId}/messages`)
  return data
}

/** 删除对话 */
export async function deleteConversation(conversationId: number) {
  await api.delete(`/conversations/${conversationId}`)
}

/** 更新标题 */
export async function updateTitle(conversationId: number, title: string) {
  await api.put(`/conversations/${conversationId}/title`, { title })
}

/** 切换置顶 */
export async function togglePin(conversationId: number) {
  const { data } = await api.post(`/conversations/${conversationId}/pin`)
  return data
}

/** 生成标题 */
export async function generateTitle(conversationId: number) {
  await api.post(`/conversations/${conversationId}/generate-title`)
}
