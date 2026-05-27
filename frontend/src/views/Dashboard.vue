<template>
  <div class="space-y-6">
    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard
        title="持仓数量"
        :value="tradeStore.openTrades.length"
        icon="📈"
        color="primary"
      />
      <StatCard
        title="今日盈亏"
        :value="formatPnl(todayPnl)"
        :is-pnl="true"
        icon="💰"
        :color="todayPnl >= 0 ? 'green' : 'red'"
      />
      <StatCard
        title="持仓总值"
        :value="`$${tradeStore.totalStake.toFixed(2)}`"
        icon="🏦"
        color="blue"
      />
      <StatCard
        title="候选数量"
        :value="candidateStore.candidates.length"
        icon="🎯"
        color="yellow"
      />
    </div>

    <!-- 图表区域 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- 盈亏曲线 -->
      <div class="card">
        <h3 class="text-sm font-medium text-gray-400 mb-4">累计盈亏曲线</h3>
        <PnlChart :data="pnlHistory" />
      </div>

      <!-- 持仓分布 -->
      <div class="card">
        <h3 class="text-sm font-medium text-gray-400 mb-4">持仓方向分布</h3>
        <DirectionChart :data="directionData" />
      </div>
    </div>

    <!-- 当前持仓 -->
    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-medium text-gray-400">当前持仓</h3>
        <router-link to="/trades" class="text-sm text-primary-400 hover:underline">
          查看全部 →
        </router-link>
      </div>
      <TradeTable :trades="tradeStore.openTrades" :loading="tradeStore.loading" />
    </div>

    <!-- 最近信号 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">最近信号</h3>
      <SignalList :limit="5" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useTradeStore, useCandidateStore } from '@/stores'
import StatCard from '@/components/StatCard.vue'
import PnlChart from '@/components/PnlChart.vue'
import DirectionChart from '@/components/DirectionChart.vue'
import TradeTable from '@/components/TradeTable.vue'
import SignalList from '@/components/SignalList.vue'

const tradeStore = useTradeStore()
const candidateStore = useCandidateStore()

const todayPnl = computed(() => {
  const today = new Date().toISOString().split('T')[0]
  return tradeStore.trades
    .filter(t => t.status === 'closed' && t.closed_at?.startsWith(today))
    .reduce((sum, t) => sum + (t.pnl || 0), 0)
})

const pnlHistory = computed(() => {
  // 生成模拟数据，实际从API获取
  return tradeStore.closedTrades
    .sort((a, b) => a.closed_at.localeCompare(b.closed_at))
    .reduce((acc, t) => {
      const last = acc.length > 0 ? acc[acc.length - 1].value : 0
      acc.push({
        date: t.closed_at.split('T')[0],
        value: last + (t.pnl || 0),
      })
      return acc
    }, [] as { date: string; value: number }[])
})

const directionData = computed(() => {
  const short = tradeStore.openTrades.filter(t => t.direction === 'SHORT').length
  const long = tradeStore.openTrades.filter(t => t.direction === 'LONG').length
  return [
    { name: '做空', value: short },
    { name: '做多', value: long },
  ]
})

function formatPnl(value: number): string {
  const prefix = value >= 0 ? '+' : ''
  return `${prefix}$${value.toFixed(2)}`
}

onMounted(() => {
  tradeStore.fetchTrades()
  candidateStore.fetchCandidates()
})
</script>
