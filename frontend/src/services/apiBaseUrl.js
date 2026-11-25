import { BRAND } from '../brand.js'

const brandApiUrl = `https://api.${BRAND.domain}`
const knownCrossSiteApiHosts = new Set([
  'etfdata-production.up.railway.app',
  'api.goetf.ch',
  'api.trueetf.com',
])

export function getApiBaseUrl() {
  const configuredUrl = import.meta.env.VITE_API_URL?.trim().replace(/\/+$/, '')
  if (!configuredUrl) return brandApiUrl

  const configuredHost = new URL(configuredUrl, window.location.origin).hostname.toLowerCase()
  return knownCrossSiteApiHosts.has(configuredHost) ? brandApiUrl : configuredUrl
}
