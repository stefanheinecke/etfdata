<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">ETF Explorer</h1>
      <p class="page-subtitle">Browse all tracked ETFs, inspect holdings, allocations and performance data.</p>
    </div>
    <div v-if="!apiKey" class="cta-banner">
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
          <label class="label">Replication</label>
          <select class="input" v-model="filterReplication">
            <option value="">All</option>
            <option v-for="r in filterOptions.replications" :key="r" :value="r">{{ r }}</option>
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
              <option value="domicile">Domicile</option>
              <option value="currency">Currency</option>
              <option value="replication_method">Replication</option>
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
    <div v-if="loading" class="loading"><div class="spinner"></div> Loading ETFs...</div>
    <div v-else-if="filteredETFs.length" class="etf-grid">
      <div v-for="etf in filteredETFs" :key="etf.id" class="etf-card" @click="openETF(etf)">
        <div class="etf-card-top">
          <div><span class="etf-ticker">{{ etf.ticker }}</span><span v-if="etf.provider" class="badge" style="margin-left:.5rem">{{ etf.provider }}</span></div>
          <span class="etf-ter">TER {{ etf.ter != null ? etf.ter + '%' : '—' }}</span>
        </div>
        <h3 class="etf-name">{{ etf.name }}</h3>
        <p class="etf-isin">{{ etf.isin || '' }}</p>
        <div class="etf-meta">
          <span v-if="etf.domicile">{{ etf.domicile }}</span><span v-if="etf.currency">{{ etf.currency }}</span>
          <span v-if="etf.fund_size">{{ formatSize(etf.fund_size) }}</span>
          <span v-if="etf.dividend_policy" :class="etf.dividend_policy === 'Accumulating' ? 'badge-acc' : 'badge-dist'">{{ etf.dividend_policy === 'Accumulating' ? 'Acc' : 'Dist' }}</span>
        </div>
        <div v-if="etf.replication_method" class="etf-replication">{{ etf.replication_method }}</div>
      </div>
    </div>
    <div v-else-if="!loading && !error" class="empty-state">
      <div class="empty-icon">📭</div>
      <p>No ETFs found. Make sure your API key is configured and the database is seeded.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'

const showApiKeyModal = inject('showApiKeyModal')
const navigateToETF = inject('navigateToETF')
import { etfService } from '../services/api.js'

const allETFs = ref([])
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
const filterReplication = ref('')

// Sort
const sortKey = ref('ticker')
const sortDir = ref('asc')

// Derive unique filter option lists from loaded data
const filterOptions = computed(() => {
  const uniq = (arr) => [...new Set(arr.filter(Boolean))].sort()
  return {
    providers:    uniq(allETFs.value.map(e => e.provider)),
    domiciles:    uniq(allETFs.value.map(e => e.domicile)),
    currencies:   uniq(allETFs.value.map(e => e.currency)),
    replications: uniq(allETFs.value.map(e => e.replication_method)),
  }
})

const filteredETFs = computed(() => {
  let list = allETFs.value

  const q = search.value.trim().toLowerCase()
  if (q) list = list.filter(e => e.ticker?.toLowerCase().includes(q) || e.name?.toLowerCase().includes(q))
  if (filterProvider.value)    list = list.filter(e => e.provider === filterProvider.value)
  if (filterDomicile.value)    list = list.filter(e => e.domicile === filterDomicile.value)
  if (filterCurrency.value)    list = list.filter(e => e.currency === filterCurrency.value)
  if (filterReplication.value) list = list.filter(e => e.replication_method === filterReplication.value)

  const key = sortKey.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...list].sort((a, b) => {
    const av = a[key] ?? ''
    const bv = b[key] ?? ''
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
    return String(av).localeCompare(String(bv)) * dir
  })
})

function resetFilters() {
  search.value = ''
  filterProvider.value = ''
  filterDomicile.value = ''
  filterCurrency.value = ''
  filterReplication.value = ''
  sortKey.value = 'ticker'
  sortDir.value = 'asc'
}

function formatSize(n) {
  if (n>=1e9) return (n/1e9).toFixed(1)+'B'
  if (n>=1e6) return (n/1e6).toFixed(0)+'M'
  return n.toLocaleString()
}

async function loadETFs() {
  loading.value=true; error.value=''
  try {
    const r = await etfService.getETFs(0, 100)
    allETFs.value = r.data
  } catch(e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

function openETF(etf) {
  navigateToETF(etf)
}

onMounted(loadETFs)
</script>

<style scoped>
.filters{display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-end}
.filters>div{flex:1;min-width:150px}
.sort-dir-btn{padding:.45rem .65rem;font-size:1rem;line-height:1;flex-shrink:0}
.etf-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}
.etf-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem;cursor:pointer;transition:all .2s;box-shadow:var(--shadow)}
.etf-card:hover{border-color:var(--green-400);box-shadow:var(--shadow-md);transform:translateY(-2px)}
.etf-card-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem}
.etf-ticker{font-size:1rem;font-weight:700;color:var(--green-600)}
.etf-ter{font-size:.75rem;color:var(--text-muted);font-weight:500}
.etf-name{font-size:.95rem;font-weight:600;color:var(--text);margin-bottom:.25rem;line-height:1.3}
.etf-isin{font-size:.75rem;color:var(--text-muted);font-family:monospace;margin-bottom:.75rem}
.etf-meta{display:flex;gap:.75rem;font-size:.8rem;color:var(--text-muted);flex-wrap:wrap}
.etf-replication{margin-top:.5rem;font-size:.75rem;color:var(--text-muted)}
.badge-acc{background:#d1fae5;color:#065f46;border-radius:4px;padding:1px 6px;font-size:.7rem;font-weight:600}
.badge-dist{background:#dbeafe;color:#1e40af;border-radius:4px;padding:1px 6px;font-size:.7rem;font-weight:600}
.cta-banner{display:flex;align-items:center;justify-content:space-between;gap:1rem;background:linear-gradient(135deg,#667eea15,#764ba215);border:1.5px solid #667eea55;border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.5rem;flex-wrap:wrap}
.cta-text{display:flex;flex-direction:column;gap:.2rem;font-size:.9rem}
.cta-text strong{color:var(--text)}
.cta-text span{color:var(--text-muted)}
.cta-btn{padding:.55rem 1.2rem;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;border-radius:8px;font-weight:700;font-size:.875rem;cursor:pointer;white-space:nowrap;flex-shrink:0}
.cta-btn:hover{opacity:.9}
</style>
