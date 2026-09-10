<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">ETF Explorer</h1>
      <p class="page-subtitle">Select ETFs to explore their holdings, allocations and performance together in Portfolio Exposure.</p>
    </div>
    <div v-if="!hasApiKey" class="cta-banner">
      <div class="cta-text">
        <strong>You need an API key to load ETF data.</strong>
        <span>It's free and takes 10 seconds.</span>
      </div>
      <button class="cta-btn" @click="showApiKeyModal = true">Get Free API Key</button>
    </div>
    <div class="card" style="margin-bottom:1.5rem">
      <div class="filters">
        <div>
          <label class="label">Search</label>
          <input class="input" v-model="search" placeholder="Ticker or name…" />
        </div>
        <div>
          <label class="label">Provider</label>
          <select class="input" v-model="filterProvider">
            <option value="">All</option>
            <option v-for="p in filterOptions.providers" :key="p" :value="p">{{ p }}</option>
          </select>
        </div>
        <div>
          <label class="label">Domicile</label>
          <select class="input" v-model="filterDomicile">
            <option value="">All</option>
            <option v-for="d in filterOptions.domiciles" :key="d" :value="d">{{ d }}</option>
          </select>
        </div>
        <div>
          <label class="label">Currency</label>
          <select class="input" v-model="filterCurrency">
            <option value="">All</option>
            <option v-for="c in filterOptions.currencies" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div>
          <label class="label">Dividend Policy</label>
          <select class="input" v-model="filterDividendPolicy">
            <option value="">All</option>
            <option v-for="d in filterOptions.dividendPolicies" :key="d" :value="d">{{ d }}</option>
          </select>
        </div>
        <div>
          <label class="label">Sort by</label>
          <div style="display:flex;gap:.35rem">
            <select class="input" v-model="sortKey" style="flex:1">
              <option value="ticker">Ticker</option>
              <option value="name">Name</option>
              <option value="ter">TER</option>
              <option value="fund_size">Fund Size</option>
              <option value="holdings_count">Constituents in DB</option>
              <option value="domicile">Domicile</option>
              <option value="currency">Currency</option>
              <option value="dividend_policy">Dividend Policy</option>
              <option value="benchmark">Benchmark</option>
            </select>
            <button class="btn btn-outline sort-dir-btn" @click="sortDir = sortDir === 'asc' ? 'desc' : 'asc'" :title="sortDir === 'asc' ? 'Ascending' : 'Descending'">
              {{ sortDir === 'asc' ? '↑' : '↓' }}
            </button>
          </div>
        </div>
        <div style="display:flex;align-items:flex-end;gap:.5rem">
          <button class="btn btn-primary" @click="loadETFs" :disabled="loading">
            <span v-if="loading" class="spinner" style="width:14px;height:14px;border-width:2px"></span>
            {{ loading ? 'Loading…' : 'Refresh' }}
          </button>
          <button class="btn btn-outline" @click="resetFilters" title="Clear filters">✕</button>
        </div>
      </div>
      <div v-if="filteredETFs.length !== allETFs.length" style="margin-top:.75rem;font-size:.8rem;color:var(--text-muted)">
        Showing {{ filteredETFs.length }} of {{ allETFs.length }} ETFs
      </div>
    </div>
    <div v-if="error" class="error-box" style="margin-bottom:1.5rem">{{ error }}</div>
    <div v-if="selectedETFs.length" class="selection-bar">
      <span role="status">{{ selectedETFs.length }} ETF{{ selectedETFs.length === 1 ? '' : 's' }} selected</span>
      <div class="selection-actions">
        <button class="btn btn-outline" @click="selectedIds = []">Clear selection</button>
        <button class="btn btn-primary" @click="useForPortfolio" :disabled="loading">Use for Portfolio Exposure</button>
      </div>
    </div>
    <div v-if="loading" class="loading"><div class="spinner"></div> Loading ETFs...</div>
    <div v-else-if="filteredETFs.length" class="etf-grid">
      <div v-for="etf in paginatedETFs" :key="etf.id" class="etf-card" :class="{ 'is-selected': selectedIds.includes(etf.id) }" @click="toggleETF(etf.id)">
        <label class="etf-selection" @click.stop>
          <input type="checkbox" v-model="selectedIds" :value="etf.id" :aria-label="'Select ' + etf.isin + ' — ' + etf.name" />
          {{ selectedIds.includes(etf.id) ? 'Selected' : 'Select for portfolio' }}
        </label>
        <div class="etf-card-top">
          <div><span class="etf-ticker">{{ etf.isin }}</span><span v-if="etf.provider" class="badge" style="margin-left:.5rem">{{ etf.provider }}</span></div>
          <span class="etf-ter">TER {{ etf.ter != null ? etf.ter + '%' : '—' }}</span>
        </div>
        <h3 class="etf-name">{{ etf.name }}</h3>
        <p class="etf-isin">{{ etf.isin || '' }}</p>
        <div class="etf-meta">
          <span v-if="etf.domicile">{{ etf.domicile }}</span><span v-if="etf.currency">{{ etf.currency }}</span>
          <span v-if="etf.fund_size" :title="'Fund size in ETF currency (' + etf.currency + ')'">{{ formatSize(etf.fund_size) }}</span>
          <span v-if="etf.fund_size_usd" title="Fund size in USD" style="color:var(--text-muted)">(≈ {{ formatSize(etf.fund_size_usd) }} USD)</span>
          <span v-if="etf.dividend_policy" :class="etf.dividend_policy === 'Accumulating' ? 'badge-acc' : 'badge-dist'">{{ etf.dividend_policy === 'Accumulating' ? 'Acc' : 'Dist' }}</span>
        </div>
        <div class="etf-constituents" title="Number of holdings stored in the database for the latest available date. Historical snapshots are not added together.">
          <span>Constituents in DB</span>
          <strong>{{ (etf.holdings_count ?? 0).toLocaleString() }}</strong>
        </div>
        <div v-if="etf.replication_method" class="etf-replication">{{ etf.replication_method }}</div>
      </div>
    </div>
    <div v-if="!loading && filteredETFs.length" class="pagination">
      <button class="btn btn-outline" @click="currentPage--" :disabled="currentPage <= 1">‹ Prev</button>
      <span>Page {{ currentPage }} of {{ totalPages }} ({{ pageRangeLabel }})</span>
      <button class="btn btn-outline" @click="currentPage++" :disabled="currentPage >= totalPages">Next ›</button>
    </div>
    <div v-else-if="!loading && !error" class="empty-state">
      <div class="empty-icon">📭</div>
      <p>No ETFs found. Make sure your API key is configured and the database is seeded.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, inject } from 'vue'

const showApiKeyModal = inject('showApiKeyModal')
const navigateToPortfolio = inject('navigateToPortfolio')
const hasApiKey = inject('hasApiKey', ref(!!localStorage.getItem('api_key')))
import { etfService } from '../services/api.js'

const allETFs = ref([])
const selectedIds = ref([])
const selectedETFs = computed(() => allETFs.value.filter(etf => selectedIds.value.includes(etf.id)))
const loading = ref(false)
const error = ref('')
const apiKey = ref(localStorage.getItem('api_key') || '')
// Refresh apiKey when the Get API Key modal saves a new one
window.addEventListener('storage', (e) => { if (e.key === 'api_key') { apiKey.value = e.newValue || ''; if (e.newValue) loadETFs() } })
// Refresh apiKey when modal saves a new one
window.addEventListener('storage', (e) => { if (e.key === 'api_key') apiKey.value = e.newValue || '' })

// Filters
const search = ref('')
const filterProvider = ref('')
const filterDomicile = ref('')
const filterCurrency = ref('')
const filterDividendPolicy = ref('')

// Sort
const sortKey = ref('ticker')
const sortDir = ref('asc')

// Pagination (client-side, over the full fetched + filtered set)
const currentPage = ref(1)
const pageSize = 60

// Derive unique filter option lists from loaded data
const filterOptions = computed(() => {
  const uniq = (arr) => [...new Set(arr.filter(Boolean))].sort()
  return {
    providers:        uniq(allETFs.value.map(e => e.provider)),
    domiciles:        uniq(allETFs.value.map(e => e.domicile)),
    currencies:       uniq(allETFs.value.map(e => e.currency)),
    dividendPolicies: uniq(allETFs.value.map(e => e.dividend_policy)),
  }
})

const filteredETFs = computed(() => {
  let list = allETFs.value

  const q = search.value.trim().toLowerCase()
  if (q) list = list.filter(e => e.isin?.toLowerCase().includes(q) || e.name?.toLowerCase().includes(q))
  if (filterProvider.value)        list = list.filter(e => e.provider === filterProvider.value)
  if (filterDomicile.value)        list = list.filter(e => e.domicile === filterDomicile.value)
  if (filterCurrency.value)        list = list.filter(e => e.currency === filterCurrency.value)
  if (filterDividendPolicy.value)  list = list.filter(e => e.dividend_policy === filterDividendPolicy.value)

  const key = sortKey.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  // Fund size varies by ETF currency, so sort on the USD-normalized value instead
  const getVal = (e) => {
    if (key === 'holdings_count') return Number(e.holdings_count ?? 0)
    if (key === 'fund_size') return e.fund_size_usd ?? e.fund_size ?? ''
    return e[key] ?? ''
  }
  return [...list].sort((a, b) => {
    const av = getVal(a)
    const bv = getVal(b)
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
    return String(av).localeCompare(String(bv)) * dir
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredETFs.value.length / pageSize)))
const paginatedETFs = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredETFs.value.slice(start, start + pageSize)
})
const pageRangeLabel = computed(() => {
  if (!filteredETFs.value.length) return '0 of 0'
  const start = (currentPage.value - 1) * pageSize + 1
  const end = Math.min(start + pageSize - 1, filteredETFs.value.length)
  return `${start}–${end} of ${filteredETFs.value.length}`
})

// Jump back to page 1 whenever the filtered/sorted set changes shape
watch([search, filterProvider, filterDomicile, filterCurrency, filterDividendPolicy, sortKey, sortDir], () => {
  currentPage.value = 1
})

function resetFilters() {
  search.value = ''
  filterProvider.value = ''
  filterDomicile.value = ''
  filterCurrency.value = ''
  filterDividendPolicy.value = ''
  sortKey.value = 'ticker'
  sortDir.value = 'asc'
  currentPage.value = 1
}

function formatSize(n) {
  if (n>=1e9) return (n/1e9).toFixed(1)+'B'
  if (n>=1e6) return (n/1e6).toFixed(0)+'M'
  return n.toLocaleString()
}

async function loadETFs() {
  loading.value=true; error.value=''
  try {
    const r = await etfService.getETFs(0, 5000)
    allETFs.value = r.data
    const availableIds = new Set(allETFs.value.map(etf => etf.id))
    selectedIds.value = selectedIds.value.filter(id => availableIds.has(id))
    currentPage.value = 1
  } catch(e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

function toggleETF(id) {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter(selectedId => selectedId !== id)
    : [...selectedIds.value, id]
}

function useForPortfolio() {
  if (selectedETFs.value.length) navigateToPortfolio(selectedETFs.value)
}

onMounted(loadETFs)
</script>

<style scoped>
.filters{display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-end}
.filters>div{flex:1;min-width:150px}
.sort-dir-btn{padding:.45rem .65rem;font-size:1rem;line-height:1;flex-shrink:0}
.etf-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}
.etf-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem;cursor:pointer;transition:all .2s;box-shadow:var(--shadow)}
.etf-card:hover{border-color:#1a6ab8;box-shadow:var(--shadow-md);transform:translateY(-2px)}
.etf-card.is-selected{border-color:#0f4c81;box-shadow:0 0 0 2px rgba(15,76,129,.2)}
.etf-card:focus-within{outline:2px solid #1a6ab8;outline-offset:3px}
.etf-selection{display:flex;align-items:center;gap:.5rem;margin-bottom:.85rem;font-size:.8rem;color:var(--text-muted);cursor:pointer;width:fit-content}
.etf-selection input{width:17px;height:17px;accent-color:#0f4c81;cursor:pointer}
.selection-bar{display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap;margin-bottom:1rem;padding:1rem 1.25rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)}
.selection-bar>span{font-weight:600;color:var(--text)}
.selection-actions{display:flex;gap:.5rem;flex-wrap:wrap}
.etf-card-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem}
.etf-ticker{font-size:1rem;font-weight:700;color:#0f4c81}
.etf-ter{font-size:.75rem;color:var(--text-muted);font-weight:500}
.etf-name{font-size:.95rem;font-weight:600;color:var(--text);margin-bottom:.25rem;line-height:1.3}
.etf-isin{font-size:.75rem;color:var(--text-muted);font-family:monospace;margin-bottom:.75rem}
.etf-meta{display:flex;gap:.75rem;font-size:.8rem;color:var(--text-muted);flex-wrap:wrap}
.etf-constituents{display:flex;justify-content:space-between;align-items:center;margin-top:.85rem;padding-top:.65rem;border-top:1px solid var(--border);font-size:.8rem;color:var(--text-muted)}
.etf-constituents strong{color:var(--text);font-variant-numeric:tabular-nums}
.etf-replication{margin-top:.5rem;font-size:.75rem;color:var(--text-muted)}
.pagination{display:flex;align-items:center;justify-content:center;gap:1rem;margin-top:1.5rem;font-size:.85rem;color:var(--text-muted)}
.badge-acc{background:rgba(0,201,167,.12);color:#009f86;border-radius:4px;padding:1px 6px;font-size:.7rem;font-weight:600}
.badge-dist{background:rgba(15,76,129,.1);color:#0f4c81;border-radius:4px;padding:1px 6px;font-size:.7rem;font-weight:600}
.cta-banner{display:flex;align-items:center;justify-content:space-between;gap:1rem;background:var(--surface);border:1.5px solid var(--border);border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.5rem;flex-wrap:wrap;box-shadow:var(--shadow)}
.cta-text{display:flex;flex-direction:column;gap:.2rem;font-size:.9rem}
.cta-text strong{color:var(--text)}
.cta-text span{color:var(--text-muted)}
.cta-btn{padding:.55rem 1.2rem;background:#0f4c81;color:#fff;border:none;border-radius:8px;font-weight:700;font-size:.875rem;cursor:pointer;white-space:nowrap;flex-shrink:0}
.cta-btn:hover{background:#1a6ab8}
</style>
