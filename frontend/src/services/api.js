import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://etfdata-production.up.railway.app'

function getApiKey() {
  return localStorage.getItem('api_key') || ''
}

const api = axios.create({ baseURL: API_BASE_URL })

// Inject API key dynamically on every request
api.interceptors.request.use(config => {
  const key = getApiKey()
  if (key) config.headers['x-api-key'] = key
  return config
})

export const etfService = {
  getETFs(skip = 0, limit = 50, provider = null) {
    return api.get('/etfs', { params: { skip, limit, provider } })
  },
  getETFById(etfId) {
    return api.get(`/etfs/${etfId}`)
  },
  getHoldings(etfId, date = null) {
    return api.get(`/etfs/${etfId}/holdings`, { params: { date } })
  },
  getAllocations(etfId, type = null, date = null) {
    return api.get(`/etfs/${etfId}/allocations`, { params: { type, date } })
  },
  getPerformance(etfId, fromDate = null, toDate = null) {
    return api.get(`/etfs/${etfId}/performance`, { params: { from_date: fromDate, to_date: toDate } })
  },
  getETFRiskMetrics(etfId, rfRate = 0.04) {
    return api.get(`/etfs/${etfId}/risk-metrics`, { params: { rf_rate: rfRate } })
  },
  deleteETF(etfId) {
    return api.delete(`/etfs/${etfId}`)
  },
  deleteETFs(etfIds) {
    return api.delete('/etfs', { data: etfIds })
  }
}

export const analyticsService = {
  calculateOverlap(etfIds, date = null) {
    return api.post('/analytics/overlap', { etf_ids: etfIds, date })
  },
  pairwiseOverlap(etfA, etfB, date = null) {
    return api.get(`/analytics/overlap/${etfA}/${etfB}`, { params: { date } })
  },
  calculateExposure(portfolio, date = null) {
    return api.post('/analytics/exposure', { portfolio }, { params: { date } })
  },
  findSimilar(etfId, topN = 5) {
    return api.get(`/analytics/similar/${etfId}`, { params: { top_n: topN } })
  },
  getRiskMetrics(rfRate = 0.04) {
    return api.get('/analytics/risk-metrics', { params: { rf_rate: rfRate } })
  }
}

export const healthService = {
  checkHealth() {
    return api.get('/health')
  }
}

export const authService = {
  requestKey(email) {
    return api.post('/auth/request-key', null, { params: { email } })
  }
}

export const adminService = {
  verify(adminSecret) {
    return api.get('/admin/verify', { headers: { 'x-admin-secret': adminSecret } })
  },
  importETF(adminSecret, ticker, isin, csvFile = null, name = null, ter = null) {
    const form = new FormData()
    if (csvFile) form.append('csv_file', csvFile)
    const params = { ticker, isin }
    if (name) params.name = name
    if (ter != null) params.ter = ter
    return api.post('/admin/import-etf', form, {
      params,
      headers: { 'x-admin-secret': adminSecret },
    })
  },
  createApiKey(adminSecret, name, rateLimit = 60, email = null) {
    const params = { name, rate_limit_per_minute: rateLimit }
    if (email) params.email = email
    return api.post(`/admin/api-keys`, null, {
      params,
      headers: { 'x-admin-secret': adminSecret }
    })
  },
  initDb(adminSecret) {
    return api.post('/admin/init-db', null, { headers: { 'x-admin-secret': adminSecret } })
  },
  seed(adminSecret) {
    return api.post('/admin/seed', null, { headers: { 'x-admin-secret': adminSecret } })
  },
  reset(adminSecret) {
    return api.post('/admin/reset', null, { headers: { 'x-admin-secret': adminSecret } })
  },
  deleteETFs(adminSecret, etfIds) {
    return api.delete('/admin/etfs', {
      data: etfIds,
      headers: { 'x-admin-secret': adminSecret }
    })
  },
  requestLogs(adminSecret, { limit = 100, offset = 0, api_key_name = '', email = '', path = '' } = {}) {
    const params = { limit, offset }
    if (api_key_name) params.api_key_name = api_key_name
    if (email) params.email = email
    if (path) params.path = path
    return api.get('/admin/request-logs', { params, headers: { 'x-admin-secret': adminSecret } })
  },
}

