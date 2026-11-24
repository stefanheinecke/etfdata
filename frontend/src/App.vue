<template>
  <div :data-theme="theme">
    <nav v-if="currentPage !== 'home'" class="navbar" :class="{ scrolled: navScrolled }">
      <div class="nav-inner">
        <a href="#" class="logo" @click.prevent="goToPage('home')">{{ BRAND_PREFIX }}<span>ETF</span></a>
        <ul class="nav-links">
          <li><a href="#" :class="{ active: currentPage === 'etfs' || currentPage === 'etf-detail' }" @click.prevent="goToPage('etfs')">ETF Explorer</a></li>
          <li><a href="#" @click.prevent="goToPage('analytics', 'exposure')">Portfolio</a></li>
          <li><a href="#" :class="{ active: currentPage === 'scores' }" @click.prevent="goToPage('scores')">Scores</a></li>
          <li><a href="#" :class="{ active: currentPage === 'docs' }" @click.prevent="goToPage('docs')">API</a></li>
          <li><a href="#" :class="{ active: currentPage === 'methodology' }" @click.prevent="goToPage('methodology')">Methodology</a></li>
          <li v-if="isAdminApiUser"><a href="#" :class="{ active: currentPage === 'admin' }" @click.prevent="goToPage('admin')" style="color:#dc2626;font-weight:600">Admin</a></li>
        </ul>
        <a v-if="!hasAuth" href="#" class="btn btn-outline nav-cta" @click.prevent="openApiKeyModal()">Get API Key</a>
        <template v-else>
          <a v-if="!hasApiKey" href="#" class="btn btn-outline nav-cta" @click.prevent="openApiKeyModal()">Get API Key</a>
          <span class="api-online-pill"><span class="status-dot"></span><span v-if="currentUserEmail" class="user-email" :title="currentUserEmail">{{ currentUserEmail }}</span><span v-else>API Online</span></span>
          <button class="switch-key-btn" @click="logout" title="Log off">Log off</button>
        </template>
        <button class="hamburger" @click="mobileMenuOpen = true" aria-label="Open menu">
          <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>
        </button>
      </div>
    </nav>

    <div v-if="currentPage !== 'home'" class="nav-drawer" :class="{ open: mobileMenuOpen }">
      <div class="drawer-backdrop" @click="mobileMenuOpen = false"></div>
      <div class="drawer-panel">
        <a href="#" @click.prevent="goToPage('etfs')">ETF Explorer</a>
        <a href="#" @click.prevent="goToPage('analytics', 'exposure')">Portfolio</a>
        <a href="#" @click.prevent="goToPage('scores')">Scores</a>
        <a href="#" @click.prevent="goToPage('docs')">API</a>
        <a href="#" @click.prevent="goToPage('methodology')">Methodology</a>
        <a v-if="isAdminApiUser" href="#" @click.prevent="goToPage('admin'); mobileMenuOpen = false" style="color:#dc2626;font-weight:600">Admin</a>
        <a v-if="!hasApiKey" href="#" class="btn btn-primary" @click.prevent="openApiKeyModal(); mobileMenuOpen = false">Get API Key</a>
      </div>
    </div>

    <!-- Main -->
    <main class="main" :class="{ 'main-home': currentPage === 'home' }">
      <Home v-if="currentPage === 'home'" :key="pageRefreshKey" @navigate="currentPage = $event" />
      <ETFList v-else-if="currentPage === 'etfs'" :key="pageRefreshKey" />
      <ETFDetail v-else-if="currentPage === 'etf-detail'" :key="pageRefreshKey" />
      <Scores v-else-if="currentPage === 'scores'" :key="pageRefreshKey" />
      <Analytics v-else-if="currentPage === 'analytics'" :key="pageRefreshKey" />
      <Methodology v-else-if="currentPage === 'methodology'" />
      <ApiDocs v-else-if="currentPage === 'docs'" :key="pageRefreshKey" />
      <Admin v-else-if="currentPage === 'admin'" />

      <Home v-else />
    </main>

    <!-- Footer -->
    <footer v-if="currentPage !== 'home'" class="footer">
      <div class="container">
        <div class="footer-inner">
          <div class="footer-top">
            <div class="footer-brand">
              <div class="footer-logo">{{ BRAND_PREFIX }}<span>ETF</span></div>
              <p>ETF analysis for investors and developers. Not investment advice.</p>
            </div>
            <div class="footer-links">
              <div class="footer-col">
                <h4>Product</h4>
                <ul>
                  <li><a href="#" @click.prevent="goToPage('etfs')">ETF Explorer</a></li>
                  <li><a href="#" @click.prevent="goToPage('analytics', 'exposure')">Portfolio</a></li>
                  <li><a href="#" @click.prevent="goToPage('scores')">Scores</a></li>
                  <li><a href="#" @click.prevent="goToPage('methodology')">Methodology</a></li>
                </ul>
              </div>
              <div class="footer-col">
                <h4>Developers</h4>
                <ul>
                  <li><a href="#" @click.prevent="goToPage('docs')">API Docs</a></li>
                  <li v-if="!hasApiKey"><a href="#" @click.prevent="openApiKeyModal()">Get API Key</a></li>
                  <li><a href="#" @click.prevent="goToPage('docs')">Live Explorer</a></li>
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
            <p>© 2026 {{ BRAND.domain }} · Not investment advice · All data for informational purposes only.</p>
            <button class="footer-contact-link" type="button" @click="showContactModal = true"></button>
          </div>
        </div>
      </div>
    </footer>
    <!-- Get API Key Modal -->
    <GetApiKeyModal
      :show="showApiKeyModal"
      @close="onApiKeyModalClose"
      @google-authenticated="onGoogleAuthenticated"
      @email-confirmation-pending="startEmailConfirmationPolling"
    />

    <!-- Contact Modal -->
    <ContactModal :show="showContactModal" @close="showContactModal = false" />

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, provide } from 'vue'
import { healthService, authService } from './services/api.js'
import { BRAND, BRAND_PREFIX } from './brand.js'

import Home from './pages/Home.vue'
import ETFList from './pages/ETFList.vue'
import ETFDetail from './pages/ETFDetail.vue'
import Scores from './pages/Scores.vue'
import Analytics from './pages/Analytics.vue'
import ApiDocs from './pages/ApiDocs.vue'
import Methodology from './pages/Methodology.vue'
import Admin from './pages/Admin.vue'
import GetApiKeyModal from './components/GetApiKeyModal.vue'
import ContactModal from './components/ContactModal.vue'

const showContactModal = ref(false)

const currentPage = ref('home')
const theme = ref('light')
const navScrolled = ref(false)
const apiStatus = ref('checking')
const apiStatusText = ref('Checking...')
const showApiKeyModal = ref(false)
const mobileMenuOpen = ref(false)
const hasApiKey = ref(!!localStorage.getItem('api_key'))
const hasWebSession = ref(false)
const hasAuth = computed(() => hasApiKey.value || hasWebSession.value)
const currentUserEmail = ref('')
const isAdminApiUser = ref(false)
const pageRefreshKey = ref(0)
let emailConfirmationPollTimer = null
let checkingEmailConfirmation = false

function openApiKeyModal() {
  showApiKeyModal.value = true
}

provide('showApiKeyModal', showApiKeyModal)
provide('hasAuth', hasAuth)

const portfolioInit = ref(null)
provide('portfolioInit', portfolioInit)
const selectedETF = ref(null)
provide('selectedETF', selectedETF)
provide('navigateToDetail', (etf) => {
  selectedETF.value = etf
  currentPage.value = 'etf-detail'
  window.scrollTo({ top: 0, behavior: 'auto' })
})
provide('navigateToETF', (etf) => {
  portfolioInit.value = { etf_id: etf.id, weight: 100 }
  currentPage.value = 'analytics'
  window.scrollTo({ top: 0, behavior: 'auto' })
})
const analyticsInitTab = ref(null)
provide('analyticsInitTab', analyticsInitTab)
provide('navigateToPortfolio', (etfs) => {
  const ids = [...new Set(etfs.map(etf => etf.id).filter(Boolean))]
  if (!ids.length) return
  const base = Math.floor(10000 / ids.length)
  const remainder = 10000 % ids.length
  portfolioInit.value = ids.map((id, index) => ({
    etf_id: id,
    weight: (base + (index < remainder ? 1 : 0)) / 100,
  }))
  goToPage('analytics', 'exposure')
})
provide('navigateTo', (page, tab) => { goToPage(page, tab) })

function goToPage(page, tab = null) {
  if (page === 'admin' && !isAdminApiUser.value) return
  currentPage.value = page
  if (tab) analyticsInitTab.value = tab
  mobileMenuOpen.value = false
  window.scrollTo({ top: 0, behavior: 'auto' })
}

function onGoogleAuthenticated(user) {
  const nextHasApiKey = !!user.has_api_key || !!localStorage.getItem('api_key')
  const nextEmail = user.email || ''
  const nextIsAdmin = !!user.is_admin
  const changed = (
    !hasWebSession.value
    || hasApiKey.value !== nextHasApiKey
    || currentUserEmail.value !== nextEmail
    || isAdminApiUser.value !== nextIsAdmin
  )

  hasWebSession.value = true
  hasApiKey.value = nextHasApiKey
  currentUserEmail.value = nextEmail
  isAdminApiUser.value = nextIsAdmin
  if (changed) pageRefreshKey.value += 1
}

async function onApiKeyModalClose() {
  showApiKeyModal.value = false
  try {
    const { data } = await authService.session()
    onGoogleAuthenticated(data)
  } catch (e) {
    if (e.response?.status !== 401) {
      console.error('Could not refresh browser session after closing the sign-in dialog:', e)
    }
  }
}

function stopEmailConfirmationPolling() {
  if (emailConfirmationPollTimer) {
    window.clearInterval(emailConfirmationPollTimer)
    emailConfirmationPollTimer = null
  }
}

async function checkEmailConfirmation() {
  if (checkingEmailConfirmation) return
  checkingEmailConfirmation = true
  try {
    const { data } = await authService.emailStatus()
    if (data.authenticated) {
      stopEmailConfirmationPolling()
      onGoogleAuthenticated(data)
      showApiKeyModal.value = false
    } else if (!data.pending) {
      stopEmailConfirmationPolling()
    }
  } catch (e) {
    console.error('Could not check email confirmation status:', e)
    stopEmailConfirmationPolling()
  } finally {
    checkingEmailConfirmation = false
  }
}

function startEmailConfirmationPolling() {
  if (emailConfirmationPollTimer) return
  emailConfirmationPollTimer = window.setInterval(checkEmailConfirmation, 3000)
  checkEmailConfirmation()
}

async function logout() {
  try {
    await authService.logout()
  } catch (e) {
    console.error('Could not sign out:', e)
    window.alert('Sign-out failed. Please try again.')
    return
  }
  localStorage.removeItem('api_key')
  sessionStorage.removeItem('admin_secret')
  hasApiKey.value = false
  hasWebSession.value = false
  currentUserEmail.value = ''
  isAdminApiUser.value = false
  goToPage('home')
  openApiKeyModal()
}

// Reflect key changes from the modal's "Use this key" button
window.addEventListener('storage', (e) => {
  if (e.key === 'api_key') hasApiKey.value = !!e.newValue
})

function onScroll() {
  navScrolled.value = window.scrollY > 20
}

function onAdminShortcut(e) {
  if (e.ctrlKey && e.shiftKey && e.key === 'A') goToPage('admin')
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
    currentPage.value = 'scores'
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
  sessionStorage.removeItem('admin_secret')
  applyPathRoute(window.location.pathname)
  window.addEventListener('popstate', onPopState)
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('keydown', onAdminShortcut)
  document.documentElement.setAttribute('data-theme', 'light')
  try {
    await healthService.checkHealth()
    apiStatus.value = 'online'
    apiStatusText.value = 'API Online'
  } catch {
    apiStatus.value = 'offline'
    apiStatusText.value = 'API Offline'
  }
  if (hasApiKey.value) {
    try {
      const res = await authService.me()
      currentUserEmail.value = res.data.email || ''
      isAdminApiUser.value = !!res.data.is_admin
    } catch { /* key may be invalid — silently ignore */ }
  }
  try {
    const res = await authService.session()
    hasWebSession.value = true
    hasApiKey.value = !!res.data.has_api_key || !!localStorage.getItem('api_key')
    currentUserEmail.value = res.data.email || ''
    isAdminApiUser.value = !!res.data.is_admin
  } catch (e) {
    if (e.response?.status !== 401) {
      console.error('Could not restore browser session:', e)
    }
  }
  startEmailConfirmationPolling()
})

onUnmounted(() => {
  stopEmailConfirmationPolling()
  window.removeEventListener('popstate', onPopState)
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('keydown', onAdminShortcut)
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
.api-online-pill {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: .8rem;
  font-weight: 600;
  color: #0a3a66;
  background: rgba(0, 201, 167, .14);
  border: 1px solid rgba(0, 201, 167, .3);
}
.user-email {
  max-width: min(320px, 30vw);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.switch-key-btn {
  margin-left: 6px;
  background: #dc2626;
  border: 1px solid #dc2626;
  border-radius: 7px;
  font-size: .8rem;
  font-weight: 600;
  color: #fff;
  cursor: pointer;
  padding: 7px 11px;
  white-space: nowrap;
}
.switch-key-btn:hover { background: #b91c1c; border-color: #b91c1c; }
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #16a34a;
}
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
.footer-contact-link { background: none; border: none; padding: 0; cursor: pointer; font-family: inherit; color: rgba(255,255,255,.4); font-size: .78rem; }
.footer-contact-link:hover { color: rgba(255,255,255,.7); }

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
  .api-online-pill { display: none; }
  .nav-inner { padding: 0 16px; gap: .5rem; }
  .page { padding: 1.25rem 16px; }
  .admin-login-modal { width: calc(100% - 2rem); padding: 1.5rem; }
  .footer-top { flex-direction: column; gap: 24px; }
  .footer-links { gap: 24px; }
  .page-title { font-size: 1.4rem; }
  pre { font-size: .75rem; padding: 1rem; }
}
</style>
