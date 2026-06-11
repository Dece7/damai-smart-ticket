<script setup lang="ts">
import { ref } from 'vue'
import { marked } from 'marked'
import ReasoningTimeline from './ReasoningTimeline.vue'
import SourceCard from './SourceCard.vue'
import type { Message } from '../api/conversation'

defineProps<{
  message: Message & { _showSteps?: boolean; _showSources?: boolean }
}>()

const showStats = ref(false)

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

      <!-- 用户消息：纯文本，不走 Markdown -->
      <div
        v-if="message.role === 'user' && message.content"
        class="msg-bubble user-bubble"
      >{{ message.content }}</div>

      <!-- AI 消息：Markdown 渲染 -->
      <div
        v-if="message.role === 'assistant' && message.content"
        class="msg-bubble assistant-bubble md-content"
        v-html="renderMd(message.content)"
      />

      <!-- Token 统计（点击展开） -->
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
  background: linear-gradient(135deg, #e94560, #ff6b6b);
  color: #fff;
}

.msg-row.assistant .msg-avatar {
  background: linear-gradient(135deg, #0f3460, #16213e);
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
}

/* 用户气泡：柔和浅色 */
.user-bubble {
  white-space: pre-wrap;
  background: linear-gradient(135deg, #fef2f2, #fce7f3);
  color: #1a1a2e;
  border: 1px solid #fecaca;
  border-bottom-right-radius: 4px;
}

/* AI 气泡：白底 + 左侧蓝色标识 */
.assistant-bubble {
  background: #fff;
  color: #1a1a2e;
  border-bottom-left-radius: 4px;
  border-left: 3px solid #3b82f6;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.error-card {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 10px;
  padding: 10px 14px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #991b1b;
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
  color: #94a3b8;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.15s;
}

.stats-toggle:hover {
  background: #f1f5f9;
  color: #64748b;
}

.token-stats {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 3px 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 11px;
  color: #64748b;
}

.token-stats .label {
  color: #94a3b8;
}

.token-stats .value {
  color: #475569;
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
