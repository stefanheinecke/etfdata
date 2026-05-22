import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_KEY = localStorage.getItem('api_key') || 'test-key'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
  }
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
