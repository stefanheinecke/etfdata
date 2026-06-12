<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">Admin</h1>
      <p class="page-subtitle">Manage API keys, seed data and configure your connection settings.</p>
    </div>

    <!-- Tab Navigation -->
    <div class="tab-bar">
      <button :class="['tab-btn', { active: activeTab === 'management' }]" @click="activeTab = 'management'">Management</button>
      <button :class="['tab-btn', { active: activeTab === 'etfvalues' }]" @click="switchToValues">ETF Values</button>
    </div>

    <template v-if="activeTab === 'management'">

    <!-- API Key Config -->
    <div class="card" style="margin-bottom:1.5rem">
      <h2 class="card-title">API Key</h2>
      <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">
        Your API key is stored locally in the browser and sent with every request.
      </p>
      <label class="label">API Key</label>
      <div class="key-row">
        <input :type="showKey ? 'text' : 'password'" class="input" v-model="apiKey" placeholder="Paste your API key here..." />
        <button class="btn btn-outline" @click="showKey=!showKey">{{ showKey ? 'Hide' : 'Show' }}</button>
        <button class="btn btn-primary" @click="saveKey">Save</button>
      </div>
      <div v-if="keySaved" class="success-msg">✓ API key saved. Reload the ETF pages to apply.</div>
    </div>

    <!-- Admin credentials -->
    <div class="card" style="margin-bottom:1.5rem">
      <h2 class="card-title">Admin Credentials</h2>
      <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">
        Enter your <code>ADMIN_SECRET</code> from Railway to unlock admin operations.
        Stored in <strong>sessionStorage</strong> — cleared automatically when you close the browser tab.
      </p>
      <label class="label">Admin Secret</label>
      <div class="key-row">
        <input :type="showAdmin ? 'text' : 'password'" class="input" v-model="adminSecret" @input="adminVerified = false; verifyError = ''" placeholder="Your ADMIN_SECRET..." />
        <button class="btn btn-outline" @click="showAdmin=!showAdmin">{{ showAdmin ? 'Hide' : 'Show' }}</button>
        <button class="btn btn-primary" @click="verifySecret" :disabled="!adminSecret || verifyLoading">
          {{ verifyLoading ? 'Verifying...' : adminVerified ? '✓ Verified' : 'Verify' }}
        </button>
      </div>
      <div v-if="verifyError" class="error-box" style="margin-top:.5rem">{{ verifyError }}</div>
      <div v-if="adminVerified" class="success-msg" style="margin-top:.5rem;display:flex;align-items:center;justify-content:space-between;gap:1rem">
        <span>✓ Admin secret verified — operations unlocked.</span>
        <button class="btn btn-outline" style="font-size:.8rem;padding:.35rem .75rem" @click="logout">Log out</button>
      </div>
    </div>

    <!-- Admin operations -->
    <div class="grid-2" style="margin-bottom:1.5rem">
      <div class="card">
        <h3 class="card-title">Create New API Key</h3>
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">Generate a new API key. Copy it — it won't be shown again.</p>
        <label class="label">Key Name</label>
        <input class="input" v-model="newKeyName" placeholder="e.g. my-app" style="margin-bottom:.75rem" />
        <label class="label">Rate Limit (req/min)</label>
        <input class="input" type="number" v-model.number="newKeyRateLimit" style="margin-bottom:.75rem" />
        <label class="label">User Email <span style="font-weight:400;color:var(--text-muted)">(optional)</span></label>
        <input class="input" type="email" v-model="newKeyEmail" placeholder="user@example.com" style="margin-bottom:.75rem" />
        <button class="btn btn-primary" @click="createKey" :disabled="!adminVerified || !newKeyName || createLoading">
          {{ createLoading ? 'Creating...' : 'Create API Key' }}
        </button>
        <div v-if="createError" class="error-box" style="margin-top:.75rem">{{ createError }}</div>
        <div v-if="createdKey" class="success-msg" style="margin-top:.75rem">
          <strong>New API Key (copy now!):</strong><br/>
          <code style="word-break:break-all;font-size:.8rem">{{ createdKey }}</code>
          <button class="btn btn-outline" style="margin-top:.5rem;width:100%" @click="useAsApiKey">Use as my API key</button>
        </div>
      </div>

      <div class="card">
        <h3 class="card-title">Database Management</h3>
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1.25rem">Manage the database schema and sample data.</p>
        <div style="display:flex;flex-direction:column;gap:.75rem">
          <div>
            <button class="btn btn-outline" style="width:100%" @click="initDb" :disabled="!adminVerified || initLoading">
              {{ initLoading ? 'Running...' : '⚡ Init DB (create tables)' }}
            </button>
            <p style="font-size:.75rem;color:var(--text-muted);margin-top:.3rem">Creates missing tables without deleting data.</p>
          </div>
          <div>
            <button class="btn btn-outline" style="width:100%" @click="seedDb" :disabled="!adminVerified || seedLoading">
              {{ seedLoading ? 'Seeding...' : '🌱 Seed (add missing data)' }}
            </button>
            <p style="font-size:.75rem;color:var(--text-muted);margin-top:.3rem">Inserts sample ETFs and holdings if not already present.</p>
          </div>
          <div>
            <button class="btn btn-danger" style="width:100%" @click="confirmReset" :disabled="!adminVerified || resetLoading">
              {{ resetLoading ? 'Resetting...' : '🗑 Reset & Reseed (wipes all ETF data)' }}
            </button>
            <p style="font-size:.75rem;color:var(--text-muted);margin-top:.3rem">Deletes all ETF data and reseeds fresh sample data.</p>
          </div>
        </div>
        <div v-if="dbResult" class="success-msg" style="margin-top:.75rem">{{ dbResult }}</div>
        <div v-if="dbError" class="error-box" style="margin-top:.75rem">{{ dbError }}</div>
      </div>
    </div>

    <!-- Import ETF -->
    <div class="card" style="margin-bottom:1.5rem">
      <h2 class="card-title">Import ETF</h2>
      <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">
        Provide an EODHD symbol (e.g. <code>EIMI.SW</code>, <code>SWDA.LSE</code>) to import or refresh an ETF.
        All metadata — name, ISIN, TER, benchmark, holdings — is fetched automatically from EODHD.
        Use a USD-denominated listing (e.g. <code>.SW</code>) to store prices in USD.
      </p>
      <div style="margin-bottom:.75rem">
        <label class="label">EODHD Symbol</label>
        <input class="input" v-model="importSymbol" placeholder="e.g. EIMI.SW or SWDA.LSE" style="text-transform:uppercase" />
      </div>
      <div class="grid-2" style="margin-bottom:.75rem">
        <div>
          <label class="label">Name <span style="font-weight:400;color:var(--text-muted)">(optional override)</span></label>
          <input class="input" v-model="importName" placeholder="e.g. iShares Core FTSE 100 UCITS ETF" />
        </div>
        <div>
          <label class="label">TER % <span style="font-weight:400;color:var(--text-muted)">(optional override)</span></label>
          <input class="input" type="number" step="0.01" v-model.number="importTer" placeholder="e.g. 0.07" />
        </div>
      </div>
      <label class="label">Holdings CSV <span style="font-weight:400;color:var(--text-muted)">(optional — EODHD holdings used if not provided)</span></label>
      <input type="file" accept=".csv" class="input" style="margin-bottom:.75rem" @change="e => importCsvFile = e.target.files[0]" />
      <button class="btn btn-primary" @click="importETF" :disabled="!adminVerified || !importSymbol || importLoading" style="width:100%">
        {{ importLoading ? 'Importing…' : 'Import ETF' }}
      </button>
      <div v-if="importError" class="error-box" style="margin-top:.75rem">{{ importError }}</div>
      <div v-if="importResult" class="success-msg" style="margin-top:.75rem">
        ✓ {{ importResult.name }} ({{ importResult.ticker }}) imported — {{ importResult.holdings }} holdings, {{ importResult.allocations }} allocations.
      </div>
      <div v-if="importLogs.length" style="margin-top:.75rem;background:#f8f9fa;border-radius:6px;padding:.75rem;font-family:monospace;font-size:.8rem;white-space:pre-wrap;max-height:200px;overflow-y:auto;">{{ importLogs.join('\n') }}</div>
    </div>

    <!-- ETF Management -->
    <div class="card" style="margin-bottom:1.5rem">
      <h2 class="card-title">ETF Management</h2>
      <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">
        Select ETFs to permanently delete them along with all their holdings and allocations.
      </p>
      <button class="btn btn-outline" @click="loadETFs" :disabled="!adminVerified || etfLoading" style="margin-bottom:1rem">
        {{ etfLoading ? 'Loading...' : 'Load ETF List' }}
      </button>
      <div v-if="etfError" class="error-box" style="margin-bottom:.75rem">{{ etfError }}</div>

      <div v-if="etfList.length > 0">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem">
          <label style="display:flex;align-items:center;gap:.4rem;cursor:pointer;font-weight:600">
            <input type="checkbox" :checked="allEtfsSelected" @change="toggleAllEtfs"> Select all
          </label>
          <span style="font-size:.85rem;color:var(--text-muted)">{{ etfList.length }} ETF(s)</span>
        </div>
        <div class="etf-list">
          <div v-for="etf in etfList" :key="etf.id" class="etf-row">
            <input type="checkbox" :value="etf.id" v-model="selectedEtfIds">
            <span class="etf-ticker">{{ etf.ticker }}</span>
            <span class="etf-name">{{ etf.name }}</span>
            <span class="etf-provider">{{ etf.provider }}</span>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:1rem;margin-top:.75rem">
          <button class="btn btn-danger" :disabled="selectedEtfIds.length === 0 || deleteEtfLoading" @click="deleteSelectedEtfs">
            {{ deleteEtfLoading ? 'Deleting...' : `Delete Selected (${selectedEtfIds.length})` }}
          </button>
          <span v-if="deleteEtfResult" class="success-msg">{{ deleteEtfResult }}</span>
          <span v-if="deleteEtfError" class="error-box">{{ deleteEtfError }}</span>
        </div>
      </div>
    </div>

    <!-- Health status -->
    <div class="card">
      <h3 class="card-title">API Health</h3>
      <button class="btn btn-outline" @click="checkHealth" :disabled="healthLoading" style="margin-bottom:1rem">
        {{ healthLoading ? 'Checking...' : 'Check Health' }}
      </button>
      <div v-if="healthResult" class="health-grid">
        <div class="stat-card">
          <div class="stat-label">Status</div>
          <div class="stat-value" style="font-size:1.2rem;color:var(--green-600)">{{ healthResult.status }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Database</div>
          <div class="stat-value" style="font-size:1.2rem" :style="{color: healthResult.database==='healthy'?'var(--green-600)':'#dc2626'}">
            {{ healthResult.database }}
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Timestamp</div>
          <div class="stat-value" style="font-size:.9rem">{{ new Date(healthResult.timestamp).toLocaleString() }}</div>
        </div>
      </div>
    </div>

    <!-- Request Logs -->
    <div v-if="adminVerified" class="card" style="margin-top:1.5rem">
      <h2 class="section-title">📡 Request Logs</h2>
      <div class="log-filters">
        <input v-model="logFilterName" class="input" placeholder="Filter by key name…" style="flex:1" />
        <input v-model="logFilterEmail" class="input" placeholder="Filter by email…" style="flex:1" />
        <input v-model="logFilterPath" class="input" placeholder="Filter by path prefix…" style="flex:1" />
        <button class="btn" @click="loadLogs(0)" :disabled="logsLoading">{{ logsLoading ? 'Loading…' : 'Search' }}</button>
      </div>
      <div v-if="logsError" class="error-msg" style="margin-top:.5rem">{{ logsError }}</div>
      <div v-if="logsData" style="margin-top:.75rem">
        <div class="log-meta">{{ logsData.total }} total &nbsp;|&nbsp; showing {{ logsData.offset + 1 }}–{{ Math.min(logsData.offset + logsData.limit, logsData.total) }}</div>
        <div class="log-table-wrap">
          <table class="log-table">
            <thead>
              <tr>
                <th>Time (UTC)</th>
                <th>Method</th>
                <th>Path</th>
                <th>Status</th>
                <th>ms</th>
                <th>Key / Email</th>
                <th>IP</th>
                <th>Query / Body</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in logsData.logs" :key="row.id" :class="row.status_code >= 400 ? 'row-error' : ''">
                <td class="td-time">{{ row.created_at ? row.created_at.replace('T',' ').slice(0,19) : '—' }}</td>
                <td><span :class="'method-' + row.method">{{ row.method }}</span></td>
                <td class="td-path">{{ row.path }}</td>
                <td :class="row.status_code >= 400 ? 'cell-red' : 'cell-green'">{{ row.status_code }}</td>
                <td>{{ row.response_time_ms }}</td>
                <td class="td-key">
                  <span v-if="row.api_key_name">{{ row.api_key_name }}</span>
                  <span v-if="row.email" style="color:var(--text-muted);font-size:.8rem"><br>{{ row.email }}</span>
                  <span v-if="!row.api_key_name" style="color:var(--text-muted)">—</span>
                </td>
                <td>{{ row.client_ip || '—' }}</td>
                <td class="td-detail">
                  <span v-if="row.query_string" class="detail-chip">?{{ row.query_string }}</span>
                  <span v-if="row.request_body" class="detail-chip body-chip" :title="row.request_body">body</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="log-pagination">
          <button class="btn" :disabled="logsData.offset === 0" @click="loadLogs(logsData.offset - logsData.limit)">← Prev</button>
          <span>Page {{ Math.floor(logsData.offset / logsData.limit) + 1 }}</span>
          <button class="btn" :disabled="logsData.offset + logsData.limit >= logsData.total" @click="loadLogs(logsData.offset + logsData.limit)">Next →</button>
        </div>
      </div>
    </div>

    <!-- Disclaimer -->
    <div class="disclaimer-card" style="margin-top:1.5rem">
      <h3>📋 Admin Disclaimer</h3>
      <p>
        Admin operations directly modify the production database. The Reset operation permanently deletes all ETF data.
        ETF Data is for <strong>informational purposes only</strong> — none of the data constitutes investment advice.
        Do not use real financial data without appropriate licensing and compliance review.
      </p>
    </div>

    </template><!-- /management tab -->

    <!-- ETF Values Tab -->
    <template v-if="activeTab === 'etfvalues'">
      <div class="card" style="margin-bottom:1.5rem">
        <h2 class="card-title">ETF Values (Performance Data)</h2>
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">
          Select an ETF and an optional date range to view daily close price and NAV data. Use this to test performance and risk calculations.
        </p>

        <div class="grid-2" style="margin-bottom:.75rem">
          <div>
            <label class="label">ETF</label>
            <div style="display:flex;gap:.5rem">
              <select class="input" v-model="valuesEtfId" style="flex:1">
                <option value="">— select ETF —</option>
                <option v-for="e in valuesEtfList" :key="e.id" :value="e.id">{{ e.ticker }} — {{ e.name }}</option>
              </select>
              <button class="btn btn-outline" @click="loadValuesEtfList" :disabled="valuesEtfListLoading" title="Refresh ETF list">
                {{ valuesEtfListLoading ? '…' : '↻' }}
              </button>
            </div>
          </div>
          <div style="display:flex;gap:.5rem;align-items:flex-end">
            <div style="flex:1">
              <label class="label">From</label>
              <input class="input" type="date" v-model="valuesFromDate" />
            </div>
            <div style="flex:1">
              <label class="label">To</label>
              <input class="input" type="date" v-model="valuesToDate" />
            </div>
          </div>
        </div>

        <div style="display:flex;gap:.75rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap">
          <button class="btn btn-primary" @click="loadEtfValues" :disabled="!valuesEtfId || valuesLoading">
            {{ valuesLoading ? 'Loading…' : 'Load Data' }}
          </button>
          <button class="btn btn-outline" @click="downloadValuesCsv" :disabled="!valuesData || valuesData.length === 0">
            ⬇ Download CSV
          </button>
          <span v-if="valuesData" style="font-size:.85rem;color:var(--text-muted)">{{ valuesData.length }} row(s)</span>
        </div>

        <div v-if="valuesError" class="error-box" style="margin-bottom:.75rem">{{ valuesError }}</div>

        <div v-if="valuesData && valuesData.length > 0" class="log-table-wrap">
          <table class="log-table">
            <thead>
              <tr>
                <th>Date</th>
                <th style="text-align:right">Close Price</th>
                <th style="text-align:right">NAV</th>
                <th>Currency</th>
                <th style="text-align:right">Dividend</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in valuesData" :key="row.date">
                <td>{{ row.date }}</td>
                <td style="text-align:right;font-variant-numeric:tabular-nums">{{ row.close_price != null ? Number(row.close_price).toFixed(4) : '—' }}</td>
                <td style="text-align:right;font-variant-numeric:tabular-nums">{{ row.nav != null ? Number(row.nav).toFixed(4) : '—' }}</td>
                <td>{{ row.currency }}</td>
                <td style="text-align:right;font-variant-numeric:tabular-nums">{{ row.dividend != null ? Number(row.dividend).toFixed(4) : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else-if="valuesData && valuesData.length === 0" style="padding:1.5rem;text-align:center;color:var(--text-muted);font-size:.875rem">
          No performance data found for this ETF and date range.
        </div>
      </div>
    </template><!-- /etfvalues tab -->

  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { healthService, adminService, etfService } from '../services/api.js'

const setAdminActive = inject('setAdminActive')

// ─── Tab state ────────────────────────────────────────────────
const activeTab = ref('management')

function switchToValues() {
  activeTab.value = 'etfvalues'
  if (valuesEtfList.value.length === 0) loadValuesEtfList()
}

const apiKey = ref(localStorage.getItem('api_key') || '')
const showKey = ref(false)
const keySaved = ref(false)
const adminSecret = ref('')
const showAdmin = ref(false)
const adminVerified = ref(false)
const verifyLoading = ref(false)
const verifyError = ref('')

onMounted(() => {
  const saved = sessionStorage.getItem('admin_secret')
  if (saved) {
    adminSecret.value = saved
    verifySecret()
  }
})

const newKeyName = ref('my-key')
const newKeyRateLimit = ref(60)
const newKeyEmail = ref('')
const createLoading = ref(false)
const createError = ref('')
const createdKey = ref('')

const initLoading = ref(false)
const seedLoading = ref(false)
const resetLoading = ref(false)
const dbResult = ref('')
const dbError = ref('')

const importSymbol = ref('')
const importName = ref('')
const importTer = ref(null)
const importCsvFile = ref(null)
const importLoading = ref(false)
const importError = ref('')
const importResult = ref(null)
const importLogs = ref([])

const healthLoading = ref(false)
const healthResult = ref(null)

function saveKey() {
  localStorage.setItem('api_key', apiKey.value)
  // Update the api service dynamically
  window.__etfApiKey = apiKey.value
  keySaved.value = true
  setTimeout(() => keySaved.value = false, 3000)
}

function useAsApiKey() {
  apiKey.value = createdKey.value
  saveKey()
}

async function verifySecret() {
  verifyLoading.value = true; verifyError.value = ''
  try {
    await adminService.verify(adminSecret.value)
    sessionStorage.setItem('admin_secret', adminSecret.value)
    setAdminActive(true)
    adminVerified.value = true
    loadLogs(0)
  } catch(e) {
    adminVerified.value = false
    verifyError.value = e.response?.status === 403 ? 'Invalid admin secret.' : (e.response?.data?.detail || e.message)
  }
  finally { verifyLoading.value = false }
}

function logout() {
  sessionStorage.removeItem('admin_secret')
  setAdminActive(false)
  adminVerified.value = false
  adminSecret.value = ''
  logsData.value = null
}

async function createKey() {
  createLoading.value = true; createError.value = ''; createdKey.value = ''
  try {
    const r = await adminService.createApiKey(adminSecret.value, newKeyName.value, newKeyRateLimit.value, newKeyEmail.value || null)
    createdKey.value = r.data.api_key
  } catch(e) { createError.value = e.response?.data?.detail || e.message }
  finally { createLoading.value = false }
}

async function importETF() {
  importLoading.value = true; importError.value = ''; importResult.value = null; importLogs.value = []
  try {
    const r = await adminService.importETF(
      adminSecret.value,
      importSymbol.value.trim().toUpperCase(),
      importCsvFile.value || null,
      importName.value.trim() || null,
      importTer.value != null && importTer.value !== '' ? importTer.value : null,
    )
    importResult.value = r.data
    importLogs.value = r.data.logs || []
  } catch(e) {
    importError.value = e.response?.data?.detail || e.message
    importLogs.value = e.response?.data?.logs || []
  }
  finally { importLoading.value = false }
}

async function initDb() {
  initLoading.value = true; dbResult.value = ''; dbError.value = ''
  try { const r = await adminService.initDb(adminSecret.value); dbResult.value = r.data.message }
  catch(e) { dbError.value = e.response?.data?.detail || e.message }
  finally { initLoading.value = false }
}

async function seedDb() {
  seedLoading.value = true; dbResult.value = ''; dbError.value = ''
  try { const r = await adminService.seed(adminSecret.value); dbResult.value = `Seeded: ${JSON.stringify(r.data.seeded)}` }
  catch(e) { dbError.value = e.response?.data?.detail || e.message }
  finally { seedLoading.value = false }
}

async function confirmReset() {
  if (!confirm('This will DELETE all ETF data and reseed. Continue?')) return
  resetLoading.value = true; dbResult.value = ''; dbError.value = ''
  try { const r = await adminService.reset(adminSecret.value); dbResult.value = `Reset complete. Seeded: ${JSON.stringify(r.data.seeded)}` }
  catch(e) { dbError.value = e.response?.data?.detail || e.message }
  finally { resetLoading.value = false }
}

async function checkHealth() {
  healthLoading.value = true; healthResult.value = null
  try { const r = await healthService.checkHealth(); healthResult.value = r.data }
  catch(e) { console.error(e) }
  finally { healthLoading.value = false }
}

// ETF management
const etfList = ref([])
const selectedEtfIds = ref([])
const etfLoading = ref(false)
const etfError = ref('')
const deleteEtfLoading = ref(false)
const deleteEtfResult = ref('')
const deleteEtfError = ref('')

const allEtfsSelected = computed(
  () => etfList.value.length > 0 && selectedEtfIds.value.length === etfList.value.length
)

function toggleAllEtfs() {
  selectedEtfIds.value = allEtfsSelected.value ? [] : etfList.value.map(e => e.id)
}

async function loadETFs() {
  etfLoading.value = true; etfError.value = ''; etfList.value = []; selectedEtfIds.value = []
  try {
    const r = await etfService.getETFs(0, 200)
    etfList.value = r.data
  } catch(e) {
    etfError.value = e.response?.data?.detail || e.message
  } finally {
    etfLoading.value = false
  }
}

async function deleteSelectedEtfs() {
  if (!selectedEtfIds.value.length) return
  const names = etfList.value.filter(e => selectedEtfIds.value.includes(e.id)).map(e => e.ticker).join(', ')
  if (!confirm(`Delete ${selectedEtfIds.value.length} ETF(s): ${names}?\n\nThis removes all holdings and allocations.`)) return
  deleteEtfLoading.value = true; deleteEtfResult.value = ''; deleteEtfError.value = ''
  try {
    const r = await adminService.deleteETFs(adminSecret.value, selectedEtfIds.value)
    deleteEtfResult.value = `Deleted ${r.data.deleted} ETF(s).`
    selectedEtfIds.value = []
    await loadETFs()
  } catch(e) {
    deleteEtfError.value = e.response?.status === 403 ? 'Invalid admin secret.' : (e.response?.data?.detail || e.message)
  } finally {
    deleteEtfLoading.value = false
  }
}

// ─── ETF Values ───────────────────────────────────────────────
const valuesEtfList = ref([])
const valuesEtfListLoading = ref(false)
const valuesEtfId = ref('')
const valuesFromDate = ref('')
const valuesToDate = ref('')
const valuesLoading = ref(false)
const valuesError = ref('')
const valuesData = ref(null)

async function loadValuesEtfList() {
  valuesEtfListLoading.value = true
  try {
    const r = await etfService.getETFs(0, 200)
    valuesEtfList.value = r.data
  } catch (e) {
    console.error('Failed to load ETF list for values tab', e)
  } finally {
    valuesEtfListLoading.value = false
  }
}

async function loadEtfValues() {
  valuesLoading.value = true
  valuesError.value = ''
  valuesData.value = null
  try {
    const r = await etfService.getPerformance(
      valuesEtfId.value,
      valuesFromDate.value || null,
      valuesToDate.value || null
    )
    valuesData.value = r.data
  } catch (e) {
    valuesError.value = e.response?.data?.detail || e.message
  } finally {
    valuesLoading.value = false
  }
}

function downloadValuesCsv() {
  if (!valuesData.value || valuesData.value.length === 0) return
  const etf = valuesEtfList.value.find(e => e.id === valuesEtfId.value)
  const ticker = etf ? etf.ticker : 'etf'
  const header = ['date', 'close_price', 'nav', 'currency', 'dividend']
  const rows = valuesData.value.map(r => [
    r.date,
    r.close_price ?? '',
    r.nav ?? '',
    r.currency,
    r.dividend ?? ''
  ])
  const csv = [header, ...rows].map(row => row.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${ticker}_performance.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ─── Request Logs ─────────────────────────────────────────────
const logFilterName = ref('')
const logFilterEmail = ref('')
const logFilterPath = ref('')
const logsLoading = ref(false)
const logsError = ref('')
const logsData = ref(null)

async function loadLogs(offset = 0) {
  logsLoading.value = true; logsError.value = ''
  try {
    const r = await adminService.requestLogs(adminSecret.value, {
      limit: 50,
      offset,
      api_key_name: logFilterName.value,
      email: logFilterEmail.value,
      path: logFilterPath.value,
    })
    logsData.value = r.data
  } catch(e) {
    logsError.value = e.response?.data?.detail || e.message
  } finally {
    logsLoading.value = false
  }
}
</script>

<style scoped>
.tab-bar { display: flex; gap: 0; margin-bottom: 1.5rem; border-bottom: 2px solid var(--border); }
.tab-btn { background: none; border: none; border-bottom: 2px solid transparent; margin-bottom: -2px; padding: .6rem 1.25rem; font-size: .9rem; font-weight: 500; color: var(--text-muted); cursor: pointer; transition: color .15s, border-color .15s; border-radius: var(--radius-sm) var(--radius-sm) 0 0; }
.tab-btn:hover { color: var(--text); background: var(--bg-2); }
.tab-btn.active { color: var(--green-600); border-bottom-color: var(--green-600); }
[data-theme="dark"] .tab-btn.active { color: #4ade80; border-bottom-color: #4ade80; }
.key-row { display: flex; gap: .5rem; align-items: center; }
.key-row .input { flex: 1; }
.success-msg { background: var(--green-50); border: 1px solid var(--green-200); border-radius: var(--radius-sm); padding: .75rem 1rem; color: var(--green-700); font-size: .875rem; margin-top: .75rem; }
[data-theme="dark"] .success-msg { background: #052e16; border-color: #14532d; color: #86efac; }
.btn-danger { background: #dc2626; color: #fff; border: none; }
.btn-danger:hover { background: #b91c1c; }
.btn-danger:disabled { background: #fca5a5; cursor: not-allowed; }
.health-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr)); gap: 1rem; }
.disclaimer-card { background: var(--bg-3); border: 1px solid var(--green-200); border-radius: var(--radius); padding: 1.5rem; }
.disclaimer-card h3 { font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: .75rem; }
.disclaimer-card p { font-size: .875rem; color: var(--text-muted); line-height: 1.7; }
.etf-list { border: 1px solid var(--border); border-radius: var(--radius); max-height: 280px; overflow-y: auto; margin-bottom: .75rem; }
.etf-row { display: flex; align-items: center; gap: .75rem; padding: .5rem .75rem; border-bottom: 1px solid var(--border); }
.etf-row:last-child { border-bottom: none; }
.etf-row:hover { background: var(--bg-2); }
.etf-ticker { font-family: monospace; font-weight: 600; width: 70px; flex-shrink: 0; }
.etf-name { flex: 1; font-size: .875rem; }
.etf-provider { font-size: .8rem; color: var(--text-muted); width: 80px; text-align: right; flex-shrink: 0; }
.log-filters { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; }
.log-table-wrap { overflow-x: auto; margin-top: .5rem; border: 1px solid var(--border); border-radius: var(--radius); }
.log-table { width: 100%; border-collapse: collapse; font-size: .78rem; }
.log-table th { background: var(--bg-3); padding: .45rem .75rem; text-align: left; border-bottom: 1px solid var(--border); white-space: nowrap; font-weight: 600; color: var(--text-muted); }
.log-table td { padding: .4rem .75rem; border-bottom: 1px solid var(--border); vertical-align: top; }
.log-table tbody tr:hover { background: var(--bg-2); }
.log-table tbody tr:last-child td { border-bottom: none; }
.row-error td { background: #fef2f2; }
[data-theme="dark"] .row-error td { background: #2d0707; }
.td-time { white-space: nowrap; font-size: .74rem; color: var(--text-muted); }
.td-path { font-family: monospace; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-key { max-width: 140px; }
.td-detail { max-width: 160px; }
.method-GET { color: #2563eb; font-weight: 700; font-family: monospace; }
.method-POST { color: #16a34a; font-weight: 700; font-family: monospace; }
.method-DELETE { color: #dc2626; font-weight: 700; font-family: monospace; }
.method-PUT,.method-PATCH { color: #d97706; font-weight: 700; font-family: monospace; }
.cell-green { color: #16a34a; font-weight: 600; }
.cell-red { color: #dc2626; font-weight: 600; }
.log-meta { font-size: .8rem; color: var(--text-muted); }
.log-pagination { display: flex; align-items: center; gap: 1rem; margin-top: .75rem; font-size: .875rem; }
.detail-chip { display: inline-block; font-family: monospace; font-size: .72rem; background: var(--bg-3); border: 1px solid var(--border); border-radius: 4px; padding: 0 .4rem; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: middle; margin-right: .2rem; }
.body-chip { color: #7c3aed; cursor: help; }
</style>
