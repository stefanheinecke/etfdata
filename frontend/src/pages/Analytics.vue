<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">Analytics</h1>
      <p class="page-subtitle">Portfolio overlap analysis, exposure breakdown and ETF similarity search.</p>
    </div>
    <div class="ana-tabs">
      <button v-for="t in tabs" :key="t.id" :class="['ana-tab',{active:activeTab===t.id}]" @click="activeTab=t.id">
        <span>{{ t.icon }}</span> {{ t.label }}
      </button>
    </div>

    <!-- OVERLAP -->
    <div v-if="activeTab==='overlap'">
      <div class="card" style="margin-bottom:1.5rem">
        <h2 class="card-title">ETF Overlap Analysis</h2>
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">Select two or more ETFs to calculate their holdings overlap.</p>
        <div v-if="etfsLoading" class="loading"><div class="spinner"></div> Loading ETFs...</div>
        <div v-else>
          <label class="label">Select ETFs (hold Ctrl/Cmd for multiple)</label>
          <select class="input" multiple v-model="selectedIds" style="height:160px">
            <option v-for="e in allEtfs" :key="e.id" :value="e.id">{{ e.ticker }} — {{ e.name }}</option>
          </select>
          <div style="margin-top:1rem">
            <button class="btn btn-primary" @click="runOverlap" :disabled="selectedIds.length < 2 || overlapLoading">
              {{ overlapLoading ? 'Calculating...' : 'Calculate Overlap' }}
            </button>
            <span style="font-size:.8rem;color:var(--text-muted);margin-left:.75rem">{{ selectedIds.length }} selected</span>
          </div>
        </div>
      </div>
      <div v-if="overlapError" class="error-box" style="margin-bottom:1rem">{{ overlapError }}</div>
      <div v-if="overlapResult" class="card">
        <h3 class="card-title">Overlap Matrix</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>ETF A</th><th>ETF B</th><th>Common Holdings</th><th>Overlap %</th></tr></thead>
            <tbody>
              <tr v-for="row in overlapRows" :key="row.key">
                <td>{{ row.a }}</td><td>{{ row.b }}</td><td>{{ row.common }}</td>
                <td>
                  <div style="display:flex;align-items:center;gap:.5rem">
                    <div class="alloc-track" style="width:80px"><div class="alloc-fill" :style="{width:row.pct+'%'}"></div></div>
                    <strong>{{ row.pct.toFixed(1) }}%</strong>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="margin-top:1rem">
          <h4 class="card-title" style="font-size:.9rem">Common Holdings</h4>
          <div v-if="overlapResult.common_holdings?.length" style="display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.5rem">
            <span v-for="h in overlapResult.common_holdings" :key="h.isin" class="badge">{{ h.isin }}</span>
          </div>
          <p v-else style="font-size:.875rem;color:var(--text-muted)">No common holdings found.</p>
        </div>
      </div>
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
        <div style="display:flex;gap:.75rem;margin-top:.75rem">
          <button class="btn btn-outline" @click="portfolio.push({etf_id:'',weight:0})">+ Add ETF</button>
          <button class="btn btn-primary" @click="runExposure" :disabled="exposureLoading || !portfolio.some(p=>p.etf_id)">
            {{ exposureLoading ? 'Calculating...' : 'Analyse Exposure' }}
          </button>
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
    </div>

    <!-- SIMILAR -->
    <div v-if="activeTab==='similar'">
      <div class="card" style="margin-bottom:1.5rem">
        <h2 class="card-title">Find Similar ETFs</h2>
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">Find ETFs most similar to a reference ETF based on holdings overlap.</p>
        <label class="label">Reference ETF</label>
        <select class="input" v-model="similarId" style="max-width:400px">
          <option value="">Select ETF...</option>
          <option v-for="e in allEtfs" :key="e.id" :value="e.id">{{ e.ticker }} — {{ e.name }}</option>
        </select>
        <div style="margin-top:1rem">
          <button class="btn btn-primary" @click="runSimilar" :disabled="!similarId||similarLoading">
            {{ similarLoading ? 'Searching...' : 'Find Similar' }}
          </button>
        </div>
      </div>
      <div v-if="similarError" class="error-box" style="margin-bottom:1rem">{{ similarError }}</div>
      <div v-if="similarResult?.similar_etfs?.length" class="etf-grid">
        <div v-for="s in similarResult.similar_etfs" :key="s.etf_id" class="etf-card">
          <div class="etf-card-top">
            <span class="etf-ticker">{{ s.ticker || s.etf_id?.slice(0,8) }}</span>
            <span class="badge">{{ s.overlap_percentage?.toFixed(1) }}% overlap</span>
          </div>
          <p class="etf-name">{{ s.name || s.etf_id }}</p>
          <div class="alloc-track" style="margin-top:.75rem"><div class="alloc-fill" :style="{width:(s.overlap_percentage||0)+'%'}"></div></div>
        </div>
      </div>
    </div>

    <!-- RISK METRICS -->
    <div v-if="activeTab==='risk'">
      <div class="card" style="margin-bottom:1rem">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.75rem">
          <div>
            <h2 class="card-title">Risk Metrics Overview</h2>
            <p style="font-size:.875rem;color:var(--text-muted)">Annualised statistics computed from 1-year daily price history and current holdings.</p>
          </div>
          <div style="display:flex;align-items:center;gap:.5rem">
            <label style="font-size:.8rem;color:var(--text-muted)">Risk-free rate</label>
            <input class="input" type="number" v-model.number="riskFreeRate" min="0" max="20" step="0.5"
              style="width:80px;padding:.3rem .5rem;font-size:.875rem" />
            <span style="font-size:.8rem;color:var(--text-muted)">%</span>
            <button class="btn btn-primary" @click="loadRisk" :disabled="riskLoading" style="padding:.35rem .9rem">
              {{ riskLoading ? 'Loading…' : riskResult ? 'Refresh' : 'Load' }}
            </button>
          </div>
        </div>
      </div>
      <div v-if="riskError" class="error-box" style="margin-bottom:1rem">{{ riskError }}</div>
      <div v-if="riskResult" class="card" style="padding:0;overflow:hidden">
        <div class="table-wrap">
          <table class="risk-table">
            <thead>
              <tr>
                <th v-for="col in riskCols" :key="col.key" @click="setRiskSort(col.key)" class="sortable-th">
                  {{ col.label }}
                  <span class="sort-arrow" v-if="riskSortKey===col.key">{{ riskSortDir==='asc' ? '▲' : '▼' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in riskRows" :key="row.etf_id">
                <td><strong style="color:var(--green-600)">{{ row.ticker }}</strong></td>
                <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ row.name }}</td>
                <td :class="signClass(row.ann_return)">{{ fmtPct(row.ann_return) }}</td>
                <td :class="volClass(row.volatility)">{{ fmtPct(row.volatility) }}</td>
                <td :class="sharpeClass(row.sharpe_ratio)">{{ row.sharpe_ratio !== null ? row.sharpe_ratio : '—' }}</td>
                <td :class="ddClass(row.max_drawdown)">{{ fmtPct(row.max_drawdown) }}</td>
                <td :class="hhiClass(row.hhi)">
                  <span v-if="row.hhi !== null">{{ row.hhi.toFixed(0) }}</span>
                  <span v-else>—</span>
                </td>
                <td style="text-align:right">{{ row.num_holdings.toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="padding:.75rem 1.25rem;font-size:.75rem;color:var(--text-muted);border-top:1px solid var(--border)">
          Volatility &amp; Sharpe: annualised from daily log-returns &nbsp;·&nbsp;
          Max Drawdown: peak-to-trough over 1 year &nbsp;·&nbsp;
          HHI: Herfindahl–Hirschman Index (0–10 000; lower = more diversified) &nbsp;·&nbsp;
          Risk-free rate used: {{ riskFreeRate }}%
        </div>
        <div style="padding:.5rem 1.25rem .75rem;font-size:.72rem;color:var(--text-muted);opacity:.7;display:flex;flex-wrap:wrap;gap:.25rem 1.5rem">
          <span><span style="color:#16a34a">■</span> / <span style="color:#ca8a04">■</span> / <span style="color:#ef4444">■</span> &nbsp;colour thresholds:</span>
          <span><strong>1Y Return</strong> ≥ 0% / &lt; 0%</span>
          <span><strong>Volatility</strong> &lt; 12% / 12–22% / &gt; 22%</span>
          <span><strong>Sharpe</strong> ≥ 1 / 0–1 / &lt; 0</span>
          <span><strong>Max Drawdown</strong> &gt; −10% / −10 to −20% / &lt; −20%</span>
          <span><strong>HHI</strong> &lt; 500 / 500–2 000 / &gt; 2 000</span>
        </div>
      </div>
      <div v-else-if="!riskLoading" class="card" style="text-align:center;padding:2rem;color:var(--text-muted)">
        Click <strong>Load</strong> to compute risk metrics for all ETFs.
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { etfService, analyticsService } from '../services/api.js'

const activeTab = ref('overlap')
const tabs = [
  {id:'overlap',label:'Overlap Analysis',icon:'🔗'},
  {id:'exposure',label:'Portfolio Exposure',icon:'🌍'},
  {id:'similar',label:'Similar ETFs',icon:'🔍'},
  {id:'risk',label:'Risk Metrics',icon:'📉'},
]
const allEtfs = ref([])
const etfsLoading = ref(false)

// Overlap
const selectedIds = ref([])
const overlapLoading = ref(false)
const overlapResult = ref(null)
const overlapError = ref('')
const overlapRows = computed(() => {
  if (!overlapResult.value?.matrix) return []
  const rows = []
  const m = overlapResult.value.matrix
  const ids = Object.keys(m)
  for (let i=0;i<ids.length;i++) for (let j=i+1;j<ids.length;j++) {
    const a=ids[i],b=ids[j]
    const ea=allEtfs.value.find(e=>e.id===a),eb=allEtfs.value.find(e=>e.id===b)
    rows.push({key:a+b,a:ea?.ticker||a.slice(0,8),b:eb?.ticker||b.slice(0,8),common:m[a]?.[b]?.common_count||0,pct:m[a]?.[b]?.overlap_percentage||0})
  }
  return rows
})

// Exposure
const portfolio = ref([{etf_id:'',weight:50},{etf_id:'',weight:50}])
const exposureLoading = ref(false)
const exposureResult = ref(null)
const exposureError = ref('')
const exposureGroups = computed(() => {
  if (!exposureResult.value) return []
  const r = exposureResult.value
  return [
    {label:'Sectors',entries:Object.entries(r.sectors||{}).sort((a,b)=>b[1]-a[1]).slice(0,8)},
    {label:'Countries',entries:Object.entries(r.countries||{}).sort((a,b)=>b[1]-a[1]).slice(0,8)},
    {label:'Currencies',entries:Object.entries(r.currencies||{}).sort((a,b)=>b[1]-a[1])},
  ].filter(g=>g.entries.length)
})

// Similar
const similarId = ref('')
const similarLoading = ref(false)
const similarResult = ref(null)
const similarError = ref('')

async function loadETFs() {
  etfsLoading.value=true
  try { const r=await etfService.getETFs(0,50); allEtfs.value=r.data } catch(e){console.error(e)} finally{etfsLoading.value=false}
}
async function runOverlap() {
  overlapLoading.value=true; overlapError.value=''; overlapResult.value=null
  try { const r=await analyticsService.calculateOverlap(selectedIds.value); overlapResult.value=r.data }
  catch(e){overlapError.value=e.response?.data?.detail||e.message} finally{overlapLoading.value=false}
}
async function runExposure() {
  exposureLoading.value=true; exposureError.value=''; exposureResult.value=null
  const p=portfolio.value.filter(x=>x.etf_id)
  try { const r=await analyticsService.calculateExposure(p); exposureResult.value=r.data }
  catch(e){exposureError.value=e.response?.data?.detail||e.message} finally{exposureLoading.value=false}
}
// Risk metrics
const riskLoading    = ref(false)
const riskError      = ref('')
const riskResult     = ref(null)
const riskFreeRate   = ref(4.0)     // % per year
const riskSortKey    = ref('ticker')
const riskSortDir    = ref('asc')

const riskCols = [
  { key: 'ticker',       label: 'Ticker' },
  { key: 'name',         label: 'Name' },
  { key: 'ann_return',   label: '1Y Return' },
  { key: 'volatility',   label: 'Volatility (ann.)' },
  { key: 'sharpe_ratio', label: 'Sharpe Ratio' },
  { key: 'max_drawdown', label: 'Max Drawdown' },
  { key: 'hhi',          label: 'HHI' },
  { key: 'num_holdings', label: '# Holdings' },
]

function setRiskSort(key) {
  if (riskSortKey.value === key) riskSortDir.value = riskSortDir.value === 'asc' ? 'desc' : 'asc'
  else { riskSortKey.value = key; riskSortDir.value = 'asc' }
}

const riskRows = computed(() => {
  if (!riskResult.value) return []
  const dir = riskSortDir.value === 'asc' ? 1 : -1
  return [...riskResult.value].sort((a, b) => {
    const av = a[riskSortKey.value], bv = b[riskSortKey.value]
    if (av === null && bv === null) return 0
    if (av === null) return 1
    if (bv === null) return -1
    return typeof av === 'string' ? av.localeCompare(bv) * dir : (av - bv) * dir
  })
})

// Formatting & colour helpers
const fmtPct = v => v !== null && v !== undefined ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '—'
const signClass = v  => v === null ? '' : v >= 0 ? 'cell-green' : 'cell-red'
const volClass  = v  => v === null ? '' : v < 12 ? 'cell-green' : v < 22 ? 'cell-yellow' : 'cell-red'
const sharpeClass = v => v === null ? '' : v >= 1 ? 'cell-green' : v >= 0 ? 'cell-yellow' : 'cell-red'
const ddClass   = v  => v === null ? '' : v > -10 ? 'cell-green' : v > -20 ? 'cell-yellow' : 'cell-red'
const hhiClass  = v  => v === null ? '' : v < 500 ? 'cell-green' : v < 2000 ? 'cell-yellow' : 'cell-red'

async function loadRisk() {
  riskLoading.value = true; riskError.value = ''; riskResult.value = null
  try {
    const r = await analyticsService.getRiskMetrics(riskFreeRate.value / 100)
    riskResult.value = r.data
  } catch (e) {
    riskError.value = e.response?.data?.detail || e.message
  } finally {
    riskLoading.value = false
  }
}
.risk-table{width:100%;border-collapse:collapse;font-size:.875rem}
.risk-table thead tr{background:var(--bg-3)}
.risk-table th,.risk-table td{padding:.6rem 1rem;text-align:left;border-bottom:1px solid var(--border)}
.risk-table tbody tr:hover{background:var(--bg-3)}
.sortable-th{cursor:pointer;user-select:none;white-space:nowrap}
.sortable-th:hover{color:var(--green-600)}
.sort-arrow{margin-left:.25rem;font-size:.7rem}
.cell-green{color:#16a34a;font-weight:600}
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
