<script setup lang="ts">
import { ref } from 'vue'
import type { Source } from '../api/conversation'

defineProps<{
  sources: Source[]
}>()

const show = ref(false)
const openItems = ref<Set<number>>(new Set())

function toggleItem(index: number) {
  if (openItems.value.has(index)) {
    openItems.value.delete(index)
  } else {
    openItems.value.add(index)
  }
}
</script>

<template>
  <div class="sources-card">
    <div class="sources-title" @click="show = !show">
      <span class="arrow" :class="{ open: show }">▶</span>
       参考来源 ({{ sources.length }})
    </div>
    <transition name="fade">
      <div v-if="show" class="sources-list">
        <div v-for="(s, i) in sources" :key="i" class="source-item">
          <div class="source-header">
            <span class="source-name">{{ s.doc }}</span>
            <span class="source-toggle" @click="toggleItem(i)">
              {{ openItems.has(i) ? '收起' : '详情' }}
            </span>
          </div>
          <div v-if="openItems.has(i)" class="source-excerpt">
            {{ s.excerpt }}
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.sources-card {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 10px;
  padding: 8px 12px;
  margin-bottom: 8px;
  font-size: 12px;
  color: #166534;
}

.sources-title {
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}

.arrow {
  transition: transform 0.2s;
  font-size: 10px;
}

.arrow.open {
  transform: rotate(90deg);
}

.sources-list {
  margin-top: 6px;
}

.source-item {
  padding: 4px 0;
  border-top: 1px solid #d1fae5;
}

.source-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.source-name {
  font-weight: 600;
  color: #15803d;
}

.source-toggle {
  color: #22c55e;
  cursor: pointer;
  font-size: 11px;
}

.source-excerpt {
  margin-top: 4px;
  color: #166534;
  font-size: 11px;
  line-height: 1.5;
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
