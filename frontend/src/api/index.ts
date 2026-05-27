import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// 交易相关
export const tradeApi = {
  getAll: (params?: { status?: string; account_id?: string }) =>
    api.get('/trades', { params }),
  
  getById: (id: string) =>
    api.get(`/trades/${id}`),
  
  getOpen: (account_id?: string) =>
    api.get('/trades', { params: { status: 'open', account_id } }),
}

// 候选池
export const candidateApi = {
  getAll: (params?: { strategy?: string; direction?: string }) =>
    api.get('/candidates', { params }),
}

// 风控
export const riskApi = {
  getStatus: (accountId: string) =>
    api.get(`/risk/${accountId}`),
}

// 事件
export const eventApi = {
  getRecent: (params?: { event_type?: string; symbol?: string; limit?: number }) =>
    api.get('/events', { params }),
}

// 系统
export const systemApi = {
  getStatus: () => api.get('/system/status'),
  getConfig: () => api.get('/config'),
  updateConfig: (key: string, value: any) =>
    api.post('/config', { key, value }),
}

// 健康检查
export const healthApi = {
  check: () => api.get('/health'),
}

export default api
