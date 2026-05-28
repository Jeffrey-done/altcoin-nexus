<template>
  <div class="min-h-screen" style="background: #0a0e1a;">
    <!-- 顶部状态栏 -->
    <header class="px-8 py-4 flex items-center justify-between" style="border-bottom: 1px solid #1e2740;">
      <div>
        <h1 class="text-heading text-steel-100">仪表盘</h1>
        <p class="text-label text-steel-500 mt-0.5">系统概览与盈亏</p>
      </div>
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <span class="text-[9px] font-mono text-steel-500 uppercase tracking-widest">更新</span>
          <span class="text-[11px] font-mono text-steel-300">实时</span>
          <span class="animate-ticker">●</span>
        </div>
        <button @click="refresh" class="btn-ghost text-[9px] py-1 px-3">
          刷新
        </button>
      </div>
    </header>

    <div class="p-8 space-y-6">
      <!-- ===== 核心指标行 ===== -->
      <div class="grid grid-cols-4 gap-3">
        <!-- 当日盈亏 -->
        <div class="card-accent p-5 anim-in anim-d1">
          <div class="flex items-center justify-between mb-3">
            <span class="text-label text-steel-500">当日盈亏</span>
            <span class="text-[9px] font-mono px-1.5 py-0.5 rounded" :class="pnlTagClass">{{ pnlDirection }}</span>
          </div>
          <p class="stat-value" :class="(s.today_pnl||0) >= 0 ? 'text-gain' : 'text-loss'">
            {{ (s.today_pnl||0) >= 0 ? '+' : '' }}${{ (s.today_pnl||0).toFixed(2) }}
          </p>
          <div class="mt-2 h-[1px]" style="background: #1e2740;"></div>
          <p class="text-[10px] font-mono text-steel-500 mt-2">
            未实现 + 已实现
          </p>
        </div>

        <!-- 持仓数量 -->
        <div class="card p-5 anim-in anim-d2">
          <span class="text-label text-steel-500">持仓数量</span>
          <p class="stat-value text-steel-100 mt-2">{{ s.open_trades || 0 }}</p>
          <div class="mt-2 flex items-center gap-1.5">
            <span class="text-[10px] font-mono text-steel-500">上限</span>
            <span class="text-[10px] font-mono text-steel-300">{{ s.max_daily_trades || 10 }}</span>
          </div>
        </div>

        <!-- 总敞口 -->
        <div class="card p-5 anim-in anim-d3">
          <span class="text-label text-steel-500">总敞口</span>
          <p class="stat-value text-steel-100 mt-2 font-mono">${{ (s.total_stake||0).toFixed(2) }}</p>
          <div class="mt-2 h-[1px]" style="background: #1e2740;"></div>
          <p class="text-[10px] font-mono text-steel-500 mt-2">全交易所合计</p>
        </div>

        <!-- 候选池 -->
        <div class="card p-5 anim-in anim-d4">
          <span class="text-label text-steel-500">候选池</span>
          <p class="stat-value text-gold-400 mt-2">{{ s.candidates_count || 0 }}</p>
          <div class="mt-2 flex items-center gap-1.5">
            <span class="status-dot-active"></span>
            <span class="text-[10px] font-mono text-steel-500">扫描中</span>
          </div>
        </div>
      </div>

      <!-- ===== 风控指标 ===== -->
      <div class="grid grid-cols-3 gap-3">
        <!-- 日亏损限额 -->
        <div class="card p-5 anim-in anim-d3">
          <div class="flex items-center justify-between mb-4">
            <span class="text-label text-steel-500">日亏损限额</span>
            <span class="text-[11px] font-mono font-semibold" :class="lossColor">{{ lossPct.toFixed(1) }}%</span>
          </div>
          <div class="flex items-end justify-between mb-2">
            <span class="text-data-lg font-mono text-steel-100">${{ s.daily_loss || 0 }}</span>
            <span class="text-[11px] font-mono text-steel-500">/ ${{ s.daily_loss_limit || 100 }}</span>
          </div>
          <div class="progress-track">
            <div class="progress-bar" :class="lossBarColor" :style="{ width: Math.min(lossPct, 100) + '%' }"></div>
          </div>
          <div class="flex justify-between mt-2">
            <span class="text-[9px] font-mono text-steel-600">0%</span>
            <span class="text-[9px] font-mono" :class="lossPct > 80 ? 'text-loss' : 'text-steel-600'">100% 强制暂停</span>
          </div>
        </div>

        <!-- 当日开仓笔数 -->
        <div class="card p-5 anim-in anim-d4">
          <div class="flex items-center justify-between mb-4">
            <span class="text-label text-steel-500">当日开仓笔数</span>
            <span class="text-[11px] font-mono font-semibold text-primary-400">{{ tradePct.toFixed(1) }}%</span>
          </div>
          <div class="flex items-end justify-between mb-2">
            <span class="text-data-lg font-mono text-steel-100">{{ s.today_trades || 0 }}</span>
            <span class="text-[11px] font-mono text-steel-500">/ {{ s.max_daily_trades || 10 }}</span>
          </div>
          <div class="progress-track">
            <div class="progress-bar bg-primary-400" :style="{ width: Math.min(tradePct, 100) + '%' }"></div>
          </div>
          <div class="flex justify-between mt-2">
            <span class="text-[9px] font-mono text-steel-600">已执行</span>
            <span class="text-[9px] font-mono text-steel-600">限额</span>
          </div>
        </div>

        <!-- 连续亏损 -->
        <div class="card p-5 anim-in anim-d5">
          <div class="flex items-center justify-between mb-4">
            <span class="text-label text-steel-500">连续亏损</span>
            <span class="text-label" :class="(s.consecutive_losses||0) >= 2 ? 'text-loss' : 'text-steel-500'">
              {{ (s.consecutive_losses||0) >= 3 ? '已暂停' : '监控中' }}
            </span>
          </div>
          <div class="flex items-end gap-4">
            <p class="stat-value" :class="(s.consecutive_losses||0) > 0 ? 'text-loss' : 'text-gain'">
              {{ s.consecutive_losses || 0 }}
            </p>
            <div class="pb-1">
              <span class="text-[11px] font-mono text-steel-500">/ 阈值 3</span>
            </div>
          </div>
          <div class="flex gap-1 mt-4">
            <div v-for="i in 3" :key="i" class="h-1 flex-1 rounded-full" :class="i <= (s.consecutive_losses||0) ? 'bg-loss' : 'bg-terminal-muted'"></div>
          </div>
        </div>
      </div>

      <!-- ===== 快捷操作 ===== -->
      <div class="card p-5 anim-in anim-d6">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-label text-steel-500">快捷操作</span>
            <p class="text-[10px] text-steel-600 mt-1">手动覆盖控制 — 谨慎使用</p>
          </div>
          <div class="flex gap-2">
            <button @click="panicSell" class="btn-danger text-[10px]">
              ◉ 紧急全平仓
            </button>
            <button @click="togglePause" class="btn-ghost text-[10px]">
              {{ paused ? '▶ 恢复交易' : '⏸ 暂停交易' }}
            </button>
            <button @click="runOpt" class="btn-ghost text-[10px]">
              △ 立即优化
            </button>
          </div>
        </div>
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

// PnL
const pnlDirection = computed(() => (s.value.today_pnl || 0) >= 0 ? '盈利' : '亏损')
const pnlTagClass = computed(() =>
  (s.value.today_pnl || 0) >= 0
    ? 'bg-gain/10 text-gain border border-gain/20'
    : 'bg-loss/10 text-loss border border-loss/20'
)

// Loss
const lossPct = computed(() => ((s.value.daily_loss || 0) / (s.value.daily_loss_limit || 100)) * 100)
const lossColor = computed(() => lossPct.value > 80 ? 'text-loss' : lossPct.value > 50 ? 'text-yellow-400' : 'text-gain')
const lossBarColor = computed(() => lossPct.value > 80 ? 'bg-loss' : lossPct.value > 50 ? 'bg-yellow-500' : 'bg-gain')

// Trade count
const tradePct = computed(() => ((s.value.today_trades || 0) / (s.value.max_daily_trades || 10)) * 100)

function refresh() {
  store.fetchSummary()
}

async function panicSell() {
  if (!confirm('确认：紧急平仓所有持仓？此操作不可撤销。')) return
  await tradeApi.panicCloseAll()
}

async function togglePause() {
  await riskApi.togglePause({ paused: !paused.value, reason: '仪表盘手动操作' })
  paused.value = !paused.value
}

async function runOpt() {
  await optimizationApi.run()
}

onMounted(() => store.fetchSummary())
</script>