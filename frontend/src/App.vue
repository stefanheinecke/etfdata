<template>
  <div :data-theme="theme">
    <nav v-if="currentPage !== 'home'" class="navbar" :class="{ scrolled: navScrolled }">
      <div class="nav-inner">
        <a href="#" class="logo" @click.prevent="goToPage('home')">Go<span>ETF</span></a>
        <ul class="nav-links">
          <li><a href="#" :class="{ active: currentPage === 'etfs' || currentPage === 'etf-detail' }" @click.prevent="goToPage('etfs')">ETF Explorer</a></li>
          <li><a href="#" :class="{ active: currentPage === 'analytics' }" @click.prevent="goToPage('analytics', 'goetf')">Scores</a></li>
          <li><a href="#" @click.prevent="goToPage('analytics', 'exposure')">Portfolio</a></li>
          <li><a href="#" :class="{ active: currentPage === 'docs' }" @click.prevent="goToPage('docs')">API</a></li>
          <li><a href="#" :class="{ active: currentPage === 'methodology' }" @click.prevent="goToPage('methodology')">Methodology</a></li>
        </ul>
        <a href="#" class="btn btn-outline nav-cta" @click.prevent="openApiKeyModal('request')">Get API Key</a>
        <button class="hamburger" @click="mobileMenuOpen = true" aria-label="Open menu">
          <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>
        </button>
      </div>
    </nav>

    <div v-if="currentPage !== 'home'" class="nav-drawer" :class="{ open: mobileMenuOpen }">
      <div class="drawer-backdrop" @click="mobileMenuOpen = false"></div>
      <div class="drawer-panel">
        <a href="#" @click.prevent="goToPage('etfs')">ETF Explorer</a>
        <a href="#" @click.prevent="goToPage('analytics', 'goetf')">Scores</a>
        <a href="#" @click.prevent="goToPage('analytics', 'exposure')">Portfolio</a>
        <a href="#" @click.prevent="goToPage('docs')">API</a>
        <a href="#" @click.prevent="goToPage('methodology')">Methodology</a>
        <a href="#" class="btn btn-primary" @click.prevent="openApiKeyModal('request'); mobileMenuOpen = false">Get API Key</a>
      </div>
    </div>

    <!-- Main -->
    <main class="main" :class="{ 'main-home': currentPage === 'home' }">
      <Home v-if="currentPage === 'home'" @navigate="currentPage = $event" />
      <ETFList v-else-if="currentPage === 'etfs'" />
      <ETFDetail v-else-if="currentPage === 'etf-detail'" />
      <Analytics v-else-if="currentPage === 'analytics'" />
      <Methodology v-else-if="currentPage === 'methodology'" />
      <ApiDocs v-else-if="currentPage === 'docs'" />
      <Admin v-else-if="currentPage === 'admin' && adminActive" />
      <Home v-else-if="currentPage === 'admin' && !adminActive" @navigate="currentPage = $event" />
    </main>

    <!-- Footer -->
    <footer v-if="currentPage !== 'home'" class="footer">
      <div class="container">
        <div class="footer-inner">
          <div class="footer-top">
            <div class="footer-brand">
              <div class="footer-logo">Go<span>ETF</span></div>
              <p>ETF analysis for investors and developers. Not investment advice.</p>
            </div>
            <div class="footer-links">
              <div class="footer-col">
                <h4>Product</h4>
                <ul>
                  <li><a href="#" @click.prevent="currentPage = 'etfs'">ETF Explorer</a></li>
                  <li><a href="#" @click.prevent="navigateTo('analytics', 'goetf')">Scores</a></li>
                  <li><a href="#" @click.prevent="navigateTo('analytics', 'exposure')">Portfolio</a></li>
                  <li><a href="#" @click.prevent="currentPage = 'methodology'">Methodology</a></li>
                </ul>
              </div>
              <div class="footer-col">
                <h4>Developers</h4>
                <ul>
                  <li><a href="#" @click.prevent="currentPage = 'docs'">API Docs</a></li>
                  <li><a href="#" @click.prevent="openApiKeyModal('request')">Get API Key</a></li>
                  <li><a href="#" @click.prevent="currentPage = 'docs'">Live Explorer</a></li>
                </ul>
              </div>
              <div class="footer-col">
                <h4>Legal</h4>
                <ul>
                  <li><a href="#" @click.prevent>Imprint</a></li>
                  <li><a href="#" @click.prevent>Disclaimer</a></li>
                  <li><a href="#" @click.prevent>Privacy</a></li>
                </ul>
              </div>
            </div>
          </div>
          <div class="footer-bottom">
            <p>© 2026 GoETF.ch · Not investment advice · All data for informational purposes only.</p>
            <a href="mailto:info@goetf.ch">info@goetf.ch</a>
          </div>
        </div>
      </div>
    </footer>
    <!-- Get API Key Modal -->
    <GetApiKeyModal :show="showApiKeyModal" :initialTab="apiKeyModalTab" @close="showApiKeyModal = false" @key-saved="hasApiKey = true" />

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
import { ref, onMounted, onUnmounted, provide } from 'vue'
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
import Methodology from './pages/Methodology.vue'
import Admin from './pages/Admin.vue'
import GetApiKeyModal from './components/GetApiKeyModal.vue'

const currentPage = ref('home')
const theme = ref('light')
const navScrolled = ref(false)
const apiStatus = ref('checking')
const apiStatusText = ref('Checking...')
const showApiKeyModal = ref(false)
const apiKeyModalTab = ref('request')
const mobileMenuOpen = ref(false)
const hasApiKey = ref(!!localStorage.getItem('api_key'))

function openApiKeyModal(tab = 'request') {
  apiKeyModalTab.value = tab
  showApiKeyModal.value = true
}

provide('showApiKeyModal', showApiKeyModal)

const selectedETF = ref(null)
provide('selectedETF', selectedETF)
provide('navigateToETF', (etf) => { selectedETF.value = etf; currentPage.value = 'etf-detail' })
const analyticsInitTab = ref(null)
provide('analyticsInitTab', analyticsInitTab)
provide('navigateTo', (page, tab) => { currentPage.value = page; if (tab) analyticsInitTab.value = tab })

function goToPage(page, tab = null) {
  currentPage.value = page
  if (tab) analyticsInitTab.value = tab
  mobileMenuOpen.value = false
  window.scrollTo({ top: 0, behavior: 'auto' })
}

// Reflect key changes from the modal's "Use this key" button
window.addEventListener('storage', (e) => {
  if (e.key === 'api_key') hasApiKey.value = !!e.newValue
})

function onScroll() {
  navScrolled.value = window.scrollY > 20
}

function applyPathRoute(pathname = window.location.pathname) {
  const path = (pathname || '/').toLowerCase()
  if (path === '/' || path === '/index.html') {
    currentPage.value = 'home'
    return
  }
  if (path === '/etfs') {
    currentPage.value = 'etfs'
    return
  }
  if (path === '/scores') {
    currentPage.value = 'analytics'
    analyticsInitTab.value = 'goetf'
    return
  }
  if (path === '/portfolio' || path === '/portfolio/simplifier' || path === '/portfolio/enhancer') {
    currentPage.value = 'analytics'
    analyticsInitTab.value = 'exposure'
    return
  }
  if (path === '/api' || path === '/api/explorer') {
    currentPage.value = 'docs'
    return
  }
  if (path === '/methodology') {
    currentPage.value = 'methodology'
    return
  }
  if (path === '/api-key') {
    currentPage.value = 'home'
    showApiKeyModal.value = true
    return
  }
  currentPage.value = 'home'
}

function onPopState() {
  applyPathRoute(window.location.pathname)
}

onMounted(async () => {
  applyPathRoute(window.location.pathname)
  window.addEventListener('popstate', onPopState)
  window.addEventListener('scroll', onScroll, { passive: true })
  document.documentElement.setAttribute('data-theme', 'light')
  try {
    await healthService.checkHealth()
    apiStatus.value = 'online'
    apiStatusText.value = 'API Online'
  } catch {
    apiStatus.value = 'offline'
    apiStatusText.value = 'API Offline'
  }
})

onUnmounted(() => {
  window.removeEventListener('popstate', onPopState)
  window.removeEventListener('scroll', onScroll)
})
</script>

<style>
.navbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: rgba(248,249,251,.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid transparent;
  transition: border-color .2s, background .2s;
}
.navbar.scrolled {
  border-color: var(--border);
  background: rgba(248,249,251,.97);
}
.nav-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  height: 60px;
  display: flex;
  align-items: center;
  gap: 32px;
}
.logo {
  font-size: 1.2rem;
  font-weight: 700;
  font-family: var(--font);
  color: #0f4c81;
  letter-spacing: -.03em;
  margin-right: 8px;
  text-decoration: none;
}
.logo span { color: #00c9a7; }
.nav-links { display: flex; gap: 4px; flex: 1; list-style: none; }
.nav-links a {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: .88rem;
  font-weight: 500;
  color: var(--text-muted);
  transition: all .15s;
  text-decoration: none;
}
.nav-links a:hover { color: #0f4c81; background: rgba(15,76,129,.06); }
.nav-links a.active { color: #0f4c81; }
.nav-cta { margin-left: auto; }
.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 11px 24px;
  border-radius: 8px;
  font-size: .9rem;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all .18s ease;
  white-space: nowrap;
}
.btn-primary { background: #0f4c81; color: #fff; }
.btn-primary:hover { background: #1a6ab8; transform: translateY(-1px); box-shadow: 0 4px 16px rgba(15,76,129,.25); }
.btn-outline { background: transparent; color: #0f4c81; border: 1.5px solid #0f4c81; }
.btn-outline:hover { background: #0f4c81; color: #fff; transform: translateY(-1px); }
.hamburger { display: none; background: none; border: none; cursor: pointer; padding: 6px; color: var(--text); }
.hamburger svg { width: 22px; height: 22px; }

.nav-drawer { position: fixed; inset: 0; z-index: 99; display: none; }
.nav-drawer.open { display: flex; }
.drawer-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,.4); }
.drawer-panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 280px;
  background: #fff;
  padding: 80px 28px 28px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: -4px 0 32px rgba(0,0,0,.15);
}
.drawer-panel a {
  padding: 12px 8px;
  font-size: 1rem;
  font-weight: 500;
  color: var(--text);
  border-bottom: 1px solid var(--border);
  text-decoration: none;
}
.drawer-panel .btn { margin-top: 16px; justify-content: center; }

.main {
  flex: 1;
  padding-top: 60px;
}
.main.main-home {
  padding-top: 0;
}
.footer { background: #0a0f1a; padding: 48px 0 32px; }
.container { max-width: 1200px; margin: 0 auto; padding: 0 24px; }
.footer-inner { display: flex; flex-direction: column; gap: 32px; }
.footer-top { display: flex; gap: 64px; align-items: flex-start; }
.footer-brand { flex-shrink: 0; }
.footer-logo { font-size: 1.25rem; font-weight: 700; font-family: var(--font); color: #fff; letter-spacing: -.03em; margin-bottom: 8px; }
.footer-logo span { color: #00c9a7; }
.footer-brand p { color: rgba(255,255,255,.4); font-size: .82rem; max-width: 220px; }
.footer-links { display: flex; gap: 40px; flex-wrap: wrap; flex: 1; }
.footer-col h4 { font-size: .8rem; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: rgba(255,255,255,.35); margin-bottom: 14px; }
.footer-col ul { display: flex; flex-direction: column; gap: 10px; list-style: none; }
.footer-col a { color: rgba(255,255,255,.55); font-size: .85rem; transition: color .15s; text-decoration: none; }
.footer-col a:hover { color: #fff; }
.footer-bottom {
  border-top: 1px solid rgba(255,255,255,.07);
  padding-top: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.footer-bottom p { font-size: .78rem; color: rgba(255,255,255,.3); }
.footer-bottom a { color: rgba(255,255,255,.4); font-size: .78rem; text-decoration: none; }
.footer-bottom a:hover { color: rgba(255,255,255,.7); }

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
.page { max-width: 1200px; margin: 0 auto; padding: 2rem 24px; }
.page-header { margin-bottom: 2.2rem; }
.page-title {
  font-size: clamp(1.6rem, 3vw, 2.2rem);
  font-weight: 700;
  color: var(--text);
  letter-spacing: -.02em;
  line-height: 1.2;
}
.page-subtitle {
  font-size: .98rem;
  color: var(--text-muted);
  margin-top: .35rem;
  line-height: 1.65;
  max-width: 760px;
}
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; box-shadow: var(--shadow);
  padding: 1.5rem;
}
.card-title { font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: 1rem; }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.badge {
  display: inline-block; padding: .2rem .55rem; border-radius: 20px;
  font-size: .75rem; font-weight: 500;
  background: rgba(15,76,129,.1); color: #0f4c81;
}
.input {
  width: 100%; padding: .55rem .85rem; border-radius: 8px;
  border: 1px solid var(--border); background: var(--bg);
  color: var(--text); font-size: .875rem; font-family: inherit;
  transition: border .15s;
}
.input:focus { outline: none; border-color: #1a6ab8; box-shadow: 0 0 0 3px rgba(26,106,184,.15); }
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
  border-top-color: #0f4c81; border-radius: 50%;
  animation: spin .7s linear infinite; flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
.table-wrap { overflow-x: auto; border-radius: var(--radius-sm); border: 1px solid var(--border); }
table { width: 100%; border-collapse: collapse; font-size: .84rem; }
thead th {
  background: var(--bg-3); color: var(--text-2); font-weight: 600;
  padding: .72rem .95rem; text-align: left; border-bottom: 1px solid var(--border);
  font-size: .74rem; text-transform: uppercase; letter-spacing: .06em;
}
tbody tr { border-bottom: 1px solid var(--border); transition: background .1s; }
tbody tr:last-child { border-bottom: none; }
tbody tr:hover { background: var(--bg-3); }
tbody td { padding: .72rem .95rem; color: var(--text-2); }
code {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  background: var(--bg-3); border: 1px solid var(--border);
  padding: .15rem .4rem; border-radius: 4px; font-size: .85em; color: #0f4c81;
}
[data-theme="dark"] code { color: #9be7d8; }
pre {
  background: var(--bg-3); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 1.25rem;
  overflow-x: auto; font-size: .8rem; line-height: 1.7;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  color: var(--text-2);
}

/* ── Responsive breakpoints ── */
@media (max-width: 640px) {
  .hamburger { display: flex; }
  .nav-links, .nav-cta { display: none; }
  .nav-inner { padding: 0 16px; gap: .5rem; }
  .page { padding: 1.25rem 16px; }
  .admin-login-modal { width: calc(100% - 2rem); padding: 1.5rem; }
  .footer-top { flex-direction: column; gap: 24px; }
  .footer-links { gap: 24px; }
  .page-title { font-size: 1.4rem; }
  pre { font-size: .75rem; padding: 1rem; }
}
</style>
