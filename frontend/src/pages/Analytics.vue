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
async function runSimilar() {
  similarLoading.value=true; similarError.value=''; similarResult.value=null
  try { const r=await analyticsService.findSimilar(similarId.value); similarResult.value=r.data }
  catch(e){similarError.value=e.response?.data?.detail||e.message} finally{similarLoading.value=false}
}
onMounted(loadETFs)
</script>

<style scoped>
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
