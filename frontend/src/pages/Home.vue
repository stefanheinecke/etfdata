<template>
  <div class="home-page">
    <section class="hero">
      <div class="container hero-grid">
        <div>
          <div class="hero-eyebrow">
            <span class="badge badge-accent"><span class="live-dot"></span>Beta · {{ trackedCount }} ETFs tracked</span>
          </div>
          <h1>ETF Analysis<br />that actually computes.</h1>
          <p class="lead">
            GoETF scores every ETF with a weighted rating, reveals true portfolio overlap, and suggests simplifications.
            Real analysis instead of price lists.
          </p>
          <div class="hero-actions">
            <button class="btn btn-primary" @click="emit('navigate', 'etfs')">ETF Explorer</button>
            <button class="btn btn-outline" @click="openApiKey">Get API Key</button>
          </div>
          <p class="hero-disclaimer">For informational purposes only. Not investment advice.</p>
        </div>

        <div class="score-widget">
          <div class="widget-header">
            <span class="live-dot"></span>
            <span class="endpoint">GET /scores/etfs</span>
            <span class="ok-badge" style="margin-left:auto">200 OK</span>
          </div>
          <div v-if="loadingScores" class="widget-loading">Fetching live scores...</div>
          <div v-else class="score-rows">
            <div v-for="row in topScores" :key="row.ticker" class="score-row">
              <span class="score-ticker">{{ row.ticker }}</span>
              <span class="score-name">{{ row.name }}</span>
              <div class="score-bar-wrap">
                <div class="score-bar" :class="barClass(row.score)" :style="{ width: ((row.score || 0) * 10) + '%' }"></div>
              </div>
              <span class="score-num" :class="scoreClass(row.score)">{{ row.score?.toFixed(1) ?? '-' }}</span>
            </div>
          </div>
          <div class="widget-footer">
            <span>GoETF Score · 1 = very poor, 10 = excellent</span>
            <span>{{ scoreError ? 'Fallback data' : 'Live data' }}</span>
          </div>
        </div>
      </div>
    </section>

    <div class="strip">
      <div class="container strip-grid">
        <div class="strip-item">
          <h3>GoETF Score</h3>
          <p>Every ETF receives a score from 1-10 based on performance, risk, diversification, and cost.</p>
        </div>
        <div class="strip-item">
          <h3>Overlap Analysis</h3>
          <p>How much of your portfolio is in the exact same positions? GoETF shows it.</p>
        </div>
        <div class="strip-item">
          <h3>Portfolio Simplifier</h3>
          <p>Reduce redundant ETFs and keep exposure quality with less complexity.</p>
        </div>
        <div class="strip-item">
          <h3>API & Docs</h3>
          <p>REST API with free key and live response examples in the docs.</p>
        </div>
      </div>
    </div>

    <section class="section score-section">
      <div class="container score-grid">
        <div>
          <p class="section-label">GoETF Score</p>
          <h2>A score grounded in facts</h2>
          <p class="section-copy">
            Morningstar stars measure relative past performance within a category. The GoETF Score calculates on an
            absolute basis, making apples-to-apples comparisons across ETFs.
          </p>

          <div class="score-pillars">
            <div class="pillar"><span>Performance</span><div class="pillar-track"><div class="pillar-fill" style="width:40%"></div></div><em>40%</em></div>
            <div class="pillar"><span>Risk</span><div class="pillar-track"><div class="pillar-fill risk" style="width:30%"></div></div><em>30%</em></div>
            <div class="pillar"><span>Diversification</span><div class="pillar-track"><div class="pillar-fill div" style="width:20%"></div></div><em>20%</em></div>
            <div class="pillar"><span>Cost (TER)</span><div class="pillar-track"><div class="pillar-fill cost" style="width:10%"></div></div><em>10%</em></div>
          </div>

          <button class="btn btn-outline" @click="emit('navigate', 'methodology')">Read methodology</button>

          <div class="comp-table">
            <h3>ETF Comparison</h3>
            <table>
              <thead>
                <tr>
                  <th>ETF</th>
                  <th>Score</th>
                  <th>TER</th>
                  <th>Sharpe</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in topScores" :key="row.ticker + '-table'">
                  <td>{{ row.ticker }}</td>
                  <td>{{ row.score?.toFixed(1) ?? '-' }}</td>
                  <td>{{ row.terText }}</td>
                  <td>{{ row.sharpeText }}</td>
                </tr>
              </tbody>
            </table>
            <button class="link-btn" @click="navigateTo('analytics', 'goetf')">View all ETF scores</button>
          </div>
        </div>

        <div class="score-card" v-if="featuredScore">
          <div class="score-card-head">
            <div>
              <strong>{{ featuredScore.ticker }}</strong>
              <small>{{ featuredScore.name }}</small>
            </div>
            <span class="badge badge-blue">{{ featuredScore.provider || 'ETF' }}</span>
          </div>
          <div class="gauge-wrap">
            <svg width="200" height="120" viewBox="0 0 200 120">
              <path d="M 20 110 A 80 80 0 0 1 180 110" fill="none" stroke="#e5e7eb" stroke-width="14" stroke-linecap="round"/>
              <path
                d="M 20 110 A 80 80 0 0 1 180 110"
                fill="none"
                stroke="#22c55e"
                stroke-width="14"
                stroke-linecap="round"
                :stroke-dasharray="251.2"
                :stroke-dashoffset="251.2 - ((featuredScore.score || 0) / 10) * 251.2"
              />
              <text x="100" y="104" text-anchor="middle" class="gauge-text">{{ featuredScore.score?.toFixed(1) ?? '-' }}</text>
            </svg>
          </div>
          <div class="score-meta">
            <div><span>TER</span><strong>{{ featuredScore.terText }}</strong></div>
            <div><span>Fund Size</span><strong>{{ featuredScore.fundSizeText }}</strong></div>
            <div><span>Sharpe</span><strong>{{ featuredScore.sharpeText }}</strong></div>
            <div><span>Max Drawdown</span><strong>{{ featuredScore.ddText }}</strong></div>
          </div>
          <button class="btn btn-outline" style="width:100%" @click="openFeaturedETF">{{ featuredScore.ticker }} Full Analysis</button>
        </div>
      </div>
    </section>

    <section class="section overlap-section">
      <div class="container">
        <p class="section-label light">Portfolio Overlap</p>
        <h2>Do you know what's really in your portfolio?</h2>
        <p class="overlap-copy">
          Select ETFs to estimate pairwise overlap using live portfolio-score analytics.
        </p>

        <div class="overlap-selectors">
          <button
            v-for="ticker in overlapUniverse"
            :key="ticker"
            class="etf-toggle"
            :class="{ active: activeETFs.includes(ticker) }"
            @click="toggleETF(ticker)"
          >
            {{ ticker }}
          </button>
        </div>

        <div class="matrix-wrap">
          <table class="matrix-table">
            <thead>
              <tr>
                <th></th>
                <th v-for="col in activeETFs" :key="'col-' + col">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in activeETFs" :key="'row-' + row">
                <th class="row-label">{{ row }}</th>
                <td v-for="col in activeETFs" :key="row + '-' + col">
                  <div class="matrix-cell" :class="matrixClass(row, col)">
                    {{ row === col ? '-' : matrixLabel(row, col) }}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p class="overlap-insight">
          {{ overlapInsight }}
        </p>

        <div class="centered-row">
          <button class="btn btn-accent" @click="navigateTo('analytics', 'exposure')">Analyze my portfolio</button>
        </div>
      </div>
    </section>

    <section class="section tools-section">
      <div class="container">
        <p class="section-label">Portfolio Tools</p>
        <h2>Fewer ETFs. Better portfolio.</h2>
        <div class="tools-grid">
          <div class="tool-card">
            <h3>Portfolio Simplifier</h3>
            <p>Detect redundant ETF combinations and move to cleaner exposure with fewer lines.</p>
            <button class="btn btn-outline" @click="navigateTo('analytics', 'exposure')">Try it</button>
          </div>
          <div class="tool-card">
            <h3>Portfolio Enhancer</h3>
            <p>Add targeted exposure while checking overlap and portfolio quality in one place.</p>
            <button class="btn btn-outline" @click="navigateTo('analytics', 'exposure')">Try it</button>
          </div>
        </div>
      </div>
    </section>

    <section class="section api-section">
      <div class="container api-grid">
        <div>
          <p class="section-label light">API & Integration</p>
          <h2>For developers and asset managers</h2>
          <ul class="api-points">
            <li>Full REST API for holdings, allocations, analytics, and scores.</li>
            <li>Free API key without credit card.</li>
            <li>Live examples in API docs with demo key support.</li>
          </ul>
          <div class="hero-actions">
            <button class="btn btn-accent" @click="openApiKey">Get API Key</button>
            <button class="btn btn-ghost-light" @click="emit('navigate', 'docs')">Read the docs</button>
          </div>
        </div>

        <div class="code-block-wrap">
          <div class="code-tabs">
            <button
              v-for="tab in ['python', 'js', 'curl']"
              :key="tab"
              class="code-tab"
              :class="{ active: codeTab === tab }"
              @click="codeTab = tab"
            >
              {{ tab === 'js' ? 'JavaScript' : tab.toUpperCase() }}
            </button>
          </div>
          <pre class="code-content">{{ codeSnippets[codeTab] }}</pre>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref, watch } from 'vue'
import { etfService, scoreService } from '../services/api.js'

const emit = defineEmits(['navigate'])
const showApiKeyModal = inject('showApiKeyModal')
const navigateTo = inject('navigateTo')
const navigateToETF = inject('navigateToETF')

const loadingScores = ref(false)
const scoreError = ref('')
const codeTab = ref('python')

const topScores = ref([
  { ticker: 'SWDA', name: 'iShares Core MSCI World', score: 7.8, terText: '0.20%', sharpeText: '0.82', fundSizeText: '$101.7bn', ddText: '-32.9%' },
  { ticker: 'CSSPX', name: 'iShares Core S&P 500', score: 7.2, terText: '0.07%', sharpeText: '0.91', fundSizeText: '-', ddText: '-' },
  { ticker: 'VUSA', name: 'Vanguard S&P 500 UCITS ETF', score: 6.9, terText: '0.07%', sharpeText: '0.88', fundSizeText: '-', ddText: '-' },
  { ticker: 'ISF', name: 'iShares Core FTSE 100', score: 6.5, terText: '0.07%', sharpeText: '0.64', fundSizeText: '-', ddText: '-' },
  { ticker: 'SEDY', name: 'SPDR S&P Em. Mkts Dividend', score: 5.9, terText: '0.40%', sharpeText: '0.51', fundSizeText: '-', ddText: '-' },
])

const featuredScore = computed(() => topScores.value[0])
const trackedCount = computed(() => topScores.value.length)

function fmtTer(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `${Number(value).toFixed(2)}%`
}

function fmtSize(value) {
  if (!value) return '-'
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}bn`
  if (value >= 1e6) return `$${(value / 1e6).toFixed(0)}m`
  return `$${Number(value).toLocaleString()}`
}

async function loadScores() {
  loadingScores.value = true
  scoreError.value = ''
  try {
    const tickers = ['SWDA', 'CSSPX', 'VUSA', 'ISF', 'SEDY']
    const [scoresRes, etfRes] = await Promise.all([
      scoreService.getEtfScores(tickers, 0.04),
      etfService.getETFs(0, 200),
    ])

    const detailsByTicker = new Map((etfRes.data || []).map(e => [e.ticker, e]))
    const scoreByTicker = new Map((scoresRes.data || []).map(s => [s.ticker, s]))

    topScores.value = tickers.map(ticker => {
      const details = detailsByTicker.get(ticker) || {}
      const scoreData = scoreByTicker.get(ticker) || {}
      return {
        ticker,
        name: details.name || scoreData.name || ticker,
        provider: details.provider || '',
        score: scoreData.goetf_score ?? scoreData.score ?? null,
        terText: fmtTer(details.ter),
        sharpeText: scoreData.sharpe_ratio != null ? Number(scoreData.sharpe_ratio).toFixed(2) : '-',
        fundSizeText: fmtSize(details.fund_size),
        ddText: scoreData.max_drawdown != null ? `${Number(scoreData.max_drawdown).toFixed(1)}%` : '-',
      }
    })
  } catch (e) {
    scoreError.value = e?.response?.data?.detail || e.message || 'Failed to load live scores'
  } finally {
    loadingScores.value = false
  }
}

function openApiKey() {
  if (showApiKeyModal) showApiKeyModal.value = true
}

async function openFeaturedETF() {
  const ticker = featuredScore.value?.ticker
  if (!ticker) {
    emit('navigate', 'etfs')
    return
  }
  try {
    const res = await etfService.getETFs(0, 200)
    const found = (res.data || []).find(e => e.ticker === ticker)
    if (found && navigateToETF) {
      navigateToETF(found)
      return
    }
  } catch {}
  emit('navigate', 'etfs')
}

function scoreClass(score) {
  if (score == null) return ''
  if (score >= 7) return 'hi'
  if (score >= 6) return 'md'
  return 'lo'
}

function barClass(score) {
  if (score == null) return ''
  if (score >= 7) return 'bar-hi'
  if (score >= 6) return 'bar-md'
  return 'bar-lo'
}

const overlapUniverse = ['SWDA', 'CSSPX', 'VUSA', 'ISF', 'SEDY']
const activeETFs = ref(['SWDA', 'CSSPX', 'VUSA', 'ISF'])
const overlapMap = ref({})

const fallbackOverlap = {
  SWDA: { SWDA: 100, CSSPX: 78, VUSA: 71, ISF: 12, SEDY: 8 },
  CSSPX: { SWDA: 78, CSSPX: 100, VUSA: 95, ISF: 8, SEDY: 7 },
  VUSA: { SWDA: 71, CSSPX: 95, VUSA: 100, ISF: 9, SEDY: 6 },
  ISF: { SWDA: 12, CSSPX: 8, VUSA: 9, ISF: 100, SEDY: 4 },
  SEDY: { SWDA: 8, CSSPX: 7, VUSA: 6, ISF: 4, SEDY: 100 },
}

function pairKey(a, b) {
  return [a, b].sort().join('__')
}

async function loadPairOverlap(a, b) {
  const key = pairKey(a, b)
  if (overlapMap.value[key] != null) return
  try {
    const res = await scoreService.getPortfolioScore(
      [
        { etf_id: a, weight: 50 },
        { etf_id: b, weight: 50 },
      ],
      0.04
    )
    const pair = res.data?.pairwise_overlaps?.[0]
    overlapMap.value[key] = pair?.weight_overlap_pct ?? res.data?.avg_overlap_pct ?? fallbackOverlap[a][b]
  } catch {
    overlapMap.value[key] = fallbackOverlap[a][b]
  }
}

async function refreshOverlap() {
  const tasks = []
  for (let i = 0; i < activeETFs.value.length; i += 1) {
    for (let j = i + 1; j < activeETFs.value.length; j += 1) {
      tasks.push(loadPairOverlap(activeETFs.value[i], activeETFs.value[j]))
    }
  }
  await Promise.all(tasks)
}

function toggleETF(ticker) {
  const idx = activeETFs.value.indexOf(ticker)
  if (idx >= 0) {
    if (activeETFs.value.length <= 2) return
    activeETFs.value = activeETFs.value.filter(t => t !== ticker)
  } else {
    activeETFs.value = [...activeETFs.value, ticker]
  }
}

function overlapValue(a, b) {
  if (a === b) return 100
  const value = overlapMap.value[pairKey(a, b)]
  return value != null ? value : fallbackOverlap[a][b]
}

function matrixLabel(a, b) {
  const v = overlapValue(a, b)
  return `${Number(v).toFixed(0)}%`
}

function matrixClass(a, b) {
  if (a === b) return 'cell-self'
  const v = overlapValue(a, b)
  if (v >= 60) return 'cell-hi'
  if (v >= 30) return 'cell-md'
  return 'cell-lo'
}

const overlapInsight = computed(() => {
  const pairs = []
  for (let i = 0; i < activeETFs.value.length; i += 1) {
    for (let j = i + 1; j < activeETFs.value.length; j += 1) {
      const a = activeETFs.value[i]
      const b = activeETFs.value[j]
      pairs.push({ a, b, v: overlapValue(a, b) })
    }
  }
  if (!pairs.length) return 'Select at least two ETFs to evaluate overlap.'
  pairs.sort((x, y) => y.v - x.v)
  const top = pairs[0]
  return `Highest overlap right now: ${top.a} vs ${top.b} at ${top.v.toFixed(1)}%. Consider simplifying if several pairs are above 60%.`
})

const codeSnippets = {
  python: `import requests\n\nbase = "https://api.goetf.ch"\nheaders = {"x-api-key": "YOUR_API_KEY"}\n\n# ETF scores\nscores = requests.get(f"{base}/scores/etfs", headers=headers).json()\n\n# Portfolio analysis\nportfolio = {"portfolio": [{"etf_id": "SWDA", "weight": 60}, {"etf_id": "CSSPX", "weight": 40}]}\nresult = requests.post(f"{base}/analytics/exposure", json=portfolio, headers=headers).json()`,
  js: `const base = "https://api.goetf.ch";\nconst headers = { "x-api-key": "YOUR_API_KEY", "Content-Type": "application/json" };\n\nconst scores = await fetch(base + "/scores/etfs", { headers }).then(r => r.json());\n\nconst exposure = await fetch(base + "/analytics/exposure", {\n  method: "POST",\n  headers,\n  body: JSON.stringify({ portfolio: [{ etf_id: "SWDA", weight: 60 }, { etf_id: "CSSPX", weight: 40 }] })\n}).then(r => r.json());`,
  curl: `curl -H "x-api-key: YOUR_API_KEY" https://api.goetf.ch/scores/etfs\n\ncurl -X POST https://api.goetf.ch/analytics/exposure \\\n  -H "x-api-key: YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"portfolio":[{"etf_id":"SWDA","weight":60},{"etf_id":"CSSPX","weight":40}]}'`,
}

watch(activeETFs, () => {
  refreshOverlap()
}, { deep: true })

onMounted(async () => {
  await loadScores()
  await refreshOverlap()
})
</script>

<style scoped>
.home-page { background: #f8f9fb; color: #111827; }
.container { max-width: 1200px; margin: 0 auto; padding: 0 24px; }
.section { padding: 88px 0; }
.hero { padding: 96px 0 72px; }
.hero-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 56px; align-items: center; }
h1 { font-size: clamp(2rem, 4.6vw, 3.2rem); line-height: 1.1; letter-spacing: -0.02em; margin-bottom: 16px; }
.lead { color: #6b7280; max-width: 520px; margin-bottom: 30px; }
.hero-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.hero-disclaimer { margin-top: 18px; color: #9ca3af; font-size: 12px; }
.hero-eyebrow { margin-bottom: 14px; }
.badge { border-radius: 999px; font-size: 12px; font-weight: 600; padding: 4px 12px; display: inline-flex; align-items: center; gap: 6px; }
.badge-accent { background: rgba(0,201,167,.12); color: #009f86; }
.badge-blue { background: rgba(15,76,129,.1); color: #0f4c81; }
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; display: inline-block; animation: pulse 1.8s infinite; }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.4; } }

.btn { border: none; border-radius: 8px; padding: 11px 20px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-primary { background: #0f4c81; color: #fff; }
.btn-primary:hover { background: #1a6ab8; }
.btn-outline { background: transparent; border: 1.5px solid #0f4c81; color: #0f4c81; }
.btn-outline:hover { background: #0f4c81; color: #fff; }
.btn-accent { background: #00c9a7; color: #111827; }
.btn-ghost-light { background: rgba(255,255,255,.15); color: #fff; border: 1px solid rgba(255,255,255,.28); }

.score-widget { background: #fff; border: 1px solid #e5e7eb; border-radius: 16px; box-shadow: 0 8px 40px rgba(15,76,129,.12); overflow: hidden; }
.widget-header { display: flex; align-items: center; gap: 8px; padding: 14px 18px; border-bottom: 1px solid #e5e7eb; font-size: 12px; color: #6b7280; }
.endpoint { font-family: 'JetBrains Mono', monospace; color: #0f4c81; }
.ok-badge { background: #dcfce7; color: #15803d; border-radius: 4px; font-size: 11px; font-weight: 700; padding: 2px 7px; }
.widget-loading { padding: 16px 18px; color: #6b7280; font-size: 13px; }
.score-row { display: flex; align-items: center; gap: 10px; padding: 9px 18px; }
.score-ticker { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 12px; width: 48px; }
.score-name { flex: 1; color: #6b7280; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.score-bar-wrap { width: 80px; height: 6px; border-radius: 999px; background: #f3f4f6; overflow: hidden; }
.score-bar { height: 6px; }
.bar-hi { background: #22c55e; }
.bar-md { background: #f59e0b; }
.bar-lo { background: #ef4444; }
.score-num { width: 30px; text-align: right; font-weight: 700; font-size: 13px; }
.score-num.hi { color: #22c55e; }
.score-num.md { color: #f59e0b; }
.score-num.lo { color: #ef4444; }
.widget-footer { padding: 10px 18px; border-top: 1px solid #e5e7eb; font-size: 11px; color: #9ca3af; display: flex; justify-content: space-between; gap: 8px; }

.strip { background: #111827; }
.strip-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: rgba(255,255,255,.08); }
.strip-item { background: #111827; padding: 30px 24px; }
.strip-item h3 { color: #fff; margin-bottom: 8px; font-size: 16px; }
.strip-item p { color: rgba(255,255,255,.62); font-size: 14px; }

.score-section { background: #fff; }
.score-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 56px; align-items: start; }
.section-label { font-size: 12px; letter-spacing: .08em; text-transform: uppercase; font-weight: 700; color: #00c9a7; margin-bottom: 10px; }
.section-label.light { color: rgba(0,201,167,.85); }
h2 { font-size: clamp(1.65rem, 3vw, 2.2rem); line-height: 1.2; letter-spacing: -0.02em; margin-bottom: 12px; }
.section-copy { color: #6b7280; margin-bottom: 22px; }
.score-pillars { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
.pillar { display: flex; align-items: center; gap: 12px; }
.pillar span { width: 160px; font-size: 14px; }
.pillar em { width: 36px; text-align: right; color: #6b7280; font-style: normal; font-size: 13px; }
.pillar-track { flex: 1; height: 8px; border-radius: 999px; background: #f3f4f6; overflow: hidden; }
.pillar-fill { height: 8px; background: #0f4c81; }
.pillar-fill.risk { background: #1a6ab8; }
.pillar-fill.div { background: #00c9a7; }
.pillar-fill.cost { background: #9ca3af; }
.comp-table { margin-top: 24px; }
.comp-table h3 { margin-bottom: 10px; }
.comp-table table { width: 100%; border-collapse: collapse; }
.comp-table th, .comp-table td { padding: 10px 0; border-bottom: 1px solid #e5e7eb; text-align: left; font-size: 14px; }
.comp-table th:not(:first-child), .comp-table td:not(:first-child) { text-align: right; }
.link-btn { margin-top: 12px; background: none; border: none; color: #0f4c81; cursor: pointer; font-weight: 600; }

.score-card { position: sticky; top: 82px; background: #f8f9fb; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px; }
.score-card-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.score-card-head small { display: block; color: #6b7280; margin-top: 2px; }
.gauge-wrap { display: flex; justify-content: center; margin-bottom: 10px; }
.gauge-text { font-size: 38px; font-weight: 700; fill: #111827; font-family: Inter, sans-serif; }
.score-meta { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 14px; }
.score-meta div { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; }
.score-meta span { display: block; color: #6b7280; font-size: 11px; margin-bottom: 2px; }
.score-meta strong { font-size: 14px; }

.overlap-section { background: #111827; color: #fff; }
.overlap-copy { color: rgba(255,255,255,.72); margin-bottom: 18px; }
.overlap-selectors { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
.etf-toggle { border: 1px solid rgba(255,255,255,.2); border-radius: 8px; padding: 7px 14px; background: transparent; color: rgba(255,255,255,.7); cursor: pointer; }
.etf-toggle.active { background: #00c9a7; color: #111827; border-color: #00c9a7; font-weight: 700; }
.matrix-wrap { overflow-x: auto; }
.matrix-table { border-collapse: collapse; min-width: 430px; }
.matrix-table th, .matrix-table td { width: 88px; height: 50px; text-align: center; font-size: 13px; }
.row-label { text-align: right; padding-right: 12px; color: rgba(255,255,255,.7); font-family: 'JetBrains Mono', monospace; }
.matrix-cell { border-radius: 6px; height: 38px; display: flex; align-items: center; justify-content: center; }
.cell-self { background: rgba(255,255,255,.07); color: rgba(255,255,255,.35); }
.cell-hi { background: rgba(239,68,68,.25); color: #fca5a5; }
.cell-md { background: rgba(245,158,11,.22); color: #fcd34d; }
.cell-lo { background: rgba(34,197,94,.2); color: #86efac; }
.overlap-insight { margin-top: 20px; background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.15); border-radius: 12px; padding: 16px 18px; color: rgba(255,255,255,.8); }
.centered-row { text-align: center; margin-top: 26px; }

.tools-section { background: #f8f9fb; }
.tools-grid { margin-top: 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.tool-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px; }
.tool-card p { color: #6b7280; margin: 10px 0 18px; }

.api-section { background: #111827; color: #fff; }
.api-grid { display: grid; grid-template-columns: 1fr 1.25fr; gap: 48px; align-items: start; }
.api-points { margin: 20px 0 28px; padding-left: 18px; color: rgba(255,255,255,.75); }
.api-points li { margin-bottom: 10px; }
.code-block-wrap { border: 1px solid rgba(255,255,255,.08); background: #0d1117; border-radius: 12px; overflow: hidden; }
.code-tabs { display: flex; border-bottom: 1px solid rgba(255,255,255,.08); }
.code-tab { border: none; background: transparent; color: rgba(255,255,255,.45); cursor: pointer; font-family: 'JetBrains Mono', monospace; font-size: 12px; padding: 11px 16px; }
.code-tab.active { color: #00c9a7; border-bottom: 2px solid #00c9a7; }
.code-content { margin: 0; padding: 20px; color: #e2e8f0; font-size: 13px; line-height: 1.65; overflow-x: auto; }

@media (max-width: 980px) {
  .hero-grid, .score-grid, .api-grid { grid-template-columns: 1fr; }
  .tools-grid { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .container { padding: 0 16px; }
  .hero { padding-top: 84px; }
  .strip-grid { grid-template-columns: 1fr; }
  .pillar span { width: 130px; }
}
</style>
