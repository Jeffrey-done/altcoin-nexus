<template>
  <div class="min-h-screen" style="background: #0a0e1a;">
    <header class="px-8 py-4 flex items-center justify-between" style="border-bottom: 1px solid #1e2740;">
      <div>
        <h1 class="text-heading text-steel-100">候选池</h1>
        <p class="text-label text-steel-500 mt-0.5">策略扫描候选标的</p>
      </div>
      <button @click="store.fetchCandidates()" class="btn-ghost text-[9px]">刷新</button>
    </header>
    <div class="p-8 space-y-6">
      <!-- 过滤器 -->
      <div class="card p-4 flex gap-3">
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
      <!-- 候选卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="c in filtered" :key="c.id" class="card p-5 anim-in">
          <div class="flex items-center justify-between mb-3">
            <span class="text-data font-semibold text-steel-100">{{ c.symbol?.replace('/USDT','') }}</span>
            <span :class="c.direction==='SHORT'?'badge-short':'badge-long'">{{ c.direction==='SHORT'?'空':'多' }}</span>
          </div>
          <div class="grid grid-cols-2 gap-2 text-[11px]">
            <div><span class="text-steel-500">价格:</span> <span class="text-steel-200 font-mono">${{ c.price?.toFixed(4) }}</span></div>
            <div><span class="text-steel-500">评分:</span> <span class="text-gold-400 font-bold font-mono">{{ c.score }}</span></div>
            <div><span class="text-steel-500">24h:</span> <span class="font-mono" :class="(c.pct24h||0)>0?'text-gain':'text-loss'">{{ (c.pct24h||0).toFixed(1) }}%</span></div>
            <div><span class="text-steel-500">RSI:</span> <span class="font-mono text-steel-200">{{ (c.rsi_1d||50).toFixed(1) }}</span></div>
            <div><span class="text-steel-500">成交量:</span> <span class="font-mono text-steel-200">{{ fmtVol(c.vol24h) }}</span></div>
            <div><span class="text-steel-500">策略:</span> <span class="text-steel-300">{{ c.strategy?.replace('_',' ') }}</span></div>
          </div>
        </div>
      </div>
      <div v-if="filtered.length===0" class="card text-center py-10 text-steel-500">暂无候选标的</div>
    </div>
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