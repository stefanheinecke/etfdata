<template>
  <div :data-theme="theme">
    <!-- Navbar -->
    <nav class="navbar">
      <div class="nav-inner">
        <div class="nav-brand" @click="currentPage = 'home'">
          <span class="brand-icon">◈</span>
          <span class="brand-name">ETF Data</span>
        </div>
        <ul class="nav-links">
          <li v-for="item in navItems" :key="item.id">
            <button :class="['nav-btn', { active: currentPage === item.id || (item.id === 'etfs' && currentPage === 'etf-detail') }]" @click="currentPage = item.id">
              {{ item.label }}
            </button>
          </li>
        </ul>
        <div class="nav-actions">
          <div :class="['api-status', apiStatus]" :title="apiStatusText">
            <span class="status-dot"></span>{{ apiStatusText }}
          </div>
          <button class="theme-toggle" @click="toggleTheme" :title="theme === 'dark' ? 'Light mode' : 'Dark mode'">
            {{ theme === 'dark' ? '☀️' : '🌙' }}
          </button>
          <button class="btn-get-key" @click="showApiKeyModal = true">Get API Key</button>
          <button v-if="adminActive" class="nav-btn admin-btn" @click="currentPage = 'admin'">⚙ Admin</button>
        </div>
      </div>
    </nav>

    <!-- Main -->
    <main class="main">
      <Home v-if="currentPage === 'home'" @navigate="currentPage = $event" />
      <ETFList v-else-if="currentPage === 'etfs'" />
      <ETFDetail v-else-if="currentPage === 'etf-detail'" />
      <Analytics v-else-if="currentPage === 'analytics'" />
      <ApiDocs v-else-if="currentPage === 'docs'" />
      <Admin v-else-if="currentPage === 'admin' && adminActive" />
      <Home v-else-if="currentPage === 'admin' && !adminActive" @navigate="currentPage = $event" />
    </main>

    <!-- Disclaimer -->
    <div class="disclaimer-bar">
      ⚠ Disclaimer: ETF Data is for informational purposes only. Nothing on this platform constitutes financial or investment advice.
      Past performance is not indicative of future results. Always consult a qualified financial adviser before making investment decisions.
    </div>

    <!-- Footer -->
    <footer class="footer">
      <div class="footer-inner">
        <div class="footer-brand">
          <span class="brand-icon">◈</span>
          <strong>ETF Data</strong>
        </div>
        <div class="footer-links">
          <button @click="currentPage = 'home'">Home</button>
          <button @click="currentPage = 'etfs'">ETFs</button>
          <button @click="currentPage = 'analytics'">Analytics</button>
          <button @click="currentPage = 'docs'">API Docs</button>
          <button v-if="adminActive" @click="currentPage = 'admin'">Admin</button>
          <button v-else @click="showAdminLogin = true" class="admin-lock-btn" title="Admin login">🔒</button>
        </div>
        <p class="footer-copy">© {{ new Date().getFullYear() }} ETF Data. Not investment advice.</p>
      </div>
    </footer>
    <!-- Get API Key Modal -->
    <GetApiKeyModal :show="showApiKeyModal" @close="showApiKeyModal = false" />

    <!-- Admin Login Modal -->
    <Teleport to="body">
      <div v-if="showAdminLogin" class="modal-backdrop" @click.self="showAdminLogin = false">
        <div class="admin-login-modal">
          <h3 class="admin-login-title">🔐 Admin Login</h3>
          <p class="admin-login-sub">Enter your <code>ADMIN_SECRET</code> to continue.</p>
          <input
            :type="adminLoginShow ? 'text' : 'password'"
            v-model="adminLoginSecret"
            class="admin-login-input"
            placeholder="Admin secret…"
            @keydown.enter="doAdminLogin"
            autofocus
          />
          <div v-if="adminLoginError" class="admin-login-error">{{ adminLoginError }}</div>
          <div class="admin-login-actions">
            <button class="admin-login-toggle" @click="adminLoginShow = !adminLoginShow">{{ adminLoginShow ? 'Hide' : 'Show' }}</button>
            <button class="admin-login-cancel" @click="showAdminLogin = false">Cancel</button>
            <button class="admin-login-submit" @click="doAdminLogin" :disabled="!adminLoginSecret || adminLoginLoading">
              {{ adminLoginLoading ? 'Verifying…' : 'Log In' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, provide } from 'vue'
import { healthService, adminService } from './services/api.js'

const adminActive = ref(!!sessionStorage.getItem('admin_secret'))
function setAdminActive(val) {
  adminActive.value = val
  if (!val) sessionStorage.removeItem('admin_secret')
}
provide('setAdminActive', setAdminActive)

// Admin login modal state (in App.vue so non-admins never see the Admin page)
const showAdminLogin = ref(false)
const adminLoginSecret = ref('')
const adminLoginShow = ref(false)
const adminLoginLoading = ref(false)
const adminLoginError = ref('')

async function doAdminLogin() {
  if (!adminLoginSecret.value || adminLoginLoading.value) return
  adminLoginLoading.value = true; adminLoginError.value = ''
  try {
    await adminService.verify(adminLoginSecret.value)
    sessionStorage.setItem('admin_secret', adminLoginSecret.value)
    setAdminActive(true)
    showAdminLogin.value = false
    adminLoginSecret.value = ''
    currentPage.value = 'admin'
  } catch (e) {
    adminLoginError.value = e.response?.status === 403 ? 'Invalid admin secret.' : (e.response?.data?.detail || e.message)
  } finally {
    adminLoginLoading.value = false
  }
}
import Home from './pages/Home.vue'
import ETFList from './pages/ETFList.vue'
import ETFDetail from './pages/ETFDetail.vue'
import Analytics from './pages/Analytics.vue'
import ApiDocs from './pages/ApiDocs.vue'
import Admin from './pages/Admin.vue'
import GetApiKeyModal from './components/GetApiKeyModal.vue'

const currentPage = ref('home')
const theme = ref(localStorage.getItem('theme') || 'light')
const apiStatus = ref('checking')
const apiStatusText = ref('Checking...')
const showApiKeyModal = ref(false)
const hasApiKey = ref(!!localStorage.getItem('api_key'))

provide('showApiKeyModal', showApiKeyModal)

const selectedETF = ref(null)
provide('selectedETF', selectedETF)
provide('navigateToETF', (etf) => { selectedETF.value = etf; currentPage.value = 'etf-detail' })
provide('navigateTo', (page) => { currentPage.value = page })

// Reflect key changes from the modal's "Use this key" button
window.addEventListener('storage', (e) => {
  if (e.key === 'api_key') hasApiKey.value = !!e.newValue
})

const navItems = [
  { id: 'home', label: 'Home' },
  { id: 'etfs', label: 'ETFs' },
  { id: 'analytics', label: 'Analytics' },
  { id: 'docs', label: 'API Docs' },
]

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  localStorage.setItem('theme', theme.value)
  document.documentElement.setAttribute('data-theme', theme.value)
}

onMounted(async () => {
  document.documentElement.setAttribute('data-theme', theme.value)
  try {
    await healthService.checkHealth()
    apiStatus.value = 'online'
    apiStatusText.value = 'API Online'
  } catch {
    apiStatus.value = 'offline'
    apiStatusText.value = 'API Offline'
  }
})
</script>

<style>
/* Global resets already in index.html */
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  box-shadow: var(--shadow);
  backdrop-filter: blur(12px);
}
.nav-inner {
  max-width: 1280px; margin: 0 auto;
  padding: 0 1.5rem;
  display: flex; align-items: center; gap: 1rem;
  height: 64px;
}
.nav-brand {
  display: flex; align-items: center; gap: .5rem;
  cursor: pointer; text-decoration: none;
  flex-shrink: 0;
}
.brand-icon { font-size: 1.5rem; color: var(--green-500); }
.brand-name { font-size: 1.2rem; font-weight: 700; color: var(--text); letter-spacing: -.02em; }
.nav-links {
  display: flex; list-style: none; gap: .25rem;
  margin: 0 auto;
}
.nav-actions { display: flex; align-items: center; gap: .75rem; flex-shrink: 0; }
.btn-get-key {
  padding: .4rem 1rem; border-radius: 8px; font-size: .875rem; font-weight: 700;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff; border: none; cursor: pointer;
  box-shadow: 0 2px 8px rgba(102,126,234,.4);
  transition: opacity .15s, transform .1s;
  white-space: nowrap;
}
.btn-get-key:hover { opacity: .9; transform: translateY(-1px); }
.nav-btn {
  background: none; border: none; cursor: pointer;
  padding: .4rem .85rem; border-radius: 8px;
  font-size: .875rem; font-weight: 500; color: var(--text-muted);
  transition: all .15s; display: flex; align-items: center; gap: .35rem;
  font-family: inherit;
}
.nav-btn:hover { background: var(--bg-3); color: var(--green-600); }
.nav-btn.active { background: var(--green-100); color: var(--green-700); font-weight: 600; }
.admin-btn { border: 1px solid var(--border); color: var(--text-2); }
.admin-btn:hover { border-color: var(--green-400); color: var(--green-700); }
.theme-toggle {
  background: none; border: 1px solid var(--border); cursor: pointer;
  width: 36px; height: 36px; border-radius: 8px; font-size: 1rem;
  display: flex; align-items: center; justify-content: center;
  transition: all .15s;
}
.theme-toggle:hover { border-color: var(--green-400); background: var(--bg-3); }
.api-status {
  display: flex; align-items: center; gap: .4rem;
  font-size: .75rem; font-weight: 500; padding: .3rem .7rem;
  border-radius: 20px; border: 1px solid var(--border);
}
.api-status.online { color: var(--green-600); border-color: var(--green-200); background: var(--green-50); }
.api-status.offline { color: #dc2626; border-color: #fecaca; background: #fef2f2; }
.api-status.checking { color: var(--text-muted); }
.status-dot {
  width: 7px; height: 7px; border-radius: 50%; background: currentColor;
  animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
.main { flex: 1; }
.disclaimer-bar {
  background: #fefce8; border-top: 1px solid #fde68a; border-bottom: 1px solid #fde68a;
  color: #92400e; font-size: .8rem; padding: .6rem 1.5rem; text-align: center;
}
[data-theme="dark"] .disclaimer-bar {
  background: #1c1a00; border-color: #3d3500; color: #fde68a;
}
.footer {
  background: var(--surface); border-top: 1px solid var(--border);
  padding: 2rem 1.5rem;
}
.footer-inner {
  max-width: 1280px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between;
  gap: 1rem; flex-wrap: wrap;
}
.footer-brand { display: flex; align-items: center; gap: .4rem; font-size: 1rem; color: var(--text); }
.footer-links { display: flex; gap: .5rem; flex-wrap: wrap; }
.footer-links button {
  background: none; border: none; cursor: pointer; color: var(--text-muted);
  font-size: .875rem; padding: .25rem .5rem; border-radius: 6px;
  transition: color .15s; font-family: inherit;
}
.footer-links button:hover { color: var(--green-600); }
.footer-copy { font-size: .8rem; color: var(--text-muted); }
/* Admin lock icon button in footer */
.admin-lock-btn {
  background: none; border: none; cursor: pointer;
  font-size: .85rem; opacity: .25; padding: 0 .25rem;
  transition: opacity .2s;
}
.admin-lock-btn:hover { opacity: .6; }
/* Admin login modal */
.modal-backdrop {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,.5); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.admin-login-modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; padding: 2rem; width: 100%; max-width: 380px;
  box-shadow: 0 20px 60px rgba(0,0,0,.3);
}
.admin-login-title { font-size: 1.1rem; font-weight: 700; margin-bottom: .35rem; }
.admin-login-sub { font-size: .85rem; color: var(--text-muted); margin-bottom: 1rem; }
.admin-login-input {
  width: 100%; box-sizing: border-box;
  padding: .6rem .85rem; border: 1px solid var(--border);
  border-radius: 8px; font-size: .9rem; background: var(--bg-2);
  color: var(--text); font-family: inherit; margin-bottom: .5rem;
}
.admin-login-input:focus { outline: 2px solid var(--green-400); border-color: transparent; }
.admin-login-error { color: #dc2626; font-size: .82rem; margin-bottom: .5rem; }
.admin-login-actions { display: flex; gap: .5rem; justify-content: flex-end; margin-top: .75rem; }
.admin-login-toggle { background: none; border: 1px solid var(--border); border-radius: 7px; padding: .45rem .8rem; cursor: pointer; font-size: .82rem; color: var(--text-muted); font-family: inherit; }
.admin-login-cancel { background: none; border: 1px solid var(--border); border-radius: 7px; padding: .45rem .8rem; cursor: pointer; font-size: .85rem; color: var(--text-muted); font-family: inherit; }
.admin-login-cancel:hover { background: var(--bg-3); }
.admin-login-submit { background: linear-gradient(135deg,#667eea,#764ba2); color: #fff; border: none; border-radius: 7px; padding: .45rem 1.1rem; font-weight: 700; font-size: .875rem; cursor: pointer; font-family: inherit; }
.admin-login-submit:disabled { opacity: .5; cursor: not-allowed; }
.admin-login-submit:not(:disabled):hover { opacity: .9; }

/* Shared page styles */
.page { max-width: 1280px; margin: 0 auto; padding: 2rem 1.5rem; }
.page-header { margin-bottom: 2rem; }
.page-title { font-size: 1.75rem; font-weight: 700; color: var(--text); letter-spacing: -.03em; }
.page-subtitle { font-size: 1rem; color: var(--text-muted); margin-top: .35rem; }
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow);
  padding: 1.5rem;
}
.card-title { font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: 1rem; }
.btn {
  display: inline-flex; align-items: center; gap: .4rem;
  padding: .5rem 1.1rem; border-radius: 8px; border: none;
  font-size: .875rem; font-weight: 500; cursor: pointer;
  transition: all .15s; font-family: inherit;
}
.btn-primary {
  background: var(--green-500); color: #fff;
}
.btn-primary:hover { background: var(--green-600); }
.btn-primary:disabled { background: var(--green-200); cursor: not-allowed; }
.btn-outline {
  background: none; border: 1px solid var(--border); color: var(--text-2);
}
.btn-outline:hover { border-color: var(--green-400); color: var(--green-700); background: var(--bg-3); }
.badge {
  display: inline-block; padding: .2rem .55rem; border-radius: 20px;
  font-size: .75rem; font-weight: 500;
  background: var(--green-100); color: var(--green-700);
}
.input {
  width: 100%; padding: .55rem .85rem; border-radius: 8px;
  border: 1px solid var(--border); background: var(--bg);
  color: var(--text); font-size: .875rem; font-family: inherit;
  transition: border .15s;
}
.input:focus { outline: none; border-color: var(--green-400); box-shadow: 0 0 0 3px rgba(74,222,128,.15); }
.label { display: block; font-size: .8rem; font-weight: 500; color: var(--text-2); margin-bottom: .35rem; }
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px,1fr)); gap: 1.25rem; }
.grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px,1fr)); gap: 1.25rem; }
.grid-4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr)); gap: 1rem; }
.stat-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.25rem;
  box-shadow: var(--shadow);
}
.stat-label { font-size: .75rem; font-weight: 500; color: var(--text-muted); text-transform: uppercase; letter-spacing: .05em; }
.stat-value { font-size: 1.75rem; font-weight: 700; color: var(--text); margin-top: .25rem; letter-spacing: -.03em; }
.stat-sub { font-size: .8rem; color: var(--text-muted); margin-top: .2rem; }
.empty-state { text-align: center; padding: 4rem 2rem; color: var(--text-muted); }
.empty-icon { font-size: 3rem; margin-bottom: 1rem; }
.error-box {
  background: #fef2f2; border: 1px solid #fecaca; border-radius: var(--radius-sm);
  padding: .85rem 1rem; color: #dc2626; font-size: .875rem;
}
[data-theme="dark"] .error-box { background: #1f0a0a; border-color: #7f1d1d; color: #fca5a5; }
.loading { display: flex; align-items: center; gap: .5rem; color: var(--text-muted); padding: 2rem 0; }
.spinner {
  width: 20px; height: 20px; border: 2px solid var(--border);
  border-top-color: var(--green-500); border-radius: 50%;
  animation: spin .7s linear infinite; flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
.table-wrap { overflow-x: auto; border-radius: var(--radius-sm); border: 1px solid var(--border); }
table { width: 100%; border-collapse: collapse; font-size: .875rem; }
thead th {
  background: var(--bg-3); color: var(--text-2); font-weight: 600;
  padding: .75rem 1rem; text-align: left; border-bottom: 1px solid var(--border);
  font-size: .8rem; text-transform: uppercase; letter-spacing: .04em;
}
tbody tr { border-bottom: 1px solid var(--border); transition: background .1s; }
tbody tr:last-child { border-bottom: none; }
tbody tr:hover { background: var(--bg-3); }
tbody td { padding: .75rem 1rem; color: var(--text-2); }
code {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  background: var(--bg-3); border: 1px solid var(--border);
  padding: .15rem .4rem; border-radius: 4px; font-size: .85em; color: var(--green-700);
}
[data-theme="dark"] code { color: var(--green-400); }
pre {
  background: var(--bg-3); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 1.25rem;
  overflow-x: auto; font-size: .8rem; line-height: 1.7;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  color: var(--text-2);
}
</style>
