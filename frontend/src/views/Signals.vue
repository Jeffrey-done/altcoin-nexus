<template>
  <div class="p-6 space-y-4">
    <h2 class="text-xl font-bold">信号日志</h2>
    <!-- 统计 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="card" v-for="(st, name) in stats" :key="name">
        <p class="text-xs text-gray-400 mb-1">{{ strategyLabel(name) }}</p>
        <div class="flex justify-between">
          <span class="text-sm">总信号: {{ st.total_signals || 0 }}</span>
          <span class="text-sm">触发: {{ st.triggered || 0 }}</span>
          <span class="text-sm text-sky-400">{{ st.trigger_rate || 0 }}%</span>
        </div>
      </div>
    </div>
    <!-- 信号列表 -->
    <div class="card">
      <div class="space-y-2">
        <div v-for="sig in signals" :key="sig.id" class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg">
          <div class="flex items-center gap-3">
            <span class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
              :class="gradeClass(sig.grade)">{{ sig.grade }}</span>
            <div>
              <div class="font-medium text-sm">{{ sig.symbol?.replace('/USDT','') }}</div>
              <div class="text-xs text-gray-500">{{ sig.strategy?.replace('_',' ') }}</div>
            </div>
          </div>
          <div class="text-right">
            <div class="font-mono text-sm">{{ sig.score }} 分</div>
            <div class="text-xs text-gray-500">{{ fmtTime(sig.timestamp) }}</div>
          </div>
        </div>
        <div v-if="signals.length===0" class="text-center py-6 text-gray-500">暂无信号</div>
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
  if (g === 'A') return 'bg-emerald-500/20 text-emerald-400'
  if (g === 'B') return 'bg-yellow-500/20 text-yellow-400'
  return 'bg-gray-500/20 text-gray-400'
}
function fmtTime(ts: string) {
  if (!ts) return '-'
  return new Date(ts).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })
}

onMounted(() => { store.fetchSignals(); store.fetchStats() })
</script>
