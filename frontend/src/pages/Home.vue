<template>
  <div>
    <!-- Hero -->
    <section class="hero">
      <div class="hero-inner">
        <div class="hero-badge">GoETF</div>
        <h1 class="hero-title">ETF Portfolio<br/><span class="gradient-text">Analytics API</span></h1>
        <p class="hero-sub">Real ETF data via REST API. Query holdings, allocations and portfolio exposure analysis. FREE API key.</p>
        <div class="hero-actions">
          <button class="btn btn-primary btn-lg" @click="$emit('navigate','etfs')">Browse ETFs</button>
          <button class="btn btn-outline btn-lg" @click="$emit('navigate','docs')">View Docs</button>
        </div>
        <button class="hero-live-btn" @click="scrollToTryout">
          <span class="live-dot"></span> Live API Explorer
        </button>
        <p class="hero-disclaimer">For informational purposes only. Not investment advice.</p>
      </div>
      <!-- Score Carousel -->
      <div class="hero-carousel">
        <div class="hd-chrome">
          <span class="hd-dot hd-r"></span>
          <span class="hd-dot hd-y"></span>
          <span class="hd-dot hd-g"></span>
          <code class="hd-url">{{ scoreCarouselSlides[scoreCarouselIdx].label }}</code>
        </div>
        <transition name="cs" mode="out-in">
          <div :key="scoreCarouselIdx" class="hc-body">
            <!-- Slide 0: ETF GoETF Scores -->
            <template v-if="scoreCarouselIdx === 0">
              <div class="hd-score-row"><span class="hd-ticker">SWDA</span><div class="hd-score-track"><div class="hd-score-fill" style="width:78%"></div></div><span class="hds-num hds-high">7.8</span></div>
              <div class="hd-score-row"><span class="hd-ticker">CSSPX</span><div class="hd-score-track"><div class="hd-score-fill" style="width:72%"></div></div><span class="hds-num hds-high">7.2</span></div>
              <div class="hd-score-row"><span class="hd-ticker">ISF</span><div class="hd-score-track"><div class="hd-score-fill hd-score-fill-mid" style="width:65%"></div></div><span class="hds-num hds-mid">6.5</span></div>
              <div class="hd-score-row"><span class="hd-ticker">SEDY</span><div class="hd-score-track"><div class="hd-score-fill hd-score-fill-mid" style="width:59%"></div></div><span class="hds-num hds-mid">5.9</span></div>
              <div class="hd-footer"><span class="hd-status">200 OK</span><span class="hd-count">GoETF Score / 10</span></div>
            </template>
            <!-- Slide 1: Portfolio Score + Tip -->
            <template v-else>
              <div class="hd-ps-header">
                <div><div class="hd-ps-port">SWDA 60% + CSSPX 40%</div><div class="hd-ps-label">Portfolio GoETF Score</div></div>
                <span class="hd-ps-badge">7.1</span>
              </div>
              <div class="hd-ps-rows">
                <div class="hd-ps-row"><span>Base score</span><span>7.5</span></div>
                <div class="hd-ps-row"><span>Overlap penalty</span><span class="hd-neg">−0.8</span></div>
                <div class="hd-ps-row"><span>Div. bonus</span><span class="hd-pos">+0.4</span></div>
              </div>
              <div class="hd-tip-row">💡 Swap <b>CSSPX</b> → <b>ISF</b> &nbsp;·&nbsp; score +0.6 pts</div>
              <div class="hd-footer"><span class="hd-status">200 OK</span><span class="hd-count">portfolio score</span></div>
            </template>
          </div>
        </transition>
        <div class="hc-dots">
          <button v-for="(_, i) in scoreCarouselSlides" :key="i"
            :class="['hc-dot-btn', { active: scoreCarouselIdx === i }]"
            @click="scoreCarouselIdx = i"></button>
        </div>
      </div>
      <!-- API Data Carousel -->
      <div class="hero-carousel">
        <div class="hd-chrome">
          <span class="hd-dot hd-r"></span>
          <span class="hd-dot hd-y"></span>
          <span class="hd-dot hd-g"></span>
          <code class="hd-url">{{ carouselSlides[carouselIdx].label }}</code>
        </div>
        <transition name="cs" mode="out-in">
          <div :key="carouselIdx" class="hc-body">
            <!-- Slide 0: ETF list -->
            <template v-if="carouselIdx === 0">
              <div class="hd-row"><span class="hd-ticker">SWDA</span><span class="hd-name">iShares Core MSCI World <span class="hd-pill">Acc</span></span><span class="hd-ter">0.20%</span></div>
              <div class="hd-row"><span class="hd-ticker">CSSPX</span><span class="hd-name">iShares Core S&amp;P 500 <span class="hd-pill">Acc</span></span><span class="hd-ter">0.07%</span></div>
              <div class="hd-row"><span class="hd-ticker">ISF</span><span class="hd-name">iShares Core FTSE 100 <span class="hd-pill hd-pill-dist">Dist</span></span><span class="hd-ter">0.07%</span></div>
              <div class="hd-footer"><span class="hd-status">200 OK</span><span class="hd-count">10 ETFs tracked</span></div>
            </template>
            <!-- Slide 1: Holdings -->
            <template v-else-if="carouselIdx === 1">
              <div class="hd-row"><span class="hd-rank">#1</span><span class="hd-hold-name">Apple Inc.</span><span class="hd-ter">5.81%</span></div>
              <div class="hd-row"><span class="hd-rank">#2</span><span class="hd-hold-name">Microsoft Corp.</span><span class="hd-ter">5.43%</span></div>
              <div class="hd-row"><span class="hd-rank">#3</span><span class="hd-hold-name">NVIDIA Corp.</span><span class="hd-ter">4.92%</span></div>
              <div class="hd-footer"><span class="hd-status">200 OK</span><span class="hd-count">1,340 holdings</span></div>
            </template>
            <!-- Slide 2: Allocations -->
            <template v-else-if="carouselIdx === 2">
              <div class="hd-alloc-row"><span class="hd-alloc-lbl">North America</span><div class="hd-bar-track"><div class="hd-bar" style="width:68%"></div></div><span class="hd-alloc-val">68%</span></div>
              <div class="hd-alloc-row"><span class="hd-alloc-lbl">Europe</span><div class="hd-bar-track"><div class="hd-bar" style="width:22%"></div></div><span class="hd-alloc-val">22%</span></div>
              <div class="hd-alloc-row"><span class="hd-alloc-lbl">Asia Pacific</span><div class="hd-bar-track"><div class="hd-bar" style="width:10%"></div></div><span class="hd-alloc-val">10%</span></div>
              <div class="hd-footer"><span class="hd-status">200 OK</span><span class="hd-count">country breakdown</span></div>
            </template>
            <!-- Slide 3: Portfolio Exposure -->
            <template v-else>
              <div class="hd-expo-header"><span class="hd-expo-port">SWDA 60% + CSSPX 40%</span><span class="hd-expo-lbl">portfolio</span></div>
              <div class="hd-alloc-row"><span class="hd-alloc-lbl">North America</span><div class="hd-bar-track"><div class="hd-bar" style="width:72%"></div></div><span class="hd-alloc-val">72%</span></div>
              <div class="hd-alloc-row"><span class="hd-alloc-lbl">Technology</span><div class="hd-bar-track"><div class="hd-bar hd-bar-sec" style="width:28%"></div></div><span class="hd-alloc-val">28%</span></div>
              <div class="hd-footer"><span class="hd-status">200 OK</span><span class="hd-count">exposure analysis</span></div>
            </template>
          </div>
        </transition>
        <div class="hc-dots">
          <button v-for="(_, i) in carouselSlides" :key="i"
            :class="['hc-dot-btn', { active: carouselIdx === i }]"
            @click="carouselIdx = i"></button>
        </div>
      </div>
    </section>

    <!-- Features -->
    <section class="features-section">
      <div class="page">
        <div class="section-header">
          <h2 class="section-title">What you can do</h2>
          <p class="section-sub">Clean data endpoints for developers and researchers</p>
        </div>
        <div class="grid-2">
          <!-- ETF Explorer -->
          <div class="feature-card" @click="$emit('navigate','etfs')">
            <div class="feature-top">
              <div class="feature-chip fi-etf">ETF</div>
              <div style="flex:1">
                <h3 class="feature-title">ETF Explorer</h3>
                <p class="feature-desc">Browse all tracked ETFs, view holdings, allocations and performance metrics.</p>
              </div>
              <span class="feature-arrow">→</span>
            </div>
            <div class="feature-preview">
              <div class="fp-etf-row"><span class="fp-ticker">SWDA</span><span class="fp-name">iShares Core MSCI World</span><span class="fp-badge">Acc</span><span class="fp-ter">0.20%</span></div>
              <div class="fp-etf-row"><span class="fp-ticker">VUSA</span><span class="fp-name">Vanguard S&amp;P 500 UCITS ETF</span><span class="fp-badge fp-dist">Dist</span><span class="fp-ter">0.07%</span></div>
              <div class="fp-more">+ more ETFs tracked →</div>
            </div>
          </div>
          <!-- Exposure Analysis -->
          <div class="feature-card" @click="navigateTo('analytics','exposure')">
            <div class="feature-top">
              <div class="feature-chip fi-geo">GEO</div>
              <div style="flex:1">
                <h3 class="feature-title">Exposure Analysis</h3>
                <p class="feature-desc">Analyse sector, country and currency exposure of a custom portfolio.</p>
              </div>
              <span class="feature-arrow">→</span>
            </div>
            <div class="feature-preview">
              <div class="fp-bar-row"><span class="fp-bar-lbl">North America</span><div class="fp-bar-track"><div class="fp-bar-fill" style="width:68%"></div></div><span class="fp-bar-val">68%</span></div>
              <div class="fp-bar-row"><span class="fp-bar-lbl">Europe</span><div class="fp-bar-track"><div class="fp-bar-fill" style="width:22%"></div></div><span class="fp-bar-val">22%</span></div>
              <div class="fp-bar-row"><span class="fp-bar-lbl">Asia Pacific</span><div class="fp-bar-track"><div class="fp-bar-fill" style="width:10%"></div></div><span class="fp-bar-val">10%</span></div>
            </div>
          </div>
          <!-- API Reference -->
          <div class="feature-card" @click="$emit('navigate','docs')">
            <div class="feature-top">
              <div class="feature-chip fi-api">API</div>
              <div style="flex:1">
                <h3 class="feature-title">API Reference</h3>
                <p class="feature-desc">Full documentation with per-endpoint code examples for Python, JavaScript and cURL.</p>
              </div>
              <span class="feature-arrow">→</span>
            </div>
            <div class="feature-preview fp-api-preview">
              <div class="fp-api-row"><span class="fp-get">GET</span><code class="fp-path">/etfs</code></div>
              <div class="fp-api-row"><span class="fp-get">GET</span><code class="fp-path">/etfs/{id}/holdings</code></div>
              <div class="fp-api-row"><span class="fp-post">POST</span><code class="fp-path">/analytics/overlap</code></div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Try it out -->
    <section class="page" id="live-explorer">
      <div class="card tryout-card">
        <div class="tryout-header">
          <div>
            <h2 class="card-title" style="font-size:1.2rem;margin:0">Live API Explorer</h2>
            <p style="font-size:.875rem;color:var(--text-muted);margin-top:.25rem">
              Live SWDA data · public <code class="tryout-key" style="font-size:.8rem;display:inline">demo</code> key · no sign-up needed
            </p>
          </div>
          <span class="live-badge">LIVE</span>
        </div>
        <div class="demo-tabs">
          <button v-for="ep in demoEndpoints" :key="ep.key"
            :class="['demo-tab', { active: activeDemo === ep.key }]"
            @click="switchDemo(ep.key)">
            <span class="demo-method">GET</span>{{ ep.short }}
          </button>
        </div>
        <div v-if="currentDemo.loading" class="loading" style="font-size:.875rem">
          <div class="spinner"></div> Fetching live data…
        </div>
        <transition name="fade">
          <div v-if="!currentDemo.loading && currentDemo.result" class="tryout-result">
            <div class="tryout-result-header">
              <span class="tryout-status">200 OK</span>
              <span style="font-size:.75rem;color:var(--text-muted)">SWDA · iShares Core MSCI World</span>
            </div>
            <pre class="tryout-pre">{{ currentDemo.result }}</pre>
          </div>
        </transition>
        <div v-if="currentDemo.error" class="tryout-error">{{ currentDemo.error }}</div>
        <button class="btn btn-outline" style="width:fit-content" @click="$emit('navigate','docs')">
          See all APIs →
        </button>
      </div>
    </section>

    <!-- Disclaimer -->
    <section class="page">
      <div class="disclaimer-card">
        <h3>📋 Important Disclaimer</h3>
        <p>
          GoETF.ch is provided strictly for <strong>informational and educational purposes</strong>.
          None of the data, analysis, or tools on this platform constitute financial, investment,
          legal, or tax advice. GoETF.ch does not recommend any specific ETF, fund, or investment
          strategy. Past performance is not indicative of future results. Investment in ETFs involves
          risk, including the possible loss of principal. Always consult a qualified financial adviser,
          accountant, or legal professional before making any investment decisions.
        </p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject } from 'vue'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'https://etfdata-production.up.railway.app'

defineEmits(['navigate'])

const navigateTo = inject('navigateTo')

const carouselIdx = ref(0)
const carouselSlides = [
  { label: 'GET /etfs' },
  { label: 'GET /etfs/{id}/holdings' },
  { label: 'GET /etfs/{id}/allocations' },
  { label: 'POST /analytics/exposure' },
]
let _carouselTimer = null

const scoreCarouselIdx = ref(0)
const scoreCarouselSlides = [
  { label: 'GET /scores/etfs' },
  { label: 'POST /scores/portfolio' },
]
let _scoreCarouselTimer = null

function scrollToTryout() {
  document.getElementById('live-explorer')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => {
  fetchDemo('etfs')
  _carouselTimer = setInterval(() => {
    carouselIdx.value = (carouselIdx.value + 1) % carouselSlides.length
  }, 3600)
  _scoreCarouselTimer = setInterval(() => {
    scoreCarouselIdx.value = (scoreCarouselIdx.value + 1) % scoreCarouselSlides.length
  }, 4200)
})
onUnmounted(() => { clearInterval(_carouselTimer); clearInterval(_scoreCarouselTimer) })

const codeTabs = [
  {
    label: 'cURL', code:
`# List all ETFs
curl https://api.goetf.ch/etfs \\
  -H "x-api-key: YOUR_API_KEY"

# Overlap between two ETFs
curl https://api.goetf.ch/analytics/overlap/ETF_A/ETF_B \\
  -H "x-api-key: YOUR_API_KEY"`
  },
  {
    label: 'Python', code:
`import requests

BASE = "https://api.goetf.ch"
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
`const BASE = "https://api.goetf.ch";
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

// Live API Explorer
const swdaId = ref(null)
const activeDemo = ref('etfs')
const demoEndpoints = [
  { key: 'etfs',         short: '/etfs' },
  { key: 'holdings',     short: '/etfs/{id}/holdings' },
  { key: 'allocations',  short: '/etfs/{id}/allocations' },
  { key: 'risk-metrics', short: '/etfs/risk-metrics' },
  { key: 'scores-etfs',  short: '/scores/etfs' },
]
const demoStates = ref({
  etfs:          { loading: false, result: null, error: null },
  holdings:      { loading: false, result: null, error: null },
  allocations:   { loading: false, result: null, error: null },
  'risk-metrics':{ loading: false, result: null, error: null },
  'scores-etfs': { loading: false, result: null, error: null },
})
const currentDemo = computed(() => demoStates.value[activeDemo.value])

async function fetchDemo(key) {
  const state = demoStates.value[key]
  if (state.result !== null || state.loading) return
  state.loading = true; state.error = null
  try {
    let url, params
    if (key === 'etfs') {
      url = `${API_BASE}/etfs`
    } else if (key === 'risk-metrics') {
      url = `${API_BASE}/etfs/risk-metrics`
      params = { tickers: 'SWDA' }
    } else if (key === 'scores-etfs') {
      url = `${API_BASE}/scores/etfs`
      params = { tickers: 'SWDA' }
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
    const res = await axios.get(url, { headers: { 'x-api-key': 'demo' }, params })
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
  background: linear-gradient(135deg, var(--green-50) 0%, #fff 55%);
  border-bottom: 1px solid var(--border);
  padding: 1.5rem 1.5rem;
  display: flex; align-items: center; justify-content: center;
  gap: 2.5rem; flex-wrap: wrap; overflow: hidden;
}
[data-theme="dark"] .hero { background: linear-gradient(135deg, #060e1a 0%, #050a12 55%); }
.hero-inner { max-width: 500px; }
.hero-badge {
  display: inline-block; padding: .15rem .55rem; border-radius: 5px;
  background: var(--green-100); color: var(--green-700);
  font-size: .68rem; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
  margin-bottom: .6rem;
}
[data-theme="dark"] .hero-badge { background: #082d5e; color: #7ec8e3; }
.hero-title { font-size: clamp(1.5rem, 3.5vw, 2.1rem); font-weight: 800; line-height: 1.1; letter-spacing: -.04em; color: var(--text); }
.gradient-text { background: linear-gradient(135deg, #1585c8, #0b6aa5); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.hero-sub { font-size: .875rem; color: var(--text-muted); margin: .6rem 0 1rem; line-height: 1.55; }
.hero-actions { display: flex; gap: .75rem; flex-wrap: wrap; }
.btn-lg { padding: .5rem 1.1rem; font-size: .875rem; }
.hero-disclaimer { margin-top: .7rem; font-size: .68rem; color: var(--text-muted); opacity: .8; }

/* Hero API carousel */
.hero-carousel {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); overflow: hidden;
  box-shadow: var(--shadow-lg); width: 300px; flex-shrink: 0;
}
.hd-chrome {
  display: flex; align-items: center; gap: .45rem;
  padding: .35rem .7rem;
  background: var(--bg-2); border-bottom: 1px solid var(--border);
}
.hd-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.hd-r { background: #ff5f57; }
.hd-y { background: #febc2e; }
.hd-g { background: #28c840; }
.hd-url {
  flex: 1; text-align: center; font-size: .65rem;
  color: var(--text-muted); white-space: nowrap;
}
.hd-row {
  display: flex; align-items: center; gap: .55rem;
  padding: .38rem .7rem; border-bottom: 1px solid var(--border);
  font-size: .76rem;
}
.hd-ticker { font-family: monospace; font-weight: 700; color: var(--text); min-width: 42px; }
.hd-name { flex: 1; color: var(--text-muted); font-size: .72rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hd-pill {
  display: inline-block; font-size: .57rem; font-weight: 700;
  background: #c3e5ff; color: #0b6aa5;
  padding: .02rem .28rem; border-radius: 5px; margin-left: .25rem; vertical-align: middle;
}
.hd-pill-dist { background: #dbeafe; color: #1e40af; }
[data-theme="dark"] .hd-pill { background: #082d5e; color: #7ec8e3; }
[data-theme="dark"] .hd-pill-dist { background: #1e3a8a; color: #93c5fd; }
.hd-ter { font-weight: 600; color: var(--text); font-size: .74rem; flex-shrink: 0; }
.hd-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: .3rem .7rem; background: var(--bg-2);
}
.hd-status {
  font-size: .66rem; font-weight: 700; color: var(--green-700);
  background: var(--green-50); border: 1px solid var(--green-200);
  padding: .07rem .38rem; border-radius: 4px;
}
[data-theme="dark"] .hd-status { background: #061829; border-color: #0e3060; color: #2d9ee0; }
.hd-count { font-size: .66rem; color: var(--text-muted); }
/* Carousel body, dots, transitions */
.hc-body { height: 152px; overflow: hidden; }
.hc-dots {
  display: flex; align-items: center; justify-content: center; gap: .4rem;
  padding: .3rem; border-top: 1px solid var(--border); background: var(--bg-2);
}
.hc-dot-btn {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--border); border: none; cursor: pointer;
  padding: 0; transition: all .25s;
}
.hc-dot-btn.active { background: var(--green-500); width: 18px; border-radius: 3px; }
.cs-enter-active, .cs-leave-active { transition: opacity .2s ease, transform .2s ease; }
.cs-enter-from { opacity: 0; transform: translateX(10px); }
.cs-leave-to   { opacity: 0; transform: translateX(-10px); }
/* Holdings slide */
.hd-rank { font-family: monospace; font-size: .67rem; color: var(--text-muted); min-width: 22px; flex-shrink: 0; }
.hd-hold-name { flex: 1; color: var(--text); font-size: .75rem; }
/* Allocations slide */
.hd-alloc-row {
  display: flex; align-items: center; gap: .5rem;
  padding: .38rem .7rem; border-bottom: 1px solid var(--border);
}
.hd-alloc-lbl { font-size: .71rem; color: var(--text-muted); width: 90px; flex-shrink: 0; }
.hd-bar-track { flex: 1; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
.hd-bar { height: 100%; background: var(--green-500); border-radius: 2px; }
.hd-alloc-val { font-size: .69rem; font-weight: 600; color: var(--text); width: 26px; text-align: right; flex-shrink: 0; }
/* Overlap/exposure slide */
.hd-expo-header {
  display: flex; align-items: baseline; justify-content: space-between;
  padding: .38rem .7rem; border-bottom: 1px solid var(--border);
}
.hd-expo-port { font-family: monospace; font-size: .72rem; font-weight: 700; color: var(--text); }
.hd-expo-lbl { font-size: .65rem; color: var(--text-muted); }
.hd-bar-sec { background: #6366f1; }
/* Score carousel elements */
.hd-score-row { display:flex; align-items:center; gap:.5rem; padding:.35rem .7rem; border-bottom:1px solid var(--border); }
.hd-score-track { flex:1; height:5px; background:var(--border); border-radius:3px; overflow:hidden; }
.hd-score-fill { height:100%; background:var(--green-500); border-radius:3px; }
.hd-score-fill-mid { background:#2d9ee0; }
.hds-num { font-size:.82rem; font-weight:700; min-width:2.1rem; text-align:right; }
.hds-high { color:var(--green-700); }
.hds-mid { color:#2d9ee0; }
[data-theme="dark"] .hds-high { color:#93d5f0; }
/* Portfolio score carousel */
.hd-ps-header { display:flex; align-items:center; justify-content:space-between; padding:.4rem .7rem; border-bottom:1px solid var(--border); gap:.5rem; }
.hd-ps-port { font-size:.68rem; color:var(--text-muted); font-family:monospace; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.hd-ps-label { font-size:.62rem; color:var(--text-muted); margin-top:.1rem; }
.hd-ps-badge { font-size:1.4rem; font-weight:800; color:var(--green-700); line-height:1; flex-shrink:0; }
[data-theme="dark"] .hd-ps-badge { color:#93d5f0; }
.hd-ps-rows { display:flex; flex-direction:column; }
.hd-ps-row { display:flex; justify-content:space-between; font-size:.73rem; padding:.26rem .7rem; border-bottom:1px solid var(--border); }
.hd-ps-row span:first-child { color:var(--text-muted); }
.hd-ps-row span:last-child { font-weight:600; }
.hd-neg { color:#ef4444; }
.hd-pos { color:var(--green-600); }
[data-theme="dark"] .hd-pos { color:#2d9ee0; }
.hd-tip-row { font-size:.71rem; padding:.32rem .7rem; background:var(--bg-3); border-bottom:1px solid var(--border); color:var(--text); }
/* Live API Explorer button */
.hero-live-btn {
  display: inline-flex; align-items: center; gap: .45rem;
  margin-top: .6rem;
  background: var(--green-50); border: 1px solid var(--green-200);
  color: var(--green-700); font-size: .75rem; font-weight: 600;
  padding: .35rem .85rem; border-radius: 8px;
  cursor: pointer; font-family: inherit; transition: all .15s;
}
.hero-live-btn:hover { background: var(--green-100); border-color: var(--green-400); }
[data-theme="dark"] .hero-live-btn { background: #041a33; border-color: #0d3b72; color: #93d5f0; }
[data-theme="dark"] .hero-live-btn:hover { background: #082d5e; }
.live-dot {
  width: 7px; height: 7px; border-radius: 50%; background: var(--green-500);
  flex-shrink: 0; animation: pulse-badge 1.5s ease-in-out infinite;
}
.section-header { text-align: center; margin-bottom: 2rem; }
.section-title { font-size: 1.5rem; font-weight: 700; color: var(--text); letter-spacing: -.03em; }
.section-sub { color: var(--text-muted); margin-top: .35rem; }
.features-section { background: var(--bg-2); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 2.25rem 0; }
.feature-card {
  display: flex; flex-direction: column; gap: 0;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.25rem;
  cursor: pointer; transition: all .2s; box-shadow: var(--shadow);
}
.feature-card:hover { border-color: var(--green-400); box-shadow: var(--shadow-md); transform: translateY(-2px); }
.feature-top { display: flex; align-items: flex-start; gap: .85rem; }
.feature-chip {
  display: flex; align-items: center; justify-content: center;
  width: 38px; height: 38px; border-radius: 8px;
  font-size: .65rem; font-weight: 800; letter-spacing: .06em;
  flex-shrink: 0; font-family: monospace;
}
.fi-etf { background: var(--green-100); color: var(--green-700); }
.fi-geo { background: #dbeafe; color: #1d4ed8; }
.fi-api { background: #f3e8ff; color: #7e22ce; }
[data-theme="dark"] .fi-etf { background: #082d5e; color: #7ec8e3; }
[data-theme="dark"] .fi-geo { background: #1e3a8a; color: #93c5fd; }
[data-theme="dark"] .fi-api { background: #3b0764; color: #d8b4fe; }
.feature-title { font-size: .95rem; font-weight: 600; color: var(--text); margin-bottom: .2rem; }
.feature-desc { font-size: .83rem; color: var(--text-muted); line-height: 1.5; }
.feature-arrow { margin-left: auto; font-size: 1rem; color: var(--green-400); flex-shrink: 0; align-self: center; padding-left: .25rem; }
.feature-preview { border-top: 1px solid var(--border); margin-top: 1rem; padding-top: .85rem; }
.fp-etf-row { display: flex; align-items: center; gap: .4rem; padding: .25rem 0; border-bottom: 1px solid var(--border); font-size: .75rem; }
.fp-etf-row:last-child { border-bottom: none; }
.fp-ticker { font-family: monospace; font-weight: 700; color: var(--text); min-width: 40px; }
.fp-name { color: var(--text-muted); flex: 1; }
.fp-badge { font-size: .62rem; font-weight: 600; background: #c3e5ff; color: #0b6aa5; padding: .05rem .35rem; border-radius: 10px; flex-shrink: 0; }
.fp-dist { background: #dbeafe; color: #1e40af; }
.fp-ter { color: var(--text-muted); margin-left: auto; flex-shrink: 0; }
.fp-more { color: var(--green-600); font-weight: 500; padding-top: .3rem; font-size: .72rem; }
.fp-bar-row { display: flex; align-items: center; gap: .5rem; margin-bottom: .35rem; }
.fp-bar-lbl { font-size: .7rem; color: var(--text-muted); width: 95px; flex-shrink: 0; }
.fp-bar-track { flex: 1; height: 4px; background: var(--border); border-radius: 2px; }
.fp-bar-fill { height: 100%; background: var(--green-500); border-radius: 2px; }
.fp-bar-val { font-size: .7rem; font-weight: 600; color: var(--text); width: 28px; text-align: right; }
.fp-api-preview { display: flex; flex-direction: column; gap: .3rem; }
.fp-api-row { display: flex; align-items: center; gap: .5rem; font-size: .75rem; }
.fp-get { font-weight: 700; font-size: .63rem; color: #1d4ed8; background: #dbeafe; padding: .05rem .3rem; border-radius: 3px; flex-shrink: 0; }
.fp-post { font-weight: 700; font-size: .63rem; color: #0b6aa5; background: #c3e5ff; padding: .05rem .3rem; border-radius: 3px; flex-shrink: 0; }
.fp-path { font-family: monospace; color: var(--text-muted); }
[data-theme="dark"] .fp-badge { background: #082d5e; color: #7ec8e3; }
[data-theme="dark"] .fp-dist { background: #1e3a8a; color: #93c5fd; }
[data-theme="dark"] .fp-get { background: #1e3a8a; color: #93c5fd; }
[data-theme="dark"] .fp-post { background: #0d3b72; color: #93d5f0; }
.disclaimer-card {
  background: var(--bg-3); border: 1px solid var(--green-200);
  border-radius: var(--radius); padding: 1.5rem;
}
.disclaimer-card h3 { font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: .75rem; }
.disclaimer-card p { font-size: .875rem; color: var(--text-muted); line-height: 1.7; }
/* Try it out */
.tryout-card { display: flex; flex-direction: column; gap: 1.25rem; }
.tryout-header { display: flex; justify-content: space-between; align-items: flex-start; }
.live-badge {
  background: #1585c8; color: #fff; font-size: .7rem; font-weight: 700;
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
[data-theme="dark"] .tryout-key { background: #061829; border-color: #0e3060; color: #2d9ee0; }
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

/* ── Mobile responsive ── */
@media (max-width: 640px) {
  .hero { flex-direction: column; padding: 1.5rem 1rem; gap: 1.5rem; align-items: stretch; }
  .hero-inner { max-width: 100%; }
  .hero-carousel { width: 100%; flex-shrink: 1; }
  .section-title { font-size: 1.2rem; }
  .section-header { margin-bottom: 1.25rem; }
  .demo-tabs { gap: .2rem; }
  .demo-tab { padding: .25rem .6rem; font-size: .72rem; }
}
</style>
