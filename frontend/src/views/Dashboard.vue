<template>
  <div class="p-6 space-y-6">
    <h2 class="text-xl font-bold">仪表盘</h2>
    <!-- 统计卡片 -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="card">
        <p class="text-xs text-gray-400">持仓数量</p>
        <p class="stat-value text-sky-400">{{ s.open_trades || 0 }}</p>
      </div>
      <div class="card">
        <p class="text-xs text-gray-400">今日盈亏</p>
        <p class="stat-value" :class="(s.today_pnl||0) >= 0 ? 'text-profit' : 'text-loss'">
          {{ (s.today_pnl||0) >= 0 ? '+' : '' }}${{ (s.today_pnl||0).toFixed(2) }}
        </p>
      </div>
      <div class="card">
        <p class="text-xs text-gray-400">持仓总值</p>
        <p class="stat-value text-blue-400">${{ (s.total_stake||0).toFixed(2) }}</p>
      </div>
      <div class="card">
        <p class="text-xs text-gray-400">候选数量</p>
        <p class="stat-value text-yellow-400">{{ s.candidates_count || 0 }}</p>
      </div>
    </div>
    <!-- 风控摘要 -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="card">
        <p class="text-xs text-gray-400 mb-2">日亏损</p>
        <div class="flex justify-between text-sm mb-1">
          <span>${{ s.daily_loss || 0 }}</span>
          <span class="text-gray-500">/ ${{ s.daily_loss_limit || 100 }}</span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-2">
          <div class="h-2 rounded-full transition-all" :class="lossBarClass" :style="{ width: lossPct + '%' }"></div>
        </div>
      </div>
      <div class="card">
        <p class="text-xs text-gray-400 mb-2">今日开仓</p>
        <div class="flex justify-between text-sm mb-1">
          <span>{{ s.today_trades || 0 }} 笔</span>
          <span class="text-gray-500">/ {{ s.max_daily_trades || 10 }}</span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-2">
          <div class="h-2 rounded-full bg-sky-500 transition-all" :style="{ width: tradePct + '%' }"></div>
        </div>
      </div>
      <div class="card">
        <p class="text-xs text-gray-400 mb-2">连续亏损</p>
        <p class="stat-value" :class="(s.consecutive_losses||0)>0?'text-loss':'text-profit'">
          {{ s.consecutive_losses || 0 }}
        </p>
        <p class="text-xs text-gray-500">暂停阈值: {{ s.max_daily_trades ? 3 : 3 }}</p>
      </div>
    </div>
    <!-- 快捷操作 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-3">快捷操作</h3>
      <div class="flex flex-wrap gap-2">
        <button @click="panicSell" class="btn-danger">紧急全平仓</button>
        <button @click="togglePause" class="btn-ghost">{{ paused ? '恢复交易' : '暂停交易' }}</button>
        <button @click="runOpt" class="btn-ghost">立即优化</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDashboardStore } from '@/stores'
import { tradeApi, riskApi, optimizationApi } from '@/api'

const store = useDashboardStore()
const s = computed(() => store.summary)
const paused = ref(false)

const lossPct = computed(() => Math.min(((s.value.daily_loss||0) / (s.value.daily_loss_limit||100)) * 100, 100))
const tradePct = computed(() => Math.min(((s.value.today_trades||0) / (s.value.max_daily_trades||10)) * 100, 100))
const lossBarClass = computed(() => lossPct.value > 80 ? 'bg-red-500' : lossPct.value > 50 ? 'bg-yellow-500' : 'bg-emerald-500')

async function panicSell() {
  if (!confirm('确定紧急全平仓？')) return
  await tradeApi.panicCloseAll()
  alert('平仓指令已发送')
}
async function togglePause() {
  await riskApi.togglePause({ paused: !paused.value, reason: '手动操作' })
  paused.value = !paused.value
}
async function runOpt() {
  await optimizationApi.run()
  alert('优化任务已启动')
}

onMounted(() => store.fetchSummary())
</script>
