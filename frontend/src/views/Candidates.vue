<template>
  <div class="space-y-4">
    <!-- 过滤器 -->
    <div class="card">
      <div class="flex flex-wrap items-center gap-4">
        <select v-model="filters.strategy" class="input-field">
          <option value="">全部策略</option>
          <option value="short_overbought">超买做空</option>
          <option value="long_oversold">超卖做多</option>
        </select>
        <select v-model="filters.direction" class="input-field">
          <option value="">全部方向</option>
          <option value="SHORT">做空</option>
          <option value="LONG">做多</option>
        </select>
        <button @click="refresh" class="btn-primary">
          刷新
        </button>
      </div>
    </div>

    <!-- 候选列表 -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <CandidateCard
        v-for="candidate in filteredCandidates"
        :key="candidate.id"
        :candidate="candidate"
      />
    </div>

    <div v-if="filteredCandidates.length === 0" class="card text-center py-12">
      <p class="text-gray-500">暂无候选</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useCandidateStore } from '@/stores'
import CandidateCard from '@/components/CandidateCard.vue'

const candidateStore = useCandidateStore()

const filters = ref({
  strategy: '',
  direction: '',
})

const filteredCandidates = computed(() => {
  return candidateStore.candidates.filter(c => {
    if (filters.value.strategy && c.strategy !== filters.value.strategy) return false
    if (filters.value.direction && c.direction !== filters.value.direction) return false
    return true
  })
})

function refresh() {
  candidateStore.fetchCandidates()
}

onMounted(() => {
  candidateStore.fetchCandidates()
})
</script>

<style scoped>
.input-field {
  @apply bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500;
}

.btn-primary {
  @apply bg-primary-600 hover:bg-primary-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors;
}
</style>
