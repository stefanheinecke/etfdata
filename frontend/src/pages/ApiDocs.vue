<template>
  <div class="page">
    <div class="page-header">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;flex-wrap:wrap">
        <div>
          <h1 class="page-title">API Reference</h1>
          <p class="page-subtitle">Complete documentation for all GoETF.ch API endpoints.</p>
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

          <!-- Code Example -->
          <div v-if="codeSnippets[activeId]" class="doc-section">
            <h3 class="doc-section-title">Code Example</h3>
            <div class="code-tabs" style="margin-bottom:.75rem">
              <button v-for="lang in ['cURL','Python','JavaScript']" :key="lang"
                :class="['code-tab', { active: activeCodeTab === lang }]"
                @click="activeCodeTab = lang">{{ lang }}</button>
            </div>
            <pre>{{ activeCodeSnippet }}</pre>
          </div>

          <!-- Try it out -->
          <div v-if="activeTryoutConfig" class="doc-section">
            <h3 class="doc-section-title">
              Live Response
              <code class="demo-key-pill">x-api-key: demo</code>
            </h3>
            <div class="tryout-response">
              <div v-if="activeTryout.loading" style="display:flex;align-items:center;gap:.6rem;color:var(--text-muted);font-size:.875rem;padding:.35rem 0">
                <div class="spinner" style="width:14px;height:14px;border-width:2px"></div> Loading live data…
              </div>
              <template v-else-if="activeTryout.result || activeTryout.error">
                <div class="tryout-resp-header">
                  <span :class="['tryout-status-badge',
                    (activeTryout.status >= 200 && activeTryout.status < 300) ? 'status-ok' : 'status-err']">
                    {{ activeTryout.status }}
                  </span>
                  <span class="tryout-live-label">live · SWDA · demo key</span>
                  <button class="refresh-btn" @click="runTryout" :disabled="activeTryout.loading" title="Re-run">↺ Refresh</button>
                </div>
                <pre v-if="activeTryout.result" class="tryout-pre">{{ activeTryout.result }}</pre>
                <div v-if="activeTryout.error" class="tryout-error-msg">{{ activeTryout.error }}</div>
              </template>
            </div>
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
          <pre style="margin-top:.35rem">https://api.goetf.ch</pre>
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
import { ref, computed, inject, watch } from 'vue'
import axios from 'axios'
const BASE = import.meta.env.VITE_API_URL || 'https://etfdata-production.up.railway.app'

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
      },
      { id: 'get-etf', method: 'GET', short: '/etfs/{id}', path: '/etfs/{etf_id}',
        title: 'Get ETF by ID', desc: 'Returns full details of a single ETF.',
        params: [{name:'etf_id',in:'path',type:'string',required:true,desc:'ETF UUID or ticker symbol (e.g. SWDA)'}],
      },
      { id: 'holdings', method: 'GET', short: '/etfs/{id}/holdings', path: '/etfs/{etf_id}/holdings',
        title: 'Get Holdings', desc: 'Returns all holdings for an ETF on a given date (defaults to latest available date).',
        params: [
          {name:'etf_id',in:'path',type:'string',required:true,desc:'ETF UUID or ticker symbol (e.g. SWDA)'},
          {name:'date',in:'query',type:'date',required:false,desc:'Date in YYYY-MM-DD format'},
        ],
      },
      { id: 'allocations', method: 'GET', short: '/etfs/{id}/allocations', path: '/etfs/{etf_id}/allocations',
        title: 'Get Allocations', desc: 'Returns sector, country and currency allocations for an ETF.',
        params: [
          {name:'etf_id',in:'path',type:'string',required:true,desc:'ETF UUID or ticker symbol (e.g. SWDA)'},
          {name:'type',in:'query',type:'string',required:false,desc:'Filter: sector | country | currency'},
          {name:'date',in:'query',type:'date',required:false,desc:'Date in YYYY-MM-DD format'},
        ],
      },
      { id: 'etf-risk-metrics', method: 'GET', short: '/etfs/{id}/risk-metrics', path: '/etfs/{etf_id}/risk-metrics',
        title: 'ETF Risk Metrics', desc: 'Returns annualised risk statistics (volatility, Sharpe ratio, max drawdown, HHI) computed from 1-year price history for a single ETF.',
        params: [
          {name:'etf_id',in:'path',type:'string',required:true,desc:'ETF UUID or ticker symbol (e.g. SWDA)'},
          {name:'rf_rate',in:'query',type:'float',required:false,desc:'Annual risk-free rate as decimal (default 0.04 = 4%)'},
        ],
      },
    ]
  },
  {
    label: 'Analytics',
    endpoints: [
      { id: 'exposure', method: 'POST', short: '/analytics/exposure', path: '/analytics/exposure',
        title: 'Portfolio Exposure & Risk', desc: 'Analyses a weighted portfolio of ETFs. Returns sector, country and currency exposure breakdown plus per-ETF risk metrics (volatility, Sharpe, max drawdown, HHI) and a portfolio-level weighted summary.',
        body: `{\n  "portfolio": [\n    {"etf_id": "SWDA", "weight": 60},  // UUID or ticker\n    {"etf_id": "CSSPX", "weight": 40}\n  ]\n}`,
        params: [
          {name:'rf_rate',in:'query',type:'float',required:false,desc:'Annual risk-free rate as decimal for Sharpe (default 0.04 = 4%)'},
        ],
      },
    ]
  }
]

const allEndpoints = computed(() => groups.flatMap(g => g.endpoints))
const active = computed(() => allEndpoints.value.find(e => e.id === activeId.value))

// ── Try it out ─────────────────────────────────────────────────────────────
const swdaId = ref(null)
const secondEtfId = ref(null)

async function fetchEtfIds() {
  if (swdaId.value) return
  // Always use the demo key for swdaId — demo always returns SWDA, so all single-ETF
  // demos work with the demo key used in runTryout.
  try {
    const demoRes = await axios.get(`${BASE}/etfs`, { headers: { 'x-api-key': 'demo' } })
    swdaId.value = demoRes.data[0]?.id ?? null
  } catch {}
  // For the exposure demo (2 ETFs), try to pick a second ETF via the user's own key.
  const userKey = localStorage.getItem('api_key')
  if (userKey && swdaId.value) {
    try {
      const res = await axios.get(`${BASE}/etfs`, { headers: { 'x-api-key': userKey }, params: { limit: 10 } })
      secondEtfId.value = res.data.find(e => e.id !== swdaId.value)?.id ?? swdaId.value
    } catch {}
  }
  if (!secondEtfId.value) secondEtfId.value = swdaId.value
}

const tryoutConfigs = {
  'list-etfs':    { build: ()    => ({ method: 'GET',  url: `${BASE}/etfs` }) },
  'get-etf':      { build: (id)  => ({ method: 'GET',  url: `${BASE}/etfs/${id}` }) },
  'holdings':     { build: (id)  => ({ method: 'GET',  url: `${BASE}/etfs/${id}/holdings` }) },
  'allocations':  { build: (id)  => ({ method: 'GET',  url: `${BASE}/etfs/${id}/allocations` }) },
  'exposure':          { build: (id, id2) => ({ method: 'POST', url: `${BASE}/analytics/exposure`,
                                        body: { portfolio: [{ etf_id: id, weight: 60 }, { etf_id: id2, weight: 40 }] } }) },
  'etf-risk-metrics':  { build: (id) => ({ method: 'GET',  url: `${BASE}/etfs/${id}/risk-metrics` }) },
  'risk-metrics-get':  { build: ()   => ({ method: 'GET',  url: `${BASE}/analytics/risk-metrics` }) },
  'risk-metrics-post': { build: (id) => ({ method: 'POST', url: `${BASE}/analytics/risk-metrics`,
                                            body: { etf_ids: [id] } }) },
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
    await fetchEtfIds()
    const id  = swdaId.value
    const id2 = secondEtfId.value ?? id
    const req = cfg.build(id, id2)
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

// ── Code Examples ─────────────────────────────────────────────────────────
const activeCodeTab = ref('cURL')

const codeSnippets = {
  'list-etfs': {
    cURL: `curl https://api.goetf.ch/etfs \\
  -H "x-api-key: YOUR_API_KEY"`,
    Python: `import requests

r = requests.get(
    "https://api.goetf.ch/etfs",
    headers={"x-api-key": "YOUR_API_KEY"}
)
etfs = r.json()`,
    JavaScript: `const etfs = await fetch(
  "https://api.goetf.ch/etfs",
  { headers: { "x-api-key": "YOUR_API_KEY" } }
).then(r => r.json());`,
  },
  'get-etf': {
    cURL: `curl https://api.goetf.ch/etfs/{ETF_ID} \\
  -H "x-api-key: YOUR_API_KEY"`,
    Python: `import requests

r = requests.get(
    "https://api.goetf.ch/etfs/{ETF_ID}",
    headers={"x-api-key": "YOUR_API_KEY"}
)
etf = r.json()`,
    JavaScript: `const etf = await fetch(
  "https://api.goetf.ch/etfs/{ETF_ID}",
  { headers: { "x-api-key": "YOUR_API_KEY" } }
).then(r => r.json());`,
  },
  'holdings': {
    cURL: `curl https://api.goetf.ch/etfs/{ETF_ID}/holdings \\
  -H "x-api-key: YOUR_API_KEY"`,
    Python: `import requests

r = requests.get(
    "https://api.goetf.ch/etfs/{ETF_ID}/holdings",
    headers={"x-api-key": "YOUR_API_KEY"}
)
holdings = r.json()
for h in holdings[:5]:
    print(h["instrument_name"], h["weight"])`,
    JavaScript: `const holdings = await fetch(
  "https://api.goetf.ch/etfs/{ETF_ID}/holdings",
  { headers: { "x-api-key": "YOUR_API_KEY" } }
).then(r => r.json());`,
  },
  'allocations': {
    cURL: `curl https://api.goetf.ch/etfs/{ETF_ID}/allocations \\
  -H "x-api-key: YOUR_API_KEY"`,
    Python: `import requests

r = requests.get(
    "https://api.goetf.ch/etfs/{ETF_ID}/allocations",
    headers={"x-api-key": "YOUR_API_KEY"}
)
allocs = r.json()`,
    JavaScript: `const allocs = await fetch(
  "https://api.goetf.ch/etfs/{ETF_ID}/allocations",
  { headers: { "x-api-key": "YOUR_API_KEY" } }
).then(r => r.json());`,
  },
  'performance': {
    cURL: `curl "https://api.goetf.ch/etfs/SWDA/performance" \\
  -H "x-api-key: YOUR_API_KEY"`,
    Python: `import requests

r = requests.get(
    "https://api.goetf.ch/etfs/SWDA/performance",
    params={"from_date": "2025-01-01"},
    headers={"x-api-key": "YOUR_API_KEY"}
)
history = r.json()`,
    JavaScript: `const history = await fetch(
  "https://api.goetf.ch/etfs/SWDA/performance",
  { headers: { "x-api-key": "YOUR_API_KEY" } }
).then(r => r.json());`,
  },
  'performance': {
    cURL: `curl "https://api.goetf.ch/etfs/SWDA/performance" \\
  -H "x-api-key: YOUR_API_KEY"`,
    Python: `import requests

r = requests.get(
    "https://api.goetf.ch/etfs/SWDA/performance",
    params={"from_date": "2025-01-01"},
    headers={"x-api-key": "YOUR_API_KEY"}
)
history = r.json()`,
    JavaScript: `const history = await fetch(
  "https://api.goetf.ch/etfs/SWDA/performance",
  { headers: { "x-api-key": "YOUR_API_KEY" } }
).then(r => r.json());`,
  },
  'etf-risk-metrics': {
    cURL: `curl "https://api.goetf.ch/etfs/SWDA/risk-metrics" \\
  -H "x-api-key: YOUR_API_KEY"`,
    Python: `import requests

r = requests.get(
    "https://api.goetf.ch/etfs/SWDA/risk-metrics",
    params={"rf_rate": 0.04},
    headers={"x-api-key": "YOUR_API_KEY"}
)
metrics = r.json()`,
    JavaScript: `const metrics = await fetch(
  "https://api.goetf.ch/etfs/SWDA/risk-metrics?rf_rate=0.04",
  { headers: { "x-api-key": "YOUR_API_KEY" } }
).then(r => r.json());`,
  },
  'exposure': {
    cURL: `curl -X POST "https://api.goetf.ch/analytics/exposure?rf_rate=0.04" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"portfolio": [{"etf_id": "SWDA", "weight": 60}, {"etf_id": "CSSPX", "weight": 40}]}'`,
    Python: `import requests

r = requests.post(
    "https://api.goetf.ch/analytics/exposure",
    params={"rf_rate": 0.04},
    headers={"x-api-key": "YOUR_API_KEY"},
    json={"portfolio": [
        {"etf_id": "SWDA", "weight": 60},
        {"etf_id": "CSSPX", "weight": 40}
    ]}
)
# Response includes sectors, countries, currencies + risk_metrics per ETF
result = r.json()`,
    JavaScript: `const result = await fetch(
  "https://api.goetf.ch/analytics/exposure?rf_rate=0.04",
  {
    method: "POST",
    headers: {
      "x-api-key": "YOUR_API_KEY",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      portfolio: [
        { etf_id: "SWDA", weight: 60 },
        { etf_id: "CSSPX", weight: 40 }
      ]
    })
  }
).then(r => r.json());
// result.sectors / result.countries / result.currencies / result.risk_metrics`,
  },
  'risk-metrics-get': {
    cURL: `curl "https://api.goetf.ch/analytics/risk-metrics" \\
  -H "x-api-key: YOUR_API_KEY"`,
    Python: `import requests

r = requests.get(
    "https://api.goetf.ch/analytics/risk-metrics",
    params={"rf_rate": 0.04},
    headers={"x-api-key": "YOUR_API_KEY"}
)
all_metrics = r.json()`,
    JavaScript: `const allMetrics = await fetch(
  "https://api.goetf.ch/analytics/risk-metrics?rf_rate=0.04",
  { headers: { "x-api-key": "YOUR_API_KEY" } }
).then(r => r.json());`,
  },
  'risk-metrics-post': {
    cURL: `curl -X POST https://api.goetf.ch/analytics/risk-metrics \\
  -H "x-api-key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"etf_ids": ["SWDA", "CSSPX"]}'`,
    Python: `import requests

r = requests.post(
    "https://api.goetf.ch/analytics/risk-metrics",
    headers={"x-api-key": "YOUR_API_KEY"},
    json={"etf_ids": ["SWDA", "CSSPX"]}
)
metrics = r.json()`,
    JavaScript: `const metrics = await fetch(
  "https://api.goetf.ch/analytics/risk-metrics",
  {
    method: "POST",
    headers: {
      "x-api-key": "YOUR_API_KEY",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ etf_ids: ["SWDA", "CSSPX"] })
  }
).then(r => r.json());`,
  },
}
const activeCodeSnippet = computed(() => codeSnippets[activeId.value]?.[activeCodeTab.value] ?? '')

watch(activeId, (id) => {
  if (tryoutConfigs[id]) {
    const state = getTryoutState(id)
    if (!state.result && !state.loading) runTryout()
  }
}, { immediate: true })
</script>

<style scoped>
.key-banner {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
  background: var(--green-50); border: 1px solid var(--green-200); border-radius: var(--radius);
  padding: .75rem 1.25rem; margin-bottom: 1.5rem; font-size: .875rem; color: var(--green-700);
}
[data-theme="dark"] .key-banner { background: #041a33; border-color: #0d3b72; color: #93d5f0; }
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
.method-post { background: #c3e5ff; color: #0b6aa5; }
.method-delete { background: #fee2e2; color: #dc2626; }
[data-theme="dark"] .method-get { background: #1e3a8a; color: #93c5fd; }
[data-theme="dark"] .method-post { background: #0d3b72; color: #93d5f0; }
.code-tabs { display: flex; gap: .25rem; }
.code-tab { background: none; border: 1px solid var(--border); cursor: pointer; padding: .3rem .75rem; border-radius: 6px; font-size: .8rem; font-weight: 500; color: var(--text-muted); transition: all .15s; font-family: inherit; }
.code-tab.active { background: var(--green-500); border-color: var(--green-500); color: #fff; }

/* Try it out */
.try-btn { width: fit-content; margin-bottom: .75rem; }
.refresh-btn {
  background: none; border: 1px solid var(--border); cursor: pointer;
  padding: .15rem .55rem; border-radius: 6px; font-size: .75rem;
  color: var(--text-muted); font-family: inherit; transition: all .15s;
  margin-left: auto;
}
.refresh-btn:hover:not(:disabled) { border-color: var(--green-400); color: var(--green-600); }
.refresh-btn:disabled { opacity: .5; cursor: not-allowed; }
.demo-key-pill {
  display: inline-block; background: var(--green-50); border: 1px solid var(--green-200);
  color: var(--green-700); padding: .1rem .5rem; border-radius: 20px;
  font-size: .75rem; font-weight: 600; letter-spacing: .04em; margin-left: .5rem;
  vertical-align: middle;
}
[data-theme="dark"] .demo-key-pill { background: #061829; border-color: #0e3060; color: #2d9ee0; }
.tryout-response { display: flex; flex-direction: column; gap: .5rem; }
.tryout-resp-header { display: flex; align-items: center; gap: .75rem; }
.tryout-status-badge {
  display: inline-block; font-size: .75rem; font-weight: 700;
  padding: .15rem .55rem; border-radius: 4px;
}
.status-ok  { background: var(--green-50); border: 1px solid var(--green-200); color: var(--green-700); }
.status-err { background: #fee2e2; border: 1px solid #fecaca; color: #dc2626; }
[data-theme="dark"] .status-ok  { background: #061829; border-color: #0e3060; color: #2d9ee0; }
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
