<template>
  <div class="space-y-4">
    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-medium text-gray-400">信号日志</h3>
        <button @click="refresh" class="btn-primary">刷新</button>
      </div>
      <SignalList :limit="50" />
    </div>
  </div>
</template>

<script setup lang="ts">
import SignalList from '@/components/SignalList.vue'

function refresh() {
  window.location.reload()
}
</script>

<style scoped>
.btn-primary {
  @apply bg-primary-600 hover:bg-primary-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors;
}
</style>
