<template>
  <div class="etf-list">
    <h2>ETF Database</h2>

    <div class="filters">
      <input v-model="searchTicker" type="text" placeholder="Filter by ticker..." class="input">
      <select v-model="selectedProvider" class="input">
        <option value="">All Providers</option>
        <option value="Vanguard">Vanguard</option>
        <option value="iShares">iShares</option>
        <option value="UBS">UBS</option>
      </select>
      <button @click="loadETFs" class="btn btn-primary">Load</button>
    </div>

    <div v-if="loading" class="loading">Loading ETFs...</div>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="table-container">
      <table class="table">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>ISIN</th>
            <th>Name</th>
            <th>Provider</th>
            <th>TER</th>
            <th>Fund Size (€)</th>
            <th>Currency</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="etf in filteredETFs" :key="etf.id" class="table-row">
            <td class="ticker">{{ etf.ticker }}</td>
            <td class="isin">{{ etf.isin }}</td>
            <td class="name">{{ etf.name }}</td>
            <td>{{ etf.provider }}</td>
            <td>{{ etf.ter ? etf.ter + '%' : 'N/A' }}</td>
            <td>{{ formatCurrency(etf.fund_size) }}</td>
            <td>{{ etf.currency }}</td>
            <td>
              <button @click="selectETF(etf)" class="btn btn-small btn-info">Details</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="selectedETF" class="detail-panel">
      <h3>{{ selectedETF.name }}</h3>
      <div class="detail-grid">
        <div class="detail-item">
          <strong>ISIN:</strong> {{ selectedETF.isin }}
        </div>
        <div class="detail-item">
          <strong>Provider:</strong> {{ selectedETF.provider }}
        </div>
        <div class="detail-item">
          <strong>Replication:</strong> {{ selectedETF.replication_method }}
        </div>
        <div class="detail-item">
          <strong>Benchmark:</strong> {{ selectedETF.benchmark }}
        </div>
      </div>

      <div class="tabs">
        <button
          @click="selectedTab = 'holdings'"
          :class="{ active: selectedTab === 'holdings' }"
          class="tab-btn"
        >Holdings</button>
        <button
          @click="selectedTab = 'allocations'"
          :class="{ active: selectedTab === 'allocations' }"
          class="tab-btn"
        >Allocations</button>
      </div>

      <div v-if="selectedTab === 'holdings'" class="holdings-list">
        <h4>Top Holdings</h4>
        <div v-for="holding in holdings.slice(0, 10)" :key="holding.id" class="holding-item">
          <span class="holding-name">{{ holding.instrument_name }}</span>
          <span class="holding-weight">{{ holding.weight }}%</span>
          <span class="holding-sector" v-if="holding.sector">{{ holding.sector }}</span>
        </div>
      </div>

      <div v-if="selectedTab === 'allocations'" class="allocations-section">
        <h4>Sector Allocation</h4>
        <div v-for="alloc in getSectorAllocations()" :key="alloc.bucket" class="alloc-item">
          <span>{{ alloc.bucket }}</span>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: alloc.weight + '%' }"></div>
          </div>
          <span>{{ alloc.weight }}%</span>
        </div>
      </div>

      <button @click="selectedETF = null" class="btn btn-secondary">Close</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { etfService } from '../services/api.js'

const etfs = ref([])
const selectedETF = ref(null)
const holdings = ref([])
const allocations = ref([])
const loading = ref(false)
const error = ref(null)
const searchTicker = ref('')
const selectedProvider = ref('')
const selectedTab = ref('holdings')

const filteredETFs = computed(() => {
  return etfs.value.filter(etf => {
    const tickerMatch = etf.ticker.toLowerCase().includes(searchTicker.value.toLowerCase())
    const providerMatch = !selectedProvider.value || etf.provider === selectedProvider.value
    return tickerMatch && providerMatch
  })
})

const loadETFs = async () => {
  loading.value = true
  error.value = null
  try {
    const response = await etfService.getETFs(0, 100, selectedProvider.value || null)
    etfs.value = response.data
  } catch (err) {
    error.value = err.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

const selectETF = async (etf) => {
  selectedETF.value = etf
  selectedTab.value = 'holdings'

  try {
    const holdingsResponse = await etfService.getHoldings(etf.id)
    holdings.value = holdingsResponse.data || []

    const allocationsResponse = await etfService.getAllocations(etf.id)
    allocations.value = allocationsResponse.data || []
  } catch (err) {
    error.value = err.message
  }
}

const getSectorAllocations = () => {
  return allocations.value.filter(a => a.type === 'sector').slice(0, 10)
}

const formatCurrency = (value) => {
  if (!value) return 'N/A'
  if (value >= 1_000_000_000) return (value / 1_000_000_000).toFixed(1) + 'B'
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(1) + 'M'
  return value
}

onMounted(loadETFs)
</script>

<style scoped>
.etf-list {
  background: white;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

h2 {
  margin-bottom: 1.5rem;
  color: #333;
}

.filters {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.input {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  transition: background-color 0.3s;
}

.btn-primary {
  background: #667eea;
  color: white;
}

.btn-primary:hover {
  background: #5568d3;
}

.btn-secondary {
  background: #999;
  color: white;
  margin-top: 1rem;
}

.btn-small {
  padding: 0.5rem 1rem;
  font-size: 0.9rem;
}

.btn-info {
  background: #17a2b8;
  color: white;
}

.loading, .error {
  padding: 1rem;
  text-align: center;
  font-weight: bold;
}

.error {
  color: #d32f2f;
  background: #ffebee;
  border-radius: 4px;
}

.table-container {
  overflow-x: auto;
  margin-bottom: 2rem;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}

.table thead {
  background: #f5f5f5;
}

.table th {
  padding: 1rem;
  text-align: left;
  font-weight: 600;
  border-bottom: 2px solid #ddd;
}

.table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #eee;
}

.table-row:hover {
  background: #f9f9f9;
}

.ticker {
  font-weight: 600;
  color: #667eea;
}

.isin {
  font-family: monospace;
  font-size: 0.9rem;
}

.detail-panel {
  background: #f9f9f9;
  border-left: 4px solid #667eea;
  padding: 1.5rem;
  margin-top: 2rem;
  border-radius: 4px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin: 1rem 0;
}

.detail-item {
  padding: 0.75rem;
  background: white;
  border-radius: 4px;
}

.tabs {
  display: flex;
  gap: 1rem;
  margin: 1.5rem 0 1rem 0;
  border-bottom: 2px solid #ddd;
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.75rem;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  color: #666;
  font-weight: 500;
}

.tab-btn.active {
  color: #667eea;
  border-bottom-color: #667eea;
}

.holdings-list {
  margin-top: 1rem;
}

.holding-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  border-bottom: 1px solid #eee;
  gap: 1rem;
}

.holding-weight {
  font-weight: 600;
  color: #667eea;
}

.holding-sector {
  font-size: 0.85rem;
  background: #e0e7ff;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  color: #667eea;
}

.allocations-section {
  margin-top: 1rem;
}

.alloc-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  font-size: 0.95rem;
}

.alloc-item > span:first-child {
  min-width: 120px;
}

.progress-bar {
  flex: 1;
  height: 24px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.3s;
}
</style>
