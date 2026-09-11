// Single source of truth for domain-based branding.
// Add a new domain here to market the same app under a different name.
const BRANDS = {
  'trueetf.com': { name: 'TrueETF', domain: 'trueetf.com' },
  'goetf.ch':    { name: 'GoETF',   domain: 'goetf.ch' },
}
const DEFAULT_BRAND = BRANDS['goetf.ch']

function resolveBrand(hostname) {
  const host = (hostname || '').toLowerCase().replace(/^www\./, '')
  return BRANDS[host] || DEFAULT_BRAND
}

export const BRAND = resolveBrand(typeof window !== 'undefined' ? window.location.hostname : '')
// Two-tone logo styling stays generic: prefix + accent-colored "ETF" (e.g. "Go"+"ETF", "True"+"ETF").
export const BRAND_PREFIX = BRAND.name.replace(/ETF$/, '')
