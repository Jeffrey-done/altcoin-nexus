<template>
  <div class="space-y-3">
    <div
      v-for="candidate in candidates"
      :key="candidate.id"
      class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-colors"
    >
      <div class="flex items-center space-x-3">
        <span
          class="px-2 py-0.5 rounded text-xs font-medium"
          :class="candidate.direction === 'SHORT' ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'"
        >
          {{ candidate.direction === 'SHORT' ? '做空' : '做多' }}
        </span>
        <span class="font-medium">{{ formatSymbol(candidate.symbol) }}</span>
      </div>
      <div class="text-right">
        <div class="font-mono text-sm">${{ candidate.price?.toFixed(4) || '-' }}</div>
        <div class="text-xs" :class="candidate.pct24h > 0 ? 'text-profit' : 'text-loss'">
          {{ candidate.pct24h > 0 ? '+' : '' }}{{ candidate.pct24h?.toFixed(2) || 0 }}%
        </div>
      </div>
    </div>
    <div v-if="candidates.length === 0" class="text-center py-4 text-gray-500">
      暂无候选
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCandidateStore } from '@/stores'

const candidateStore = useCandidateStore()

const candidates = computed(() => candidateStore.candidates.slice(0, 10))

function formatSymbol(symbol: string): string {
  return symbol?.replace('/USDT', '') || '-'
}
</script>
