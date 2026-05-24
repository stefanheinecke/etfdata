<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">Admin</h1>
      <p class="page-subtitle">Manage API keys, seed data and configure your connection settings.</p>
    </div>

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
        Enter your <code>ADMIN_SECRET</code> from Railway to use admin operations below.
        This is never stored — only used for the current session.
      </p>
      <label class="label">Admin Secret</label>
      <div class="key-row">
        <input :type="showAdmin ? 'text' : 'password'" class="input" v-model="adminSecret" placeholder="Your ADMIN_SECRET..." />
        <button class="btn btn-outline" @click="showAdmin=!showAdmin">{{ showAdmin ? 'Hide' : 'Show' }}</button>
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
        <button class="btn btn-primary" @click="createKey" :disabled="!adminSecret || !newKeyName || createLoading">
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
            <button class="btn btn-outline" style="width:100%" @click="initDb" :disabled="!adminSecret || initLoading">
              {{ initLoading ? 'Running...' : '⚡ Init DB (create tables)' }}
            </button>
            <p style="font-size:.75rem;color:var(--text-muted);margin-top:.3rem">Creates missing tables without deleting data.</p>
          </div>
          <div>
            <button class="btn btn-outline" style="width:100%" @click="seedDb" :disabled="!adminSecret || seedLoading">
              {{ seedLoading ? 'Seeding...' : '🌱 Seed (add missing data)' }}
            </button>
            <p style="font-size:.75rem;color:var(--text-muted);margin-top:.3rem">Inserts sample ETFs and holdings if not already present.</p>
          </div>
          <div>
            <button class="btn btn-danger" style="width:100%" @click="confirmReset" :disabled="!adminSecret || resetLoading">
              {{ resetLoading ? 'Resetting...' : '🗑 Reset & Reseed (wipes all ETF data)' }}
            </button>
            <p style="font-size:.75rem;color:var(--text-muted);margin-top:.3rem">Deletes all ETF data and reseeds fresh sample data.</p>
          </div>
        </div>
        <div v-if="dbResult" class="success-msg" style="margin-top:.75rem">{{ dbResult }}</div>
        <div v-if="dbError" class="error-box" style="margin-top:.75rem">{{ dbError }}</div>
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

    <!-- Disclaimer -->
    <div class="disclaimer-card" style="margin-top:1.5rem">
      <h3>📋 Admin Disclaimer</h3>
      <p>
        Admin operations directly modify the production database. The Reset operation permanently deletes all ETF data.
        ETF Data is for <strong>informational purposes only</strong> — none of the data constitutes investment advice.
        Do not use real financial data without appropriate licensing and compliance review.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { healthService, adminService } from '../services/api.js'

const apiKey = ref(localStorage.getItem('api_key') || '')
const showKey = ref(false)
const keySaved = ref(false)
const adminSecret = ref('')
const showAdmin = ref(false)

const newKeyName = ref('my-key')
const newKeyRateLimit = ref(60)
const createLoading = ref(false)
const createError = ref('')
const createdKey = ref('')

const initLoading = ref(false)
const seedLoading = ref(false)
const resetLoading = ref(false)
const dbResult = ref('')
const dbError = ref('')

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

async function createKey() {
  createLoading.value = true; createError.value = ''; createdKey.value = ''
  try {
    const r = await adminService.createApiKey(adminSecret.value, newKeyName.value, newKeyRateLimit.value)
    createdKey.value = r.data.api_key
  } catch(e) { createError.value = e.response?.data?.detail || e.message }
  finally { createLoading.value = false }
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
</script>

<style scoped>
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
</style>
