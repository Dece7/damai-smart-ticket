<script setup lang="ts">
import { ref } from 'vue'
import type { Step } from '../api/conversation'

const props = defineProps<{
  steps: Step[]
  streaming?: boolean
}>()

const show = ref(false)

function parseStep(s: Step) {
  const content = s.content || ''
  const action = s.action || ''

  if (action === 'node_enter') {
    return { icon: '→', label: content, type: 'node' }
  }

  if (action === 'reasoning' || content.includes('选择工具')) {
    const match = content.match(/选择工具:\s*(\w+)\((.*?)\)/)
    if (match) {
      return { icon: ' ', label: `${match[1]}`, detail: match[2], type: 'tool_call' }
    }
    return { icon: ' ', label: content, type: 'reasoning' }
  }

  if (action === 'tool_start' || content.includes('执行工具') || content.includes('执行:')) {
    const toolName = content.replace(/.*执行工具:\s*/, '').replace(/.*执行:\s*/, '')
    return { icon: '⚙', label: toolName, type: 'tool_exec' }
  }

  if (action === 'tool_end' || content.includes('工具返回')) {
    const preview = content.replace(/^工具返回:\s*/, '').replace(/"/g, '').substring(0, 60)
    return { icon: '←', label: preview + (content.length > 60 ? '...' : ''), type: 'tool_result' }
  }

  if (content.includes('查询改写')) {
    return { icon: ' ', label: content, type: 'rewrite' }
  }

  return { icon: '·', label: content, type: 'default' }
}
</script>

<template>
  <div class="reasoning-timeline">
    <div class="timeline-toggle" @click="show = !show">
      <span class="arrow" :class="{ open: show }">▶</span>
      <span v-if="streaming" class="streaming-indicator">
        <span class="dot-pulse"></span>
        思考中
      </span>
      <span v-else>推理 ({{ steps.length }})</span>
    </div>
    <transition name="fade">
      <div v-if="show" class="timeline-content">
        <div
          v-for="(s, i) in steps"
          :key="i"
          :class="['step-item', parseStep(s).type]"
        >
          <span class="step-icon">{{ parseStep(s).icon }}</span>
          <span class="step-label">{{ parseStep(s).label }}</span>
          <span v-if="parseStep(s).detail" class="step-detail">{{ parseStep(s).detail }}</span>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.reasoning-timeline {
  margin-bottom: 8px;
  background: var(--bg-code, #f8f9fa);
  border: 1px solid var(--border-default, #e5e7eb);
  border-radius: 8px;
  overflow: hidden;
}

.timeline-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  font-size: 11px;
  color: var(--text-muted, #9ca3af);
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.timeline-toggle:hover {
  background: var(--bg-hover, #f0f0f0);
  color: var(--text-secondary, #6b7280);
}

.arrow {
  transition: transform 0.2s;
  font-size: 9px;
  color: var(--text-muted, #9ca3af);
}

.arrow.open {
  transform: rotate(90deg);
}

.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--color-primary, #c2703e);
  font-weight: 500;
}

.dot-pulse {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-primary, #c2703e);
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}

.timeline-content {
  padding: 2px 10px 8px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.step-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 2px 0;
  font-size: 11px;
  line-height: 1.4;
}

.step-icon {
  flex-shrink: 0;
  width: 16px;
  text-align: center;
  font-size: 10px;
  opacity: 0.7;
}

.step-label {
  color: var(--text-muted, #8a8a8a);
  word-break: break-word;
}

.step-detail {
  color: var(--text-muted, #aaa);
  font-size: 10px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  word-break: break-all;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 步骤类型颜色 - 全部用淡色，不抢回答的视觉权重 */
.step-item.node .step-icon { color: #81c784; }
.step-item.reasoning .step-icon,
.step-item.tool_call .step-icon { color: #ffb74d; }
.step-item.tool_exec .step-icon { color: #64b5f6; }
.step-item.tool_result .step-icon { color: #ba68c8; }
.step-item.rewrite .step-icon { color: #f06292; }

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
