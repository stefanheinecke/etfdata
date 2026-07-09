<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">Portfolio Analytics</h1>
      <p class="page-subtitle">Portfolio exposure breakdown and per-ETF risk metrics in one call.</p>
    </div>
    <div v-if="!hasApiKey" class="cta-banner">
      <div class="cta-text">
        <strong>An API key is required to run analytics.</strong>
        <span>Get yours for free in 10 seconds.</span>
      </div>
      <button class="cta-btn" @click="showApiKeyModal = true">Get Free API Key</button>
    </div>
    <div class="ana-tabs">
      <button v-for="t in tabs" :key="t.id" :class="['ana-tab',{active:activeTab===t.id}]" @click="activeTab=t.id">
        <span>{{ t.icon }}</span> {{ t.label }}
      </button>
    </div>

    <!-- EXPOSURE -->
    <div v-if="activeTab==='exposure'">
      <div class="card" style="margin-bottom:1.5rem">
        <h2 class="card-title">Portfolio Exposure</h2>
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">Define a portfolio (ETF ID + weight%) to analyse sector, country and currency exposure.</p>
        <div v-for="(item,i) in portfolio" :key="i" style="display:flex;gap:.5rem;margin-bottom:.5rem;align-items:center">
          <select class="input" v-model="item.etf_id" style="flex:2">
            <option value="">Select ETF...</option>
            <option v-for="e in allEtfs" :key="e.id" :value="e.id">{{ e.ticker }} - {{ e.name }}</option>
          </select>
          <input class="input" type="number" v-model.number="item.weight" placeholder="Weight %" style="flex:1;max-width:120px" min="0" max="100" />
          <button class="btn btn-outline" @click="portfolio.splice(i,1)" style="flex-shrink:0">✕</button>
        </div>
        <div style="display:flex;gap:.75rem;margin-top:.75rem;align-items:center;flex-wrap:wrap">
          <button class="btn btn-outline" @click="portfolio.push({etf_id:'',weight:0})">+ Add ETF</button>
          <button class="btn btn-primary" @click="runExposure" :disabled="exposureLoading || !portfolio.some(p=>p.etf_id)">
            {{ exposureLoading ? 'Calculating...' : 'Analyse Exposure' }}
          </button>
          <label style="font-size:.8rem;color:var(--text-muted);margin-left:auto">Risk-free rate</label>
          <input class="input" type="number" v-model.number="riskFreeRate" min="0" max="20" step="0.5"
            style="width:72px;padding:.3rem .5rem;font-size:.875rem" />
          <span style="font-size:.8rem;color:var(--text-muted)">% p.a.</span>
        </div>
      </div>
      <!-- GoETF Portfolio Score - quick feedback below builder -->
      <div v-if="portfolioScoreLoading" style="margin-bottom:1.5rem;padding:1rem 1.25rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);font-size:.875rem;color:var(--text-muted)">Computing GoETF Portfolio Score…</div>
      <div v-if="portfolioScoreResult" class="card" style="margin-bottom:1.5rem">
        <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap;margin-bottom:1rem">
          <h3 class="card-title" style="margin:0">GoETF Portfolio Score</h3>
          <span class="score-badge score-lg" :class="scoreBadgeClass(portfolioScoreResult.portfolio_score)">
            {{ portfolioScoreResult.portfolio_score?.toFixed(1) }}
          </span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:.75rem;margin-bottom:1rem">
          <div class="stat-box">
            <div class="stat-label">Base Score</div>
            <div class="stat-value">{{ portfolioScoreResult.base_score?.toFixed(1) }}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Overlap Penalty</div>
            <div class="stat-value" style="color:#ef4444">−{{ portfolioScoreResult.overlap_penalty?.toFixed(2) }}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Diversification Bonus</div>
            <div class="stat-value" style="color:#0b6aa5">+{{ portfolioScoreResult.allocation_bonus?.toFixed(2) }}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Avg Holdings Overlap</div>
            <div class="stat-value" :class="portfolioScoreResult.avg_overlap_pct > 50 ? 'cell-red' : portfolioScoreResult.avg_overlap_pct > 20 ? 'cell-yellow' : 'cell-green'">
              {{ portfolioScoreResult.avg_overlap_pct?.toFixed(1) }}%
            </div>
          </div>
        </div>
        <div v-if="portfolioScoreResult.pairwise_overlaps?.length" style="margin-bottom:1rem">
          <div style="font-size:.8rem;font-weight:600;color:var(--text-muted);margin-bottom:.5rem">Holdings Overlap by Pair</div>
          <div v-for="ov in portfolioScoreResult.pairwise_overlaps" :key="ov.etf_a_id+ov.etf_b_id" style="display:flex;align-items:center;gap:.75rem;margin-bottom:.4rem">
            <span style="font-size:.85rem;font-weight:600;color:var(--green-600)">{{ ov.etf_a_ticker }}</span>
            <span style="font-size:.75rem;color:var(--text-muted)">↔</span>
            <span style="font-size:.85rem;font-weight:600;color:var(--green-600)">{{ ov.etf_b_ticker }}</span>
            <div class="alloc-track" style="flex:1;max-width:180px"><div class="alloc-fill" :style="{width:Math.min(ov.weight_overlap_pct,100)+'%',background:ov.weight_overlap_pct>50?'#ef4444':ov.weight_overlap_pct>20?'#ca8a04':'#0b6aa5'}"></div></div>
            <span style="font-size:.85rem;font-weight:600">{{ ov.weight_overlap_pct?.toFixed(1) }}%</span>
          </div>
        </div>
        <div v-if="portfolioScoreResult.tip" class="tip-box">
          <span class="tip-icon">💡</span>
          <div>
            <strong style="color:var(--green-600)">{{ portfolioScoreResult.tip.with_ticker }}</strong>
            has lower holdings overlap than <strong style="color:var(--green-600)">{{ portfolioScoreResult.tip.replace_ticker }}</strong>.
            Using <strong style="color:var(--green-600)">{{ portfolioScoreResult.tip.with_ticker }}</strong>
            instead would increase your portfolio score to <strong>{{ portfolioScoreResult.tip.new_score }}</strong>
            (<span style="color:#0b6aa5">+{{ portfolioScoreResult.tip.improvement }}</span>).
            <div style="font-size:.8rem;color:var(--text-muted);margin-top:.2rem">{{ portfolioScoreResult.tip.reason }}</div>
          </div>
        </div>
        <div v-else-if="portfolioScoreResult.tip === null" style="font-size:.8rem;color:var(--text-muted)">No higher-scoring alternative cleared the +0.1 threshold.</div>
        <p style="font-size:.7rem;color:var(--text-muted);margin-top:.75rem;margin-bottom:0">
          Base = weighted avg of individual GoETF Scores &nbsp;·&nbsp; Overlap Penalty: max −2 pts for 100% overlap &nbsp;·&nbsp; Bonus: portfolio country diversification vs individual weighted avg
          &nbsp;<button class="meth-link" @click="navigateTo('methodology')">→ Methodology</button>
        </p>
      </div>
      <div v-if="exposureError" class="error-box" style="margin-bottom:1rem">{{ exposureError }}</div>
      <div v-if="exposureResult" class="grid-3">
        <div class="card" v-for="group in exposureGroups" :key="group.label">
          <h3 class="card-title">{{ group.label }}</h3>
          <div class="alloc-bars">
            <div v-for="[k,v] in group.entries" :key="k" class="alloc-row">
              <span class="alloc-label">{{ k }}</span>
              <div class="alloc-track"><div class="alloc-fill" :style="{width:Math.min(v,100)+'%'}"></div></div>
              <span class="alloc-pct">{{ Number(v).toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Portfolio Risk Metrics -->
      <div v-if="portfolioRiskResult">

        <!-- Portfolio-level summary -->
        <div v-if="portfolioSummary" class="card" style="margin-top:1.5rem">
          <h3 class="card-title" style="margin-bottom:1rem">Portfolio Summary <span style="font-size:.75rem;font-weight:400;color:var(--text-muted)">(weighted average across ETFs)</span></h3>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:.75rem">
            <div class="stat-box">
              <div class="stat-label">1Y Return</div>
              <div class="stat-value" :class="signClass(portfolioSummary.ann_return)">{{ fmtPct(portfolioSummary.ann_return) }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Volatility</div>
              <div class="stat-value" :class="volClass(portfolioSummary.volatility)">{{ fmtPct(portfolioSummary.volatility) }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Sharpe Ratio</div>
              <div class="stat-value" :class="sharpeClass(portfolioSummary.sharpe_ratio)">{{ portfolioSummary.sharpe_ratio !== null ? portfolioSummary.sharpe_ratio.toFixed(2) : '—' }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Max Drawdown</div>
              <div class="stat-value" :class="ddClass(portfolioSummary.max_drawdown)">{{ fmtPct(portfolioSummary.max_drawdown) }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Avg HHI</div>
              <div class="stat-value" :class="hhiClass(portfolioSummary.hhi)">{{ portfolioSummary.hhi.toFixed(0) }}</div>
            </div>
          </div>
          <p style="font-size:.7rem;color:var(--text-muted);margin-top:.75rem;margin-bottom:0">
            Weighted by portfolio allocation &nbsp;·&nbsp; Rf = {{ riskFreeRate }}% &nbsp;·&nbsp; Volatility is a weighted average (not true portfolio volatility, which requires correlation data)
          </p>
        </div>

        <!-- Per-ETF breakdown -->
        <div class="card" style="margin-top:1rem;padding:0;overflow:hidden">
          <div style="padding:1rem 1.25rem;border-bottom:1px solid var(--border)">
            <h3 class="card-title" style="margin:0">Per-ETF Risk Breakdown</h3>
          </div>
          <div class="table-wrap">
          <table class="risk-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>1Y Return</th>
                <th>Volatility</th>
                <th>Sharpe</th>
                <th>Max Drawdown</th>
                <th>HHI</th>
                <th># Holdings</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in portfolioRiskResult" :key="row.etf_id">
                <td><strong style="color:var(--green-600)">{{ row.ticker }}</strong></td>
                <td :class="signClass(row.ann_return)">{{ fmtPct(row.ann_return) }}</td>
                <td :class="volClass(row.volatility)">{{ fmtPct(row.volatility) }}</td>
                <td :class="sharpeClass(row.sharpe_ratio)">{{ row.sharpe_ratio !== null ? row.sharpe_ratio : '—' }}</td>
                <td :class="ddClass(row.max_drawdown)">{{ fmtPct(row.max_drawdown) }}</td>
                <td :class="hhiClass(row.hhi)">{{ row.hhi !== null ? row.hhi.toFixed(0) : '—' }}</td>
                <td>{{ row.num_holdings?.toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="padding:.6rem 1.25rem;font-size:.72rem;color:var(--text-muted);border-top:1px solid var(--border)">
          Rf = {{ riskFreeRate }}% &nbsp;·&nbsp; HHI: Herfindahl-Hirschman Index (0-10,000; lower = more diversified)
        </div>
      </div>
      </div>    </div>

    <!-- RISK METRICS -->
    <div v-if="activeTab==='risk'">
      <div class="card" style="margin-bottom:1.5rem;display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
        <h2 class="card-title" style="margin:0">Risk Metrics</h2>
        <label style="font-size:.8rem;color:var(--text-muted);margin-left:auto">Risk-free rate</label>
        <input class="input" type="number" v-model.number="riskRfRate" min="0" max="20" step="0.5"
          style="width:72px;padding:.3rem .5rem;font-size:.875rem" />
        <span style="font-size:.8rem;color:var(--text-muted)">% p.a.</span>
        <button class="btn btn-outline" style="font-size:.875rem" @click="runRiskMetrics" :disabled="riskLoading">
          {{ riskLoading ? 'Loading…' : '↻ Recalculate' }}
        </button>
      </div>
      <div v-if="riskError" class="error-box" style="margin-bottom:1rem">{{ riskError }}</div>
      <div v-if="riskResult" class="card" style="padding:0;overflow:hidden">
        <div style="padding:.75rem 1.25rem;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center">
          <h3 class="card-title" style="margin:0">{{ riskResult.length }} ETF{{ riskResult.length !== 1 ? 's' : '' }}</h3>
          <span style="font-size:.75rem;color:var(--text-muted)">Rf = {{ riskRfRate }}% &nbsp;·&nbsp; Click column header to sort</span>
        </div>
        <div class="table-wrap">
          <table class="risk-table">
            <thead>
              <tr>
                <th class="sortable-th" @click="toggleRiskSort('ticker')">Ticker <span class="sort-arrow">{{ riskSortKey==='ticker' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('ann_return')">1Y Return <span class="sort-arrow">{{ riskSortKey==='ann_return' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('volatility')">Volatility <span class="sort-arrow">{{ riskSortKey==='volatility' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('sharpe_ratio')">Sharpe <span class="sort-arrow">{{ riskSortKey==='sharpe_ratio' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('max_drawdown')">Max Drawdown <span class="sort-arrow">{{ riskSortKey==='max_drawdown' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('hhi')">HHI <span class="sort-arrow">{{ riskSortKey==='hhi' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('num_holdings')">Holdings <span class="sort-arrow">{{ riskSortKey==='num_holdings' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in riskSorted" :key="row.etf_id">
                <td><strong style="color:var(--green-600)">{{ row.ticker }}</strong></td>
                <td :class="signClass(row.ann_return)">{{ fmtPct(row.ann_return) }}</td>
                <td :class="volClass(row.volatility)">{{ fmtPct(row.volatility) }}</td>
                <td :class="sharpeClass(row.sharpe_ratio)">{{ row.sharpe_ratio !== null ? row.sharpe_ratio : '—' }}</td>
                <td :class="ddClass(row.max_drawdown)">{{ fmtPct(row.max_drawdown) }}</td>
                <td :class="hhiClass(row.hhi)">{{ row.hhi !== null ? row.hhi.toFixed(0) : '—' }}</td>
                <td>{{ row.num_holdings?.toLocaleString() ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="padding:.6rem 1.25rem;font-size:.72rem;color:var(--text-muted);border-top:1px solid var(--border)">
          HHI: Herfindahl-Hirschman Index (0-10,000; lower = more diversified)
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { etfService, analyticsService, scoreService } from '../services/api.js'

const showApiKeyModal = inject('showApiKeyModal')
const analyticsInitTab = inject('analyticsInitTab', ref(null))
const navigateTo = inject('navigateTo')
const hasApiKey = inject('hasApiKey', ref(!!localStorage.getItem('api_key')))

const activeTab = ref('exposure')
const tabs = [
  {id:'exposure',label:'Portfolio Exposure',icon:'🌍'},
  {id:'risk',label:'Risk Metrics',icon:'📊'},
]
const allEtfs = ref([])
const etfsLoading = ref(false)

// Exposure
const portfolio = ref([{etf_id:'',weight:50},{etf_id:'',weight:50}])
const exposureLoading = ref(false)
const exposureResult = ref(null)
const exposureError = ref('')
const portfolioRiskResult = ref(null)
const portfolioScoreResult = ref(null)
const portfolioScoreLoading = ref(false)

const portfolioSummary = computed(() => {
  if (!portfolioRiskResult.value?.length) return null
  const p = portfolio.value.filter(x => x.etf_id)
  const totalW = p.reduce((s, x) => s + (x.weight || 0), 0)
  if (!totalW) return null
  let wReturn = 0, wVol = 0, wDD = 0, wHHI = 0
  for (const row of portfolioRiskResult.value) {
    const pw = p.find(x => x.etf_id === row.etf_id)
    const w = pw ? (pw.weight || 0) / totalW : 0
    if (row.ann_return   !== null) wReturn += w * row.ann_return
    if (row.volatility   !== null) wVol    += w * row.volatility
    if (row.max_drawdown !== null) wDD     += w * row.max_drawdown
    if (row.hhi          !== null) wHHI    += w * row.hhi
  }
  const rfDecimal = riskFreeRate.value / 100
  const sharpe = wVol > 0 ? ((wReturn - rfDecimal) / wVol).toFixed(2) : null
  return { ann_return: wReturn, volatility: wVol, sharpe_ratio: sharpe !== null ? Number(sharpe) : null, max_drawdown: wDD, hhi: wHHI }
})

const exposureGroups = computed(() => {
  if (!exposureResult.value) return []
  const r = exposureResult.value
  return [
    {label:'Sectors',entries:Object.entries(r.sectors||{}).sort((a,b)=>b[1]-a[1]).slice(0,8)},
    {label:'Countries',entries:Object.entries(r.countries||{}).sort((a,b)=>b[1]-a[1]).slice(0,8)},
    {label:'Currencies',entries:Object.entries(r.currencies||{}).sort((a,b)=>b[1]-a[1])},
  ].filter(g=>g.entries.length)
})

async function loadETFs() {
  etfsLoading.value=true
  try { const r=await etfService.getETFs(0,50); allEtfs.value=r.data } catch(e){console.error(e)} finally{etfsLoading.value=false}
}
async function runExposure() {
  exposureLoading.value=true; exposureError.value=''; exposureResult.value=null; portfolioRiskResult.value=null; portfolioScoreResult.value=null
  const p=portfolio.value.filter(x=>x.etf_id)
  try {
    const r = await analyticsService.calculateExposure(p, null, riskFreeRate.value / 100)
    exposureResult.value = r.data
    portfolioRiskResult.value = r.data.risk_metrics ?? null
    if (p.length >= 1) {
      portfolioScoreLoading.value = true
      try {
        const sr = await scoreService.getPortfolioScore(p, riskFreeRate.value / 100)
        portfolioScoreResult.value = sr.data
      } catch(e) { console.warn('Portfolio score failed:', e.message) }
        finally { portfolioScoreLoading.value = false }
    }
  } catch(e){exposureError.value=e.response?.data?.detail||e.message} finally{exposureLoading.value=false}
}
// Risk-free rate (used for portfolio Sharpe in summary)
const riskFreeRate = ref(4.0)     // % per year

const scoreBadgeClass = (s) => s >= 7 ? 'score-high' : s >= 5 ? 'score-mid' : s >= 3.5 ? 'score-low' : 'score-poor'
const hhiClass     = (v) => v == null ? '' : v < 200  ? 'cell-green' : v < 1000 ? 'cell-yellow' : 'cell-red'

// Risk Metrics tab
const riskSelectedEtfs = ref([])
const riskRfRate = ref(4.0)
const riskLoading = ref(false)
const riskResult = ref(null)
const riskError = ref('')
const riskSortKey = ref('ticker')
const riskSortDir = ref('asc')

const riskSorted = computed(() => {
  if (!riskResult.value) return []
  return [...riskResult.value].sort((a, b) => {
    let va = a[riskSortKey.value], vb = b[riskSortKey.value]
    if (va === null || va === undefined) va = riskSortDir.value === 'asc' ? Infinity : -Infinity
    if (vb === null || vb === undefined) vb = riskSortDir.value === 'asc' ? Infinity : -Infinity
    if (typeof va === 'string') return riskSortDir.value === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
    return riskSortDir.value === 'asc' ? va - vb : vb - va
  })
})

function toggleRiskSort(key) {
  if (riskSortKey.value === key) riskSortDir.value = riskSortDir.value === 'asc' ? 'desc' : 'asc'
  else { riskSortKey.value = key; riskSortDir.value = 'asc' }
}

async function runRiskMetrics() {
  riskLoading.value = true; riskError.value = ''; riskResult.value = null
  try {
    const tickers = riskSelectedEtfs.value.length
      ? riskSelectedEtfs.value.map(id => allEtfs.value.find(e => e.id === id)?.ticker).filter(Boolean)
      : []
    const r = await etfService.getRiskMetrics(tickers, riskRfRate.value / 100)
    riskResult.value = r.data
  } catch (e) {
    riskError.value = e.response?.data?.detail || e.message
  } finally {
    riskLoading.value = false
  }
}
const fmtPct = v => v !== null && v !== undefined ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '—'
const signClass = v  => v === null ? '' : v >= 0 ? 'cell-green' : 'cell-red'
const volClass  = v  => v === null ? '' : v < 12 ? 'cell-green' : v < 22 ? 'cell-yellow' : 'cell-red'
const sharpeClass = v => v === null ? '' : v >= 1 ? 'cell-green' : v >= 0 ? 'cell-yellow' : 'cell-red'
const ddClass   = v  => v === null ? '' : v > -10 ? 'cell-green' : v > -20 ? 'cell-yellow' : 'cell-red'

onMounted(() => {
  loadETFs()
  runRiskMetrics()
  if (analyticsInitTab.value && ['exposure', 'risk'].includes(analyticsInitTab.value)) {
    activeTab.value = analyticsInitTab.value
    analyticsInitTab.value = null
  }
})
</script>

<style scoped>
.page {
  --green-50: rgba(15, 76, 129, 0.07);
  --green-100: rgba(15, 76, 129, 0.1);
  --green-200: rgba(15, 76, 129, 0.2);
  --green-400: #2f85c8;
  --green-500: #0f4c81;
  --green-600: #1a6ab8;
  --green-700: #0a3a66;
  --green-800: #072b4b;
}
.page-header{margin-bottom:2.25rem}
.cta-banner{display:flex;align-items:center;justify-content:space-between;gap:1rem;background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.75rem;flex-wrap:wrap;box-shadow:var(--shadow)}
.cta-text{display:flex;flex-direction:column;gap:.2rem;font-size:.9rem}
.cta-text strong{color:var(--text)}
.cta-text span{color:var(--text-muted)}
.cta-btn{padding:.55rem 1.2rem;background:#0f4c81;color:#fff;border:none;border-radius:8px;font-weight:700;font-size:.875rem;cursor:pointer;white-space:nowrap;flex-shrink:0}
.cta-btn:hover{background:#1a6ab8}
.risk-table{width:100%;border-collapse:collapse;font-size:.8rem}
.risk-table thead tr{background:var(--bg-3)}
.risk-table th,.risk-table td{padding:.58rem .75rem;text-align:left;border-bottom:1px solid var(--border)}
.risk-table tbody tr:hover{background:var(--bg-3)}
.sortable-th{cursor:pointer;user-select:none;white-space:nowrap}
.stat-box{background:var(--bg-3);border-radius:10px;padding:.75rem 1rem;display:flex;flex-direction:column}
.stat-box .stat-value{font-size:1.25rem}
.sortable-th:hover{color:#1a6ab8}
.sort-arrow{margin-left:.25rem;font-size:.7rem}
.cell-green{color:#16a34a;font-weight:600}
.cell-yellow{color:#ca8a04;font-weight:600}
.cell-red{color:#ef4444;font-weight:600}
.table-wrap{overflow-x:auto}
.ana-tabs{display:flex;gap:.5rem;margin-bottom:1.75rem;flex-wrap:wrap}
.ana-tab{background:none;border:1px solid var(--border);cursor:pointer;padding:6px 12px;border-radius:6px;font-size:.88rem;font-weight:500;color:var(--text-muted);transition:all .15s;display:flex;align-items:center;gap:.35rem;font-family:inherit}
.ana-tab:hover{border-color:#2f85c8;color:#0f4c81;background:var(--bg-3)}
.ana-tab.active{background:#0f4c81;border-color:#0f4c81;color:#fff}
.etf-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:1rem}
.etf-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem;box-shadow:var(--shadow)}
.etf-card-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem}
.etf-ticker{font-size:1rem;font-weight:700;color:var(--green-600)}
.etf-name{font-size:.875rem;color:var(--text-muted)}
.alloc-bars{display:flex;flex-direction:column;gap:.5rem}
.alloc-row{display:flex;align-items:center;gap:.75rem}
.alloc-label{width:100px;font-size:.8rem;color:var(--text-2);flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.alloc-track{flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden}
.alloc-fill{height:100%;background:#1a6ab8;border-radius:4px;transition:width .4s}
.alloc-pct{width:45px;text-align:right;font-size:.8rem;font-weight:600;color:var(--text)}
.meth-link{background:none;border:none;padding:0;cursor:pointer;font-size:.76rem;color:#0f4c81;text-decoration:underline;margin-top:.2rem;display:inline-block}
.meth-link:hover{color:#1a6ab8}
.score-badge{display:inline-block;padding:.2rem .55rem;border-radius:6px;font-size:.85rem;font-weight:700;min-width:2.4rem;text-align:center}
.score-badge.score-lg{font-size:1.5rem;padding:.35rem .9rem;border-radius:10px}
.score-high{background:#dcfce7;color:#166534}
.score-mid{background:#fef9c3;color:#854d0e}
.score-low{background:#ffedd5;color:#9a3412}
.score-poor{background:#fee2e2;color:#b91c1c}
[data-theme="dark"] .score-high{background:#052e16;color:#86efac}
[data-theme="dark"] .score-mid{background:#2d1b00;color:#fde68a}
[data-theme="dark"] .score-low{background:#3d1a00;color:#fdba74}
[data-theme="dark"] .score-poor{background:#3d0000;color:#fca5a5}
.tip-box{display:flex;gap:.75rem;align-items:flex-start;background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:.85rem 1rem;margin-top:.5rem}
.tip-icon{font-size:1.2rem;flex-shrink:0}
</style>
