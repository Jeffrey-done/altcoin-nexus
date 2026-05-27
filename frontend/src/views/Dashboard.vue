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

    <!-- 系统状态栏 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <!-- 对账状态 -->
      <div class="card">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-medium text-gray-400">对账状态</h3>
          <button 
            @click="refreshReconciliation" 
            class="text-xs text-primary-400 hover:text-primary-300"
          >
            刷新
          </button>
        </div>
        <div class="flex items-center space-x-3">
          <span 
            class="w-3 h-3 rounded-full"
            :class="reconciliationStatusClass"
          ></span>
          <div>
            <p class="text-sm font-medium">{{ reconciliationStatusText }}</p>
            <p class="text-xs text-gray-500">
              上次检查: {{ reconciliation.last_check || '未检查' }}
            </p>
          </div>
        </div>
        <div class="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div class="bg-gray-700 rounded p-2">
            <span class="text-gray-400">检查次数:</span>
            <span class="ml-1 font-mono">{{ reconciliation.stats?.total_checks || 0 }}</span>
          </div>
          <div class="bg-gray-700 rounded p-2">
            <span class="text-gray-400">发现差异:</span>
            <span class="ml-1 font-mono" :class="discrepancies > 0 ? 'text-yellow-400' : 'text-green-400'">
              {{ discrepancies }}
            </span>
          </div>
        </div>
      </div>

      <!-- 熔断器状态 -->
      <div class="card">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-medium text-gray-400">熔断器状态</h3>
          <button 
            @click="systemRecover" 
            class="px-3 py-1 text-xs bg-yellow-600 hover:bg-yellow-700 rounded"
            :disabled="!hasOpenBreakers"
          >
            一键恢复
          </button>
        </div>
        <div class="space-y-2">
          <div 
            v-for="(breaker, exchange) in circuitBreakers" 
            :key="exchange"
            class="flex items-center justify-between p-2 bg-gray-700 rounded"
          >
            <div class="flex items-center space-x-2">
              <span 
                class="w-2 h-2 rounded-full"
                :class="breakerStateClass(breaker.state)"
              ></span>
              <span class="text-sm">{{ exchange }}</span>
            </div>
            <div class="flex items-center space-x-2">
              <span class="text-xs text-gray-400">
                {{ breaker.state === 'open' ? '熔断中' : breaker.state === 'half_open' ? '探测中' : '正常' }}
              </span>
              <button 
                v-if="breaker.state !== 'closed'"
                @click="resetBreaker(exchange)"
                class="text-xs text-primary-400 hover:text-primary-300"
              >
                重置
              </button>
            </div>
          </div>
          <div v-if="Object.keys(circuitBreakers).length === 0" class="text-center text-gray-500 text-sm py-2">
            无熔断器
          </div>
        </div>
      </div>
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
import { ref, computed, onMounted } from 'vue'
import { useTradeStore, useCandidateStore } from '@/stores'
import api from '@/api'
import StatCard from '@/components/StatCard.vue'
import PnlChart from '@/components/PnlChart.vue'
import DirectionChart from '@/components/DirectionChart.vue'
import TradeTable from '@/components/TradeTable.vue'
import SignalList from '@/components/SignalList.vue'

const tradeStore = useTradeStore()
const candidateStore = useCandidateStore()

// 对账状态
const reconciliation = ref<any>({
  status: 'inactive',
  stats: {},
  circuit_breakers: {},
})

const circuitBreakers = computed(() => reconciliation.value.circuit_breakers || {})
const discrepancies = computed(() => reconciliation.value.stats?.discrepancies_found || 0)

const reconciliationStatusClass = computed(() => {
  if (reconciliation.value.status === 'active') {
    return discrepancies.value > 0 ? 'bg-yellow-400' : 'bg-green-400'
  }
  return 'bg-gray-500'
})

const reconciliationStatusText = computed(() => {
  if (reconciliation.value.status !== 'active') return '未启动'
  if (discrepancies.value > 0) return `${discrepancies.value} 个差异`
  return '同步正常'
})

const hasOpenBreakers = computed(() => {
  return Object.values(circuitBreakers.value).some((b: any) => b.state !== 'closed')
})

function breakerStateClass(state: string) {
  switch (state) {
    case 'closed': return 'bg-green-400'
    case 'half_open': return 'bg-yellow-400'
    case 'open': return 'bg-red-400'
    default: return 'bg-gray-400'
  }
}

async function refreshReconciliation() {
  try {
    reconciliation.value = await api.get('/reconciliation/status')
  } catch (e) {
    console.error('Failed to fetch reconciliation status:', e)
  }
}

async function resetBreaker(exchange: string) {
  try {
    await api.post('/circuit-breaker/reset', { exchange })
    await refreshReconciliation()
  } catch (e) {
    console.error('Failed to reset breaker:', e)
  }
}

async function systemRecover() {
  if (!confirm('确定要执行系统恢复吗？这将重置所有熔断器。')) return
  
  try {
    const result = await api.post('/system/recover')
    alert(`系统已恢复，重置了 ${result.reset_breakers} 个熔断器`)
    await refreshReconciliation()
  } catch (e) {
    console.error('Failed to recover system:', e)
    alert('系统恢复失败')
  }
}

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
  refreshReconciliation()
})
</script>
