<template>
  <div>
    <!-- Hero -->
    <section class="hero">
      <div class="hero-inner">
        <div class="hero-badge">◈ ETF Data Platform</div>
        <h1 class="hero-title">ETF Portfolio<br/><span class="gradient-text">Analytics API</span></h1>
        <p class="hero-sub">
          Explore ETF holdings, calculate portfolio overlap, analyze sector exposure
          and find similar funds — all through a clean REST API.
        </p>
        <div class="hero-actions">
          <button class="btn btn-primary btn-lg" @click="$emit('navigate','etfs')">Browse ETFs</button>
          <button class="btn btn-outline btn-lg" @click="$emit('navigate','docs')">API Documentation</button>
        </div>
        <p class="hero-disclaimer">
          ⚠ For informational purposes only. Not investment advice.
        </p>
      </div>
      <div class="hero-art" aria-hidden="true">
        <div class="art-ring r1"></div>
        <div class="art-ring r2"></div>
        <div class="art-ring r3"></div>
        <div class="art-center">◈</div>
      </div>
    </section>

    <!-- Stats -->
    <section class="page">
      <div class="grid-4">
        <div class="stat-card" v-for="s in stats" :key="s.label">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value" :class="{ 'stat-loading': statsLoading && s.value === '—' }">{{ s.value }}</div>
          <div class="stat-sub">{{ s.sub }}</div>
        </div>
      </div>
    </section>

    <!-- Features -->
    <section class="features-section">
      <div class="page">
        <div class="section-header">
          <h2 class="section-title">What you can do</h2>
          <p class="section-sub">Four powerful endpoints to analyse ETF data</p>
        </div>
        <div class="grid-2">
          <div class="feature-card" v-for="f in features" :key="f.title" @click="$emit('navigate', f.nav)">
            <div class="feature-icon">{{ f.icon }}</div>
            <div>
              <h3 class="feature-title">{{ f.title }}</h3>
              <p class="feature-desc">{{ f.desc }}</p>
            </div>
            <span class="feature-arrow">→</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Quick API intro -->
    <section class="page">
      <div class="card">
        <div class="qapi-header">
          <div>
            <h2 class="card-title" style="font-size:1.2rem;margin:0">Quick Start</h2>
            <p style="font-size:.875rem;color:var(--text-muted);margin-top:.25rem">Integrate the API in minutes</p>
          </div>
          <button class="btn btn-outline" @click="$emit('navigate','docs')">Full Docs →</button>
        </div>
        <div class="code-tabs">
          <button v-for="tab in codeTabs" :key="tab.label"
            :class="['code-tab', { active: activeTab === tab.label }]"
            @click="activeTab = tab.label">{{ tab.label }}</button>
        </div>
        <pre>{{ currentCode }}</pre>
      </div>
    </section>

    <!-- Try it out -->
    <section class="page">
      <div class="card tryout-card">
        <div class="tryout-header">
          <div>
            <h2 class="card-title" style="font-size:1.2rem;margin:0">Try it out — no sign-up needed</h2>
            <p style="font-size:.875rem;color:var(--text-muted);margin-top:.25rem">
              Use the public demo key to fetch live SWDA ETF data right now
            </p>
          </div>
          <span class="live-badge">LIVE</span>
        </div>
        <div class="tryout-meta">
          <div class="tryout-row">
            <span class="tryout-label">Demo API Key</span>
            <code class="tryout-key">demo</code>
          </div>
          <div class="tryout-row">
            <span class="tryout-label">Endpoint</span>
            <code class="tryout-endpoint">GET /etfs</code>
          </div>
        </div>
        <button class="btn btn-primary" :disabled="tryoutLoading" @click="runDemo" style="width:fit-content">
          {{ tryoutLoading ? 'Loading…' : '▶  Execute' }}
        </button>
        <transition name="fade">
          <div v-if="tryoutResult" class="tryout-result">
            <div class="tryout-result-header">
              <span class="tryout-status">200 OK</span>
              <span style="font-size:.75rem;color:var(--text-muted)">SWDA — iShares MSCI World</span>
            </div>
            <pre class="tryout-pre">{{ tryoutResult }}</pre>
          </div>
        </transition>
        <div v-if="tryoutError" class="tryout-error">{{ tryoutError }}</div>
      </div>
    </section>

    <!-- Disclaimer -->
    <section class="page">
      <div class="disclaimer-card">
        <h3>📋 Important Disclaimer</h3>
        <p>
          ETF Data is provided strictly for <strong>informational and educational purposes</strong>.
          None of the data, analysis, or tools on this platform constitute financial, investment,
          legal, or tax advice. ETF Data does not recommend any specific ETF, fund, or investment
          strategy. Past performance is not indicative of future results. Investment in ETFs involves
          risk, including the possible loss of principal. Always consult a qualified financial adviser,
          accountant, or legal professional before making any investment decisions.
        </p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'
import { etfService } from '../services/api.js'

const API_BASE = import.meta.env.VITE_API_URL || 'https://etfdata-production.up.railway.app'

defineEmits(['navigate'])

const etfCount = ref('—')
const holdingsCount = ref('—')
const statsLoading = ref(true)

const stats = computed(() => [
  { label: 'ETFs Tracked', value: etfCount.value, sub: 'iShares funds' },
  { label: 'API Endpoints', value: '12+', sub: 'REST JSON' },
  { label: 'Holdings Tracked', value: holdingsCount.value, sub: 'Top positions per ETF' },
  { label: 'Uptime', value: '99%', sub: 'Railway hosted' },
])

onMounted(async () => {
  try {
    const r = await etfService.getETFs(0, 100)
    const etfs = r.data
    etfCount.value = etfs.length.toString()
    holdingsCount.value = (etfs.length * 10).toLocaleString() + '+'
  } catch {
    etfCount.value = '—'
    holdingsCount.value = '—'
  } finally {
    statsLoading.value = false
  }
  fetchDemo('etfs')
})

const features = [
  { icon: '📊', title: 'ETF Explorer', desc: 'Browse all tracked ETFs, view holdings, allocations and performance metrics.', nav: 'etfs' },
  { icon: '🔬', title: 'Overlap Analysis', desc: 'Calculate the percentage overlap between two or more ETFs based on their holdings.', nav: 'analytics' },
  { icon: '🌍', title: 'Exposure Analysis', desc: 'Analyse sector, country and currency exposure of a custom portfolio.', nav: 'analytics' },
  { icon: '📖', title: 'API Reference', desc: 'Full documentation with code examples for Python, JavaScript and cURL.', nav: 'docs' },
]

const codeTabs = [
  {
    label: 'cURL', code:
`# List all ETFs
curl https://etfdata-production.up.railway.app/etfs \\
  -H "x-api-key: YOUR_API_KEY"

# Overlap between two ETFs
curl https://etfdata-production.up.railway.app/analytics/overlap/ETF_A/ETF_B \\
  -H "x-api-key: YOUR_API_KEY"`
  },
  {
    label: 'Python', code:
`import requests

BASE = "https://etfdata-production.up.railway.app"
HEADERS = {"x-api-key": "YOUR_API_KEY"}

# List ETFs
etfs = requests.get(f"{BASE}/etfs", headers=HEADERS).json()

# Overlap
overlap = requests.get(
    f"{BASE}/analytics/overlap/{etfs[0]['id']}/{etfs[1]['id']}",
    headers=HEADERS
).json()`
  },
  {
    label: 'JavaScript', code:
`const BASE = "https://etfdata-production.up.railway.app";
const HEADERS = { "x-api-key": "YOUR_API_KEY" };

// List ETFs
const etfs = await fetch(\`\${BASE}/etfs\`, { headers: HEADERS })
  .then(r => r.json());

// Overlap
const overlap = await fetch(
  \`\${BASE}/analytics/overlap/\${etfs[0].id}/\${etfs[1].id}\`,
  { headers: HEADERS }
).then(r => r.json());`
  },
]

const activeTab = ref('cURL')
const currentCode = ref(codeTabs[0].code)

function setTab(tab) {
  activeTab.value = tab.label
  currentCode.value = tab.code
}

// watch activeTab
watch(activeTab, val => {
  currentCode.value = codeTabs.find(t => t.label === val)?.code ?? ''
})

// Live API Explorer
const swdaId = ref(null)
const activeDemo = ref('etfs')
const demoEndpoints = [
  { key: 'etfs',        short: '/etfs' },
  { key: 'holdings',    short: '/etfs/{id}/holdings' },
  { key: 'allocations', short: '/etfs/{id}/allocations' },
]
const demoStates = ref({
  etfs:        { loading: false, result: null, error: null },
  holdings:    { loading: false, result: null, error: null },
  allocations: { loading: false, result: null, error: null },
})
const currentDemo = computed(() => demoStates.value[activeDemo.value])

async function fetchDemo(key) {
  const state = demoStates.value[key]
  if (state.result !== null || state.loading) return
  state.loading = true; state.error = null
  try {
    let url
    if (key === 'etfs') {
      url = `${API_BASE}/etfs`
    } else {
      if (!swdaId.value) {
        const r = await axios.get(`${API_BASE}/etfs`, { headers: { 'x-api-key': 'demo' } })
        swdaId.value = r.data[0]?.id ?? null
        if (!demoStates.value.etfs.result && r.data[0]) {
          demoStates.value.etfs.result = JSON.stringify(r.data[0], null, 2)
        }
      }
      url = `${API_BASE}/etfs/${swdaId.value}/${key}`
    }
    const res = await axios.get(url, { headers: { 'x-api-key': 'demo' } })
    const data = res.data
    if (key === 'etfs') {
      state.result = data[0] ? JSON.stringify(data[0], null, 2) : '[]'
      if (!swdaId.value) swdaId.value = data[0]?.id ?? null
    } else if (Array.isArray(data)) {
      state.result = JSON.stringify(data.slice(0, 5), null, 2) +
        (data.length > 5 ? `\n// … ${data.length - 5} more items` : '')
    } else {
      state.result = JSON.stringify(data, null, 2)
    }
  } catch (e) {
    state.error = e?.response?.data?.detail || 'Request failed. Is the API reachable?'
  } finally {
    state.loading = false
  }
}

function switchDemo(key) {
  activeDemo.value = key
  fetchDemo(key)
}
</script>

<style scoped>
.hero {
  background: linear-gradient(135deg, var(--green-50) 0%, #fff 60%);
  border-bottom: 1px solid var(--border);
  padding: 5rem 1.5rem 4rem;
  display: flex; align-items: center; justify-content: center;
  gap: 4rem; flex-wrap: wrap; position: relative; overflow: hidden;
}
[data-theme="dark"] .hero { background: linear-gradient(135deg, #0a1a0a 0%, #0a0f0a 60%); }
.hero-inner { max-width: 560px; z-index: 1; }
.hero-badge {
  display: inline-block; padding: .35rem .85rem; border-radius: 20px;
  background: var(--green-100); color: var(--green-700);
  font-size: .8rem; font-weight: 600; letter-spacing: .05em;
  margin-bottom: 1.25rem;
}
.hero-title { font-size: clamp(2rem, 5vw, 3rem); font-weight: 800; line-height: 1.1; letter-spacing: -.04em; color: var(--text); }
.gradient-text { background: linear-gradient(135deg, #22c55e, #16a34a); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.hero-sub { font-size: 1.05rem; color: var(--text-muted); margin: 1.25rem 0 2rem; line-height: 1.7; }
.hero-actions { display: flex; gap: .75rem; flex-wrap: wrap; }
.btn-lg { padding: .7rem 1.5rem; font-size: 1rem; }
.hero-disclaimer { margin-top: 1.5rem; font-size: .8rem; color: var(--text-muted); }
.hero-art { position: relative; width: 260px; height: 260px; flex-shrink: 0; }
.art-ring {
  position: absolute; border-radius: 50%; border: 2px solid;
  top: 50%; left: 50%; transform: translate(-50%,-50%);
  animation: rot 20s linear infinite;
}
.r1 { width: 260px; height: 260px; border-color: var(--green-200); opacity: .5; }
.r2 { width: 180px; height: 180px; border-color: var(--green-300); opacity: .6; animation-duration: 14s; animation-direction: reverse; }
.r3 { width: 100px; height: 100px; border-color: var(--green-400); opacity: .7; animation-duration: 9s; }
.art-center { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); font-size: 2.5rem; color: var(--green-500); }
@keyframes rot { to { transform: translate(-50%,-50%) rotate(360deg); } }
.section-header { text-align: center; margin-bottom: 2rem; }
.section-title { font-size: 1.5rem; font-weight: 700; color: var(--text); letter-spacing: -.03em; }
.section-sub { color: var(--text-muted); margin-top: .35rem; }
.features-section { background: var(--bg-2); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 3rem 0; }
.feature-card {
  display: flex; align-items: flex-start; gap: 1rem;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.5rem;
  cursor: pointer; transition: all .2s; box-shadow: var(--shadow);
}
.feature-card:hover { border-color: var(--green-400); box-shadow: var(--shadow-md); transform: translateY(-2px); }
.feature-icon { font-size: 2rem; flex-shrink: 0; }
.feature-title { font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: .25rem; }
.feature-desc { font-size: .875rem; color: var(--text-muted); line-height: 1.5; }
.feature-arrow { margin-left: auto; font-size: 1.25rem; color: var(--green-400); flex-shrink: 0; align-self: center; }
.qapi-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.25rem; }
.code-tabs { display: flex; gap: .25rem; margin-bottom: 1rem; }
.code-tab {
  background: none; border: 1px solid var(--border); cursor: pointer;
  padding: .3rem .75rem; border-radius: 6px; font-size: .8rem; font-weight: 500;
  color: var(--text-muted); transition: all .15s; font-family: inherit;
}
.code-tab.active { background: var(--green-500); border-color: var(--green-500); color: #fff; }
.disclaimer-card {
  background: var(--bg-3); border: 1px solid var(--green-200);
  border-radius: var(--radius); padding: 1.5rem;
}
.disclaimer-card h3 { font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: .75rem; }
.disclaimer-card p { font-size: .875rem; color: var(--text-muted); line-height: 1.7; }
.stat-loading { opacity: .35; }

/* Try it out */
.tryout-card { display: flex; flex-direction: column; gap: 1.25rem; }
.tryout-header { display: flex; justify-content: space-between; align-items: flex-start; }
.live-badge {
  background: #22c55e; color: #fff; font-size: .7rem; font-weight: 700;
  letter-spacing: .1em; padding: .2rem .55rem; border-radius: 20px;
  animation: pulse-badge 2s ease-in-out infinite;
}
@keyframes pulse-badge {
  0%, 100% { opacity: 1; }
  50% { opacity: .6; }
}
.tryout-meta { display: flex; flex-direction: column; gap: .6rem; }
.tryout-row { display: flex; align-items: center; gap: .75rem; flex-wrap: wrap; }
.tryout-label { font-size: .8rem; color: var(--text-muted); min-width: 90px; }
.tryout-key {
  background: var(--green-50); border: 1px solid var(--green-200);
  color: var(--green-700); padding: .2rem .6rem; border-radius: 6px;
  font-family: monospace; font-size: .9rem; font-weight: 600; letter-spacing: .05em;
}
[data-theme="dark"] .tryout-key { background: #0d2d0d; border-color: #1a4d1a; color: #4ade80; }
.tryout-endpoint {
  background: var(--bg-3); border: 1px solid var(--border);
  color: var(--text-muted); padding: .2rem .6rem; border-radius: 6px;
  font-family: monospace; font-size: .85rem;
}
.tryout-result { display: flex; flex-direction: column; gap: .5rem; }
.tryout-result-header { display: flex; align-items: center; gap: 1rem; }
.demo-tabs { display:flex; gap:.4rem; flex-wrap:wrap; }
.demo-tab {
  display:flex; align-items:center; gap:.35rem;
  background:var(--bg-3); border:1px solid var(--border);
  cursor:pointer; padding:.3rem .85rem; border-radius:20px;
  font-size:.78rem; font-weight:500; color:var(--text-muted);
  font-family:inherit; transition:all .15s;
}
.demo-tab:hover { border-color:var(--green-400); color:var(--text); }
.demo-tab.active { background:var(--green-100); border-color:var(--green-400); color:var(--green-700); font-weight:600; }
[data-theme="dark"] .demo-tab.active { background:#0d2d0d; border-color:#1a5c1a; color:#4ade80; }
.demo-method { font-weight:700; font-size:.65rem; color:#1d4ed8; background:#dbeafe; padding:.05rem .3rem; border-radius:3px; flex-shrink:0; }
[data-theme="dark"] .demo-method { background:#1e3a8a; color:#93c5fd; }
.demo-tabs { display:flex; gap:.4rem; flex-wrap:wrap; }
.demo-tab {
  display:flex; align-items:center; gap:.35rem;
  background:var(--bg-3); border:1px solid var(--border);
  cursor:pointer; padding:.3rem .85rem; border-radius:20px;
  font-size:.78rem; font-weight:500; color:var(--text-muted);
  font-family:inherit; transition:all .15s;
}
.demo-tab:hover { border-color:var(--green-400); color:var(--text); }
.demo-tab.active { background:var(--green-100); border-color:var(--green-400); color:var(--green-700); font-weight:600; }
[data-theme="dark"] .demo-tab.active { background:#0d2d0d; border-color:#1a5c1a; color:#4ade80; }
.demo-method { font-weight:700; font-size:.65rem; color:#1d4ed8; background:#dbeafe; padding:.05rem .3rem; border-radius:3px; flex-shrink:0; }
[data-theme="dark"] .demo-method { background:#1e3a8a; color:#93c5fd; }
.tryout-status {
  background: var(--green-50); border: 1px solid var(--green-200);
  color: var(--green-700); font-size: .75rem; font-weight: 700;
  padding: .15rem .5rem; border-radius: 4px;
}
[data-theme="dark"] .tryout-status { background: #0d2d0d; border-color: #1a4d1a; color: #4ade80; }
.tryout-pre {
  background: var(--bg-3); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.25rem; overflow-x: auto;
  font-size: .8rem; line-height: 1.6; max-height: 380px; overflow-y: auto;
  white-space: pre; color: var(--text);
}
.tryout-error {
  color: #dc2626; background: #fef2f2; border: 1px solid #fecaca;
  border-radius: 8px; padding: .75rem 1rem; font-size: .875rem;
}
[data-theme="dark"] .tryout-error { background: #2d0a0a; border-color: #7f1d1d; color: #f87171; }
.fade-enter-active { transition: opacity .35s, transform .35s; }
.fade-enter-from { opacity: 0; transform: translateY(-6px); }
</style>
