<template>
  <div class="space-y-4">
    <!-- 过滤器 -->
    <div class="card">
      <div class="flex flex-wrap items-center gap-4">
        <select v-model="filters.status" class="input-field">
          <option value="">全部状态</option>
          <option value="open">持仓中</option>
          <option value="closed">已平仓</option>
        </select>
        <select v-model="filters.direction" class="input-field">
          <option value="">全部方向</option>
          <option value="SHORT">做空</option>
          <option value="LONG">做多</option>
        </select>
        <select v-model="filters.exchange" class="input-field">
          <option value="">全部交易所</option>
          <option value="binance">Binance</option>
          <option value="okx">OKX</option>
          <option value="bybit">Bybit</option>
          <option value="gate">Gate.io</option>
          <option value="bitget">Bitget</option>
        </select>
        <button @click="refresh" class="btn-primary">
          刷新
        </button>
      </div>
    </div>

    <!-- 交易表格 -->
    <div class="card">
      <TradeTable 
        :trades="filteredTrades" 
        :loading="tradeStore.loading"
        :show-actions="true"
        @close="handleClose"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useTradeStore } from '@/stores'
import TradeTable from '@/components/TradeTable.vue'

const tradeStore = useTradeStore()

const filters = ref({
  status: '',
  direction: '',
  exchange: '',
})

const filteredTrades = computed(() => {
  return tradeStore.trades.filter(t => {
    if (filters.value.status && t.status !== filters.value.status) return false
    if (filters.value.direction && t.direction !== filters.value.direction) return false
    if (filters.value.exchange && t.exchange !== filters.value.exchange) return false
    return true
  })
})

function refresh() {
  tradeStore.fetchTrades()
}

async function handleClose(tradeId: string) {
  if (confirm('确定要平仓吗？')) {
    // 调用平仓API
    console.log('Close trade:', tradeId)
  }
}

onMounted(() => {
  tradeStore.fetchTrades()
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
