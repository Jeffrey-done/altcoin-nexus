<template>
  <div class="space-y-3">
    <div
      v-for="signal in signals"
      :key="signal.id"
      class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg"
    >
      <div class="flex items-center space-x-3">
        <span
          class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
          :class="gradeClass(signal.grade)"
        >
          {{ signal.grade }}
        </span>
        <div>
          <div class="font-medium">{{ formatSymbol(signal.symbol) }}</div>
          <div class="text-xs text-gray-500">{{ signal.strategy }}</div>
        </div>
      </div>
      <div class="text-right">
        <div class="font-mono">{{ signal.score }} 分</div>
        <div class="text-xs text-gray-500">{{ formatTime(signal.timestamp) }}</div>
      </div>
    </div>
    <div v-if="signals.length === 0" class="text-center py-4 text-gray-500">
      暂无信号
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { eventApi } from '@/api'

defineProps<{
  limit?: number
}>()

const signals = ref<any[]>([])

function formatSymbol(symbol: string): string {
  return symbol?.replace('/USDT', '') || '-'
}

function formatTime(timestamp: string): string {
  if (!timestamp) return '-'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function gradeClass(grade: string): string {
  switch (grade) {
    case 'A': return 'bg-green-500/20 text-green-400'
    case 'B': return 'bg-yellow-500/20 text-yellow-400'
    default: return 'bg-gray-500/20 text-gray-400'
  }
}

onMounted(async () => {
  try {
    signals.value = await eventApi.getRecent({ event_type: 'signal.scored', limit: 10 })
  } catch (e) {
    console.error('Failed to fetch signals:', e)
  }
})
</script>
