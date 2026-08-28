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

    <!-- PORTFOLIO COMPARISON -->
    <div v-if="activeTab==='compare'">
      <div class="card" style="margin-bottom:1.5rem">
        <h2 class="card-title">Compare Portfolios</h2>
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">Compare the composition and diversification characteristics of two portfolios. Results describe the differences; they do not recommend a portfolio.</p>
        <div class="compare-builders">
          <div class="compare-builder">
            <h3 class="compare-title">Portfolio A</h3>
            <div v-for="(item,i) in comparisonPortfolioA" :key="`a-${i}`" class="compare-row">
              <select class="input" v-model="item.etf_id">
                <option value="">Select ETF...</option>
                <option v-for="e in allEtfs" :key="e.id" :value="e.id">{{ e.ticker }} - {{ e.name }}</option>
              </select>
              <input class="input compare-weight" type="number" v-model.number="item.weight" aria-label="Portfolio A weight" min="0" max="100" />
              <button class="btn btn-outline compare-remove" @click="comparisonPortfolioA.splice(i,1)" aria-label="Remove ETF from Portfolio A">✕</button>
            </div>
            <button class="btn btn-outline compare-add" @click="comparisonPortfolioA.push({etf_id:'',weight:0})">+ Add ETF</button>
          </div>
          <div class="compare-builder">
            <h3 class="compare-title">Portfolio B</h3>
            <div v-for="(item,i) in comparisonPortfolioB" :key="`b-${i}`" class="compare-row">
              <select class="input" v-model="item.etf_id">
                <option value="">Select ETF...</option>
                <option v-for="e in allEtfs" :key="e.id" :value="e.id">{{ e.ticker }} - {{ e.name }}</option>
              </select>
              <input class="input compare-weight" type="number" v-model.number="item.weight" aria-label="Portfolio B weight" min="0" max="100" />
              <button class="btn btn-outline compare-remove" @click="comparisonPortfolioB.splice(i,1)" aria-label="Remove ETF from Portfolio B">✕</button>
            </div>
            <button class="btn btn-outline compare-add" @click="comparisonPortfolioB.push({etf_id:'',weight:0})">+ Add ETF</button>
          </div>
        </div>
        <div class="compare-actions">
          <button class="btn btn-primary" @click="runComparison" :disabled="comparisonLoading || !activePortfolio(comparisonPortfolioA).length || !activePortfolio(comparisonPortfolioB).length">
            {{ comparisonLoading ? 'Comparing...' : 'Compare Portfolios' }}
          </button>
          <label>Risk-free rate</label>
          <input class="input" type="number" v-model.number="riskFreeRate" min="0" max="20" step="0.5" />
          <span>% p.a.</span>
        </div>
      </div>
      <div v-if="comparisonError" class="error-box" style="margin-bottom:1rem">{{ comparisonError }}</div>
      <template v-if="comparisonResult">
        <div class="compare-summary">
          <div class="card compare-summary-card">
            <h3 class="compare-title">Portfolio A</h3>
            <div class="compare-metric"><span>GoETF Score</span><strong>{{ comparisonResult.a.score.portfolio_score?.toFixed(1) }}</strong></div>
            <div class="compare-metric"><span>Avg holdings overlap</span><strong>{{ comparisonResult.a.score.avg_overlap_pct?.toFixed(1) }}%</strong></div>
            <div class="compare-metric"><span>Country diversity</span><strong>{{ comparisonResult.a.score.portfolio_geo_div?.toFixed(3) ?? '—' }}</strong></div>
          </div>
          <div class="card compare-summary-card">
            <h3 class="compare-title">Portfolio B</h3>
            <div class="compare-metric"><span>GoETF Score</span><strong>{{ comparisonResult.b.score.portfolio_score?.toFixed(1) }}</strong></div>
            <div class="compare-metric"><span>Avg holdings overlap</span><strong>{{ comparisonResult.b.score.avg_overlap_pct?.toFixed(1) }}%</strong></div>
            <div class="compare-metric"><span>Country diversity</span><strong>{{ comparisonResult.b.score.portfolio_geo_div?.toFixed(3) ?? '—' }}</strong></div>
          </div>
        </div>
        <div v-for="group in [{key:'countries',label:'Country Exposure'}, {key:'sectors',label:'Sector Exposure'}, {key:'currencies',label:'Currency Exposure'}]" :key="group.key" class="card compare-exposure-card">
          <div class="compare-chart-header">
            <div>
              <h3 class="card-title">{{ group.label }}</h3>
              <p>Largest allocation differences between both portfolios</p>
            </div>
            <div class="compare-legend" aria-label="Chart legend">
              <span><i class="legend-a"></i>Portfolio A</span>
              <span><i class="legend-b"></i>Portfolio B</span>
            </div>
          </div>
          <div class="compare-donuts">
            <div class="compare-donut-panel compare-ring-panel">
              <div class="compare-donut-title">Inner ring: Portfolio A · Outer ring: Portfolio B</div>
              <div class="compare-donut-chart"><Doughnut :data="comparisonRingData(group.key)" :options="donutOptions" /></div>
            </div>
            <div class="compare-donut-labels" :aria-label="`${group.label} values by portfolio`">
              <div class="compare-donut-label-head"><span>Exposure</span><span>A</span><span>B</span></div>
              <div v-for="row in comparisonRingLabels(group.key)" :key="row.name" class="compare-donut-label-row">
                <span><i :style="{ background: row.color }"></i>{{ row.name }}</span>
                <strong>{{ row.a.toFixed(1) }}%</strong>
                <strong>{{ row.b.toFixed(1) }}%</strong>
              </div>
            </div>
          </div>
          <div v-if="exposureDifference(group.key).length" class="compare-chart" role="img" :aria-label="`${group.label} comparison`">
            <div v-for="row in exposureDifference(group.key)" :key="row.name" class="compare-chart-row">
              <div class="compare-chart-label" :title="row.name">{{ row.name }}</div>
              <div class="compare-bars">
                <div class="compare-bar-line">
                  <span class="compare-bar-value">{{ row.a.toFixed(1) }}%</span>
                  <div class="compare-track"><div class="compare-fill compare-fill-a" :style="{ width: `${Math.min(row.a, 100)}%` }"></div></div>
                </div>
                <div class="compare-bar-line">
                  <span class="compare-bar-value">{{ row.b.toFixed(1) }}%</span>
                  <div class="compare-track"><div class="compare-fill compare-fill-b" :style="{ width: `${Math.min(row.b, 100)}%` }"></div></div>
                </div>
              </div>
              <div class="compare-delta" :class="row.b - row.a > 0 ? 'compare-delta-up' : row.b - row.a < 0 ? 'compare-delta-down' : ''">
                {{ row.b - row.a > 0 ? '+' : '' }}{{ (row.b - row.a).toFixed(1) }} pts
              </div>
            </div>
          </div>
          <div v-else class="compare-empty">No allocation data available for this comparison.</div>
        </div>
      </template>
    </div>

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
import { Doughnut } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { etfService, analyticsService, scoreService } from '../services/api.js'

ChartJS.register(ArcElement, Tooltip, Legend)

const showApiKeyModal = inject('showApiKeyModal')
const analyticsInitTab = inject('analyticsInitTab', ref(null))
const navigateTo = inject('navigateTo')
const hasApiKey = inject('hasApiKey', ref(!!localStorage.getItem('api_key')))

const activeTab = ref('exposure')
const tabs = [
  {id:'exposure',label:'Portfolio Exposure',icon:'🌍'},
  {id:'compare',label:'Compare Portfolios',icon:'⇄'},
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

// Portfolio comparison
const comparisonPortfolioA = ref([{etf_id:'',weight:50},{etf_id:'',weight:50}])
const comparisonPortfolioB = ref([{etf_id:'',weight:50},{etf_id:'',weight:50}])
const comparisonLoading = ref(false)
const comparisonError = ref('')
const comparisonResult = ref(null)

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

function activePortfolio(items) {
  return items.filter(item => item.etf_id && item.weight > 0)
}

async function analysePortfolio(items) {
  const portfolioItems = activePortfolio(items)
  const [exposureResponse, scoreResponse] = await Promise.all([
    analyticsService.calculateExposure(portfolioItems, null, riskFreeRate.value / 100),
    scoreService.getPortfolioScore(portfolioItems, riskFreeRate.value / 100),
  ])
  return { exposure: exposureResponse.data, score: scoreResponse.data }
}

async function runComparison() {
  const portfolioA = activePortfolio(comparisonPortfolioA.value)
  const portfolioB = activePortfolio(comparisonPortfolioB.value)
  if (!portfolioA.length || !portfolioB.length) return

  comparisonLoading.value = true
  comparisonError.value = ''
  comparisonResult.value = null
  try {
    const [a, b] = await Promise.all([analysePortfolio(portfolioA), analysePortfolio(portfolioB)])
    comparisonResult.value = { a, b }
  } catch (error) {
    comparisonError.value = error.response?.data?.detail || error.message
  } finally {
    comparisonLoading.value = false
  }
}

function exposureDifference(type) {
  if (!comparisonResult.value) return []
  const a = comparisonResult.value.a.exposure[type] || {}
  const b = comparisonResult.value.b.exposure[type] || {}
  return [...new Set([...Object.keys(a), ...Object.keys(b)])]
    .map(name => ({ name, a: a[name] || 0, b: b[name] || 0 }))
    .sort((left, right) => Math.abs(right.a - right.b) - Math.abs(left.a - left.b))
    .slice(0, 6)
}

const donutPalette = ['#0f4c81', '#00a98f', '#e6a800', '#d14343', '#7b61a8', '#2f85c8', '#7a8b99']
const donutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '52%',
  layout: { padding: 2 },
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: context => ` ${context.dataset.label}: ${context.label} ${context.parsed.toFixed(1)}%` } },
  },
}

function comparisonRingLabels(type) {
  if (!comparisonResult.value) return []
  const a = comparisonResult.value.a.exposure[type] || {}
  const b = comparisonResult.value.b.exposure[type] || {}
  const names = [...new Set([...Object.keys(a), ...Object.keys(b)])]
    .sort((left, right) => Math.max(b[right] || 0, a[right] || 0) - Math.max(b[left] || 0, a[left] || 0))
  const leading = names.slice(0, 5).map((name, index) => ({ name, a: a[name] || 0, b: b[name] || 0, color: donutPalette[index] }))
  const otherA = names.slice(5).reduce((total, name) => total + (a[name] || 0), 0)
  const otherB = names.slice(5).reduce((total, name) => total + (b[name] || 0), 0)
  if (otherA > 0 || otherB > 0) leading.push({ name: 'Other', a: otherA, b: otherB, color: '#aab8c5' })
  return leading
}

function comparisonRingData(type) {
  const entries = comparisonRingLabels(type)
  return {
    labels: entries.map(entry => entry.name),
    datasets: [
      { label: 'Portfolio A', data: entries.map(entry => entry.a), backgroundColor: entries.map(entry => entry.color), borderColor: '#ffffff', borderWidth: 2, hoverOffset: 5 },
      { label: 'Portfolio B', data: entries.map(entry => entry.b), backgroundColor: entries.map(entry => entry.color), borderColor: '#ffffff', borderWidth: 2, hoverOffset: 5 },
    ],
  }
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
.compare-builders,.compare-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}
.compare-builder{min-width:0;padding:1rem;background:var(--bg-3);border:1px solid var(--border);border-radius:8px}
.compare-title{margin:0 0 .75rem;font-size:.95rem;color:var(--text)}
.compare-row{display:grid;grid-template-columns:minmax(0,1fr) 82px 34px;gap:.5rem;margin-bottom:.5rem;align-items:center}
.compare-weight{min-width:0}
.compare-remove{width:34px;height:34px;padding:0;line-height:1}
.compare-add{margin-top:.25rem;font-size:.8rem}
.compare-actions{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-top:1rem}
.compare-actions label{margin-left:auto;font-size:.8rem;color:var(--text-muted)}
.compare-actions input{width:72px;padding:.3rem .5rem;font-size:.875rem}
.compare-actions span{font-size:.8rem;color:var(--text-muted)}
.compare-summary{margin-bottom:1rem}
.compare-summary-card{padding:1rem}
.compare-metric{display:flex;justify-content:space-between;gap:1rem;padding:.45rem 0;border-top:1px solid var(--border);font-size:.82rem;color:var(--text-muted)}
.compare-metric strong{color:var(--text);font-variant-numeric:tabular-nums}
.compare-exposure-card{margin-bottom:1rem;padding:0;overflow:hidden}
.compare-chart-header{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem 1.25rem;border-bottom:1px solid var(--border)}
.compare-chart-header .card-title{margin:0}
.compare-chart-header p{margin:.25rem 0 0;font-size:.75rem;color:var(--text-muted)}
.compare-legend{display:flex;gap:.85rem;flex-wrap:wrap;font-size:.75rem;color:var(--text-muted);white-space:nowrap}
.compare-legend span{display:flex;align-items:center;gap:.35rem}
.compare-legend i{width:9px;height:9px;border-radius:50%;display:block}
.legend-a{background:#0f4c81}.legend-b{background:#00a98f}
.compare-donuts{display:grid;grid-template-columns:minmax(260px,.85fr) minmax(280px,1.15fr);gap:1rem;padding:1rem 1.25rem;background:color-mix(in srgb,var(--bg-3) 52%,transparent);border-bottom:1px solid var(--border)}
.compare-donut-panel{min-width:0;padding:.75rem;background:var(--surface);border:1px solid var(--border);border-radius:8px}
.compare-ring-panel{display:flex;flex-direction:column}
.compare-donut-title{font-size:.75rem;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em}
.compare-donut-chart{height:188px;margin-top:.35rem}
.compare-donut-labels{align-self:stretch;display:flex;flex-direction:column;justify-content:center;min-width:0}
.compare-donut-label-head,.compare-donut-label-row{display:grid;grid-template-columns:minmax(0,1fr) 52px 52px;gap:.5rem;align-items:center;padding:.45rem .6rem;font-size:.78rem}
.compare-donut-label-head{padding-top:0;color:var(--text-muted);font-size:.7rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase}
.compare-donut-label-row{border-top:1px solid var(--border);color:var(--text)}
.compare-donut-label-row span{display:flex;align-items:center;gap:.45rem;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.compare-donut-label-row i{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.compare-donut-label-row strong{text-align:right;font-variant-numeric:tabular-nums;font-size:.76rem}
.compare-chart{padding:.5rem 1.25rem .75rem}
.compare-chart-row{display:grid;grid-template-columns:minmax(100px,150px) minmax(250px,1fr) 72px;gap:1rem;align-items:center;padding:.65rem 0;border-bottom:1px solid color-mix(in srgb,var(--border) 60%,transparent)}
.compare-chart-row:last-child{border-bottom:0}
.compare-chart-label{font-size:.8rem;font-weight:600;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.compare-bars{display:flex;flex-direction:column;gap:.35rem;min-width:0}
.compare-bar-line{display:grid;grid-template-columns:38px minmax(0,1fr);align-items:center;gap:.45rem}
.compare-bar-value{font-size:.7rem;text-align:right;color:var(--text-muted);font-variant-numeric:tabular-nums}
.compare-track{height:8px;border-radius:4px;overflow:hidden;background:repeating-linear-gradient(90deg,var(--bg-3) 0,var(--bg-3) calc(25% - 1px),var(--border) calc(25% - 1px),var(--border) 25%)}
.compare-fill{height:100%;border-radius:4px;min-width:2px;animation:compare-bar-grow .55s ease-out both;transform-origin:left}
.compare-fill-a{background:#0f4c81}.compare-fill-b{background:#00a98f}
.compare-delta{text-align:right;font-size:.75rem;font-weight:700;color:var(--text-muted);font-variant-numeric:tabular-nums}
.compare-delta-up{color:#008a74}.compare-delta-down{color:#d14343}
.compare-empty{padding:1.5rem;text-align:center;color:var(--text-muted);font-size:.85rem}
@keyframes compare-bar-grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
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
  .compare-builders,.compare-summary{grid-template-columns:1fr}
  .compare-actions label{margin-left:0}
  .compare-chart-header{align-items:flex-start;flex-direction:column}
  .compare-donuts{grid-template-columns:1fr}
  .compare-donut-chart{height:205px}
  .compare-chart-row{grid-template-columns:1fr;gap:.45rem;padding:.85rem 0}
  .compare-delta{text-align:left;margin-left:43px}
}
</style>
