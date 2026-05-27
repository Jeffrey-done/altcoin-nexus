<template>
  <div class="card">
    <div class="flex items-center justify-between">
      <div>
        <p class="text-sm text-gray-400">{{ title }}</p>
        <p class="text-2xl font-bold mt-1" :class="valueColor">
          {{ value }}
        </p>
      </div>
      <div class="text-3xl opacity-50">{{ icon }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  title: string
  value: string | number
  icon: string
  color?: string
  isPnl?: boolean
}>()

const valueColor = computed(() => {
  if (props.isPnl) {
    const num = typeof props.value === 'string' 
      ? parseFloat(props.value.replace(/[$,+,]/g, ''))
      : props.value
    return num >= 0 ? 'text-profit' : 'text-loss'
  }
  
  switch (props.color) {
    case 'green': return 'text-green-400'
    case 'red': return 'text-red-400'
    case 'blue': return 'text-blue-400'
    case 'yellow': return 'text-yellow-400'
    default: return 'text-primary-400'
  }
})
</script>
