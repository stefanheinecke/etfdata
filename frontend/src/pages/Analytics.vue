<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">Portfolio Analytics</h1>
      <p class="page-subtitle">Multi-asset catalog · Equity-focused securities, country and sector overlap. Price-based risk metrics remain available where price data exists.</p>
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
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">Combine equity ETFs to compare securities, countries and sectors. Bond, commodity and unknown asset classes are not supported for holdings analytics. Reported holdings may differ from index exposure for synthetic funds.</p>
        <div v-for="(item,i) in portfolio" :key="i" style="display:flex;gap:.5rem;margin-bottom:.5rem;align-items:center">
          <ETFSelector v-model="item.etf_id" :etfs="allEtfs" :label="'Portfolio ETF ' + (i + 1)" style="flex:2" />
          <input class="input" type="number" v-model.number="item.weight" placeholder="Weight %" style="flex:1;max-width:120px" min="0" max="100" step="0.01" :aria-label="'Portfolio weight ' + (i + 1)" />
          <button class="btn btn-outline" @click="portfolio.splice(i,1)" style="flex-shrink:0">✕</button>
        </div>
        <div style="display:flex;gap:.75rem;margin-top:.75rem;align-items:center;flex-wrap:wrap">
          <button class="btn btn-outline" @click="portfolio.push({etf_id:'',weight:0})">+ Add ETF</button>
          <span style="font-size:.8rem;color:var(--text-muted)">{{ exposureLoading ? 'Calculating…' : 'Updates automatically as you edit the portfolio.' }}</span>
          <label style="font-size:.8rem;color:var(--text-muted);margin-left:auto">Risk-free rate</label>
          <input class="input" type="number" v-model.number="riskFreeRate" min="0" max="20" step="0.5"
            style="width:72px;padding:.3rem .5rem;font-size:.875rem" />
          <span style="font-size:.8rem;color:var(--text-muted)">% p.a.</span>
        </div>
      </div>
      <div v-if="exposureResult" class="portfolio-donut-grid">
        <div v-for="group in portfolioExposureGroups" :key="group.key" class="card portfolio-donut-card">
          <div class="portfolio-donut-head"><h3 class="card-title">{{ group.label }}</h3><span>{{ group.total.toFixed(1) }}% classified</span></div>
          <p class="overlap-caption">{{ group.coverage?.status || 'Coverage unavailable' }} · {{ formatCoverage(group.coverage?.coverage) }} of portfolio represented</p>
          <div v-if="group.total > 0" class="portfolio-donut-chart"><Doughnut :data="portfolioDonutData(group)" :options="portfolioDonutOptions" /></div>
          <div v-else class="donut-unavailable" role="status"><div class="empty-donut" aria-hidden="true"></div><span>Data unavailable</span><small>No supported {{ group.key }} allocation data for this selection.</small></div>
          <div v-if="group.total > 0" class="portfolio-donut-legend">
            <div v-for="entry in group.entries" :key="entry.name"><span><i :style="{ background: entry.color }"></i>{{ entry.name }}</span><strong>{{ entry.value.toFixed(1) }}%</strong></div>
          </div>
        </div>
      </div>
      <div v-if="analysisWarnings.length" class="analysis-notice" role="status">
        <strong>Data availability notices</strong>
        <p class="overlap-caption">Lists exactly why a total below is partial or unavailable, so missing data is never mistaken for zero overlap or full diversification.</p>
        <ul><li v-for="warning in analysisWarnings" :key="warning">{{ warning }}</li></ul>
      </div>
      <div v-if="pairSuggestionsError" class="analysis-notice" role="status">{{ pairSuggestionsError }}</div>
      <section v-for="section in overlapSections" :key="section.key" class="card overlap-section" v-show="section.pairs.length">
        <h3 class="card-title" style="margin-bottom:.25rem">{{ section.title }}</h3>
        <p class="overlap-caption">{{ section.description }}</p>
        <div v-if="section.loading" style="padding:.75rem 0;font-size:.85rem;color:var(--text-muted)">{{ section.loadingLabel }}</div>
        <div v-for="pair in section.pairs" :key="pair.key" class="overlap-pair">
          <button class="pair-heading" type="button" :aria-expanded="isPairOpen(pair.key)" @click="togglePair(pair.key)">
            <span class="pair-chevron" :class="{ open: isPairOpen(pair.key) }">▶</span>
            <span class="pair-etf">{{ etfLabel(pair.etf_a_isin) }}</span>
            <span style="color:var(--text-muted)">↔</span>
            <span class="pair-etf">{{ etfLabel(pair.etf_b_isin) }}</span>
            <span v-if="pair.value != null" style="margin-left:auto;font-size:.85rem;font-weight:700">{{ pair.value.toFixed(1) }}% overlap</span>
            <span v-else style="margin-left:auto">Analysis unavailable</span>
          </button>
          <p v-if="pair.value == null" class="overlap-caption">{{ pair.reason || 'Data unavailable.' }}</p>
          <div v-show="isPairOpen(pair.key)" style="margin-top:.6rem">
            <p class="overlap-caption">
              {{ etfLabel(pair.etf_a_isin) }}: {{ pair.as_of_a || 'No snapshot' }}<span v-if="pair.coverage_a != null"> · {{ formatCoverage(pair.coverage_a) }} classified</span><br />
              {{ etfLabel(pair.etf_b_isin) }}: {{ pair.as_of_b || 'No snapshot' }}<span v-if="pair.coverage_b != null"> · {{ formatCoverage(pair.coverage_b) }} classified</span>
            </p>
            <div v-if="pair.rows.length" class="table-wrap">
              <table class="holdings-table">
                <thead>
                  <tr>
                    <th>{{ section.rowLabel }}</th>
                    <th style="text-align:right">{{ etfLabel(pair.etf_a_isin) }}</th>
                    <th style="text-align:right">{{ etfLabel(pair.etf_b_isin) }}</th>
                    <th style="text-align:right">Overlap</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in pair.rows" :key="row.key">
                    <td>{{ row.label }}</td>
                    <td style="text-align:right">{{ row.a.toFixed(2) }}%</td>
                    <td style="text-align:right">{{ row.b.toFixed(2) }}%</td>
                    <td style="text-align:right;font-weight:700">{{ row.overlap.toFixed(2) }}%</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
      <div v-if="exposureError" class="error-box" style="margin-bottom:1rem">{{ exposureError }}</div>
      <!-- Top 10 Holdings -->
      <div v-if="topHoldings && topHoldings.length" class="card" style="margin-top:1.5rem;padding:0;overflow:hidden">
        <div style="padding:1rem 1.25rem;border-bottom:1px solid var(--border)">
          <h3 class="card-title" style="margin:0">Top 10 Holdings</h3>
          <p class="overlap-caption">{{ exposureResult?.top_holdings_status || 'Coverage unavailable' }} · source baskets cover {{ formatCoverage(exposureResult?.top_holdings_coverage) }} of portfolio before top-10 truncation.</p>
        </div>
        <div class="table-wrap">
          <table class="holdings-table">
            <thead>
              <tr>
                <th style="width:50%">Holding Name</th>
                <th style="text-align:right">Weight</th>
                <th>Sector</th>
                <th>Country</th>
                <th>Holding currency</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(holding, idx) in topHoldings" :key="idx">
                <td><span style="font-weight:600;color:var(--text)">{{ holding.name }}</span></td>
                <td style="text-align:right;font-weight:600">{{ holding.weight.toFixed(2) }}%</td>
                <td style="color:var(--text-muted);font-size:.85rem">{{ holding.sector || '—' }}</td>
                <td style="color:var(--text-muted);font-size:.85rem">{{ holding.country || '—' }}</td>
                <td style="color:var(--text-muted);font-size:.85rem">{{ holding.currency || '—' }}</td>
              </tr>
            </tbody>
          </table>
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
              <div class="stat-label">Max Drawdown</div>
              <div class="stat-value" :class="ddClass(portfolioSummary.max_drawdown)">{{ fmtPct(portfolioSummary.max_drawdown) }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Avg HHI</div>
              <div class="stat-value" :class="hhiClass(portfolioSummary.hhi)">{{ portfolioSummary.hhi?.toFixed(0) ?? '—' }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Active ETFs</div>
              <div class="stat-value">{{ portfolioSummary.etf_count }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Country Diversity</div>
              <div class="stat-value" :class="diversityClass(portfolioSummary.geo_div)">{{ fmtDiversity(portfolioSummary.geo_div) }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Sector Diversity</div>
              <div class="stat-value" :class="diversityClass(portfolioSummary.sector_div)">{{ fmtDiversity(portfolioSummary.sector_div) }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Weighted TER</div>
              <div class="stat-value" :class="terClass(portfolioSummary.ter_pct)">{{ portfolioSummary.ter_pct != null ? portfolioSummary.ter_pct.toFixed(2) + '%' : '—' }}</div>
            </div>
          </div>
          <p style="font-size:.7rem;color:var(--text-muted);margin-top:.75rem;margin-bottom:0">
            Based on available price, holdings, allocation, and cost data &nbsp;·&nbsp; A portfolio Sharpe ratio is not shown because it requires a synchronized portfolio return series and correlations. Return, volatility, drawdown, HHI, and TER are weighted estimates, not a backtested portfolio series.
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
                <th>ISIN</th>
                <th>1Y Return</th>
                <th>Volatility</th>
                <th>Sharpe</th>
                <th>Max Drawdown</th>
                <th>HHI</th>
                <th>Country Div.</th>
                <th>Sector Div.</th>
                <th>TER</th>
                <th># Holdings</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in portfolioRiskResult" :key="row.etf_id">
                <td><strong style="color:var(--green-600)">{{ row.isin }}</strong></td>
                <td :class="signClass(row.ann_return)">{{ fmtPct(row.ann_return) }}</td>
                <td :class="volClass(row.volatility)">{{ fmtPct(row.volatility) }}</td>
                <td :class="sharpeClass(row.sharpe_ratio)">{{ row.sharpe_ratio !== null ? row.sharpe_ratio : '—' }}</td>
                <td :class="ddClass(row.max_drawdown)">{{ fmtPct(row.max_drawdown) }}</td>
                <td :class="hhiClass(row.hhi)" :title="row.hhi_reason || ''">{{ row.hhi != null ? row.hhi.toFixed(0) : '—' }}</td>
                <td :class="diversityClass(individualScore(row.etf_id)?.geo_div)">{{ fmtDiversity(individualScore(row.etf_id)?.geo_div) }}</td>
                <td :class="diversityClass(individualScore(row.etf_id)?.sector_div)">{{ fmtDiversity(individualScore(row.etf_id)?.sector_div) }}</td>
                <td :class="terClass(individualScore(row.etf_id)?.ter_pct)">{{ individualScore(row.etf_id)?.ter_pct != null ? individualScore(row.etf_id).ter_pct.toFixed(2) + '%' : '—' }}</td>
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
import { ref, computed, onMounted, inject, watch } from 'vue'
import ETFSelector from '../components/ETFSelector.vue'
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
// Risk-free rate used for constituent ETF risk metrics and the portfolio Quality Score.
const riskFreeRate = ref(4.0)     // % per year
const exposureLoading = ref(false)
const exposureResult = ref(null)
const exposureError = ref('')
const topHoldings = ref(null)
const portfolioRiskResult = ref(null)
const portfolioScoreResult = ref(null)
const portfolioScoreLoading = ref(false)
const pairSuggestions = ref(null)
const pairSuggestionsLoading = ref(false)
const pairSuggestionsError = ref('')
const scoreError = ref('')
let analysisRun = 0
let autoRunTimer = null
// Auto-analyse as the user edits the portfolio; debounced so fast edits (typing
// a weight, picking several ETFs) trigger one request instead of many.
watch(portfolio, () => {
  analysisRun++
  exposureResult.value = null
  topHoldings.value = null
  portfolioRiskResult.value = null
  portfolioScoreResult.value = null
  pairSuggestions.value = null
  exposureError.value = ''
  scoreError.value = ''
  pairSuggestionsError.value = ''
  exposureLoading.value = false
  portfolioScoreLoading.value = false
  pairSuggestionsLoading.value = false
  clearTimeout(autoRunTimer)
  if (portfolio.value.some(item => item.etf_id && item.weight > 0)) {
    autoRunTimer = setTimeout(runExposure, 400)
  }
}, { deep: true, flush: 'sync' })
watch(riskFreeRate, () => {
  clearTimeout(autoRunTimer)
  if (portfolio.value.some(item => item.etf_id && item.weight > 0)) {
    autoRunTimer = setTimeout(runExposure, 400)
  }
})
const analysisWarnings = computed(() => [
  ...(exposureResult.value?.analysis_warnings || []),
  ...(portfolioScoreResult.value?.status === 'unavailable' ? [portfolioScoreResult.value.reason || 'Portfolio quality score unavailable.'] : []),
  ...(scoreError.value ? [scoreError.value] : []),
])
const formatCoverage = value => value == null ? 'Unknown' : `${Number(value).toFixed(1)}%`
const openPairs = ref(new Set())
function isPairOpen(key) { return openPairs.value.has(key) }
function togglePair(key) {
  const next = new Set(openPairs.value)
  next.has(key) ? next.delete(key) : next.add(key)
  openPairs.value = next
}
function etfLabel(isin) {
  const etf = allEtfs.value.find(item => item.isin === isin)
  return etf ? `${etf.name} (${etf.isin})` : (isin || 'Unknown ETF')
}

const portfolioSummary = computed(() => {
  if (!portfolioRiskResult.value?.length) return null
  const p = portfolio.value.filter(x => x.etf_id && x.weight > 0)
  const totalW = p.reduce((s, x) => s + (x.weight || 0), 0)
  if (!totalW) return null
  let wReturn = 0, wVol = 0, wDD = 0, wHHI = 0, wTer = 0, terWeight = 0
  for (const row of portfolioRiskResult.value) {
    const pw = p.find(x => x.etf_id === row.etf_id)
    const w = pw ? (pw.weight || 0) / totalW : 0
    if (row.ann_return   !== null) wReturn += w * row.ann_return
    if (row.volatility   !== null) wVol    += w * row.volatility
    if (row.max_drawdown !== null) wDD     += w * row.max_drawdown
    if (row.hhi          !== null) wHHI    += w * row.hhi
    const etf = allEtfs.value.find(item => item.id === row.etf_id)
    if (etf?.ter !== null && etf?.ter !== undefined) {
      wTer += w * Number(etf.ter)
      terWeight += w
    }
  }
  const completeMetric = key => p.every(item => portfolioRiskResult.value.find(row => row.etf_id === item.etf_id)?.[key] != null)
  const countryDiversity = exposureResult.value?.exposure_coverage?.country?.status === 'available' ? diversityFromExposure(exposureResult.value?.countries) : null
  const sectorDiversity = exposureResult.value?.exposure_coverage?.sector?.status === 'available' ? diversityFromExposure(exposureResult.value?.sectors) : null
  return {
    ann_return: completeMetric('ann_return') ? wReturn : null,
    volatility: completeMetric('volatility') ? wVol : null,
    max_drawdown: completeMetric('max_drawdown') ? wDD : null,
    hhi: completeMetric('hhi') ? wHHI : null,
    etf_count: p.length,
    geo_div: countryDiversity,
    sector_div: sectorDiversity,
    ter_pct: terWeight > 0 ? wTer / terWeight : null,
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

function diversityFromExposure(exposure) {
  const weights = Object.values(exposure || {}).map(Number)
  const total = weights.reduce((sum, weight) => sum + weight, 0)
  if (!total) return null
  return 1 - weights.reduce((sum, weight) => sum + (weight / total) ** 2, 0)
}

function buildExposureGroup(key, label, values, formatter = name => name) {
  const sorted = Object.entries(values || {}).map(([name, value]) => ({ name: formatter(name), value: Number(value) }))
    .sort((left, right) => right.value - left.value)
  const visible = sorted.slice(0, 6)
  const other = sorted.slice(6).reduce((sum, item) => sum + item.value, 0)
  if (other > 0) visible.push({ name: 'Other', value: other })
  const total = sorted.reduce((sum, item) => sum + item.value, 0)
  const portfolioWeight = portfolio.value.filter(item => item.etf_id && item.weight > 0).reduce((sum, item) => sum + item.weight, 0)
  const unknown = Math.max(0, portfolioWeight - total)
  if (unknown > 0.005) visible.push({ name: 'Unclassified / unavailable', value: unknown })
  return { key, label, total, entries: visible.map((item, index) => ({ ...item, color: ['Other', 'Unclassified / unavailable'].includes(item.name) ? '#aab8c5' : DONUT_COLORS[index % DONUT_COLORS.length] })) }
}

const portfolioExposureGroups = computed(() => {
  if (!exposureResult.value) return []
  const r = exposureResult.value
  return [
    buildExposureGroup('country', 'Country Exposure', r.countries, fullCountryName),
    buildExposureGroup('region', 'Region Exposure', regionExposures(r.countries)),
    buildExposureGroup('sector', 'Sector Exposure', r.sectors),
    buildExposureGroup('currency', 'Holding Currency Exposure', r.currencies),
  ].map(group => ({ ...group, coverage: r.exposure_coverage?.[group.key === 'region' ? 'country' : group.key] }))
})

const overlapSections = computed(() => {
  const allocationOverlap = exposureResult.value?.allocation_overlap || {}
  const securities = (pairSuggestions.value || []).map(pair => ({
    key: `securities:${pair.etf_a_id}_${pair.etf_b_id}`,
    etf_a_isin: pair.etf_a_isin, etf_b_isin: pair.etf_b_isin,
    value: pair.current_overlap, reason: pair.reason,
    as_of_a: pair.as_of_a, as_of_b: pair.as_of_b, coverage_a: null, coverage_b: null,
    rows: (pair.common_holdings || []).map(h => ({
      key: h.isin || h.name, label: h.isin ? `${h.name} (${h.isin})` : h.name,
      a: h.etf_a_weight, b: h.etf_b_weight, overlap: h.overlap,
    })),
  }))
  const buildAllocation = (kind) => (allocationOverlap[kind] || []).map(pair => ({
    key: `${kind}:${pair.etf_a}_${pair.etf_b}`,
    etf_a_isin: pair.etf_a_isin, etf_b_isin: pair.etf_b_isin,
    value: pair.weight_overlap, reason: pair.reason,
    as_of_a: pair.as_of_a, as_of_b: pair.as_of_b, coverage_a: pair.coverage_a, coverage_b: pair.coverage_b,
    rows: (pair.buckets || []).map(bucket => ({
      key: bucket.bucket, label: kind === 'country' ? fullCountryName(bucket.bucket) : bucket.bucket,
      a: bucket.etf_a_weight, b: bucket.etf_b_weight, overlap: bucket.overlap,
    })),
  }))
  return [
    { key: 'securities', title: 'Securities Overlap', rowLabel: 'Security', pairs: securities,
      loading: pairSuggestionsLoading.value, loadingLabel: 'Analysing securities overlap…',
      description: 'Matched by security ISIN. Overlap sums the smaller normalized equity-basket weight for each shared security. Up to 20 largest contributors are shown; totals use all holdings.' },
    { key: 'country', title: 'Country Overlap', rowLabel: 'Country', pairs: buildAllocation('country'), loading: false, loadingLabel: '',
      description: 'Sum of the smaller weight in each shared country. At least 95% classified fund weight is required on each side; unknown exposure is not matched or rescaled.' },
    { key: 'sector', title: 'Sector Overlap', rowLabel: 'Sector', pairs: buildAllocation('sector'), loading: false, loadingLabel: '',
      description: 'Sum of the smaller weight in each shared sector. At least 95% classified fund weight is required on each side; unknown exposure is not matched or rescaled.' },
  ]
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

function individualScore(etfId) {
  return portfolioScoreResult.value?.individual_scores?.find(score => score.etf_id === etfId)
}

async function loadETFs() {
  etfsLoading.value=true
  try { const r=await etfService.getETFs(0,5000); allEtfs.value=r.data } catch(e){exposureError.value=e.response?.data?.detail||e.message} finally{etfsLoading.value=false}
}
async function runExposure() {
  const run = ++analysisRun
  exposureLoading.value=true; exposureError.value=''; exposureResult.value=null; topHoldings.value=null; portfolioRiskResult.value=null; portfolioScoreResult.value=null; pairSuggestions.value=null; openPairs.value=new Set()
  pairSuggestionsError.value=''; scoreError.value=''
  const p=portfolio.value.filter(x=>x.etf_id && x.weight > 0).map(x=>({...x}))
  try {
    const r = await analyticsService.calculateExposure(p, null, riskFreeRate.value / 100)
    if (run !== analysisRun) return
    exposureResult.value = r.data
    topHoldings.value = r.data.top_holdings ?? null
    portfolioRiskResult.value = r.data.risk_metrics ?? null
    if (p.length >= 1) {
      portfolioScoreLoading.value = true
      try {
        const sr = await scoreService.getPortfolioScore(p, riskFreeRate.value / 100)
        if (run !== analysisRun) return
        portfolioScoreResult.value = sr.data
      } catch(e) { if (run === analysisRun) scoreError.value = 'Portfolio quality score unavailable: ' + (e.response?.data?.detail || e.message) }
        finally { if (run === analysisRun) portfolioScoreLoading.value = false }
    }
    if (p.length >= 2) {
      pairSuggestionsLoading.value = true
      try {
        const pr = await analyticsService.getPairSuggestions(p)
        if (run !== analysisRun) return
        pairSuggestions.value = pr.data
      } catch(e) { if (run === analysisRun) pairSuggestionsError.value = 'Securities overlap unavailable: ' + (e.response?.data?.detail || e.message) }
        finally { if (run === analysisRun) pairSuggestionsLoading.value = false }
    }
  } catch(e){if (run === analysisRun) exposureError.value=e.response?.data?.detail||e.message} finally{if (run === analysisRun) exposureLoading.value=false}
}

const scoreBadgeClass = (s) => s >= 7 ? 'score-high' : s >= 5 ? 'score-mid' : s >= 3.5 ? 'score-low' : 'score-poor'
const hhiClass     = (v) => v == null ? '' : v < 200  ? 'cell-green' : v < 1000 ? 'cell-yellow' : 'cell-red'

const fmtPct = v => v !== null && v !== undefined ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '—'
const signClass = v  => v === null ? '' : v >= 0 ? 'cell-green' : 'cell-red'
const volClass  = v  => v === null ? '' : v < 12 ? 'cell-green' : v < 22 ? 'cell-yellow' : 'cell-red'
const sharpeClass = v => v === null ? '' : v >= 1 ? 'cell-green' : v >= 0 ? 'cell-yellow' : 'cell-red'
const ddClass   = v  => v === null ? '' : v > -10 ? 'cell-green' : v > -20 ? 'cell-yellow' : 'cell-red'
const diversityClass = v => v == null ? '' : v >= 0.6 ? 'cell-green' : v >= 0.35 ? 'cell-yellow' : 'cell-red'
const terClass = v => v == null ? '' : v <= 0.25 ? 'cell-green' : v <= 0.75 ? 'cell-yellow' : 'cell-red'
const fmtDiversity = v => v == null ? '—' : `${(v * 100).toFixed(1)}%`

onMounted(() => {
  loadETFs()
  if (portfolioInit.value) {
    // Reassigning portfolio triggers the watcher above, which auto-runs the analysis.
    const isSelection = Array.isArray(portfolioInit.value)
    portfolio.value = (isSelection ? portfolioInit.value : [portfolioInit.value]).map(item => ({ ...item }))
    portfolioInit.value = null
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
.holdings-table{width:100%;border-collapse:collapse;font-size:.85rem}
.holdings-table thead tr{background:var(--bg-3)}
.holdings-table th,.holdings-table td{padding:.65rem .75rem;text-align:left;border-bottom:1px solid var(--border)}
.holdings-table tbody tr:hover{background:var(--bg-3)}
.sortable-th{cursor:pointer;user-select:none;white-space:nowrap}
.stat-box{background:var(--bg-3);border-radius:10px;padding:.75rem 1rem;display:flex;flex-direction:column}
.stat-box .stat-value{font-size:1.25rem}
.sortable-th:hover{color:#1a6ab8}
.sort-arrow{margin-left:.25rem;font-size:.7rem}
.cell-green{color:#16a34a;font-weight:600}
.cell-yellow{color:#ca8a04;font-weight:600}
.cell-red{color:#ef4444;font-weight:600}
.pair-chevron{display:inline-block;font-size:.7rem;color:var(--text-muted);transition:transform .15s ease}
.pair-chevron.open{transform:rotate(90deg)}
.pair-heading{display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;cursor:pointer;width:100%;border:0;background:transparent;color:var(--text);text-align:left;padding:.25rem 0;font:inherit}
.pair-etf{font-weight:700;font-size:.9rem;color:var(--green-600)}
.analysis-notice{padding:1rem 1.25rem;border:1px solid var(--border);border-left:4px solid #c99522;border-radius:8px;background:var(--surface);margin:1rem 0;font-size:.85rem}
.analysis-notice ul{padding-left:1.25rem;max-height:180px;overflow:auto}
.overlap-caption{font-size:.78rem;color:var(--text-muted);margin:.5rem 0 .75rem;line-height:1.5}
.overlap-section{margin-bottom:1.5rem}
.overlap-pair{border:1px solid var(--border);border-radius:8px;padding:.875rem 1rem;margin-bottom:.75rem}
.table-wrap{overflow-x:auto}
.portfolio-donut-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;margin-top:1.5rem}
.portfolio-donut-card{padding:1rem;min-width:0}
.portfolio-donut-head{display:flex;justify-content:space-between;gap:1rem;align-items:baseline}
.portfolio-donut-head .card-title{margin:0}
.portfolio-donut-head>span{font-size:.75rem;font-weight:700;color:var(--text-muted);font-variant-numeric:tabular-nums}
.portfolio-donut-chart{height:220px;margin:.5rem 0 .75rem}
.donut-unavailable{height:250px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.65rem;text-align:center;color:var(--text-muted);font-size:.85rem}
.empty-donut{width:145px;height:145px;border:25px solid var(--border);border-radius:50%;box-sizing:border-box}
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
