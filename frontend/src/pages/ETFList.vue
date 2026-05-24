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
        <div><label class="label">Provider</label>
          <select class="input" v-model="filterProvider" @change="loadETFs">
            <option value="">All providers</option>
            <option v-for="p in providers" :key="p" :value="p">{{ p }}</option>
          </select>
        </div>
        <div><label class="label">Limit</label>
          <select class="input" v-model="limit" @change="loadETFs">
            <option :value="10">10</option><option :value="25">25</option><option :value="50">50</option>
          </select>
        </div>
        <div style="display:flex;align-items:flex-end">
          <button class="btn btn-primary" @click="loadETFs" :disabled="loading">
            <span v-if="loading" class="spinner" style="width:14px;height:14px;border-width:2px"></span>
            {{ loading ? 'Loading...' : 'Refresh' }}
          </button>
        </div>
      </div>
    </div>
    <div v-if="error" class="error-box" style="margin-bottom:1.5rem">{{ error }}</div>
    <div v-if="loading" class="loading"><div class="spinner"></div> Loading ETFs...</div>
    <div v-else-if="etfs.length" class="etf-grid">
      <div v-for="etf in etfs" :key="etf.id" class="etf-card" @click="openETF(etf)">
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
          <button v-for="t in ['Overview','Holdings','Allocations']" :key="t"
            :class="['code-tab',{active:detailTab===t}]" @click="detailTab=t;loadDetail(t)">{{ t }}</button>
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
                <div v-for="a in group.items" :key="a.bucket" class="alloc-row">
                  <span class="alloc-label">{{ a.bucket }}</span>
                  <div class="alloc-track"><div class="alloc-fill" :style="{width:Math.min(a.weight,100)+'%'}"></div></div>
                  <span class="alloc-pct">{{ Number(a.weight).toFixed(1) }}%</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="empty-state"><p>No allocation data available.</p></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { etfService } from '../services/api.js'
const etfs = ref([])
const loading = ref(false)
const error = ref('')
const filterProvider = ref('')
const limit = ref(50)
const providers = ['Vanguard', 'iShares', 'UBS']
const apiKey = ref(localStorage.getItem('api_key') || '')
const selectedETF = ref(null)
const detailTab = ref('Overview')
const detailLoading = ref(false)
const holdings = ref([])
const allocations = ref([])
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
  return Object.entries(map).map(([type,items]) => ({type,items:items.sort((a,b)=>b.weight-a.weight)}))
})
function formatSize(n) {
  if (n>=1e9) return (n/1e9).toFixed(1)+'B'
  if (n>=1e6) return (n/1e6).toFixed(0)+'M'
  return n.toLocaleString()
}
async function loadETFs() {
  loading.value=true; error.value=''
  try { const r=await etfService.getETFs(0,limit.value,filterProvider.value||null); etfs.value=r.data }
  catch(e) { error.value=e.response?.data?.detail||e.message }
  finally { loading.value=false }
}
function openETF(etf) { selectedETF.value=etf; detailTab.value='Overview'; holdings.value=[]; allocations.value=[] }
async function loadDetail(tab) {
  if (!selectedETF.value||tab==='Overview') return
  detailLoading.value=true
  try {
    if (tab==='Holdings') { const r=await etfService.getHoldings(selectedETF.value.id); holdings.value=r.data }
    else if (tab==='Allocations') { const r=await etfService.getAllocations(selectedETF.value.id); allocations.value=r.data }
  } catch(e){console.error(e)} finally{detailLoading.value=false}
}
onMounted(loadETFs)
</script>

<style scoped>
.filters{display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-end}
.filters>div{flex:1;min-width:140px}
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
.modal-tabs{display:flex;gap:.25rem;padding-bottom:1rem;border-bottom:1px solid var(--border)}
.alloc-bars{display:flex;flex-direction:column;gap:.5rem}
.alloc-row{display:flex;align-items:center;gap:.75rem}
.alloc-label{width:120px;font-size:.8rem;color:var(--text-2);flex-shrink:0}
.alloc-track{flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden}
.alloc-fill{height:100%;background:var(--green-500);border-radius:4px;transition:width .4s}
.alloc-pct{width:45px;text-align:right;font-size:.8rem;font-weight:600;color:var(--text)}
</style>
