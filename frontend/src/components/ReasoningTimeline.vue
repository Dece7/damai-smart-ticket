<script setup lang="ts">
import { ref } from 'vue'
import type { Step } from '../api/conversation'

const props = defineProps<{
  steps: Step[]
  streaming?: boolean
}>()

const show = ref(false)
</script>

<template>
  <div class="reasoning-timeline">
    <div class="timeline-toggle" @click="show = !show">
      <span class="arrow" :class="{ open: show }">▶</span>
      <span v-if="streaming">推理中...</span>
      <span v-else>推理过程 ({{ steps.length }} 步)</span>
    </div>
    <transition name="fade">
      <div v-if="show" class="timeline-content">
        <div
          v-for="(s, i) in steps"
          :key="i"
          :class="['step-item', s.action]"
        >
          <span class="step-dot" />
          <span class="step-text">{{ s.content }}</span>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.reasoning-timeline {
  margin-bottom: 8px;
  border-left: 2px solid #e5e7eb;
  padding-left: 14px;
}

.timeline-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #6b7280;
  cursor: pointer;
  margin-bottom: 6px;
  user-select: none;
}

.timeline-toggle:hover {
  color: #374151;
}

.arrow {
  transition: transform 0.2s;
  font-size: 10px;
}

.arrow.open {
  transform: rotate(90deg);
}

.timeline-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.step-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  color: #6b7280;
  position: relative;
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 2px solid #d1d5db;
  background: #fff;
  flex-shrink: 0;
  margin-top: 2px;
}

.step-item.reasoning .step-dot {
  border-color: #f59e0b;
  background: #fef3c7;
}

.step-item.tool_start .step-dot {
  border-color: #3b82f6;
  background: #dbeafe;
}

.step-item.tool_end .step-dot {
  border-color: #22c55e;
  background: #dcfce7;
}

.step-text {
  flex: 1;
  word-break: break-word;
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
