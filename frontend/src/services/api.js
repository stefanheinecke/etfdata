import axios from 'axios'
import { getApiBaseUrl } from './apiBaseUrl.js'

const API_BASE_URL = getApiBaseUrl()

function getApiKey() {
  return localStorage.getItem('api_key') || ''
}

const api = axios.create({ baseURL: API_BASE_URL, withCredentials: true })

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
  getRiskMetrics(isins = [], rfRate = 0.04) {
    return api.get('/etfs/risk-metrics', { params: { isins: isins.join(','), rf_rate: rfRate } })
  },
  getETFRiskMetrics(etfId, rfRate = 0.04) {
    return api.get('/etfs/risk-metrics', { params: { isins: etfId, rf_rate: rfRate } })
      .then(r => ({ ...r, data: r.data[0] ?? null }))
  },
  getPerformance(etfId, fromDate = null, toDate = null) {
    return api.get(`/etfs/${etfId}/performance`, { params: { from_date: fromDate, to_date: toDate } })
  },
  getExplanation(etfId) {
    return api.get(`/etfs/${etfId}/explain`, { params: { brand: BRAND.name } })
  },
  deleteETF(etfId) {
    return api.delete(`/etfs/${etfId}`)
  },
  deleteETFs(etfIds) {
    return api.delete('/etfs', { data: etfIds })
  }
}

export const analyticsService = {
  calculateExposure(portfolio, date = null, rfRate = 0.04) {
    return api.post('/analytics/exposure', { portfolio }, { params: { date, rf_rate: rfRate } })
  },
  getPairSuggestions(portfolio) {
    return api.post('/analytics/pair-suggestions', { portfolio })
  },
}

export const scoreService = {
  getEtfScores(isins = []) {
    const params = {}
    if (isins.length > 0) params.isins = isins.join(',')
    return api.get('/scores/etfs', { params })
  },
}

export const healthService = {
  checkHealth() {
    return api.get('/health')
  }
}

export const authService = {
  requestKey(email) {
    return api.post('/auth/request-key', null, { params: { email } })
  },
  googleSignIn(credential) {
    return api.post('/auth/google/session', { credential })
  },
  session() {
    return api.get('/auth/session')
  },
  emailStatus() {
    return api.get('/auth/email-status')
  },
  logout() {
    return api.post('/auth/logout')
  },
  me() {
    return api.get('/auth/me')
  },
  contact({ name, email, message }) {
    return api.post('/auth/contact', { name, email, message })
  }
}

export const adminService = {
  verify() {
    return api.get('/admin/verify')
  },
  importETF(symbol, csvFile = null, name = null, ter = null, isin = null) {
    const params = { symbol }
    if (isin) params.isin = isin
    if (name) params.name = name
    if (ter != null) params.ter = ter
    const config = { params }
    if (csvFile) {
      const form = new FormData()
      form.append('csv_file', csvFile)
      return api.post('/admin/import-etf', form, config)
    }
    return api.post('/admin/import-etf', null, config)
  },
  createApiKey(name, rateLimit = 60, email = null) {
    const params = { name, rate_limit_per_minute: rateLimit }
    if (email) params.email = email
    return api.post(`/admin/api-keys`, null, {
      params,
    })
  },
  initDb() {
    return api.post('/admin/init-db')
  },
  seed() {
    return api.post('/admin/seed')
  },
  reset() {
    return api.post('/admin/reset')
  },
  refreshPrices() {
    return api.post('/admin/refresh-prices')
  },
  refreshPricesStatus(jobId) {
    return api.get(`/admin/refresh-prices/status/${jobId}`)
  },
  backfillEodhdSymbols() {
    return api.post('/admin/backfill-eodhd-symbols')
  },
  refreshFxRates() {
    return api.post('/admin/refresh-fx-rates')
  },
  recalculateScores() {
    return api.post('/admin/recalculate-scores')
  },
  deleteETFs(etfIds) {
    return api.delete('/admin/etfs', { data: etfIds })
  },
  deleteETFByISIN(isin) {
    return api.delete(`/admin/etfs/by-isin/${isin}`)
  },
  requestLogs({ limit = 100, offset = 0, api_key_name = '', email = '', path = '' } = {}) {
    const params = { limit, offset }
    if (api_key_name) params.api_key_name = api_key_name
    if (email) params.email = email
    if (path) params.path = path
    return api.get('/admin/request-logs', { params })
  },
  updateETF(etfId, data) {
    return api.patch(`/admin/etfs/${etfId}`, data)
  },
  updateHolding(etfId, holdingId, data) {
    return api.patch(`/admin/etfs/${etfId}/holdings/${holdingId}`, data)
  },
  deleteHolding(etfId, holdingId) {
    return api.delete(`/admin/etfs/${etfId}/holdings/${holdingId}`)
  },
  addHolding(etfId, holdingData) {
    return api.post(`/admin/etfs/${etfId}/holdings`, holdingData)
  },
  previewImport(symbol, csvFile = null, name = null, ter = null, isin = null) {
    const params = { symbol }
    if (isin) params.isin = isin
    if (name) params.name = name
    if (ter != null) params.ter = ter
    const config = { params }
    if (csvFile) {
      const form = new FormData()
      form.append('csv_file', csvFile)
      return api.post('/admin/preview-import', form, config)
    }
    return api.post('/admin/preview-import', null, config)
  },
  uploadFactsheet(pdfFile) {
    const form = new FormData()
    form.append('file', pdfFile)
    return api.post('/admin/etf/upload-factsheet', form)
  },
  importPdfData(metadata, holdings) {
    return api.post('/admin/etf/import-data', { metadata, holdings })
  },
  importHoldings(isin, provider, holdingsFile = null, asOf = null) {
    const params = { isin, provider }
    if (asOf) params.as_of = asOf
    const config = { params }
    if (holdingsFile) {
      const form = new FormData()
      form.append('holdings_file', holdingsFile)
      return api.post('/admin/import-holdings', form, config)
    }
    return api.post('/admin/import-holdings', null, config)
  },
  importProviderMetadata(ubsFile, isharesFile) {
    const form = new FormData()
    if (ubsFile) form.append('ubs_file', ubsFile)
    if (isharesFile) form.append('ishares_file', isharesFile)
    return api.post('/admin/import-provider-metadata', form)
  },
  downloadProviderFile(provider) {
    return api.get(`/admin/provider-metadata/${provider}-file`, {
      responseType: 'blob',
    })
  },
}
