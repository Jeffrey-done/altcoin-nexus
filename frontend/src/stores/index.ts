import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { tradeApi, candidateApi, riskApi, systemApi } from '@/api'

export const useTradeStore = defineStore('trade', () => {
  const trades = ref<any[]>([])
  const loading = ref(false)

  const openTrades = computed(() => 
    trades.value.filter(t => t.status === 'open')
  )

  const closedTrades = computed(() => 
    trades.value.filter(t => t.status === 'closed')
  )

  const totalPnl = computed(() => 
    trades.value.reduce((sum, t) => sum + (t.pnl || 0), 0)
  )

  const totalStake = computed(() => 
    openTrades.value.reduce((sum, t) => sum + (t.stake || 0), 0)
  )

  async function fetchTrades(params?: any) {
    loading.value = true
    try {
      trades.value = await tradeApi.getAll(params)
    } finally {
      loading.value = false
    }
  }

  return {
    trades,
    loading,
    openTrades,
    closedTrades,
    totalPnl,
    totalStake,
    fetchTrades,
  }
})

export const useCandidateStore = defineStore('candidate', () => {
  const candidates = ref<any[]>([])
  const loading = ref(false)

  async function fetchCandidates(params?: any) {
    loading.value = true
    try {
      candidates.value = await candidateApi.getAll(params)
    } finally {
      loading.value = false
    }
  }

  return {
    candidates,
    loading,
    fetchCandidates,
  }
})

export const useSystemStore = defineStore('system', () => {
  const status = ref<any>(null)
  const config = ref<any>(null)
  const loading = ref(false)

  async function fetchStatus() {
    loading.value = true
    try {
      status.value = await systemApi.getStatus()
    } finally {
      loading.value = false
    }
  }

  async function fetchConfig() {
    config.value = await systemApi.getConfig()
  }

  return {
    status,
    config,
    loading,
    fetchStatus,
    fetchConfig,
  }
})
