import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, dashboardApi, tradeApi, candidateApi, riskApi, configApi, secretsApi, signalApi } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('nexus_token') || '')
  const user = ref<any>(null)
  const isAuthenticated = computed(() => !!token.value)

  async function login(username: string, password: string, totp_code?: string) {
    const res: any = await authApi.login({ username, password, totp_code })
    token.value = res.token
    localStorage.setItem('nexus_token', res.token)
    user.value = { username: res.username, totp_enabled: res.totp_enabled }
    return res
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('nexus_token')
  }

  async function fetchMe() {
    try {
      user.value = await authApi.me()
    } catch { logout() }
  }

  return { token, user, isAuthenticated, login, logout, fetchMe }
})

export const useDashboardStore = defineStore('dashboard', () => {
  const summary = ref<any>({})
  const loading = ref(false)
  async function fetchSummary() {
    loading.value = true
    try { summary.value = await dashboardApi.summary() }
    finally { loading.value = false }
  }
  return { summary, loading, fetchSummary }
})

export const useTradeStore = defineStore('trade', () => {
  const trades = ref<any[]>([])
  const loading = ref(false)
  const openTrades = computed(() => trades.value.filter(t => t.status === 'open'))
  const closedTrades = computed(() => trades.value.filter(t => t.status === 'closed'))
  async function fetchTrades(params?: any) {
    loading.value = true
    try {
      const res: any = await tradeApi.list(params)
      trades.value = res.trades || []
    } finally { loading.value = false }
  }
  return { trades, loading, openTrades, closedTrades, fetchTrades }
})

export const useCandidateStore = defineStore('candidate', () => {
  const candidates = ref<any[]>([])
  const loading = ref(false)
  async function fetchCandidates(params?: any) {
    loading.value = true
    try {
      const res: any = await candidateApi.list(params)
      candidates.value = res.candidates || []
    } finally { loading.value = false }
  }
  return { candidates, loading, fetchCandidates }
})

export const useRiskStore = defineStore('risk', () => {
  const status = ref<any>({})
  const events = ref<any[]>([])
  async function fetchStatus() {
    status.value = await riskApi.status()
  }
  async function fetchEvents() {
    const res: any = await riskApi.events(20)
    events.value = res.events || []
  }
  return { status, events, fetchStatus, fetchEvents }
})

export const useConfigStore = defineStore('config', () => {
  const config = ref<any>({})
  const secrets = ref<any>({})
  const telegram = ref<any>({})
  async function fetchConfig() { config.value = await configApi.getAll() }
  async function fetchSecrets() { secrets.value = await secretsApi.exchanges() }
  async function fetchTelegram() { telegram.value = await secretsApi.telegram() }
  return { config, secrets, telegram, fetchConfig, fetchSecrets, fetchTelegram }
})

export const useSignalStore = defineStore('signal', () => {
  const signals = ref<any[]>([])
  const stats = ref<any>({})
  async function fetchSignals(params?: any) {
    const res: any = await signalApi.list(params)
    signals.value = res.signals || []
  }
  async function fetchStats() { stats.value = await signalApi.stats() }
  return { signals, stats, fetchSignals, fetchStats }
})
