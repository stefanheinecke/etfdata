<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">GoETF Scores</h1>
      <p class="page-subtitle">Composite 1-10 score based on 8 risk and diversification metrics across all tracked ETFs.</p>
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
        <h2 class="card-title" style="margin:0">GoETF Score</h2>
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
              <th class="sortable-th" @click="toggleGoetfSort('sortino')">Sortino <span class="sort-arrow">{{ goetfSortKey==='sortino' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('calmar')">Calmar <span class="sort-arrow">{{ goetfSortKey==='calmar' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('cvar')">CVaR 95% <span class="sort-arrow">{{ goetfSortKey==='cvar' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('hit_ratio')">Hit Ratio <span class="sort-arrow">{{ goetfSortKey==='hit_ratio' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('hhi')">HHI <span class="sort-arrow">{{ goetfSortKey==='hhi' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('effective_n')">Eff. N <span class="sort-arrow">{{ goetfSortKey==='effective_n' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('geo_div')">Geo Div <span class="sort-arrow">{{ goetfSortKey==='geo_div' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              <th class="sortable-th" @click="toggleGoetfSort('max_underwater')">Max UW <span class="sort-arrow">{{ goetfSortKey==='max_underwater' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in goetfSorted" :key="row.etf_id">
              <td>
                <span v-if="row.goetf_score != null" class="score-badge" :class="scoreBadgeClass(row.goetf_score)">{{ row.goetf_score.toFixed(1) }}</span>
                <span v-else class="score-badge score-na">N/A</span>
              </td>
              <td><strong style="color:var(--green-600)">{{ row.ticker }}</strong></td>
              <td style="font-size:.8rem;color:var(--text-muted);max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ row.name }}</td>
              <td :class="sortinoClass(row.sortino)">{{ row.sortino != null ? row.sortino.toFixed(2) : '—' }}</td>
              <td :class="calmarClass(row.calmar)">{{ row.calmar != null ? row.calmar.toFixed(2) : '—' }}</td>
              <td :class="cvarClass(row.cvar)">{{ row.cvar != null ? row.cvar.toFixed(1) + '%' : '—' }}</td>
              <td :class="hitClass(row.hit_ratio)">{{ row.hit_ratio != null ? (row.hit_ratio * 100).toFixed(1) + '%' : '—' }}</td>
              <td :class="hhiClass(row.hhi)">{{ row.hhi != null ? row.hhi.toFixed(0) : '—' }}</td>
              <td :class="effNClass(row.effective_n)">{{ row.effective_n != null ? row.effective_n.toFixed(0) : '—' }}</td>
              <td :class="geodivClass(row.geo_div)">{{ row.geo_div != null ? (row.geo_div * 100).toFixed(1) + '%' : '—' }}</td>
              <td :class="uwClass(row.max_underwater)">{{ row.max_underwater != null ? row.max_underwater + 'd' : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div style="padding:.5rem 1.25rem;border-top:1px solid var(--border);font-size:.7rem;color:var(--text-muted)">
        Score uses fixed benchmark ranges and is not investment advice.
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject, onMounted } from 'vue'
import { scoreService } from '../services/api.js'

const showApiKeyModal = inject('showApiKeyModal')
const hasApiKey = inject('hasApiKey', ref(!!localStorage.getItem('api_key')))
const navigateTo = inject('navigateTo')

const goetfRfRate = ref(4.0)
const goetfLoading = ref(false)
const goetfResult = ref(null)
const goetfError = ref('')
const goetfSortKey = ref('goetf_score')
const goetfSortDir = ref('desc')

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
const sortinoClass = (v) => v == null ? '' : v >= 1.0 ? 'cell-green' : v >= 0.5 ? 'cell-yellow' : 'cell-red'
const calmarClass  = (v) => v == null ? '' : v >= 0.5 ? 'cell-green' : v >= 0.2 ? 'cell-yellow' : 'cell-red'
const cvarClass    = (v) => v == null ? '' : v > -20  ? 'cell-green' : v > -40  ? 'cell-yellow' : 'cell-red'
const hitClass     = (v) => v == null ? '' : v >= 0.55 ? 'cell-green' : v >= 0.48 ? 'cell-yellow' : 'cell-red'
const hhiClass     = (v) => v == null ? '' : v < 200  ? 'cell-green' : v < 1000 ? 'cell-yellow' : 'cell-red'
const effNClass    = (v) => v == null ? '' : v >= 100 ? 'cell-green' : v >= 20  ? 'cell-yellow' : 'cell-red'
const geodivClass  = (v) => v == null ? '' : v >= 0.6 ? 'cell-green' : v >= 0.2 ? 'cell-yellow' : 'cell-red'
const uwClass      = (v) => v == null ? '' : v < 250  ? 'cell-green' : v < 500  ? 'cell-yellow' : 'cell-red'

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
</style>
