<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">GoETF Quality Scores</h1>
      <p class="page-subtitle">Composite 1-10 quality score based on seven equal-weight return, risk, diversification, and cost metrics.</p>
    </div>

    <div v-if="!hasApiKey" class="cta-banner">
      <div class="cta-text">
        <strong>An API key is required to load ETF scores.</strong>
        <span>Get yours for free in 10 seconds.</span>
      </div>
      <button class="cta-btn" @click="showApiKeyModal = true">Get Free API Key</button>
    </div>

    <div class="card" style="margin-bottom:1.5rem;display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
      <div>
        <h2 class="card-title" style="margin:0">GoETF Quality Score</h2>
        <p style="font-size:.8rem;color:var(--text-muted);margin:.2rem 0 0">Absolute quality score against fixed benchmarks, independent of ETF universe size.</p>
        <button class="meth-link" @click="navigateTo('methodology')">How is this calculated?</button>
      </div>
      <label style="font-size:.8rem;color:var(--text-muted);margin-left:auto">Risk-free rate</label>
      <input class="input" type="number" v-model.number="goetfRfRate" min="0" max="20" step="0.5"
        style="width:72px;padding:.3rem .5rem;font-size:.875rem" />
      <span style="font-size:.8rem;color:var(--text-muted)">% p.a.</span>
      <button class="btn btn-outline" style="font-size:.875rem" @click="runGoetfScores" :disabled="goetfLoading">
        {{ goetfLoading ? 'Loading…' : 'Recalculate' }}
      </button>
    </div>

    <div v-if="goetfError" class="error-box" style="margin-bottom:1rem">{{ goetfError }}</div>

    <div v-if="goetfResult" class="card" style="padding:0;overflow:hidden">
      <div style="padding:.75rem 1.25rem;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center">
        <h3 class="card-title" style="margin:0">{{ goetfResult.length }} ETF{{ goetfResult.length !== 1 ? 's' : '' }}</h3>
        <span style="font-size:.75rem;color:var(--text-muted)">Rf = {{ goetfRfRate }}% · Click column header to sort</span>
      </div>
      <div class="table-wrap">
        <table class="risk-table">
          <thead>
            <tr>
              <th class="sortable-th" @click="toggleGoetfSort('goetf_score')">
                <span class="col-label" :data-tip="`Absolute quality score (1-10) based on fixed reference ranges for each metric.`">Score <span class="col-i">i</span></span>
                <span class="sort-arrow">{{ goetfSortKey==='goetf_score' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span>
              </th>
              <th class="sortable-th" @click="toggleGoetfSort('ticker')">Ticker <span class="sort-arrow">{{ goetfSortKey==='ticker' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th>Name</th>
              <th class="sortable-th" @click="toggleGoetfSort('cagr_pct')">CAGR <span class="sort-arrow">{{ goetfSortKey==='cagr_pct' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('sortino')">Sortino <span class="sort-arrow">{{ goetfSortKey==='sortino' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('max_drawdown_pct')">Max Drawdown <span class="sort-arrow">{{ goetfSortKey==='max_drawdown_pct' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('hhi')">HHI <span class="sort-arrow">{{ goetfSortKey==='hhi' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('geo_div')">Geo Div <span class="sort-arrow">{{ goetfSortKey==='geo_div' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('sector_div')">Sector Div <span class="sort-arrow">{{ goetfSortKey==='sector_div' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('ter_pct')">TER <span class="sort-arrow">{{ goetfSortKey==='ter_pct' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in goetfSorted" :key="row.etf_id" class="score-row" tabindex="0" @click="openETF(row)" @keydown.enter="openETF(row)" @keydown.space.prevent="openETF(row)">
              <td>
                <div class="score-cell">
                  <template v-if="row.goetf_score != null">
                    <span class="score-badge" :class="scoreBadgeClass(row.goetf_score)" :title="row.missing_components?.length ? `Calculated without: ${row.missing_components.join(', ')}` : 'All seven components available'">{{ row.goetf_score.toFixed(1) }}</span>
                    <button class="score-info-btn" type="button" :aria-label="`Show ${row.isin} Quality Score calculation`" @click.stop="showScoreDetail(row)" @keydown.stop>i</button>
                  </template>
                  <span v-else class="score-badge score-na">N/A</span>
                </div>
              </td>
              <td><strong style="color:var(--green-600)">{{ row.isin }}</strong></td>
              <td style="font-size:.8rem;color:var(--text-muted);max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ row.name }}</td>
              <td :class="signClass(row.cagr_pct)">{{ row.cagr_pct != null ? row.cagr_pct.toFixed(1) + '%' : '—' }}</td>
              <td :class="sortinoClass(row.sortino)">{{ row.sortino != null ? row.sortino.toFixed(2) : '—' }}</td>
              <td :class="ddClass(row.max_drawdown_pct)">{{ row.max_drawdown_pct != null ? row.max_drawdown_pct.toFixed(1) + '%' : '—' }}</td>
              <td :class="hhiClass(row.hhi)">{{ row.hhi != null ? row.hhi.toFixed(0) : '—' }}</td>
              <td :class="geodivClass(row.geo_div)">{{ row.geo_div != null ? (row.geo_div * 100).toFixed(1) + '%' : '—' }}</td>
              <td :class="geodivClass(row.sector_div)">{{ row.sector_div != null ? (row.sector_div * 100).toFixed(1) + '%' : '—' }}</td>
              <td :class="terClass(row.ter_pct)">{{ row.ter_pct != null ? row.ter_pct.toFixed(2) + '%' : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div style="padding:.5rem 1.25rem;border-top:1px solid var(--border);font-size:.7rem;color:var(--text-muted)">
        Seven available components are equally weighted. Scores require at least one year of price history; unavailable holdings, allocation, or TER components are disclosed in the score tooltip and excluded from the average.
      </div>
    </div>
    <div v-if="scoreDetail" class="score-detail-backdrop" @click.self="closeScoreDetail">
      <section class="score-detail" role="dialog" aria-modal="true" :aria-label="`${scoreDetail.isin} Quality Score calculation`">
        <div class="score-detail-head">
          <div>
            <p>GoETF Quality Score</p>
            <h2>{{ scoreDetail.isin }} <span>{{ scoreDetail.goetf_score.toFixed(1) }} / 10</span></h2>
          </div>
          <button class="score-detail-close" type="button" aria-label="Close calculation details" @click="closeScoreDetail">×</button>
        </div>
        <p class="score-detail-copy">Each available component is converted to a 0-1 quality score against a fixed benchmark. The final score is the equal-weight average, scaled to 1-10.</p>
        <div class="score-detail-list">
          <div v-for="component in scoreDetailComponents" :key="component.key" class="score-detail-row">
            <div><strong>{{ component.label }}</strong><span>{{ component.value }}</span></div>
            <div class="score-detail-quality"><span>Quality score</span><strong>{{ component.score.toFixed(3) }}</strong></div>
          </div>
        </div>
        <div class="score-detail-formula">
          <span>Equal-weight average</span>
          <strong>{{ scoreDetailAverage.toFixed(3) }}</strong>
          <span>1 + ({{ scoreDetailAverage.toFixed(3) }} × 9)</span>
          <strong>{{ scoreDetail.goetf_score.toFixed(1) }} / 10</strong>
        </div>
        <p v-if="scoreDetail.missing_components?.length" class="score-detail-missing">Not included because data is unavailable: {{ scoreDetail.missing_components.map(componentLabel).join(', ') }}.</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject, onMounted } from 'vue'
import { scoreService } from '../services/api.js'

const showApiKeyModal = inject('showApiKeyModal')
const hasApiKey = inject('hasApiKey', ref(!!localStorage.getItem('api_key')))
const navigateTo = inject('navigateTo')
const navigateToETF = inject('navigateToETF')

const goetfRfRate = ref(4.0)
const goetfLoading = ref(false)
const goetfResult = ref(null)
const goetfError = ref('')
const goetfSortKey = ref('goetf_score')
const goetfSortDir = ref('desc')
const scoreDetail = ref(null)

const COMPONENT_LABELS = {
  cagr_pct: 'CAGR',
  sortino: 'Sortino Ratio',
  max_drawdown_pct: 'Maximum Drawdown',
  hhi: 'Holdings HHI',
  geo_div: 'Country Diversity',
  sector_div: 'Sector Diversity',
  ter_pct: 'TER',
}

const goetfSorted = computed(() => {
  if (!goetfResult.value) return []
  return [...goetfResult.value].sort((a, b) => {
    let va = a[goetfSortKey.value], vb = b[goetfSortKey.value]
    if (va === null || va === undefined) va = goetfSortDir.value === 'asc' ? Infinity : -Infinity
    if (vb === null || vb === undefined) vb = goetfSortDir.value === 'asc' ? Infinity : -Infinity
    if (typeof va === 'string') return goetfSortDir.value === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
    return goetfSortDir.value === 'asc' ? va - vb : vb - va
  })
})

function toggleGoetfSort(key) {
  if (goetfSortKey.value === key) goetfSortDir.value = goetfSortDir.value === 'asc' ? 'desc' : 'asc'
  else { goetfSortKey.value = key; goetfSortDir.value = 'desc' }
}

function openETF(row) {
  navigateToETF({ id: row.etf_id })
}

function showScoreDetail(row) {
  scoreDetail.value = row
}

function closeScoreDetail() {
  scoreDetail.value = null
}

function componentLabel(key) {
  return COMPONENT_LABELS[key] || key
}

function componentValue(row, key) {
  const value = row[key]
  if (value == null) return 'Unavailable'
  if (key === 'sortino') return value.toFixed(2)
  if (key === 'hhi') return value.toFixed(0)
  if (key === 'geo_div' || key === 'sector_div') return `${(value * 100).toFixed(1)}%`
  if (key === 'ter_pct' || key === 'cagr_pct' || key === 'max_drawdown_pct') return `${value.toFixed(2)}%`
  return String(value)
}

const scoreDetailComponents = computed(() => {
  if (!scoreDetail.value) return []
  return (scoreDetail.value.available_components || []).map(key => ({
    key,
    label: componentLabel(key),
    value: componentValue(scoreDetail.value, key),
    score: scoreDetail.value.metric_scores[key],
  }))
})

const scoreDetailAverage = computed(() => {
  const components = scoreDetailComponents.value
  return components.length ? components.reduce((sum, component) => sum + component.score, 0) / components.length : 0
})

async function runGoetfScores() {
  goetfLoading.value = true
  goetfError.value = ''
  goetfResult.value = null
  try {
    const r = await scoreService.getEtfScores([], goetfRfRate.value / 100)
    goetfResult.value = r.data
  } catch (e) {
    goetfError.value = e.response?.data?.detail || e.message
  } finally {
    goetfLoading.value = false
  }
}

const scoreBadgeClass = (s) => s >= 7 ? 'score-high' : s >= 5 ? 'score-mid' : s >= 3.5 ? 'score-low' : 'score-poor'
const signClass = (v) => v == null ? '' : v >= 0 ? 'cell-green' : 'cell-red'
const sortinoClass = (v) => v == null ? '' : v >= 1.0 ? 'cell-green' : v >= 0.5 ? 'cell-yellow' : 'cell-red'
const ddClass      = (v) => v == null ? '' : v > -10 ? 'cell-green' : v > -20 ? 'cell-yellow' : 'cell-red'
const hhiClass     = (v) => v == null ? '' : v < 200  ? 'cell-green' : v < 1000 ? 'cell-yellow' : 'cell-red'
const geodivClass  = (v) => v == null ? '' : v >= 0.6 ? 'cell-green' : v >= 0.2 ? 'cell-yellow' : 'cell-red'
const terClass     = (v) => v == null ? '' : v <= 0.25 ? 'cell-green' : v <= 0.75 ? 'cell-yellow' : 'cell-red'

onMounted(runGoetfScores)
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
}
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
.score-row{cursor:pointer}
.score-row:focus-visible{outline:2px solid #2f85c8;outline-offset:-2px}
.score-cell{display:flex;align-items:center;gap:.35rem}
.score-info-btn{width:18px;height:18px;padding:0;border:1px solid var(--border);border-radius:50%;background:var(--surface);color:var(--text-muted);font-family:Georgia,serif;font-size:.72rem;font-weight:700;line-height:1;cursor:pointer}
.score-info-btn:hover,.score-info-btn:focus-visible{color:#0f4c81;border-color:#2f85c8;outline:none}
.sortable-th{cursor:pointer;user-select:none;white-space:nowrap}
.sortable-th:hover{color:#1a6ab8}
.sort-arrow{margin-left:.25rem;font-size:.7rem}
.cell-green{color:#16a34a;font-weight:600}
.cell-yellow{color:#ca8a04;font-weight:600}
.cell-red{color:#ef4444;font-weight:600}
.score-badge{display:inline-block;padding:.2rem .55rem;border-radius:6px;font-size:.85rem;font-weight:700;min-width:2.4rem;text-align:center}
.score-high{background:#dcfce7;color:#166534}
.score-mid{background:#fef9c3;color:#854d0e}
.score-low{background:#ffedd5;color:#9a3412}
.score-poor{background:#fee2e2;color:#b91c1c}
.score-na{background:var(--bg-3);color:var(--text-muted)}
.meth-link{background:none;border:none;padding:0;cursor:pointer;font-size:.76rem;color:#0f4c81;text-decoration:underline;margin-top:.2rem;display:inline-block}
.meth-link:hover{color:#1a6ab8}

.col-label{display:inline-flex;align-items:center;gap:.2rem;cursor:help;text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px;text-decoration-color:var(--text-muted,#aaa);position:relative;font-weight:600}
.col-i{display:inline-flex;align-items:center;justify-content:center;width:13px;height:13px;border-radius:50%;font-size:.6rem;font-weight:700;font-style:italic;background:var(--bg-3,#e8edf2);color:var(--text-muted,#888);flex-shrink:0;line-height:1}
.col-label::after{content:attr(data-tip);position:absolute;top:calc(100% + 8px);left:0;min-width:210px;max-width:250px;background:#1e293b;color:#f1f5f9;font-size:.73rem;font-weight:400;line-height:1.6;padding:.65rem .85rem;border-radius:8px;white-space:pre-line;text-align:left;box-shadow:0 4px 20px rgba(0,0,0,.4);pointer-events:none;opacity:0;transition:opacity .15s;z-index:300;text-decoration:none;font-style:normal}
.col-label:hover::after{opacity:1}
.score-detail-backdrop{position:fixed;inset:0;z-index:500;display:flex;align-items:center;justify-content:center;padding:1rem;background:rgba(15,23,42,.48)}
.score-detail{width:min(520px,100%);max-height:min(680px,calc(100vh - 2rem));overflow:auto;background:var(--surface);border:1px solid var(--border);border-radius:8px;box-shadow:0 24px 60px rgba(15,23,42,.28);padding:1.25rem}
.score-detail-head{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;border-bottom:1px solid var(--border);padding-bottom:1rem}
.score-detail-head p{margin:0 0 .25rem;font-size:.7rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted)}
.score-detail-head h2{margin:0;font-size:1.25rem;color:var(--text)}
.score-detail-head h2 span{color:#0f4c81;font-variant-numeric:tabular-nums}
.score-detail-close{width:28px;height:28px;padding:0;border:0;background:var(--bg-3);border-radius:5px;color:var(--text-muted);font-size:1.35rem;line-height:1;cursor:pointer}
.score-detail-close:hover{color:var(--text);background:var(--border)}
.score-detail-copy{font-size:.82rem;line-height:1.55;color:var(--text-muted);margin:1rem 0}
.score-detail-list{border-top:1px solid var(--border)}
.score-detail-row{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.65rem 0;border-bottom:1px solid var(--border)}
.score-detail-row>div:first-child{display:flex;flex-direction:column;gap:.12rem;min-width:0}
.score-detail-row strong{font-size:.82rem;color:var(--text)}
.score-detail-row span{font-size:.75rem;color:var(--text-muted)}
.score-detail-quality{display:flex;align-items:flex-end;flex-direction:column;gap:.12rem;white-space:nowrap}
.score-detail-formula{display:grid;grid-template-columns:1fr auto;gap:.35rem .75rem;margin-top:1rem;padding:.8rem;background:var(--bg-3);border-radius:6px;font-size:.78rem}
.score-detail-formula span{color:var(--text-muted)}
.score-detail-formula strong{color:#0f4c81;font-variant-numeric:tabular-nums}
.score-detail-missing{margin:1rem 0 0;font-size:.75rem;line-height:1.5;color:var(--text-muted)}
</style>
