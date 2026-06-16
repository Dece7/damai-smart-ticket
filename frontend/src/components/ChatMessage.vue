<script setup lang="ts">
import { ref } from 'vue'
import { marked } from 'marked'
import { ElMessage } from 'element-plus'
import ReasoningTimeline from './ReasoningTimeline.vue'
import SourceCard from './SourceCard.vue'
import type { Message } from '../api/conversation'

const props = defineProps<{
  message: Message & { _showSteps?: boolean; _showSources?: boolean }
}>()

const emit = defineEmits<{
  regenerate: []
}>()

const showStats = ref(false)
const copied = ref(false)

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

async function copyContent() {
  const text = props.message.content || ''
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    ElMessage.success('已复制')
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    copied.value = true
    ElMessage.success('已复制')
    setTimeout(() => { copied.value = false }, 2000)
  }
}

function handleRegenerate() {
  emit('regenerate')
}
</script>

<template>
  <div :class="['msg-row', message.role]">
    <div class="msg-avatar">
      {{ message.role === 'user' ? '我' : 'AI' }}
    </div>
    <div class="msg-body">
      <!-- 推理过程 -->
      <ReasoningTimeline
        v-if="message.steps?.length"
        :steps="message.steps"
      />

      <!-- 参考来源 -->
      <SourceCard
        v-if="message.sources?.length"
        :sources="message.sources"
      />

      <!-- 错误 -->
      <div v-if="message.error" class="error-card">
        {{ message.error }}
      </div>

      <!-- 用户消息 -->
      <div
        v-if="message.role === 'user' && message.content"
        class="msg-bubble user-bubble"
      >{{ message.content }}
        <div class="msg-actions">
          <button class="msg-action-btn" @click="copyContent" title="复制">
            <svg v-if="!copied" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- AI 消息 -->
      <div
        v-if="message.role === 'assistant' && message.content"
        class="msg-bubble assistant-bubble md-content"
      >
        <div v-html="renderMd(message.content)" />
        <div class="msg-actions">
          <button class="msg-action-btn" @click="copyContent" title="复制">
            <svg v-if="!copied" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </button>
          <button class="msg-action-btn" @click="handleRegenerate" title="重新生成">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Token 统计 -->
      <div v-if="message.token_usage" class="token-stats-wrap">
        <span class="stats-toggle" @click="showStats = !showStats">
          {{ showStats ? '收起' : 'Token' }}
        </span>
        <transition name="fade">
          <span v-if="showStats" class="token-stats">
            <span><span class="label">输入</span> <span class="value">{{ message.token_usage.prompt_tokens }}</span></span>
            <span><span class="label">输出</span> <span class="value">{{ message.token_usage.completion_tokens }}</span></span>
            <span><span class="label">合计</span> <span class="value">{{ message.token_usage.total_tokens }}</span></span>
          </span>
        </transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.msg-row {
  display: flex;
  margin-bottom: 20px;
  gap: 12px;
}

.msg-row.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.msg-row.user .msg-avatar {
  background: var(--color-accent);
  color: #fff;
}

.msg-row.assistant .msg-avatar {
  background: var(--color-primary);
  color: #fff;
}

.msg-body {
  max-width: 70%;
  min-width: 60px;
}

.msg-bubble {
  padding: 12px 16px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
  position: relative;
}

/* 用户气泡 */
.user-bubble {
  white-space: pre-wrap;
  background: var(--bg-bubble-user);
  color: var(--text-primary);
  border: 1px solid var(--border-bubble-user);
  border-bottom-right-radius: 4px;
}

/* AI 气泡 */
.assistant-bubble {
  background: var(--bg-bubble-ai);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
  border-left: 3px solid var(--border-bubble-ai);
  box-shadow: var(--shadow-sm);
}

/* 消息操作按钮 */
.msg-actions {
  display: none;
  position: absolute;
  bottom: -28px;
  gap: 2px;
  background: var(--bg-card, #fff);
  border: 1px solid var(--border-default, #e5e7eb);
  border-radius: 6px;
  padding: 2px;
  box-shadow: var(--shadow-sm);
  z-index: 10;
}

.msg-row.user .msg-actions {
  right: 0;
}

.msg-row.assistant .msg-actions {
  left: 0;
}

.msg-bubble:hover .msg-actions {
  display: flex;
}

.msg-action-btn {
  width: 26px;
  height: 26px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: var(--text-secondary, #6b7280);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.msg-action-btn:hover {
  background: var(--bg-hover, #f3f4f6);
  color: var(--text-primary, #1a1a2e);
}

.error-card {
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  border-radius: 10px;
  padding: 10px 14px;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--error-text);
  transition: box-shadow 0.2s;
}

.error-card:hover {
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.15);
}

/* Token 统计 */
.token-stats-wrap {
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.stats-toggle {
  font-size: 11px;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.15s;
}

.stats-toggle:hover {
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.token-stats {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 3px 10px;
  background: var(--stats-bg);
  border: 1px solid var(--stats-border);
  border-radius: 8px;
  font-size: 11px;
  color: var(--stats-text);
}

.token-stats .label {
  color: var(--text-muted);
}

.token-stats .value {
  color: var(--text-secondary);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
