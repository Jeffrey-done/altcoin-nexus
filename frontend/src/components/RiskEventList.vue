<template>
  <div class="space-y-3">
    <div
      v-for="event in events"
      :key="event.id"
      class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg"
    >
      <div class="flex items-center space-x-3">
        <span class="text-lg">{{ eventIcon(event.event_type) }}</span>
        <div>
          <div class="text-sm">{{ eventMessage(event) }}</div>
          <div class="text-xs text-gray-500">{{ formatTime(event.timestamp) }}</div>
        </div>
      </div>
    </div>
    <div v-if="events.length === 0" class="text-center py-4 text-gray-500">
      暂无风控事件
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { eventApi } from '@/api'

const events = ref<any[]>([])

function eventIcon(type: string): string {
  if (type?.includes('alert')) return '⚠️'
  if (type?.includes('pause')) return '⏸️'
  if (type?.includes('resume')) return '▶️'
  return '📋'
}

function eventMessage(event: any): string {
  const data = event.extra_data ? JSON.parse(event.extra_data) : {}
  
  if (event.event_type === 'risk.alert') {
    return `风控告警: ${data.alert_type || '未知'}`
  }
  if (event.event_type === 'risk.paused') {
    return '交易已暂停'
  }
  return event.event_type || '未知事件'
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

onMounted(async () => {
  try {
    events.value = await eventApi.getRecent({ 
      event_type: 'risk.alert', 
      limit: 10 
    })
  } catch (e) {
    console.error('Failed to fetch risk events:', e)
  }
})
</script>
