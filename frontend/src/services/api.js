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
  }
}

export const healthService = {
  checkHealth() {
    return api.get('/health')
  }
}

export const adminService = {
  createApiKey(adminSecret, name, rateLimit = 60) {
    return api.post(`/admin/api-keys`, null, {
      params: { name, rate_limit_per_minute: rateLimit },
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
  }
}

