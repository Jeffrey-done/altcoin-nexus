<template>
  <div class="min-h-screen" style="background: #0a0e1a;">
    <header class="px-8 py-4" style="border-bottom: 1px solid #1e2740;">
      <h1 class="text-heading text-steel-100">信号日志</h1>
      <p class="text-label text-steel-500 mt-0.5">策略信号触发记录与统计</p>
    </header>
    <div class="p-8 space-y-6">
      <!-- 统计卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="card p-5" v-for="(st, name) in stats" :key="name">
          <p class="text-label text-steel-500 mb-3">{{ strategyLabel(name) }}</p>
          <div class="flex justify-between items-center">
            <div>
              <span class="text-[10px] font-mono text-steel-500">总信号</span>
              <p class="text-data-lg font-mono text-steel-100">{{ st.total_signals || 0 }}</p>
            </div>
            <div>
              <span class="text-[10px] font-mono text-steel-500">触发</span>
              <p class="text-data-lg font-mono text-gold-400">{{ st.triggered || 0 }}</p>
            </div>
            <div>
              <span class="text-[10px] font-mono text-steel-500">触发率</span>
              <p class="text-data-lg font-mono text-primary-400">{{ st.trigger_rate || 0 }}%</p>
            </div>
          </div>
        </div>
      </div>
      <!-- 信号列表 -->
      <div class="card p-0">
        <div class="p-4" style="border-bottom: 1px solid #1e2740;">
          <span class="text-label text-steel-500">最近信号</span>
        </div>
        <div class="divide-y" style="border-color: rgba(30,39,64,0.4);">
          <div v-for="sig in signals" :key="sig.id" class="flex items-center justify-between px-4 py-3 hover:bg-white/[0.02] transition-colors">
            <div class="flex items-center gap-3">
              <span class="w-8 h-8 rounded flex items-center justify-center text-xs font-bold"
                :class="gradeClass(sig.grade)">{{ sig.grade }}</span>
              <div>
                <div class="text-data font-medium text-steel-100">{{ sig.symbol?.replace('/USDT','') }}</div>
                <div class="text-[10px] font-mono text-steel-500">{{ sig.strategy?.replace('_',' ') }}</div>
              </div>
            </div>
            <div class="text-right">
              <div class="text-data font-mono text-gold-400">{{ sig.score }} 分</div>
              <div class="text-[10px] font-mono text-steel-500">{{ fmtTime(sig.timestamp) }}</div>
            </div>
          </div>
          <div v-if="signals.length===0" class="py-10 text-center text-steel-500">暂无信号记录</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useSignalStore } from '@/stores'

const store = useSignalStore()
const signals = computed(() => store.signals)
const stats = computed(() => store.stats)

function strategyLabel(n: string) {
  const m: any = { short_overbought: '超买做空', long_oversold: '超卖做多', prepump_sniffer: '异动捕获' }
  return m[n] || n
}
function gradeClass(g: string) {
  if (g === 'A') return 'bg-gain/15 text-gain border border-gain/20'
  if (g === 'B') return 'bg-yellow-500/15 text-yellow-400 border border-yellow-500/20'
  return 'bg-terminal-muted/30 text-steel-400 border border-terminal-border'
}
function fmtTime(ts: string) {
  if (!ts) return '-'
  return new Date(ts).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })
}

onMounted(() => { store.fetchSignals(); store.fetchStats() })
</script>