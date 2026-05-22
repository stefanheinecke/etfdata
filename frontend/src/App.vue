<template>
  <div id="app">
    <nav class="navbar">
      <div class="nav-container">
        <h1 class="logo">ETF Analytics</h1>
        <ul class="nav-menu">
          <li><a href="#/" :class="{ active: currentPage === 'list' }" @click.prevent="currentPage = 'list'">ETFs</a></li>
          <li><a href="#/" :class="{ active: currentPage === 'analytics' }" @click.prevent="currentPage = 'analytics'">Analytics</a></li>
          <li><a href="#/" :class="{ active: currentPage === 'settings' }" @click.prevent="currentPage = 'settings'">Settings</a></li>
        </ul>
      </div>
    </nav>

    <main class="container">
      <ETFList v-if="currentPage === 'list'" />
      <Analytics v-if="currentPage === 'analytics'" />
      <Settings v-if="currentPage === 'settings'" />
    </main>

    <footer class="footer">
      <p>&copy; 2024 ETF Analytics API. Public data only - no investment advice.</p>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { healthService } from './services/api.js'
import ETFList from './pages/ETFList.vue'
import Analytics from './pages/Analytics.vue'
import Settings from './pages/Settings.vue'

const currentPage = ref('list')

onMounted(async () => {
  try {
    const response = await healthService.checkHealth()
    console.log('✓ API Health:', response.data)
  } catch (error) {
    console.error('✗ API Error:', error.message)
  }
})
</script>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background: #f5f5f5;
  color: #333;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.navbar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.nav-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.logo {
  font-size: 1.5rem;
  font-weight: bold;
}

.nav-menu {
  display: flex;
  list-style: none;
  gap: 2rem;
}

.nav-menu a {
  color: white;
  text-decoration: none;
  cursor: pointer;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.nav-menu a:hover,
.nav-menu a.active {
  background-color: rgba(255,255,255,0.2);
}

.container {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 2rem;
}

.footer {
  background: #333;
  color: white;
  text-align: center;
  padding: 2rem;
  margin-top: 2rem;
}

@media (max-width: 768px) {
  .nav-container {
    flex-direction: column;
    gap: 1rem;
  }

  .nav-menu {
    gap: 1rem;
  }

  .container {
    padding: 1rem;
  }
}
</style>
