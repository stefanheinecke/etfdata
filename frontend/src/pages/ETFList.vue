<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">ETF Explorer</h1>
      <p class="page-subtitle">Browse all tracked ETFs, inspect holdings, allocations and performance data.</p>
    </div>
    <div v-if="!apiKey" class="error-box" style="margin-bottom:1.5rem">
      No API key set — go to <strong>Admin</strong> and enter your API key first.
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
          <div><span class="etf-ticker">{{ etf.ticker }}</span><span class="badge" style="margin-left:.5rem">{{ etf.provider }}</span></div>
          <span class="etf-ter">TER {{ etf.ter }}%</span>
        </div>
        <h3 class="etf-name">{{ etf.name }}</h3>
        <p class="etf-isin">{{ etf.isin }}</p>
        <div class="etf-meta">
          <span>{{ etf.domicile }}</span><span>{{ etf.currency }}</span>
          <span v-if="etf.fund_size">{{ formatSize(etf.fund_size) }}</span>
        </div>
        <div class="etf-replication">{{ etf.replication_method }}</div>
      </div>
    </div>
    <div v-else-if="!loading && !error" class="empty-state">
      <div class="empty-icon">📭</div>
      <p>No ETFs found. Make sure your API key is configured and the database is seeded.</p>
    </div>
    <div v-if="selectedETF" class="modal-backdrop" @click.self="selectedETF = null">
      <div class="modal">
        <div class="modal-header">
          <div>
            <h2 class="modal-title">{{ selectedETF.ticker }} - {{ selectedETF.name }}</h2>
            <p style="font-size:.875rem;color:var(--text-muted)">{{ selectedETF.isin }}</p>
          </div>
          <button class="modal-close" @click="selectedETF = null">X</button>
        </div>
        <div class="modal-tabs">
          <button v-for="t in ['Overview','Holdings','Allocations','Performance','Risk']" :key="t"
            :class="['modal-tab',{active:detailTab===t}]" @click="detailTab=t;loadDetail(t)">{{ t }}</button>
        </div>
        <div v-if="detailTab==='Overview'" class="grid-4" style="margin-top:1rem">
          <div class="stat-card" v-for="s in etfStats" :key="s.label">
            <div class="stat-label">{{ s.label }}</div>
            <div class="stat-value" style="font-size:1.1rem">{{ s.value }}</div>
          </div>
        </div>
        <div v-if="detailTab==='Holdings'">
          <div v-if="detailLoading" class="loading"><div class="spinner"></div> Loading...</div>
          <div v-else-if="holdings.length" class="table-wrap" style="margin-top:1rem">
            <table><thead><tr><th>ISIN</th><th>Name</th><th>Weight%</th><th>Country</th><th>Sector</th></tr></thead>
              <tbody>
                <tr v-for="h in holdings" :key="h.id">
                  <td><code>{{ h.instrument_isin }}</code></td><td>{{ h.instrument_name }}</td>
                  <td><strong>{{ h.weight }}%</strong></td><td>{{ h.country }}</td><td>{{ h.sector }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty-state"><p>No holdings data available.</p></div>
        </div>
        <div v-if="detailTab==='Allocations'">
          <div v-if="detailLoading" class="loading"><div class="spinner"></div> Loading...</div>
          <div v-else-if="allocations.length">
            <div v-for="group in allocationGroups" :key="group.type" style="margin-top:1.25rem">
              <h4 style="font-size:.8rem;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.75rem">{{ group.type }}</h4>
              <div class="alloc-bars">
                <div v-for="a in group.visible" :key="a.bucket" class="alloc-row">
                  <span class="alloc-label">{{ a.label }}</span>
                  <div class="alloc-track"><div class="alloc-fill" :style="{width:Math.min(a.weight,100)+'%'}"></div></div>
                  <span class="alloc-pct">{{ Number(a.weight).toFixed(1) }}%</span>
                </div>
              </div>
              <button v-if="group.items.length > 5" class="show-more-btn" @click="toggleGroup(group.type)">
                {{ expandedGroups.has(group.type) ? 'Show less ↑' : `Show ${group.items.length - 5} more ↓` }}
              </button>
            </div>
          </div>
          <div v-else class="empty-state"><p>No allocation data available.</p></div>
        </div>
        <div v-if="detailTab==='Performance'">
          <div v-if="detailLoading" class="loading"><div class="spinner"></div> Loading...</div>
          <div v-else-if="performance.length">
            <div class="perf-kpi" style="margin-top:1rem">
              <div class="perf-stat" v-for="s in perfStats" :key="s.label">
                <div class="stat-label">{{ s.label }}</div>
                <div class="stat-value" style="font-size:1.1rem" :style="{color:s.color}">{{ s.value }}</div>
              </div>
            </div>
            <div style="margin-top:1.25rem;position:relative;height:220px">
              <canvas ref="chartCanvas"></canvas>
            </div>
          </div>
          <div v-else class="empty-state"><p>No performance data. Re-run the import to fetch 1-year price history.</p></div>
        </div>
        <div v-if="detailTab==='Risk'">
          <div v-if="detailLoading" class="loading"><div class="spinner"></div> Loading...</div>
          <div v-else-if="etfRisk" style="margin-top:1rem">
            <div class="perf-kpi">
              <div class="perf-stat" v-for="s in riskStats" :key="s.label">
                <div class="stat-label">{{ s.label }}</div>
                <div class="stat-value" style="font-size:1.15rem;font-weight:700" :style="{color:s.color}">{{ s.value }}</div>
              </div>
            </div>
            <p style="margin-top:1rem;font-size:.75rem;color:var(--text-muted)">
              Annualised from {{ etfRisk.data_points }} daily price observations &nbsp;·&nbsp;
              Risk-free rate: 4% &nbsp;·&nbsp;
              HHI based on {{ etfRisk.num_holdings.toLocaleString() }} holdings
            </p>
            <div style="margin-top:.5rem;font-size:.72rem;color:var(--text-muted);opacity:.7;display:flex;flex-wrap:wrap;gap:.2rem 1.25rem">
              <span><span style="color:#16a34a">■</span>&nbsp;Volatility &lt;12% &nbsp;·&nbsp; Sharpe ≥1 &nbsp;·&nbsp; Drawdown &gt;−10% &nbsp;·&nbsp; HHI &lt;500</span>
              <span><span style="color:#ca8a04">■</span>&nbsp;Volatility 12–22% &nbsp;·&nbsp; Sharpe 0–1 &nbsp;·&nbsp; Drawdown −10 to −20% &nbsp;·&nbsp; HHI 500–2 000</span>
              <span><span style="color:#ef4444">■</span>&nbsp;Volatility &gt;22% &nbsp;·&nbsp; Sharpe &lt;0 &nbsp;·&nbsp; Drawdown &lt;−20% &nbsp;·&nbsp; HHI &gt;2 000</span>
            </div>
          </div>
          <div v-else class="empty-state"><p>No price history available to compute risk metrics.</p></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { Chart } from 'chart.js/auto'
import { etfService } from '../services/api.js'

const allETFs = ref([])
const loading = ref(false)
const error = ref('')
const apiKey = ref(localStorage.getItem('api_key') || '')

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

// Modal
const selectedETF = ref(null)
const detailTab = ref('Overview')
const detailLoading = ref(false)
const holdings = ref([])
const allocations = ref([])

const COUNTRY_NAMES = {
  AF:'Afghanistan',AL:'Albania',DZ:'Algeria',AR:'Argentina',AU:'Australia',
  AT:'Austria',BE:'Belgium',BM:'Bermuda',BR:'Brazil',CA:'Canada',KY:'Cayman Islands',
  CL:'Chile',CN:'China',CO:'Colombia',CZ:'Czech Republic',DK:'Denmark',EG:'Egypt',
  FI:'Finland',FR:'France',DE:'Germany',GR:'Greece',HK:'Hong Kong',HU:'Hungary',
  IN:'India',ID:'Indonesia',IE:'Ireland',IL:'Israel',IT:'Italy',JP:'Japan',
  LU:'Luxembourg',MY:'Malaysia',MX:'Mexico',NL:'Netherlands',NZ:'New Zealand',
  NO:'Norway',PH:'Philippines',PL:'Poland',PT:'Portugal',QA:'Qatar',SA:'Saudi Arabia',
  SG:'Singapore',ZA:'South Africa',KR:'South Korea',ES:'Spain',SE:'Sweden',
  CH:'Switzerland',TW:'Taiwan',TH:'Thailand',TR:'Turkey',AE:'United Arab Emirates',
  GB:'United Kingdom',US:'United States',VN:'Vietnam',
}

const expandedGroups = ref(new Set())
function toggleGroup(type) {
  const s = new Set(expandedGroups.value)
  s.has(type) ? s.delete(type) : s.add(type)
  expandedGroups.value = s
}
const performance = ref([])
const etfRisk = ref(null)

const riskStats = computed(() => {
  const r = etfRisk.value
  if (!r) return []
  const fmtPct = v => v !== null ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '\u2014'
  const signClr  = v => v === null ? 'var(--text)' : v >= 0 ? '#16a34a' : '#ef4444'
  const volClr   = v => v === null ? 'var(--text)' : v < 12 ? '#16a34a' : v < 22 ? '#ca8a04' : '#ef4444'
  const sharpeClr = v => v === null ? 'var(--text)' : v >= 1 ? '#16a34a' : v >= 0 ? '#ca8a04' : '#ef4444'
  const ddClr    = v => v === null ? 'var(--text)' : v > -10 ? '#16a34a' : v > -20 ? '#ca8a04' : '#ef4444'
  const hhiClr   = v => v === null ? 'var(--text)' : v < 500 ? '#16a34a' : v < 2000 ? '#ca8a04' : '#ef4444'
  return [
    { label: '1Y Return (ann.)',  value: fmtPct(r.ann_return),   color: signClr(r.ann_return) },
    { label: 'Volatility (ann.)', value: fmtPct(r.volatility),   color: volClr(r.volatility) },
    { label: 'Sharpe Ratio',      value: r.sharpe_ratio !== null ? r.sharpe_ratio.toFixed(2) : '\u2014', color: sharpeClr(r.sharpe_ratio) },
    { label: 'Max Drawdown',      value: fmtPct(r.max_drawdown), color: ddClr(r.max_drawdown) },
    { label: 'HHI',               value: r.hhi !== null ? Number(r.hhi).toFixed(0) : '\u2014', color: hhiClr(r.hhi) },
    { label: '# Holdings',        value: r.num_holdings.toLocaleString(), color: 'var(--text)' },
  ]
})
const chartCanvas = ref(null)
let chartInstance = null

const etfStats = computed(() => {
  const e = selectedETF.value; if (!e) return []
  return [
    {label:'Provider',value:e.provider},{label:'Domicile',value:e.domicile},
    {label:'Currency',value:e.currency},{label:'TER',value:e.ter?e.ter+'%':'—'},
    {label:'Fund Size',value:e.fund_size?formatSize(e.fund_size):'—'},
    {label:'Replication',value:e.replication_method||'—'},
    {label:'Benchmark',value:e.benchmark||'—'},{label:'ISIN',value:e.isin},
  ]
})
const allocationGroups = computed(() => {
  const map = {}
  allocations.value.forEach(a => { if (!map[a.type]) map[a.type]=[]; map[a.type].push(a) })
  return Object.entries(map).map(([type, items]) => {
    const sorted = items
      .map(a => ({ ...a, label: type === 'country' ? (COUNTRY_NAMES[a.bucket] || a.bucket) : a.bucket }))
      .sort((a, b) => b.weight - a.weight)
    const expanded = expandedGroups.value.has(type)
    return { type, items: sorted, visible: expanded ? sorted : sorted.slice(0, 5) }
  })
})

const perfStats = computed(() => {
  const data = performance.value
  if (!data.length) return []
  const last = data[data.length - 1]
  const current = parseFloat(last.close_price)
  function pctReturn(daysAgo) {
    const cutoff = new Date(last.date)
    cutoff.setDate(cutoff.getDate() - daysAgo)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    const entry = [...data].reverse().find(p => p.date <= cutoffStr)
    if (!entry) return null
    const base = parseFloat(entry.close_price)
    return ((current - base) / base * 100).toFixed(2)
  }
  const fmt = v => v !== null ? `${parseFloat(v) >= 0 ? '+' : ''}${v}%` : '—'
  const clr = v => v !== null ? (parseFloat(v) >= 0 ? 'var(--green-600)' : '#ef4444') : ''
  const [m1,m3,m6,y1] = [30,90,180,365].map(pctReturn)
  return [
    { label: 'Current Price', value: `${current.toFixed(2)} ${last.currency}`, color: 'var(--text)' },
    { label: '1 Month',  value: fmt(m1), color: clr(m1) },
    { label: '3 Months', value: fmt(m3), color: clr(m3) },
    { label: '6 Months', value: fmt(m6), color: clr(m6) },
    { label: '1 Year',   value: fmt(y1), color: clr(y1) },
  ]
})

async function renderChart() {
  await nextTick()
  if (!chartCanvas.value || !performance.value.length) return
  if (chartInstance) { chartInstance.destroy(); chartInstance = null }
  const labels = performance.value.map(p => p.date)
  const prices = performance.value.map(p => parseFloat(p.close_price))
  chartInstance = new Chart(chartCanvas.value, {
    type: 'line',
    data: {
      labels,
      datasets: [{ data: prices, borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.08)',
        fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { maxTicksLimit: 8, font: { size: 11 } }, grid: { display: false } },
        y: { ticks: { font: { size: 11 } } }
      }
    }
  })
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
  selectedETF.value=etf; detailTab.value='Overview'
  holdings.value=[]; allocations.value=[]; performance.value=[]; etfRisk.value=null
  expandedGroups.value = new Set()
  if (chartInstance) { chartInstance.destroy(); chartInstance = null }
}

async function loadDetail(tab) {
  if (!selectedETF.value || tab==='Overview') return
  detailLoading.value=true
  try {
    if (tab==='Holdings') { const r=await etfService.getHoldings(selectedETF.value.id); holdings.value=r.data.slice().sort((a,b)=>b.weight-a.weight) }
    else if (tab==='Allocations') { const r=await etfService.getAllocations(selectedETF.value.id); allocations.value=r.data }
    else if (tab==='Performance') {
      const r=await etfService.getPerformance(selectedETF.value.id); performance.value=r.data
      renderChart()
    }
    else if (tab==='Risk') { const r=await etfService.getETFRiskMetrics(selectedETF.value.id); etfRisk.value=r.data }
  } catch(e){console.error(e)} finally{detailLoading.value=false}
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
.modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:200;padding:1rem}
.modal{background:var(--surface);border-radius:var(--radius);box-shadow:var(--shadow-lg);width:100%;max-width:800px;max-height:90vh;overflow-y:auto;padding:1.5rem}
.modal-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1.25rem}
.modal-title{font-size:1.2rem;font-weight:700;color:var(--text)}
.modal-close{background:none;border:none;font-size:1.2rem;cursor:pointer;color:var(--text-muted);padding:.25rem .5rem;border-radius:6px;transition:all .15s}
.modal-close:hover{background:var(--bg-3);color:var(--text)}
.modal-tabs{display:flex;gap:.25rem;border-bottom:2px solid var(--border);margin-bottom:1.25rem}
.modal-tab{background:none;border:none;border-bottom:2px solid transparent;margin-bottom:-2px;cursor:pointer;padding:.55rem 1.1rem;font-size:.875rem;font-weight:500;color:var(--text-muted);border-radius:6px 6px 0 0;transition:color .15s,border-color .15s,background .15s;font-family:inherit}
.modal-tab:hover{color:var(--text);background:var(--bg-2)}
.modal-tab.active{color:var(--green-600);border-bottom-color:var(--green-500);font-weight:600}
.alloc-bars{display:flex;flex-direction:column;gap:.5rem}
.alloc-row{display:flex;align-items:center;gap:.75rem}
.alloc-label{width:150px;font-size:.8rem;color:var(--text-2);flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.alloc-track{flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden}
.alloc-fill{height:100%;background:var(--green-500);border-radius:4px;transition:width .4s}
.alloc-pct{width:45px;text-align:right;font-size:.8rem;font-weight:600;color:var(--text)}
.show-more-btn{margin-top:.5rem;background:none;border:none;cursor:pointer;font-size:.8rem;color:var(--green-600);padding:.25rem 0;font-family:inherit;font-weight:500}
.show-more-btn:hover{text-decoration:underline}
.perf-kpi{display:flex;gap:.75rem;flex-wrap:wrap}
.perf-stat{flex:1;min-width:110px;background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);padding:.65rem 1rem}
</style>
