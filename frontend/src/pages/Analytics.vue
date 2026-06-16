<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">Analytics</h1>
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
            <option v-for="e in allEtfs" :key="e.id" :value="e.id">{{ e.ticker }} — {{ e.name }}</option>
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
          Rf = {{ riskFreeRate }}% &nbsp;·&nbsp; HHI: Herfindahl–Hirschman Index (0–10 000; lower = more diversified)
        </div>
      </div>      </div>    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { etfService, analyticsService } from '../services/api.js'

const showApiKeyModal = inject('showApiKeyModal')
const analyticsInitTab = inject('analyticsInitTab', ref(null))
const hasApiKey = ref(!!localStorage.getItem('api_key'))
window.addEventListener('storage', (e) => { if (e.key === 'api_key') hasApiKey.value = !!e.newValue })

const activeTab = ref('exposure')
const tabs = [
  {id:'exposure',label:'Portfolio Exposure',icon:'🌍'},
]
const allEtfs = ref([])
const etfsLoading = ref(false)

// Exposure
const portfolio = ref([{etf_id:'',weight:50},{etf_id:'',weight:50}])
const exposureLoading = ref(false)
const exposureResult = ref(null)
const exposureError = ref('')
const portfolioRiskResult = ref(null)

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
  exposureLoading.value=true; exposureError.value=''; exposureResult.value=null; portfolioRiskResult.value=null
  const p=portfolio.value.filter(x=>x.etf_id)
  try {
    const r = await analyticsService.calculateExposure(p, null, riskFreeRate.value / 100)
    exposureResult.value = r.data
    portfolioRiskResult.value = r.data.risk_metrics ?? null
  } catch(e){exposureError.value=e.response?.data?.detail||e.message} finally{exposureLoading.value=false}
}
// Risk-free rate (used for portfolio Sharpe in summary)
const riskFreeRate = ref(4.0)     // % per year

// Formatting & colour helpers
const fmtPct = v => v !== null && v !== undefined ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '—'
const signClass = v  => v === null ? '' : v >= 0 ? 'cell-green' : 'cell-red'
const volClass  = v  => v === null ? '' : v < 12 ? 'cell-green' : v < 22 ? 'cell-yellow' : 'cell-red'
const sharpeClass = v => v === null ? '' : v >= 1 ? 'cell-green' : v >= 0 ? 'cell-yellow' : 'cell-red'
const ddClass   = v  => v === null ? '' : v > -10 ? 'cell-green' : v > -20 ? 'cell-yellow' : 'cell-red'
const hhiClass  = v  => v === null ? '' : v < 500 ? 'cell-green' : v < 2000 ? 'cell-yellow' : 'cell-red'

async function loadRisk() {}
async function runSimilar() {}
onMounted(() => {
  loadETFs()
  if (analyticsInitTab.value) { activeTab.value = analyticsInitTab.value; analyticsInitTab.value = null }
})
</script>

<style scoped>
.cta-banner{display:flex;align-items:center;justify-content:space-between;gap:1rem;background:linear-gradient(135deg,#667eea15,#764ba215);border:1.5px solid #667eea55;border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.5rem;flex-wrap:wrap}
.cta-text{display:flex;flex-direction:column;gap:.2rem;font-size:.9rem}
.cta-text strong{color:var(--text)}
.cta-text span{color:var(--text-muted)}
.cta-btn{padding:.55rem 1.2rem;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;border-radius:8px;font-weight:700;font-size:.875rem;cursor:pointer;white-space:nowrap;flex-shrink:0}
.cta-btn:hover{opacity:.9}
.risk-table{width:100%;border-collapse:collapse;font-size:.875rem}
.risk-table thead tr{background:var(--bg-3)}
.risk-table th,.risk-table td{padding:.6rem 1rem;text-align:left;border-bottom:1px solid var(--border)}
.risk-table tbody tr:hover{background:var(--bg-3)}
.sortable-th{cursor:pointer;user-select:none;white-space:nowrap}
.stat-box{background:var(--bg-3);border-radius:10px;padding:.75rem 1rem;display:flex;flex-direction:column}
.stat-box .stat-value{font-size:1.25rem}
.sortable-th:hover{color:var(--green-600)}
.sort-arrow{margin-left:.25rem;font-size:.7rem}
.cell-green{color:#0b6aa5;font-weight:600}
.cell-yellow{color:#ca8a04;font-weight:600}
.cell-red{color:#ef4444;font-weight:600}
.table-wrap{overflow-x:auto}
.ana-tabs{display:flex;gap:.5rem;margin-bottom:1.5rem;flex-wrap:wrap}
.ana-tab{background:none;border:1px solid var(--border);cursor:pointer;padding:.5rem 1.1rem;border-radius:8px;font-size:.875rem;font-weight:500;color:var(--text-muted);transition:all .15s;display:flex;align-items:center;gap:.35rem;font-family:inherit}
.ana-tab:hover{border-color:var(--green-400);color:var(--green-700);background:var(--bg-3)}
.ana-tab.active{background:var(--green-500);border-color:var(--green-500);color:#fff}
.etf-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:1rem}
.etf-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem;box-shadow:var(--shadow)}
.etf-card-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem}
.etf-ticker{font-size:1rem;font-weight:700;color:var(--green-600)}
.etf-name{font-size:.875rem;color:var(--text-muted)}
.alloc-bars{display:flex;flex-direction:column;gap:.5rem}
.alloc-row{display:flex;align-items:center;gap:.75rem}
.alloc-label{width:100px;font-size:.8rem;color:var(--text-2);flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.alloc-track{flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden}
.alloc-fill{height:100%;background:var(--green-500);border-radius:4px;transition:width .4s}
.alloc-pct{width:45px;text-align:right;font-size:.8rem;font-weight:600;color:var(--text)}
</style>
