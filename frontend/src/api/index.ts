import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 15000 })

// 请求拦截 - 自动附加 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('nexus_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截 - 401 自动跳转登录
api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('nexus_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// === Auth ===
export const authApi = {
  login: (data: { username: string; password: string; totp_code?: string }) =>
    api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
  sessions: () => api.get('/auth/sessions'),
  revokeSession: (id: string) => api.delete(`/auth/sessions/${id}`),
  totpSetup: () => api.get('/auth/totp/setup'),
}

// === Dashboard ===
export const dashboardApi = {
  summary: () => api.get('/dashboard/summary'),
}

// === Trades ===
export const tradeApi = {
  list: (params?: any) => api.get('/trades', { params }),
  get: (id: string) => api.get(`/trades/${id}`),
  close: (id: string) => api.post(`/trades/${id}/close`),
  panicCloseAll: () => api.post('/trades/panic-close-all'),
}

// === Candidates ===
export const candidateApi = {
  list: (params?: any) => api.get('/candidates', { params }),
}

// === Signals ===
export const signalApi = {
  list: (params?: any) => api.get('/signals', { params }),
  stats: () => api.get('/signals/stats'),
}

// === Risk ===
export const riskApi = {
  status: () => api.get('/risk/status'),
  togglePause: (data: any) => api.post('/risk/toggle-pause', data),
  events: (limit?: number) => api.get('/risk/events', { params: { limit } }),
}

// === Config ===
export const configApi = {
  getAll: () => api.get('/config/all'),
  update: (section: string, key: string, value: any) =>
    api.post('/config/update', { section, key, value }),
}

// === Secrets ===
export const secretsApi = {
  exchanges: () => api.get('/secrets/exchanges'),
  updateExchange: (data: any) => api.post('/secrets/exchanges', data),
  telegram: () => api.get('/secrets/telegram'),
  updateTelegram: (data: any) => api.post('/secrets/telegram', data),
}

// === Strategy ===
export const strategyApi = {
  blacklist: () => api.get('/strategy/blacklist'),
  addBlacklist: (symbol: string, reason?: string) =>
    api.post('/strategy/blacklist', { symbol, reason }),
  removeBlacklist: (symbol: string) => api.delete(`/strategy/blacklist/${symbol}`),
  forceRegime: (regime: string, reason?: string) =>
    api.post('/strategy/regime', { regime, reason }),
}

// === System ===
export const systemApi = {
  health: () => api.get('/system/health'),
  reconciliation: () => api.get('/system/reconciliation'),
  runReconciliation: () => api.post('/system/reconciliation/run'),
  resetBreaker: (exchange: string) =>
    api.post('/system/circuit-breaker/reset', { exchange }),
  recover: () => api.post('/system/recover'),
  events: (params?: any) => api.get('/system/events', { params }),
}

// === Optimization ===
export const optimizationApi = {
  run: () => api.post('/optimization/run'),
  history: () => api.get('/optimization/history'),
}

export default api
