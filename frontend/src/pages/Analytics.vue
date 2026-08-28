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
    <div>
      <div class="card" style="margin-bottom:1.5rem">
        <h2 class="card-title">Portfolio Exposure</h2>
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">Select one ETF for a complete ETF view, or combine several ETFs to analyse the portfolio as a whole.</p>
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
        <p style="font-size:.7rem;color:var(--text-muted);margin-top:.75rem;margin-bottom:0">
          Base = weighted avg of individual GoETF Scores &nbsp;·&nbsp; Overlap Penalty: max −2 pts for 100% overlap &nbsp;·&nbsp; Bonus: portfolio country diversification vs individual weighted avg
          &nbsp;<button class="meth-link" @click="navigateTo('methodology')">→ Methodology</button>
        </p>
      </div>
      <div v-if="exposureError" class="error-box" style="margin-bottom:1rem">{{ exposureError }}</div>
      <div v-if="exposureResult" class="portfolio-donut-grid">
        <div v-for="group in portfolioExposureGroups" :key="group.key" class="card portfolio-donut-card">
          <div class="portfolio-donut-head"><h3 class="card-title">{{ group.label }}</h3><span>{{ group.total.toFixed(1) }}%</span></div>
          <div class="portfolio-donut-chart"><Doughnut :data="portfolioDonutData(group)" :options="portfolioDonutOptions" /></div>
          <div class="portfolio-donut-legend">
            <div v-for="entry in group.entries" :key="entry.name"><span><i :style="{ background: entry.color }"></i>{{ entry.name }}</span><strong>{{ entry.value.toFixed(1) }}%</strong></div>
          </div>
        </div>
      </div>

      <!-- Portfolio Risk Metrics -->
      <div v-if="portfolioRiskResult">

        <!-- Portfolio-level summary -->
        <div v-if="portfolioSummary" class="card" style="margin-top:1.5rem">
          <h3 class="card-title" style="margin-bottom:1rem">Financial Figures <span style="font-size:.75rem;font-weight:400;color:var(--text-muted)">(weighted portfolio estimates)</span></h3>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:.75rem">
            <div class="stat-box">
              <div class="stat-label">Annual Return</div>
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
            <div class="stat-box">
              <div class="stat-label">Active ETFs</div>
              <div class="stat-value">{{ portfolioSummary.etf_count }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Price History</div>
              <div class="stat-value">{{ portfolioSummary.data_points?.toLocaleString() ?? '—' }}</div>
            </div>
          </div>
          <p style="font-size:.7rem;color:var(--text-muted);margin-top:.75rem;margin-bottom:0">
            Based on available price and holdings data &nbsp;·&nbsp; Rf = {{ riskFreeRate }}% &nbsp;·&nbsp; Return, volatility, drawdown, and HHI are weighted estimates, not a backtested portfolio series.
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
      </div>

  </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { Doughnut } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { etfService, analyticsService, scoreService } from '../services/api.js'

ChartJS.register(ArcElement, Tooltip, Legend)

const showApiKeyModal = inject('showApiKeyModal')
const analyticsInitTab = inject('analyticsInitTab', ref(null))
const portfolioInit = inject('portfolioInit', ref(null))
const navigateTo = inject('navigateTo')
const hasApiKey = inject('hasApiKey', ref(!!localStorage.getItem('api_key')))

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
  const dataPoints = portfolioRiskResult.value
    .map(row => row.data_points || 0)
    .filter(Boolean)
  return {
    ann_return: wReturn,
    volatility: wVol,
    sharpe_ratio: sharpe !== null ? Number(sharpe) : null,
    max_drawdown: wDD,
    hhi: wHHI,
    etf_count: p.length,
    data_points: dataPoints.length ? Math.min(...dataPoints) : 0,
  }
})

const COUNTRY_NAMES = {
  AF:'Afghanistan',AL:'Albania',DZ:'Algeria',AR:'Argentina',AU:'Australia',AT:'Austria',BE:'Belgium',BM:'Bermuda',BR:'Brazil',CA:'Canada',KY:'Cayman Islands',CL:'Chile',CN:'China',CO:'Colombia',CZ:'Czech Republic',DK:'Denmark',EG:'Egypt',FI:'Finland',FR:'France',DE:'Germany',GR:'Greece',HK:'Hong Kong',HU:'Hungary',IN:'India',ID:'Indonesia',IE:'Ireland',IL:'Israel',IT:'Italy',JP:'Japan',LU:'Luxembourg',MY:'Malaysia',MX:'Mexico',NL:'Netherlands',NZ:'New Zealand',NO:'Norway',PH:'Philippines',PL:'Poland',PT:'Portugal',QA:'Qatar',SA:'Saudi Arabia',SG:'Singapore',ZA:'South Africa',KR:'South Korea',ES:'Spain',SE:'Sweden',CH:'Switzerland',TW:'Taiwan',TH:'Thailand',TR:'Turkey',AE:'United Arab Emirates',GB:'United Kingdom',US:'United States',VN:'Vietnam',
}
const REGION_BY_COUNTRY = {
  Afghanistan:'Asia',Albania:'Europe',Algeria:'Africa',Argentina:'Latin America',Australia:'Pacific',Austria:'Europe',Belgium:'Europe',Bermuda:'North America',Brazil:'Latin America',Canada:'North America','Cayman Islands':'Latin America',Chile:'Latin America',China:'Asia',Colombia:'Latin America','Czech Republic':'Europe',Denmark:'Europe',Egypt:'Africa',Finland:'Europe',France:'Europe',Germany:'Europe',Greece:'Europe','Hong Kong':'Asia',Hungary:'Europe',India:'Asia',Indonesia:'Asia',Ireland:'Europe',Israel:'Middle East',Italy:'Europe',Japan:'Asia',Luxembourg:'Europe',Malaysia:'Asia',Mexico:'Latin America',Netherlands:'Europe','New Zealand':'Pacific',Norway:'Europe',Philippines:'Asia',Poland:'Europe',Portugal:'Europe',Qatar:'Middle East','Saudi Arabia':'Middle East',Singapore:'Asia','South Africa':'Africa','South Korea':'Asia',Spain:'Europe',Sweden:'Europe',Switzerland:'Europe',Taiwan:'Asia',Thailand:'Asia',Turkey:'Europe','United Arab Emirates':'Middle East','United Kingdom':'Europe','United States':'North America',Vietnam:'Asia',
}
const DONUT_COLORS = ['#0f4c81','#00a98f','#e6a800','#d14343','#7b61a8','#2f85c8','#aab8c5']

function fullCountryName(country) {
  return COUNTRY_NAMES[country] || country
}

function regionExposures(countries) {
  return Object.entries(countries || {}).reduce((regions, [country, weight]) => {
    const region = REGION_BY_COUNTRY[fullCountryName(country)] || 'Other / Unclassified'
    regions[region] = (regions[region] || 0) + weight
    return regions
  }, {})
}

function buildExposureGroup(key, label, values, formatter = name => name) {
  const sorted = Object.entries(values || {}).map(([name, value]) => ({ name: formatter(name), value: Number(value) }))
    .sort((left, right) => right.value - left.value)
  const visible = sorted.slice(0, 6)
  const other = sorted.slice(6).reduce((sum, item) => sum + item.value, 0)
  if (other > 0) visible.push({ name: 'Other', value: other })
  return { key, label, total: sorted.reduce((sum, item) => sum + item.value, 0), entries: visible.map((item, index) => ({ ...item, color: item.name === 'Other' ? '#aab8c5' : DONUT_COLORS[index % DONUT_COLORS.length] })) }
}

const portfolioExposureGroups = computed(() => {
  if (!exposureResult.value) return []
  const r = exposureResult.value
  return [
    buildExposureGroup('country', 'Country Exposure', r.countries, fullCountryName),
    buildExposureGroup('region', 'Region Exposure', regionExposures(r.countries)),
    buildExposureGroup('sector', 'Sector Exposure', r.sectors),
    buildExposureGroup('currency', 'Currency Exposure', r.currencies),
  ].filter(group => group.entries.length)
})

const portfolioDonutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '62%',
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: context => ` ${context.label}: ${context.parsed.toFixed(1)}%` } },
  },
}

function portfolioDonutData(group) {
  return {
    labels: group.entries.map(entry => entry.name),
    datasets: [{ data: group.entries.map(entry => entry.value), backgroundColor: group.entries.map(entry => entry.color), borderColor: '#ffffff', borderWidth: 2, hoverOffset: 5 }],
  }
}

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

const fmtPct = v => v !== null && v !== undefined ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '—'
const signClass = v  => v === null ? '' : v >= 0 ? 'cell-green' : 'cell-red'
const volClass  = v  => v === null ? '' : v < 12 ? 'cell-green' : v < 22 ? 'cell-yellow' : 'cell-red'
const sharpeClass = v => v === null ? '' : v >= 1 ? 'cell-green' : v >= 0 ? 'cell-yellow' : 'cell-red'
const ddClass   = v  => v === null ? '' : v > -10 ? 'cell-green' : v > -20 ? 'cell-yellow' : 'cell-red'

onMounted(() => {
  loadETFs()
  if (portfolioInit.value) {
    portfolio.value = [{ ...portfolioInit.value }]
    portfolioInit.value = null
    runExposure()
  }
  analyticsInitTab.value = null
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
.portfolio-donut-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;margin-top:1.5rem}
.portfolio-donut-card{padding:1rem;min-width:0}
.portfolio-donut-head{display:flex;justify-content:space-between;gap:1rem;align-items:baseline}
.portfolio-donut-head .card-title{margin:0}
.portfolio-donut-head>span{font-size:.75rem;font-weight:700;color:var(--text-muted);font-variant-numeric:tabular-nums}
.portfolio-donut-chart{height:220px;margin:.5rem 0 .75rem}
.portfolio-donut-legend{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.35rem .75rem}
.portfolio-donut-legend div{display:flex;align-items:center;justify-content:space-between;gap:.5rem;min-width:0;font-size:.75rem;color:var(--text-muted)}
.portfolio-donut-legend span{display:flex;align-items:center;gap:.35rem;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.portfolio-donut-legend i{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.portfolio-donut-legend strong{color:var(--text);font-size:.73rem;font-variant-numeric:tabular-nums}
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
@media (max-width:640px){
  .portfolio-donut-grid{grid-template-columns:1fr}
  .portfolio-donut-chart{height:240px}
}
</style>
