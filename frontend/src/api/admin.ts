import api from './index'

export interface StatsSummary {
  total_conversations: number
  total_messages: number
  total_tokens: number
  avg_tokens: number
}

export interface TrendItem {
  date: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface ModeItem {
  chat_type: string
  total_tokens: number
  message_count: number
}

/** 总览统计 */
export async function getStatsSummary(): Promise<StatsSummary> {
  const { data } = await api.get('/admin/stats/summary')
  return data
}

/** 每日趋势 */
export async function getStatsTrend(days = 30): Promise<TrendItem[]> {
  const { data } = await api.get('/admin/stats/trend', { params: { days } })
  return data
}

/** 模式用量 */
export async function getStatsByMode(): Promise<ModeItem[]> {
  const { data } = await api.get('/admin/stats/by_mode')
  return data
}
