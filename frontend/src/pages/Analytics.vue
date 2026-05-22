<template>
  <div class="analytics">
    <h2>Analytics Tools</h2>

    <div class="tabs-main">
      <button
        @click="selectedAnalytics = 'overlap'"
        :class="{ active: selectedAnalytics === 'overlap' }"
        class="tab-btn-main"
      >Overlap Analysis</button>
      <button
        @click="selectedAnalytics = 'exposure'"
        :class="{ active: selectedAnalytics === 'exposure' }"
        class="tab-btn-main"
      >Portfolio Exposure</button>
      <button
        @click="selectedAnalytics = 'similarity'"
        :class="{ active: selectedAnalytics === 'similarity' }"
        class="tab-btn-main"
      >Find Similar</button>
    </div>

    <!-- Overlap Analysis -->
    <div v-if="selectedAnalytics === 'overlap'" class="panel">
      <h3>Overlap Analysis</h3>
      <p class="description">Compare holdings between multiple ETFs</p>

      <div class="form-group">
        <label>Enter ETF IDs (comma-separated):</label>
        <input
          v-model="overlapInput"
          type="text"
          placeholder="e.g., uuid1,uuid2,uuid3"
          class="input"
        >
        <button @click="calculateOverlap" class="btn btn-primary">Calculate</button>
      </div>

      <div v-if="overlapLoading" class="loading">Calculating overlap...</div>

      <div v-if="overlapResult">
        <h4>Overlap Matrix</h4>
        <div class="matrix-grid">
          <div v-for="(pair, key) in overlapResult.matrix" :key="key" class="matrix-item">
            <div class="matrix-header">{{ pair.etf_a.substring(0, 8) }} ↔ {{ pair.etf_b.substring(0, 8) }}</div>
            <div class="matrix-stat">
              <span>Common Holdings:</span>
              <strong>{{ pair.common_count }}</strong>
            </div>
            <div class="matrix-stat">
              <span>Overlap Score:</span>
              <strong>{{ pair.overlap_percent }}%</strong>
            </div>
            <div class="matrix-stat">
              <span>Weight Overlap:</span>
              <strong>{{ pair.weight_overlap }}%</strong>
            </div>
          </div>
        </div>

        <h4 style="margin-top: 2rem;">Common Holdings (Top 20)</h4>
        <div class="holdings-table">
          <div v-for="(holding, idx) in overlapResult.common_holdings" :key="idx" class="holding-row">
            <span class="isin">{{ holding.isin }}</span>
            <span class="weight">{{ holding.etf_a_weight }}% / {{ holding.etf_b_weight }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Portfolio Exposure -->
    <div v-if="selectedAnalytics === 'exposure'" class="panel">
      <h3>Portfolio Exposure</h3>
      <p class="description">Analyze sector and country exposure of your portfolio</p>

      <div class="portfolio-builder">
        <h4>Build Portfolio</h4>
        <div class="portfolio-input">
          <input
            v-model="newETFInput"
            type="text"
            placeholder="ETF ID"
            class="input"
          >
          <input
            v-model.number="newWeightInput"
            type="number"
            placeholder="Weight %"
            min="0"
            max="100"
            class="input"
            style="width: 100px;"
          >
          <button @click="addToPortfolio" class="btn btn-primary">Add</button>
        </div>

        <div v-if="portfolio.length > 0" class="portfolio-list">
          <h4>Portfolio (Total: {{ portfolioTotal }}%)</h4>
          <div v-for="(item, idx) in portfolio" :key="idx" class="portfolio-item">
            <span>{{ item.etf_id.substring(0, 8) }}...</span>
            <span>{{ item.weight }}%</span>
            <button @click="removeFromPortfolio(idx)" class="btn-remove">×</button>
          </div>
        </div>

        <button
          v-if="portfolio.length > 0"
          @click="calculateExposure"
          class="btn btn-primary"
          style="margin-top: 1rem;"
        >Calculate Exposure</button>
      </div>

      <div v-if="exposureLoading" class="loading">Calculating exposure...</div>

      <div v-if="exposureResult" class="exposure-result">
        <div class="exposure-section">
          <h4>Sector Exposure</h4>
          <div v-for="(weight, sector) in exposureResult.sectors" :key="sector" class="alloc-item">
            <span>{{ sector }}</span>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: weight + '%' }"></div>
            </div>
            <span>{{ weight }}%</span>
          </div>
        </div>

        <div class="exposure-section">
          <h4>Country Exposure</h4>
          <div v-for="(weight, country) in exposureResult.countries" :key="country" class="alloc-item">
            <span>{{ country }}</span>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: weight + '%' }"></div>
            </div>
            <span>{{ weight }}%</span>
          </div>
        </div>

        <div class="exposure-section">
          <h4>Currency Exposure</h4>
          <div v-for="(weight, currency) in exposureResult.currencies" :key="currency" class="alloc-item">
            <span>{{ currency }}</span>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: weight + '%' }"></div>
            </div>
            <span>{{ weight }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Find Similar -->
    <div v-if="selectedAnalytics === 'similarity'" class="panel">
      <h3>Find Similar ETFs</h3>
      <p class="description">Find ETFs with similar holdings</p>

      <div class="form-group">
        <label>Enter ETF ID:</label>
        <input
          v-model="similarETFInput"
          type="text"
          placeholder="ETF ID"
          class="input"
        >
        <button @click="findSimilar" class="btn btn-primary">Find</button>
      </div>

      <div v-if="similarLoading" class="loading">Finding similar ETFs...</div>

      <div v-if="similarResult" class="similar-list">
        <h4>Similar ETFs</h4>
        <div v-for="similar in similarResult.similar_etfs" :key="similar.etf_id" class="similar-item">
          <div class="similar-header">
            <strong>{{ similar.ticker }}</strong> ({{ similar.provider }})
          </div>
          <div class="similar-info">{{ similar.name }}</div>
          <div class="similarity-score">
            <span>Similarity Score:</span>
            <strong>{{ similar.similarity_score }}%</strong>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { analyticsService, etfService } from '../services/api.js'

const selectedAnalytics = ref('overlap')

// Overlap
const overlapInput = ref('')
const overlapLoading = ref(false)
const overlapResult = ref(null)

// Exposure
const portfolio = ref([])
const newETFInput = ref('')
const newWeightInput = ref(0)
const exposureLoading = ref(false)
const exposureResult = ref(null)

// Similarity
const similarETFInput = ref('')
const similarLoading = ref(false)
const similarResult = ref(null)

const portfolioTotal = computed(() => {
  return portfolio.value.reduce((sum, item) => sum + item.weight, 0)
})

const calculateOverlap = async () => {
  const etfIds = overlapInput.value
    .split(',')
    .map(id => id.trim())
    .filter(id => id.length > 0)

  if (etfIds.length < 2) {
    alert('Please enter at least 2 ETF IDs')
    return
  }

  overlapLoading.value = true
  try {
    const response = await analyticsService.calculateOverlap(etfIds)
    overlapResult.value = response.data
  } catch (error) {
    alert(error.response?.data?.detail || error.message)
  } finally {
    overlapLoading.value = false
  }
}

const addToPortfolio = () => {
  if (!newETFInput.value || newWeightInput.value <= 0) {
    alert('Enter valid ETF ID and weight')
    return
  }

  portfolio.value.push({
    etf_id: newETFInput.value,
    weight: newWeightInput.value
  })

  newETFInput.value = ''
  newWeightInput.value = 0
}

const removeFromPortfolio = (idx) => {
  portfolio.value.splice(idx, 1)
}

const calculateExposure = async () => {
  exposureLoading.value = true
  try {
    const response = await analyticsService.calculateExposure(portfolio.value)
    exposureResult.value = response.data
  } catch (error) {
    alert(error.response?.data?.detail || error.message)
  } finally {
    exposureLoading.value = false
  }
}

const findSimilar = async () => {
  if (!similarETFInput.value) {
    alert('Enter an ETF ID')
    return
  }

  similarLoading.value = true
  try {
    const response = await analyticsService.findSimilar(similarETFInput.value)
    similarResult.value = response.data
  } catch (error) {
    alert(error.response?.data?.detail || error.message)
  } finally {
    similarLoading.value = false
  }
}
</script>

<style scoped>
.analytics {
  background: white;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

h2 {
  margin-bottom: 1.5rem;
}

.tabs-main {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  border-bottom: 2px solid #ddd;
}

.tab-btn-main {
  background: none;
  border: none;
  padding: 0.75rem 1.5rem;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  color: #666;
  font-weight: 500;
  transition: all 0.3s;
}

.tab-btn-main.active {
  color: #667eea;
  border-bottom-color: #667eea;
}

.panel {
  animation: slideIn 0.3s ease-in-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.description {
  color: #666;
  margin: 0.5rem 0 1.5rem 0;
}

.form-group {
  margin-bottom: 1.5rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
  font-family: monospace;
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

.btn-remove {
  background: none;
  border: none;
  color: #d32f2f;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0;
}

.loading {
  text-align: center;
  padding: 1rem;
  color: #667eea;
  font-weight: bold;
}

h4 {
  margin-top: 1.5rem;
  margin-bottom: 1rem;
}

.matrix-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.matrix-item {
  background: #f9f9f9;
  padding: 1rem;
  border-radius: 4px;
  border-left: 4px solid #667eea;
}

.matrix-header {
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: #667eea;
}

.matrix-stat {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-size: 0.95rem;
}

.holdings-table {
  display: grid;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
}

.holding-row {
  display: flex;
  justify-content: space-between;
  padding: 0.75rem;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 0.9rem;
}

.isin {
  font-family: monospace;
  font-weight: 500;
}

.weight {
  color: #667eea;
  font-weight: 600;
}

.portfolio-builder {
  background: #f9f9f9;
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1rem;
}

.portfolio-input {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.portfolio-input .input {
  flex: 1;
}

.portfolio-list {
  margin-top: 1rem;
}

.portfolio-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background: white;
  border-radius: 4px;
  margin-bottom: 0.5rem;
  font-family: monospace;
}

.exposure-result {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
}

.exposure-section {
  background: #f9f9f9;
  padding: 1rem;
  border-radius: 4px;
}

.alloc-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.alloc-item > span:first-child {
  min-width: 80px;
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
}

.similar-list {
  display: grid;
  gap: 1rem;
}

.similar-item {
  background: #f9f9f9;
  padding: 1rem;
  border-radius: 4px;
  border-left: 4px solid #667eea;
}

.similar-header {
  margin-bottom: 0.5rem;
}

.similar-info {
  color: #666;
  font-size: 0.95rem;
  margin-bottom: 0.5rem;
}

.similarity-score {
  display: flex;
  justify-content: space-between;
  font-weight: 600;
  color: #667eea;
}
</style>
