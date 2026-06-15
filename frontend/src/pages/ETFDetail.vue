<template>
  <div>
    <!-- Breadcrumb -->
    <div class="crumb-bar">
      <div class="page crumb-inner">
        <button class="back-link" @click="goBack">← ETF Explorer</button>
        <span class="crumb-sep">›</span>
        <span class="crumb-cur">{{ etf?.ticker }}</span>
      </div>
    </div>

    <div v-if="!etf" class="page"><p class="empty-state">No ETF selected.</p></div>
    <div v-else>
      <!-- Header -->
      <div class="header-band">
        <div class="page header-inner">
          <div class="header-id">
            <div class="ticker-row">
              <span class="ticker">{{ etf.ticker }}</span>
              <span v-if="etf.provider" class="tag">{{ etf.provider }}</span>
              <span v-if="etf.dividend_policy" :class="['tag', etf.dividend_policy === 'Accumulating' ? 'tag-acc' : 'tag-dist']">
                {{ etf.dividend_policy === 'Accumulating' ? 'Acc' : 'Dist' }}
              </span>
            </div>
            <div class="etf-full-name">{{ etf.name }}</div>
            <code class="isin-code">{{ etf.isin || '—' }}</code>
          </div>
          <div class="header-kpis">
            <div class="hkpi" v-for="s in headerKpis" :key="s.label">
              <span class="hkpi-label">{{ s.label }}</span>
              <span class="hkpi-value">{{ s.value }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab bar -->
      <div class="tabbar">
        <div class="page tabs-inner">
          <button v-for="t in tabs" :key="t"
            :class="['dtab', { active: activeTab === t }]"
            @click="switchTab(t)">{{ t }}</button>
        </div>
      </div>

      <!-- Content -->
      <div class="page detail-body">

        <!-- ── Overview ─────────────────────────────────── -->
        <div v-if="activeTab === 'Overview'" class="two-col">
          <div class="info-card">
            <div class="info-head">Fund Details</div>
            <dl class="info-dl">
              <div class="info-row" v-for="r in fundRows" :key="r.label">
                <dt>{{ r.label }}</dt><dd>{{ r.value }}</dd>
              </div>
            </dl>
          </div>
          <div class="info-card">
            <div class="info-head">Index &amp; Strategy</div>
            <dl class="info-dl">
              <div class="info-row" v-for="r in strategyRows" :key="r.label">
                <dt>{{ r.label }}</dt><dd>{{ r.value }}</dd>
              </div>
            </dl>
          </div>
        </div>

        <!-- ── Holdings ──────────────────────────────────── -->
        <div v-if="activeTab === 'Holdings'">
          <div v-if="detailLoading" class="loading"><div class="spinner"></div> Loading holdings…</div>
          <div v-else-if="holdings.length">
            <div class="tbl-meta">{{ holdings.length }} positions · sorted by weight</div>
            <div class="table-wrap">
              <table class="data-tbl">
                <thead>
                  <tr><th style="width:2rem">#</th><th>Identifier</th><th>Name</th><th style="width:170px">Weight</th><th>Country</th><th>Sector</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(h, i) in holdings" :key="h.id">
                    <td class="row-num">{{ i + 1 }}</td>
                    <td><code class="mono">{{ h.instrument_isin }}</code></td>
                    <td class="holding-name">{{ h.instrument_name }}</td>
                    <td>
                      <div class="wt-cell">
                        <div class="wt-track"><div class="wt-bar" :style="{width: barPct(h.weight)+'%'}"></div></div>
                        <span class="wt-num">{{ h.weight.toFixed(2) }}%</span>
                      </div>
                    </td>
                    <td>{{ h.country || '—' }}</td>
                    <td class="sector-td">{{ h.sector || '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="empty-state"><p>No holdings data available.</p></div>
        </div>

        <!-- ── Allocations ───────────────────────────────── -->
        <div v-if="activeTab === 'Allocations'">
          <div v-if="detailLoading" class="loading"><div class="spinner"></div> Loading…</div>
          <div v-else-if="allocations.length" class="alloc-cols">
            <div v-for="group in allocationGroups" :key="group.type" class="alloc-group">
              <div class="alloc-head">{{ groupLabel(group.type) }}</div>
              <div v-for="a in group.visible" :key="a.bucket" class="alloc-row">
                <span class="alloc-label">{{ a.label }}</span>
                <div class="alloc-track"><div class="alloc-fill" :style="{width: Math.min(a.weight,100)+'%'}"></div></div>
                <span class="alloc-pct">{{ Number(a.weight).toFixed(1) }}%</span>
              </div>
              <button v-if="group.items.length > 6" class="show-more-btn" @click="toggleGroup(group.type)">
                {{ expandedGroups.has(group.type) ? 'Show less ↑' : `+${group.items.length - 6} more` }}
              </button>
            </div>
          </div>
          <div v-else class="empty-state"><p>No allocation data available.</p></div>
        </div>

        <!-- ── Performance ───────────────────────────────── -->
        <div v-if="activeTab === 'Performance'">
          <div v-if="detailLoading" class="loading"><div class="spinner"></div> Loading…</div>
          <div v-else-if="performance.length">
            <div class="perf-toolbar">
              <div class="perf-kpis">
                <div class="pkpi" v-for="s in perfStats" :key="s.label">
                  <span class="pkpi-label">{{ s.label }}</span>
                  <span class="pkpi-value" :style="{color: s.color}">{{ s.value }}</span>
                </div>
              </div>
              <div class="period-seg">
                <button v-for="p in periods" :key="p.label"
                  :class="['period-btn', { active: activePeriod === p.label }]"
                  @click="setPeriod(p.label)">{{ p.label }}</button>
              </div>
            </div>
            <div class="chart-box">
              <canvas ref="chartCanvas"></canvas>
            </div>
          </div>
          <div v-else class="empty-state"><p>No performance data. Re-import the ETF to fetch price history.</p></div>
        </div>

        <!-- ── Risk ─────────────────────────────────────── -->
        <div v-if="activeTab === 'Risk'">
          <div v-if="detailLoading" class="loading"><div class="spinner"></div> Loading…</div>
          <div v-else-if="etfRisk">
            <div class="risk-grid">
              <div class="risk-cell" v-for="s in riskStats" :key="s.label">
                <div class="risk-lbl">{{ s.label }}</div>
                <div class="risk-val" :style="{color: s.color}">{{ s.value }}</div>
                <div class="risk-sub">{{ s.sub }}</div>
              </div>
            </div>
            <div class="risk-legend">
              <span class="rl-good">● Low risk</span>
              <span class="rl-mid">● Medium</span>
              <span class="rl-high">● High risk</span>
            </div>
            <p class="risk-note">
              Calculated from {{ etfRisk.data_points }} daily price observations ·
              Risk-free rate 4% p.a. · HHI from {{ etfRisk.num_holdings?.toLocaleString() }} holdings
            </p>
          </div>
          <div v-else class="empty-state"><p>No price history to compute risk metrics.</p></div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject, watch, nextTick } from 'vue'
import { Chart } from 'chart.js/auto'
import { etfService } from '../services/api.js'

const etf = inject('selectedETF')
const navigateTo = inject('navigateTo')
function goBack() { navigateTo('etfs') }

const tabs = ['Overview', 'Holdings', 'Allocations', 'Performance', 'Risk']
const activeTab = ref('Overview')
const detailLoading = ref(false)
const holdings = ref([])
const allocations = ref([])
const performance = ref([])
const etfRisk = ref(null)
const expandedGroups = ref(new Set())
const chartCanvas = ref(null)
let chartInstance = null
const activePeriod = ref('1Y')
const periods = [
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
  { label: 'ALL', days: null },
]

// ── Header ─────────────────────────────────────────────────────────────────
const headerKpis = computed(() => {
  const e = etf.value; if (!e) return []
  return [
    { label: 'TER', value: e.ter != null ? e.ter + '%' : '—' },
    { label: 'Domicile', value: e.domicile || '—' },
    { label: 'Currency', value: e.currency || '—' },
    { label: 'Fund Size', value: e.fund_size ? fmtSize(e.fund_size) : '—' },
  ]
})

// ── Overview ───────────────────────────────────────────────────────────────
const fundRows = computed(() => {
  const e = etf.value; if (!e) return []
  return [
    { label: 'ISIN', value: e.isin || '—' },
    { label: 'Ticker', value: e.ticker },
    { label: 'Provider', value: e.provider || '—' },
    { label: 'Domicile', value: e.domicile || '—' },
    { label: 'Currency', value: e.currency || '—' },
    { label: 'TER', value: e.ter != null ? e.ter + '%' : '—' },
    { label: 'Dividend Policy', value: e.dividend_policy || '—' },
  ]
})
const strategyRows = computed(() => {
  const e = etf.value; if (!e) return []
  return [
    { label: 'Benchmark / Index', value: e.benchmark || '—' },
    { label: 'Replication', value: e.replication_method || '—' },
    { label: 'Fund Size', value: e.fund_size ? fmtSize(e.fund_size) : '—' },
  ]
})

// ── Holdings ───────────────────────────────────────────────────────────────
const maxWeight = computed(() => Math.max(...holdings.value.map(h => h.weight), 1))
function barPct(w) { return Math.min((w / maxWeight.value) * 100, 100) }

// ── Allocations ────────────────────────────────────────────────────────────
const COUNTRY_NAMES = {
  AF:'Afghanistan',AL:'Albania',DZ:'Algeria',AR:'Argentina',AU:'Australia',AT:'Austria',
  BE:'Belgium',BM:'Bermuda',BR:'Brazil',CA:'Canada',KY:'Cayman Islands',CL:'Chile',
  CN:'China',CO:'Colombia',CZ:'Czech Republic',DK:'Denmark',EG:'Egypt',FI:'Finland',
  FR:'France',DE:'Germany',GR:'Greece',HK:'Hong Kong',HU:'Hungary',IN:'India',
  ID:'Indonesia',IE:'Ireland',IL:'Israel',IT:'Italy',JP:'Japan',LU:'Luxembourg',
  MY:'Malaysia',MX:'Mexico',NL:'Netherlands',NZ:'New Zealand',NO:'Norway',
  PH:'Philippines',PL:'Poland',PT:'Portugal',QA:'Qatar',SA:'Saudi Arabia',
  SG:'Singapore',ZA:'South Africa',KR:'South Korea',ES:'Spain',SE:'Sweden',
  CH:'Switzerland',TW:'Taiwan',TH:'Thailand',TR:'Turkey',AE:'United Arab Emirates',
  GB:'United Kingdom',US:'United States',VN:'Vietnam',
}
function groupLabel(t) { return t === 'country' ? 'Country' : t === 'sector' ? 'Sector' : t }
function toggleGroup(type) {
  const s = new Set(expandedGroups.value)
  s.has(type) ? s.delete(type) : s.add(type)
  expandedGroups.value = s
}
const allocationGroups = computed(() => {
  const map = {}
  allocations.value.forEach(a => { if (!map[a.type]) map[a.type] = []; map[a.type].push(a) })
  return Object.entries(map).map(([type, items]) => {
    const sorted = items.map(a => ({
      ...a, label: type === 'country' ? (COUNTRY_NAMES[a.bucket] || a.bucket) : a.bucket
    })).sort((a, b) => b.weight - a.weight)
    return { type, items: sorted, visible: expandedGroups.value.has(type) ? sorted : sorted.slice(0, 6) }
  })
})

// ── Performance ────────────────────────────────────────────────────────────
const filteredPerf = computed(() => {
  const p = periods.find(x => x.label === activePeriod.value)
  if (!p?.days) return performance.value
  const cut = new Date(); cut.setDate(cut.getDate() - p.days)
  const cutStr = cut.toISOString().slice(0, 10)
  return performance.value.filter(x => x.date >= cutStr)
})

const perfStats = computed(() => {
  const data = performance.value; if (!data.length) return []
  const last = data[data.length - 1]
  const cur = parseFloat(last.close_price)
  function ret(days) {
    const d = new Date(last.date); d.setDate(d.getDate() - days)
    const cut = d.toISOString().slice(0, 10)
    const e = [...data].reverse().find(p => p.date <= cut)
    if (!e) return null
    return ((cur - parseFloat(e.close_price)) / parseFloat(e.close_price) * 100).toFixed(2)
  }
  const fmt = v => v != null ? `${parseFloat(v) >= 0 ? '+' : ''}${v}%` : '—'
  const clr = v => v != null ? (parseFloat(v) >= 0 ? '#16a34a' : '#ef4444') : 'var(--text)'
  const [m1, m3, m6, y1] = [30, 90, 180, 365].map(ret)
  return [
    { label: 'Price', value: `${cur.toFixed(2)} ${last.currency || ''}`, color: 'var(--text)' },
    { label: '1M', value: fmt(m1), color: clr(m1) },
    { label: '3M', value: fmt(m3), color: clr(m3) },
    { label: '6M', value: fmt(m6), color: clr(m6) },
    { label: '1Y', value: fmt(y1), color: clr(y1) },
  ]
})

function setPeriod(label) { activePeriod.value = label; renderChart() }

async function renderChart() {
  await nextTick()
  if (!chartCanvas.value || !filteredPerf.value.length) return
  if (chartInstance) { chartInstance.destroy(); chartInstance = null }
  const data = filteredPerf.value
  const labels = data.map(p => {
    const d = new Date(p.date)
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })
  })
  const prices = data.map(p => parseFloat(p.close_price))
  const up = prices[prices.length - 1] >= prices[0]
  const lineColor = up ? '#22c55e' : '#ef4444'
  chartInstance = new Chart(chartCanvas.value, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: prices,
        borderColor: lineColor,
        backgroundColor: up ? 'rgba(34,197,94,0.05)' : 'rgba(239,68,68,0.05)',
        fill: true, tension: 0.2, pointRadius: 0, pointHoverRadius: 4, borderWidth: 1.5,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15,23,42,0.93)',
          titleColor: '#94a3b8', bodyColor: '#f1f5f9',
          borderColor: 'rgba(255,255,255,0.08)', borderWidth: 1,
          padding: 10, titleFont: { size: 11 }, bodyFont: { size: 12, weight: '600' },
          callbacks: {
            title: i => i[0].label,
            label: i => ` ${i.parsed.y.toFixed(2)}`,
          }
        }
      },
      scales: {
        x: {
          ticks: { maxTicksLimit: 8, font: { size: 10 }, color: '#94a3b8' },
          grid: { color: 'rgba(148,163,184,0.1)' },
          border: { color: 'rgba(148,163,184,0.2)' },
        },
        y: {
          position: 'right',
          ticks: { font: { size: 10 }, color: '#94a3b8', callback: v => v.toFixed(0) },
          grid: { color: 'rgba(148,163,184,0.1)' },
          border: { color: 'rgba(148,163,184,0.2)' },
        }
      }
    }
  })
}

// ── Risk ───────────────────────────────────────────────────────────────────
const riskStats = computed(() => {
  const r = etfRisk.value; if (!r) return []
  const fmt = v => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '—'
  const volClr = v => v == null ? 'var(--text)' : v < 12 ? '#16a34a' : v < 22 ? '#ca8a04' : '#ef4444'
  const sharpeClr = v => v == null ? 'var(--text)' : v >= 1 ? '#16a34a' : v >= 0 ? '#ca8a04' : '#ef4444'
  const ddClr = v => v == null ? 'var(--text)' : v > -10 ? '#16a34a' : v > -20 ? '#ca8a04' : '#ef4444'
  const hhiClr = v => v == null ? 'var(--text)' : v < 500 ? '#16a34a' : v < 2000 ? '#ca8a04' : '#ef4444'
  const signClr = v => v == null ? 'var(--text)' : v >= 0 ? '#16a34a' : '#ef4444'
  return [
    { label: 'Ann. Return',  value: fmt(r.ann_return),   color: signClr(r.ann_return),  sub: 'Annualised' },
    { label: 'Volatility',   value: fmt(r.volatility),   color: volClr(r.volatility),   sub: 'Ann. std. deviation' },
    { label: 'Sharpe Ratio', value: r.sharpe_ratio != null ? r.sharpe_ratio.toFixed(2) : '—', color: sharpeClr(r.sharpe_ratio), sub: 'Rf = 4% p.a.' },
    { label: 'Max Drawdown', value: fmt(r.max_drawdown), color: ddClr(r.max_drawdown),  sub: 'Peak to trough' },
    { label: 'HHI',          value: r.hhi != null ? Number(r.hhi).toFixed(0) : '—', color: hhiClr(r.hhi), sub: 'Concentration index' },
    { label: '# Holdings',   value: r.num_holdings?.toLocaleString() || '—', color: 'var(--text)', sub: 'Latest snapshot' },
  ]
})

// ── Helpers & data loading ─────────────────────────────────────────────────
function fmtSize(n) {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B'
  if (n >= 1e6) return (n / 1e6).toFixed(0) + 'M'
  return n.toLocaleString()
}

async function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'Holdings' && !holdings.value.length) await loadTab('Holdings')
  else if (tab === 'Allocations' && !allocations.value.length) await loadTab('Allocations')
  else if (tab === 'Performance' && !performance.value.length) await loadTab('Performance')
  else if (tab === 'Performance' && performance.value.length) renderChart()
  else if (tab === 'Risk' && !etfRisk.value) await loadTab('Risk')
}

async function loadTab(tab) {
  if (!etf.value) return
  detailLoading.value = true
  try {
    if (tab === 'Holdings') {
      const r = await etfService.getHoldings(etf.value.id)
      holdings.value = r.data.slice().sort((a, b) => b.weight - a.weight)
    } else if (tab === 'Allocations') {
      const r = await etfService.getAllocations(etf.value.id)
      allocations.value = r.data
    } else if (tab === 'Performance') {
      const r = await etfService.getPerformance(etf.value.id)
      performance.value = r.data
      await renderChart()
    } else if (tab === 'Risk') {
      const r = await etfService.getETFRiskMetrics(etf.value.id)
      etfRisk.value = r.data
    }
  } catch (e) { console.error(e) } finally { detailLoading.value = false }
}

watch(() => etf.value?.id, () => {
  activeTab.value = 'Overview'
  holdings.value = []; allocations.value = []
  performance.value = []; etfRisk.value = null
  expandedGroups.value = new Set(); activePeriod.value = '1Y'
  if (chartInstance) { chartInstance.destroy(); chartInstance = null }
}, { immediate: false })
</script>

<style scoped>
/* Breadcrumb */
.crumb-bar { background: var(--surface); border-bottom: 1px solid var(--border); padding: .55rem 0; }
.crumb-inner { display: flex; align-items: center; gap: .5rem; font-size: .8rem; }
.back-link {
  background: none; border: none; cursor: pointer; color: var(--green-600);
  font-weight: 600; font-family: inherit; padding: 0; font-size: .8rem;
  transition: color .15s;
}
.back-link:hover { color: var(--green-700); text-decoration: underline; }
.crumb-sep { color: var(--border); }
.crumb-cur { color: var(--text); font-weight: 500; }

/* Header band */
.header-band { background: var(--surface); border-bottom: 1px solid var(--border); padding: 1.4rem 0 1.25rem; }
.header-inner { display: flex; justify-content: space-between; align-items: flex-start; gap: 2rem; flex-wrap: wrap; }
.ticker-row { display: flex; align-items: center; gap: .55rem; margin-bottom: .3rem; }
.ticker { font-size: 1.6rem; font-weight: 800; color: var(--text); letter-spacing: -.04em; font-family: monospace; }
.tag {
  display: inline-block; font-size: .68rem; font-weight: 600; padding: .12rem .5rem;
  border-radius: 20px; background: var(--bg-3); border: 1px solid var(--border); color: var(--text-muted);
}
.tag-acc { background: #d1fae5; border-color: #6ee7b7; color: #065f46; }
.tag-dist { background: #dbeafe; border-color: #93c5fd; color: #1e40af; }
[data-theme="dark"] .tag-acc { background: #064e3b; border-color: #065f46; color: #6ee7b7; }
[data-theme="dark"] .tag-dist { background: #1e3a8a; border-color: #1d4ed8; color: #93c5fd; }
.etf-full-name { font-size: .95rem; font-weight: 600; color: var(--text); margin-bottom: .2rem; line-height: 1.35; }
.isin-code { font-family: monospace; font-size: .75rem; color: var(--text-muted); }
.header-kpis { display: flex; gap: 1.75rem; flex-wrap: wrap; align-items: flex-start; }
.hkpi { display: flex; flex-direction: column; gap: .1rem; }
.hkpi-label { font-size: .65rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; color: var(--text-muted); }
.hkpi-value { font-size: 1.05rem; font-weight: 700; color: var(--text); font-variant-numeric: tabular-nums; }

/* Tabs */
.tabbar { background: var(--surface); border-bottom: 2px solid var(--border); }
.tabs-inner { display: flex; }
.dtab {
  background: none; border: none; border-bottom: 2px solid transparent;
  margin-bottom: -2px; cursor: pointer; padding: .65rem 1.15rem;
  font-size: .875rem; font-weight: 500; color: var(--text-muted);
  font-family: inherit; transition: all .15s; white-space: nowrap;
}
.dtab:hover { color: var(--text); }
.dtab.active { color: var(--green-600); border-bottom-color: var(--green-500); font-weight: 600; }

/* Body */
.detail-body { padding-top: 1.5rem; padding-bottom: 3rem; }

/* Overview */
.two-col { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
.info-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.25rem; }
.info-head { font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .09em; color: var(--text-muted); margin-bottom: .9rem; }
.info-dl { margin: 0; }
.info-row { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; padding: .38rem 0; border-bottom: 1px solid var(--border); }
.info-row:last-child { border-bottom: none; }
.info-row dt { font-size: .78rem; color: var(--text-muted); font-weight: 500; flex-shrink: 0; }
.info-row dd { font-size: .85rem; color: var(--text); font-weight: 600; text-align: right; word-break: break-word; }

/* Holdings */
.tbl-meta { font-size: .72rem; color: var(--text-muted); margin-bottom: .6rem; }
.data-tbl { width: 100%; border-collapse: collapse; font-size: .78rem; }
.data-tbl th {
  text-align: left; font-size: .65rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .07em; color: var(--text-muted); padding: .45rem .75rem;
  border-bottom: 2px solid var(--border); white-space: nowrap;
}
.data-tbl td { padding: .42rem .75rem; border-bottom: 1px solid var(--border); color: var(--text); vertical-align: middle; }
.data-tbl tbody tr:hover { background: var(--bg-2); }
.row-num { color: var(--text-muted); font-size: .7rem; font-variant-numeric: tabular-nums; text-align: right; }
.mono { font-family: monospace; font-size: .72rem; color: var(--text-muted); }
.holding-name { max-width: 240px; font-size: .78rem; }
.wt-cell { display: flex; align-items: center; gap: .5rem; }
.wt-track { flex: 1; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
.wt-bar { height: 100%; background: var(--green-500); border-radius: 2px; }
.wt-num { width: 44px; text-align: right; font-size: .72rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.sector-td { color: var(--text-muted); font-size: .72rem; }

/* Allocations */
.alloc-cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; }
.alloc-group { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.1rem 1.25rem; }
.alloc-head { font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .09em; color: var(--text-muted); margin-bottom: .8rem; }
.alloc-row { display: flex; align-items: center; gap: .55rem; margin-bottom: .4rem; }
.alloc-label { width: 130px; font-size: .76rem; color: var(--text-2); flex-shrink: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.alloc-track { flex: 1; height: 5px; background: var(--border); border-radius: 3px; overflow: hidden; }
.alloc-fill { height: 100%; background: var(--green-500); border-radius: 3px; transition: width .3s; }
.alloc-pct { width: 38px; text-align: right; font-size: .76rem; font-weight: 600; color: var(--text); font-variant-numeric: tabular-nums; }
.show-more-btn { margin-top: .4rem; background: none; border: none; cursor: pointer; font-size: .76rem; color: var(--green-600); font-family: inherit; font-weight: 500; padding: 0; }
.show-more-btn:hover { text-decoration: underline; }

/* Performance */
.perf-toolbar { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
.perf-kpis { display: flex; gap: 1.5rem; flex-wrap: wrap; }
.pkpi { display: flex; flex-direction: column; gap: .08rem; }
.pkpi-label { font-size: .65rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; color: var(--text-muted); }
.pkpi-value { font-size: .95rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.period-seg { display: flex; gap: 2px; background: var(--bg-3); border: 1px solid var(--border); border-radius: 8px; padding: 3px; }
.period-btn {
  background: none; border: none; cursor: pointer; padding: .28rem .6rem;
  font-size: .76rem; font-weight: 600; color: var(--text-muted); border-radius: 5px;
  font-family: inherit; transition: all .12s;
}
.period-btn:hover { color: var(--text); }
.period-btn.active { background: var(--surface); color: var(--text); box-shadow: 0 1px 3px rgba(0,0,0,.12); }
.chart-box { height: 280px; position: relative; }

/* Risk */
.risk-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden; margin-bottom: .9rem;
}
.risk-cell { background: var(--surface); padding: 1rem 1.25rem; }
.risk-lbl { font-size: .65rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--text-muted); margin-bottom: .3rem; }
.risk-val { font-size: 1.7rem; font-weight: 800; letter-spacing: -.04em; font-variant-numeric: tabular-nums; margin-bottom: .15rem; line-height: 1; }
.risk-sub { font-size: .68rem; color: var(--text-muted); }
.risk-legend { display: flex; gap: 1.25rem; font-size: .73rem; margin-bottom: .6rem; }
.rl-good { color: #16a34a; font-weight: 600; }
.rl-mid  { color: #ca8a04; font-weight: 600; }
.rl-high { color: #ef4444; font-weight: 600; }
.risk-note { font-size: .72rem; color: var(--text-muted); line-height: 1.5; }
</style>
