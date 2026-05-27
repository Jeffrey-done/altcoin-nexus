<template>
  <div class="p-6 space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-bold">候选池</h2>
      <button @click="store.fetchCandidates()" class="btn-ghost text-xs">刷新</button>
    </div>
    <div class="card flex gap-3">
      <select v-model="filterStrategy" class="input w-40">
        <option value="">全部策略</option>
        <option value="short_overbought">超买做空</option>
        <option value="long_oversold">超卖做多</option>
        <option value="prepump_sniffer">异动捕获</option>
      </select>
      <select v-model="filterDir" class="input w-28">
        <option value="">全部方向</option><option value="SHORT">做空</option><option value="LONG">做多</option>
      </select>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="c in filtered" :key="c.id" class="card">
        <div class="flex items-center justify-between mb-2">
          <span class="font-bold">{{ c.symbol?.replace('/USDT','') }}</span>
          <span :class="c.direction==='SHORT'?'badge-short':'badge-long'">{{ c.direction==='SHORT'?'空':'多' }}</span>
        </div>
        <div class="grid grid-cols-2 gap-2 text-xs">
          <div><span class="text-gray-400">价格:</span> ${{ c.price?.toFixed(4) }}</div>
          <div><span class="text-gray-400">评分:</span> <span class="text-sky-400 font-bold">{{ c.score }}</span></div>
          <div><span class="text-gray-400">24h:</span> <span :class="(c.pct24h||0)>0?'text-profit':'text-loss'">{{ (c.pct24h||0).toFixed(1) }}%</span></div>
          <div><span class="text-gray-400">RSI:</span> {{ (c.rsi_1d||50).toFixed(1) }}</div>
          <div><span class="text-gray-400">成交量:</span> {{ fmtVol(c.vol24h) }}</div>
          <div><span class="text-gray-400">策略:</span> {{ c.strategy?.replace('_',' ') }}</div>
        </div>
      </div>
    </div>
    <div v-if="filtered.length===0" class="card text-center py-8 text-gray-500">暂无候选</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useCandidateStore } from '@/stores'

const store = useCandidateStore()
const filterStrategy = ref('')
const filterDir = ref('')

const filtered = computed(() => store.candidates.filter(c => {
  if (filterStrategy.value && c.strategy !== filterStrategy.value) return false
  if (filterDir.value && c.direction !== filterDir.value) return false
  return true
}))

function fmtVol(v: number) {
  if (!v) return '-'
  return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v.toFixed(0)
}

onMounted(() => store.fetchCandidates())
</script>
