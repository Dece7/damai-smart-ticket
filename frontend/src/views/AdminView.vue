<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getStatsSummary, getStatsTrend, getStatsByMode } from '../api/admin'
import type { StatsSummary, TrendItem, ModeItem } from '../api/admin'

const router = useRouter()
const loading = ref(true)
const summary = ref<StatsSummary>({
  total_conversations: 0,
  total_messages: 0,
  total_tokens: 0,
  avg_tokens: 0,
})
const trendChart = ref<HTMLElement>()
const modeChart = ref<HTMLElement>()
let trendInstance: echarts.ECharts | null = null
let modeInstance: echarts.ECharts | null = null

const modeLabels: Record<string, string> = {
  assistant: '贴心助手',
  rag: '规则助手',
  agent: 'Agent',
}

const modeColors: Record<string, string> = {
  assistant: '#e94560',
  rag: '#22c55e',
  agent: '#3b82f6',
}

function formatNum(n: number): string {
  return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n)
}

function renderTrendChart(data: TrendItem[]) {
  if (!trendChart.value || !data.length) return
  trendInstance = echarts.init(trendChart.value)
  trendInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, itemWidth: 12, itemGap: 16 },
    grid: { left: 50, right: 20, top: 20, bottom: 50 },
    xAxis: {
      type: 'category',
      data: data.map((d) => d.date.slice(5)),
      axisTick: { show: false },
    },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f4f6' } } },
    series: [
      {
        name: '输入 Token',
        type: 'bar',
        stack: 'total',
        data: data.map((d) => d.prompt_tokens),
        itemStyle: { color: '#f59e0b', borderRadius: [3, 3, 0, 0] },
        barWidth: '45%',
      },
      {
        name: '输出 Token',
        type: 'bar',
        stack: 'total',
        data: data.map((d) => d.completion_tokens),
        itemStyle: { color: '#06b6d4', borderRadius: [3, 3, 0, 0] },
      },
    ],
  })
}

function renderModeChart(data: ModeItem[]) {
  if (!modeChart.value || !data.length) return
  modeInstance = echarts.init(modeChart.value)
  modeInstance.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, itemWidth: 12, itemGap: 16 },
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '45%'],
        data: data.map((m) => ({
          name: modeLabels[m.chat_type] || m.chat_type,
          value: m.total_tokens,
          itemStyle: { color: modeColors[m.chat_type] || '#94a3b8' },
        })),
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 600 } },
        itemStyle: {
          borderWidth: 2,
          borderColor: '#fff',
        },
      },
    ],
  })
}

function handleResize() {
  trendInstance?.resize()
  modeInstance?.resize()
}

onMounted(async () => {
  const [s, t, m] = await Promise.all([
    getStatsSummary(),
    getStatsTrend(30),
    getStatsByMode(),
  ])
  summary.value = s
  loading.value = false
  await nextTick()
  renderTrendChart(t)
  renderModeChart(m)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendInstance?.dispose()
  modeInstance?.dispose()
})
</script>

<template>
  <div class="admin-page">
    <nav class="page-nav">
      <button class="nav-back" @click="router.push('/')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        返回对话
      </button>
      <span class="nav-title">管理后台</span>
    </nav>

    <div class="container">
      <!-- 统计卡片 -->
      <div class="cards">
        <el-card shadow="hover" class="stat-card blue">
          <el-skeleton :rows="1" animated :loading="loading">
            <template #default>
              <div class="card-label">总对话数</div>
              <div class="card-value">{{ summary.total_conversations }}</div>
            </template>
          </el-skeleton>
        </el-card>
        <el-card shadow="hover" class="stat-card purple">
          <el-skeleton :rows="1" animated :loading="loading">
            <template #default>
              <div class="card-label">总消息数</div>
              <div class="card-value">{{ summary.total_messages }}</div>
            </template>
          </el-skeleton>
        </el-card>
        <el-card shadow="hover" class="stat-card red">
          <el-skeleton :rows="1" animated :loading="loading">
            <template #default>
              <div class="card-label">总 Token</div>
              <div class="card-value accent">{{ formatNum(summary.total_tokens) }}</div>
            </template>
          </el-skeleton>
        </el-card>
        <el-card shadow="hover" class="stat-card cyan">
          <el-skeleton :rows="1" animated :loading="loading">
            <template #default>
              <div class="card-label">平均 Token / 消息</div>
              <div class="card-value">{{ formatNum(summary.avg_tokens) }}</div>
            </template>
          </el-skeleton>
        </el-card>
      </div>

      <el-empty v-if="!loading && summary.total_messages === 0" description="暂无统计数据，请先发送一些对话" />

      <div v-if="summary.total_messages > 0" class="charts">
        <el-card shadow="hover" class="chart-box">
          <template #header>
            <span class="chart-title">每日 Token 消耗趋势</span>
          </template>
          <div ref="trendChart" class="chart-canvas" />
        </el-card>
        <el-card shadow="hover" class="chart-box">
          <template #header>
            <span class="chart-title">模式用量对比</span>
          </template>
          <div ref="modeChart" class="chart-canvas" />
        </el-card>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-page {
  min-height: 100vh;
  background: #f0f2f5;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

.stat-card {
  border-left: 3px solid transparent;
}

.stat-card.blue {
  border-left-color: #3b82f6;
}

.stat-card.purple {
  border-left-color: #8b5cf6;
}

.stat-card.red {
  border-left-color: #e94560;
}

.stat-card.cyan {
  border-left-color: #06b6d4;
}

.card-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.card-value {
  font-size: 28px;
  font-weight: 700;
  color: #1a1a2e;
  font-variant-numeric: tabular-nums;
}

.card-value.accent {
  color: #e94560;
}

.charts {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 20px;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a2e;
}

.chart-canvas {
  width: 100%;
  min-height: 320px;
  height: 320px;
}

@media (max-width: 768px) {
  .cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts {
    grid-template-columns: 1fr;
  }
}
</style>
