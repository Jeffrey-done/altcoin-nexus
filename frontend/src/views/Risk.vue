<template>
  <div class="min-h-screen" style="background: #0a0e1a;">
    <header class="px-8 py-4" style="border-bottom: 1px solid #1e2740;">
      <h1 class="text-heading text-steel-100">风控状态</h1>
      <p class="text-label text-steel-500 mt-0.5">风险控制指标与事件</p>
    </header>
    <div class="p-8 space-y-6">
      <!-- 风控指标 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <!-- 日亏损 -->
        <div class="card p-5 anim-in anim-d1">
          <span class="text-label text-steel-500">日亏损限制</span>
          <div class="flex items-end justify-between mt-2 mb-2">
            <span class="text-data-lg font-mono text-loss">${{ r.daily_loss || 0 }}</span>
            <span class="text-[11px] font-mono text-steel-500">/ ${{ r.daily_loss_limit || 100 }}</span>
          </div>
          <div class="progress-track">
            <div class="progress-bar" :class="lossPct>80?'bg-loss':lossPct>50?'bg-yellow-500':'bg-gain'" :style="{width:lossPct+'%'}"></div>
          </div>
        </div>
        <!-- 今日开仓 -->
        <div class="card p-5 anim-in anim-d2">
          <span class="text-label text-steel-500">今日开仓</span>
          <div class="flex items-end justify-between mt-2 mb-2">
            <span class="text-data-lg font-mono text-steel-100">{{ r.today_trades || 0 }} 笔</span>
            <span class="text-[11px] font-mono text-steel-500">/ {{ r.daily_trades_limit || 10 }}</span>
          </div>
          <div class="flex gap-3 text-[10px] font-mono text-steel-500 mt-2">
            <span>空: ≤{{ r.max_daily_trades_short || 6 }}</span>
            <span>多: ≤{{ r.max_daily_trades_long || 4 }}</span>
          </div>
        </div>
        <!-- 连续亏损 -->
        <div class="card p-5 anim-in anim-d3">
          <span class="text-label text-steel-500">连续亏损</span>
          <p class="stat-value mt-2" :class="(r.consecutive_losses||0)>0?'text-loss':'text-gain'">{{ r.consecutive_losses || 0 }}</p>
          <p class="text-[10px] font-mono text-steel-500 mt-2">暂停阈值: {{ r.consecutive_loss_limit || 3 }}</p>
        </div>
        <!-- 持仓总额 -->
        <div class="card p-5 anim-in anim-d4">
          <span class="text-label text-steel-500">持仓总额</span>
          <div class="flex items-end justify-between mt-2 mb-2">
            <span class="text-data-lg font-mono text-steel-100">${{ (r.total_stake||0).toFixed(2) }}</span>
            <span class="text-[11px] font-mono text-steel-500">/ ${{ r.max_stake || 100 }}</span>
          </div>
          <div class="progress-track">
            <div class="progress-bar bg-primary-400" :style="{width: Math.min((r.total_stake||0)/(r.max_stake||100)*100,100)+'%'}"></div>
          </div>
        </div>
        <!-- 冷却设置 -->
        <div class="card p-5 anim-in anim-d5">
          <span class="text-label text-steel-500">冷却设置</span>
          <p class="text-data font-mono text-steel-200 mt-2">{{ r.cooldown_hours || 1 }} 小时 / {{ r.cooldown_scope || 'symbol' }}</p>
        </div>
        <!-- 系统状态 -->
        <div class="card p-5 anim-in anim-d6">
          <span class="text-label text-steel-500">系统状态</span>
          <div class="flex items-center gap-2 mt-3">
            <span :class="r.is_paused?'status-dot-error':'status-dot-active'"></span>
            <span class="text-data font-medium" :class="r.is_paused?'text-loss':'text-gain'">{{ r.is_paused?'已暂停':'运行中' }}</span>
          </div>
        </div>
      </div>
      <!-- 风控事件 -->
      <div class="card p-0">
        <div class="p-4" style="border-bottom: 1px solid #1e2740;">
          <span class="text-label text-steel-500">最近风控事件</span>
        </div>
        <div class="divide-y" style="border-color: rgba(30,39,64,0.4);">
          <div v-for="ev in events" :key="ev.id" class="flex justify-between items-center px-4 py-3">
            <span class="text-data text-steel-200">{{ ev.event_type }} <span v-if="ev.symbol" class="text-steel-500 font-mono">{{ ev.symbol }}</span></span>
            <span class="text-[10px] font-mono text-steel-500">{{ fmtTime(ev.timestamp) }}</span>
          </div>
          <div v-if="events.length===0" class="py-10 text-center text-steel-500">暂无风控事件</div>
        </div>
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