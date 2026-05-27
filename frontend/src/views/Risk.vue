<template>
  <div class="p-6 space-y-4">
    <h2 class="text-xl font-bold">风控状态</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <!-- 日亏损 -->
      <div class="card">
        <p class="text-xs text-gray-400 mb-2">日亏损限制</p>
        <div class="flex justify-between text-sm mb-1">
          <span class="text-loss">${{ r.daily_loss || 0 }}</span>
          <span class="text-gray-500">/ ${{ r.daily_loss_limit || 100 }}</span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-2">
          <div class="h-2 rounded-full transition-all" :class="lossPct>80?'bg-red-500':lossPct>50?'bg-yellow-500':'bg-emerald-500'" :style="{width:lossPct+'%'}"></div>
        </div>
      </div>
      <!-- 今日开仓 -->
      <div class="card">
        <p class="text-xs text-gray-400 mb-2">今日开仓</p>
        <div class="flex justify-between text-sm mb-1">
          <span>{{ r.today_trades || 0 }} 笔</span>
          <span class="text-gray-500">/ {{ r.daily_trades_limit || 10 }}</span>
        </div>
        <div class="flex gap-2 text-xs mt-2">
          <span>空: ≤{{ r.max_daily_trades_short || 6 }}</span>
          <span>多: ≤{{ r.max_daily_trades_long || 4 }}</span>
        </div>
      </div>
      <!-- 连续亏损 -->
      <div class="card">
        <p class="text-xs text-gray-400 mb-2">连续亏损</p>
        <p class="stat-value" :class="(r.consecutive_losses||0)>0?'text-loss':'text-profit'">{{ r.consecutive_losses || 0 }}</p>
        <p class="text-xs text-gray-500">暂停阈值: {{ r.consecutive_loss_limit || 3 }}</p>
      </div>
      <!-- 持仓总额 -->
      <div class="card">
        <p class="text-xs text-gray-400 mb-2">持仓总额</p>
        <div class="flex justify-between text-sm mb-1">
          <span>${{ (r.total_stake||0).toFixed(2) }}</span>
          <span class="text-gray-500">/ ${{ r.max_stake || 100 }}</span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-2">
          <div class="h-2 rounded-full bg-sky-500" :style="{width: Math.min((r.total_stake||0)/(r.max_stake||100)*100,100)+'%'}"></div>
        </div>
      </div>
      <!-- 冷却 -->
      <div class="card">
        <p class="text-xs text-gray-400 mb-2">冷却设置</p>
        <p class="text-sm">{{ r.cooldown_hours || 1 }} 小时 / {{ r.cooldown_scope || 'symbol' }}</p>
      </div>
      <!-- 暂停状态 -->
      <div class="card">
        <p class="text-xs text-gray-400 mb-2">系统状态</p>
        <div class="flex items-center gap-2">
          <span class="w-3 h-3 rounded-full" :class="r.is_paused?'bg-red-400':'bg-emerald-400'"></span>
          <span :class="r.is_paused?'text-red-400':'text-emerald-400'">{{ r.is_paused?'已暂停':'运行中' }}</span>
        </div>
      </div>
    </div>
    <!-- 风控事件 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-3">最近风控事件</h3>
      <div class="space-y-2">
        <div v-for="ev in events" :key="ev.id" class="flex justify-between p-2 bg-gray-700/50 rounded text-xs">
          <span>{{ ev.event_type }} {{ ev.symbol||'' }}</span>
          <span class="text-gray-500">{{ fmtTime(ev.timestamp) }}</span>
        </div>
        <div v-if="events.length===0" class="text-center py-4 text-gray-500 text-sm">暂无事件</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRiskStore } from '@/stores'

const store = useRiskStore()
const r = computed(() => store.status)
const events = computed(() => store.events)
const lossPct = computed(() => Math.min(((r.value.daily_loss||0)/(r.value.daily_loss_limit||100))*100, 100))

function fmtTime(ts: string) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })
}

onMounted(() => { store.fetchStatus(); store.fetchEvents() })
</script>
