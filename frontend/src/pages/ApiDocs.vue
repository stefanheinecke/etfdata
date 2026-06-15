<template>
  <div class="page">
    <div class="page-header">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;flex-wrap:wrap">
        <div>
          <h1 class="page-title">API Reference</h1>
          <p class="page-subtitle">Complete documentation for all ETF Data API endpoints.</p>
        </div>
        <button class="btn btn-primary" style="flex-shrink:0;margin-top:.25rem" @click="showApiKeyModal = true">
          Get API Key
        </button>
      </div>
    </div>

    <!-- No-key banner -->
    <div v-if="!hasApiKey" class="key-banner">
      <span>🔑 You don't have an API key yet — all endpoints require one.</span>
      <button class="btn btn-primary btn-sm" @click="showApiKeyModal = true">Get a free key</button>
    </div>

    <div class="docs-layout">
      <!-- Sidebar -->
      <nav class="docs-nav">
        <div class="docs-nav-section" v-for="group in groups" :key="group.label">
          <div class="docs-nav-label">{{ group.label }}</div>
          <button v-for="ep in group.endpoints" :key="ep.id"
            :class="['docs-nav-item',{active:activeId===ep.id}]" @click="activeId=ep.id">
            <span :class="['method-badge','method-'+ep.method.toLowerCase()]">{{ ep.method }}</span>
            {{ ep.short }}
          </button>
        </div>
      </nav>

      <!-- Content -->
      <div class="docs-content">
        <div v-if="active">
          <div class="ep-header">
            <span :class="['method-badge-lg','method-'+active.method.toLowerCase()]">{{ active.method }}</span>
            <code class="ep-path">{{ active.path }}</code>
          </div>
          <h2 class="ep-title">{{ active.title }}</h2>
          <p class="ep-desc">{{ active.desc }}</p>

          <!-- Auth -->
          <div class="doc-section">
            <h3 class="doc-section-title">Authentication</h3>
            <p class="doc-section-body">All endpoints require an API key passed as a request header:</p>
            <pre>x-api-key: YOUR_API_KEY</pre>
          </div>

          <!-- Parameters -->
          <div v-if="active.params?.length" class="doc-section">
            <h3 class="doc-section-title">Parameters</h3>
            <div class="table-wrap">
              <table>
                <thead><tr><th>Name</th><th>In</th><th>Type</th><th>Required</th><th>Description</th></tr></thead>
                <tbody>
                  <tr v-for="p in active.params" :key="p.name">
                    <td><code>{{ p.name }}</code></td>
                    <td><span class="badge">{{ p.in }}</span></td>
                    <td>{{ p.type }}</td>
                    <td>{{ p.required ? '✓' : '—' }}</td>
                    <td style="color:var(--text-muted)">{{ p.desc }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Request body -->
          <div v-if="active.body" class="doc-section">
            <h3 class="doc-section-title">Request Body</h3>
            <pre>{{ active.body }}</pre>
          </div>

          <!-- Response -->
          <div v-if="active.response" class="doc-section">
            <h3 class="doc-section-title">Example Response</h3>
            <pre>{{ active.response }}</pre>
          </div>

          <!-- Try it out -->
          <div v-if="activeTryoutConfig" class="doc-section">
            <h3 class="doc-section-title">
              Try it out
              <code class="demo-key-pill">x-api-key: demo</code>
            </h3>
            <p class="doc-section-body">
              Executes a live request using the public demo key — returns SWDA data only.
            </p>
            <button class="btn btn-primary try-btn" :disabled="activeTryout.loading" @click="runTryout">
              {{ activeTryout.loading ? 'Loading\u2026' : '\u25b6\u2002Execute' }}
            </button>
            <transition name="fade">
              <div v-if="activeTryout.result || activeTryout.error" class="tryout-response">
                <div class="tryout-resp-header">
                  <span :class="['tryout-status-badge',
                    (activeTryout.status >= 200 && activeTryout.status < 300) ? 'status-ok' : 'status-err']">
                    {{ activeTryout.status }}
                  </span>
                  <span class="tryout-live-label">live response</span>
                </div>
                <pre v-if="activeTryout.result" class="tryout-pre">{{ activeTryout.result }}</pre>
                <div v-if="activeTryout.error" class="tryout-error-msg">{{ activeTryout.error }}</div>
              </div>
            </transition>
          </div>
        </div>
      </div>
    </div>

    <!-- General info -->
    <div class="card" style="margin-top:2rem">
      <h2 class="card-title">Base URL & Authentication</h2>
      <div class="grid-2">
        <div>
          <p class="label">Base URL</p>
          <pre style="margin-top:.35rem">https://etfdata-production.up.railway.app</pre>
        </div>
        <div>
          <p class="label">Rate Limiting</p>
          <p style="font-size:.875rem;color:var(--text-muted);margin-top:.35rem">Default: 60 requests/minute per API key. Configurable per key via the admin endpoint.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'
import axios from 'axios'
const BASE = 'https://etfdata-production.up.railway.app'

const showApiKeyModal = inject('showApiKeyModal')
const hasApiKey = ref(!!localStorage.getItem('api_key'))
window.addEventListener('storage', e => { if (e.key === 'api_key') hasApiKey.value = !!e.newValue })
const activeId = ref('list-etfs')

const groups = [
  {
    label: 'ETFs',
    endpoints: [
      { id: 'list-etfs', method: 'GET', short: '/etfs', path: '/etfs',
        title: 'List ETFs', desc: 'Returns a paginated list of all tracked ETFs with optional provider filter.',
        params: [
          {name:'skip',in:'query',type:'integer',required:false,desc:'Number of records to skip (default 0)'},
          {name:'limit',in:'query',type:'integer',required:false,desc:'Max records to return (default 50)'},
          {name:'provider',in:'query',type:'string',required:false,desc:'Filter by provider name'},
        ],
        response: `[\n  {\n    "id": "uuid",\n    "isin": "IE00B4L5Y983",\n    "ticker": "VWRL",\n    "name": "Vanguard FTSE All-World",\n    "provider": "Vanguard",\n    "ter": 0.22,\n    "fund_size": 15000000000,\n    "currency": "EUR"\n  }\n]`,
      },
      { id: 'get-etf', method: 'GET', short: '/etfs/{id}', path: '/etfs/{etf_id}',
        title: 'Get ETF by ID', desc: 'Returns full details of a single ETF.',
        params: [{name:'etf_id',in:'path',type:'UUID',required:true,desc:'The ETF UUID'}],

      },
      { id: 'holdings', method: 'GET', short: '/etfs/{id}/holdings', path: '/etfs/{etf_id}/holdings',
        title: 'Get Holdings', desc: 'Returns all holdings for an ETF on a given date (defaults to latest available date).',
        params: [
          {name:'etf_id',in:'path',type:'UUID',required:true,desc:'The ETF UUID'},
          {name:'date',in:'query',type:'date',required:false,desc:'Date in YYYY-MM-DD format'},
        ],
        response: `[\n  {\n    "id": "uuid",\n    "instrument_isin": "US0378331005",\n    "instrument_name": "Apple Inc.",\n    "weight": 4.23,\n    "country": "US",\n    "sector": "Technology"\n  }\n]`,
      },
      { id: 'allocations', method: 'GET', short: '/etfs/{id}/allocations', path: '/etfs/{etf_id}/allocations',
        title: 'Get Allocations', desc: 'Returns sector, country and currency allocations for an ETF.',
        params: [
          {name:'etf_id',in:'path',type:'UUID',required:true,desc:'The ETF UUID'},
          {name:'type',in:'query',type:'string',required:false,desc:'Filter: sector | country | currency'},
          {name:'date',in:'query',type:'date',required:false,desc:'Date in YYYY-MM-DD format'},
        ],

      },
    ]
  },
  {
    label: 'Analytics',
    endpoints: [
      { id: 'overlap-post', method: 'POST', short: '/analytics/overlap', path: '/analytics/overlap',
        title: 'Multi-ETF Overlap', desc: 'Calculates the holdings overlap matrix between multiple ETFs.',
        body: `{\n  "etf_ids": ["uuid-a", "uuid-b", "uuid-c"],\n  "date": "2026-05-24"  // optional\n}`,
        response: `{\n  "matrix": {\n    "uuid-a": {\n      "uuid-b": {"common_count":14,"overlap_percentage":46.7}\n    }\n  },\n  "common_holdings": [\n    {"isin":"US0378331005","name":"Apple Inc."}\n  ]\n}`,
      },
      { id: 'overlap-get', method: 'GET', short: '/analytics/overlap/{a}/{b}', path: '/analytics/overlap/{etf_a}/{etf_b}',
        title: 'Pairwise Overlap', desc: 'Quick overlap calculation between exactly two ETFs.',
        params: [
          {name:'etf_a',in:'path',type:'UUID',required:true,desc:'First ETF UUID'},
          {name:'etf_b',in:'path',type:'UUID',required:true,desc:'Second ETF UUID'},
          {name:'date',in:'query',type:'date',required:false,desc:'Date in YYYY-MM-DD format'},
        ],

      },
      { id: 'exposure', method: 'POST', short: '/analytics/exposure', path: '/analytics/exposure',
        title: 'Portfolio Exposure', desc: 'Analyses the combined sector, country and currency exposure of a weighted portfolio of ETFs.',
        body: `{\n  "portfolio": [\n    {"etf_id": "uuid-a", "weight": 60},\n    {"etf_id": "uuid-b", "weight": 40}\n  ]\n}`,
        response: `{\n  "sectors": {"Technology": 28.4, "Healthcare": 12.1},\n  "countries": {"US": 65.2, "DE": 8.3},\n  "currencies": {"USD": 70.1, "EUR": 18.2}\n}`,
      },
      { id: 'similar', method: 'GET', short: '/analytics/similar/{id}', path: '/analytics/similar/{etf_id}',
        title: 'Find Similar ETFs', desc: 'Returns the top N most similar ETFs to a reference ETF based on holdings overlap.',
        params: [
          {name:'etf_id',in:'path',type:'UUID',required:true,desc:'Reference ETF UUID'},
          {name:'top_n',in:'query',type:'integer',required:false,desc:'Number of results (default 5)'},
        ],

      },
    ]
  }
]

const allEndpoints = computed(() => groups.flatMap(g => g.endpoints))
const active = computed(() => allEndpoints.value.find(e => e.id === activeId.value))

// ── Try it out ─────────────────────────────────────────────────────────────
const swdaId = ref(null)

async function fetchSwdaId() {
  if (swdaId.value) return swdaId.value
  try {
    const res = await axios.get(`${BASE}/etfs`, { headers: { 'x-api-key': 'demo' } })
    swdaId.value = res.data[0]?.id ?? null
  } catch {}
  return swdaId.value
}

const tryoutConfigs = {
  'list-etfs':    { build: ()    => ({ method: 'GET',  url: `${BASE}/etfs` }) },
  'get-etf':      { build: (id)  => ({ method: 'GET',  url: `${BASE}/etfs/${id}` }) },
  'holdings':     { build: (id)  => ({ method: 'GET',  url: `${BASE}/etfs/${id}/holdings` }) },
  'allocations':  { build: (id)  => ({ method: 'GET',  url: `${BASE}/etfs/${id}/allocations` }) },
  'overlap-post': { build: (id)  => ({ method: 'POST', url: `${BASE}/analytics/overlap`,
                                        body: { etf_ids: [id, id] } }) },
  'overlap-get':  { build: (id)  => ({ method: 'GET',  url: `${BASE}/analytics/overlap/${id}/${id}` }) },
  'exposure':     { build: (id)  => ({ method: 'POST', url: `${BASE}/analytics/exposure`,
                                        body: { portfolio: [{ etf_id: id, weight: 100 }] } }) },
  'similar':      { build: (id)  => ({ method: 'GET',  url: `${BASE}/analytics/similar/${id}` }) },
}

const activeTryoutConfig = computed(() => tryoutConfigs[activeId.value])

const tryoutStates = ref({})

function getTryoutState(id) {
  if (!tryoutStates.value[id])
    tryoutStates.value[id] = { loading: false, status: null, result: null, error: null }
  return tryoutStates.value[id]
}

const activeTryout = computed(() => getTryoutState(activeId.value))

async function runTryout() {
  const cfg = activeTryoutConfig.value
  if (!cfg) return
  const state = getTryoutState(activeId.value)
  state.loading = true
  state.result = null
  state.error  = null
  state.status = null
  try {
    const id  = await fetchSwdaId()
    const req = cfg.build(id)
    const axiosCfg = { method: req.method, url: req.url, headers: { 'x-api-key': 'demo' } }
    if (req.body) { axiosCfg.data = req.body; axiosCfg.headers['Content-Type'] = 'application/json' }
    if (req.params) axiosCfg.params = req.params
    const res  = await axios(axiosCfg)
    state.status = res.status
    const data = res.data
    if (Array.isArray(data) && data.length > 5)
      state.result = JSON.stringify(data.slice(0, 5), null, 2) + `\n// … ${data.length - 5} more items`
    else
      state.result = JSON.stringify(data, null, 2)
  } catch (e) {
    state.status = e?.response?.status ?? 0
    state.error  = e?.response?.data?.detail ?? e.message ?? 'Request failed'
  } finally {
    state.loading = false
  }
}
</script>

<style scoped>
.key-banner {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
  background: var(--green-50); border: 1px solid var(--green-200); border-radius: var(--radius);
  padding: .75rem 1.25rem; margin-bottom: 1.5rem; font-size: .875rem; color: var(--green-700);
}
[data-theme="dark"] .key-banner { background: #052e16; border-color: #14532d; color: #86efac; }
.btn-sm { padding: .35rem .85rem; font-size: .8rem; }
.docs-layout { display: grid; grid-template-columns: 240px 1fr; gap: 2rem; align-items: start; }
@media(max-width:700px) { .docs-layout { grid-template-columns: 1fr; } }
.docs-nav { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 1rem; position: sticky; top: 80px; }
.docs-nav-section { margin-bottom: 1.25rem; }
.docs-nav-label { font-size: .7rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: .08em; padding: 0 .5rem; margin-bottom: .35rem; }
.docs-nav-item { display: flex; align-items: center; gap: .5rem; width: 100%; background: none; border: none; cursor: pointer; padding: .4rem .5rem; border-radius: 6px; font-size: .8rem; color: var(--text-2); text-align: left; transition: all .15s; font-family: inherit; }
.docs-nav-item:hover { background: var(--bg-3); color: var(--text); }
.docs-nav-item.active { background: var(--green-100); color: var(--green-700); font-weight: 600; }
.docs-content { min-width: 0; }
.ep-header { display: flex; align-items: center; gap: .75rem; margin-bottom: .75rem; }
.ep-path { font-size: 1rem; }
.ep-title { font-size: 1.3rem; font-weight: 700; color: var(--text); margin-bottom: .5rem; }
.ep-desc { color: var(--text-muted); font-size: .9rem; margin-bottom: 1.5rem; line-height: 1.6; }
.doc-section { margin-bottom: 1.5rem; }
.doc-section-title { font-size: .85rem; font-weight: 600; color: var(--text); text-transform: uppercase; letter-spacing: .05em; margin-bottom: .75rem; padding-bottom: .5rem; border-bottom: 1px solid var(--border); }
.doc-section-body { font-size: .875rem; color: var(--text-muted); margin-bottom: .75rem; }
.method-badge { display: inline-block; padding: .1rem .45rem; border-radius: 4px; font-size: .7rem; font-weight: 700; letter-spacing: .03em; }
.method-badge-lg { display: inline-block; padding: .3rem .7rem; border-radius: 6px; font-size: .85rem; font-weight: 700; letter-spacing: .03em; }
.method-get { background: #dbeafe; color: #1d4ed8; }
.method-post { background: #dcfce7; color: #15803d; }
.method-delete { background: #fee2e2; color: #dc2626; }
[data-theme="dark"] .method-get { background: #1e3a8a; color: #93c5fd; }
[data-theme="dark"] .method-post { background: #14532d; color: #86efac; }
.code-tabs { display: flex; gap: .25rem; }
.code-tab { background: none; border: 1px solid var(--border); cursor: pointer; padding: .3rem .75rem; border-radius: 6px; font-size: .8rem; font-weight: 500; color: var(--text-muted); transition: all .15s; font-family: inherit; }
.code-tab.active { background: var(--green-500); border-color: var(--green-500); color: #fff; }

/* Try it out */
.try-btn { width: fit-content; margin-bottom: .75rem; }
.demo-key-pill {
  display: inline-block; background: var(--green-50); border: 1px solid var(--green-200);
  color: var(--green-700); padding: .1rem .5rem; border-radius: 20px;
  font-size: .75rem; font-weight: 600; letter-spacing: .04em; margin-left: .5rem;
  vertical-align: middle;
}
[data-theme="dark"] .demo-key-pill { background: #0d2d0d; border-color: #1a4d1a; color: #4ade80; }
.tryout-response { display: flex; flex-direction: column; gap: .5rem; }
.tryout-resp-header { display: flex; align-items: center; gap: .75rem; }
.tryout-status-badge {
  display: inline-block; font-size: .75rem; font-weight: 700;
  padding: .15rem .55rem; border-radius: 4px;
}
.status-ok  { background: var(--green-50); border: 1px solid var(--green-200); color: var(--green-700); }
.status-err { background: #fee2e2; border: 1px solid #fecaca; color: #dc2626; }
[data-theme="dark"] .status-ok  { background: #0d2d0d; border-color: #1a4d1a; color: #4ade80; }
[data-theme="dark"] .status-err { background: #2d0a0a; border-color: #7f1d1d; color: #f87171; }
.tryout-live-label { font-size: .75rem; color: var(--text-muted); }
.tryout-pre {
  background: var(--bg-3); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 1rem 1.25rem; overflow-x: auto; font-size: .78rem; line-height: 1.6;
  max-height: 420px; overflow-y: auto; white-space: pre; color: var(--text);
}
.tryout-error-msg {
  color: #dc2626; background: #fef2f2; border: 1px solid #fecaca;
  border-radius: 8px; padding: .65rem 1rem; font-size: .875rem;
}
[data-theme="dark"] .tryout-error-msg { background: #2d0a0a; border-color: #7f1d1d; color: #f87171; }
.fade-enter-active { transition: opacity .3s, transform .3s; }
.fade-enter-from { opacity: 0; transform: translateY(-4px); }
</style>
