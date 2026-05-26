<template>
  <div class="settings">
    <h2>Settings</h2>

    <div class="settings-section">
      <h3>API Configuration</h3>

      <div class="setting-item">
        <label>API Base URL:</label>
        <div class="setting-value">
          <input v-model="apiUrl" type="text" class="input">
          <button @click="saveSettings" class="btn btn-primary">Save</button>
        </div>
      </div>

      <div class="setting-item">
        <label>API Key:</label>
        <div class="setting-value">
          <input v-model="apiKey" type="password" class="input" placeholder="Enter your API key">
          <button @click="saveAPIKey" class="btn btn-primary">Save</button>
        </div>
        <p class="hint">Your API key is stored locally in browser storage only</p>
      </div>
    </div>

    <div class="settings-section">
      <h3>Database Info</h3>

      <div class="info-grid">
        <div class="info-item">
          <strong>Status:</strong>
          <span :class="{ healthy: healthStatus === 'healthy', unhealthy: healthStatus !== 'healthy' }">
            {{ healthStatus }}
          </span>
        </div>
        <div class="info-item">
          <strong>Database:</strong>
          <span>{{ databaseStatus }}</span>
        </div>
        <div class="info-item">
          <strong>Last Check:</strong>
          <span>{{ lastHealthCheck }}</span>
        </div>
      </div>

      <button @click="checkHealth" class="btn btn-secondary">Check Health Now</button>
    </div>

    <div class="settings-section">
      <h3>About</h3>
      <div class="about-text">
        <p><strong>ETF Analytics API</strong> - v1.0.0</p>
        <p>REST API für strukturierte ETF-Datenanalyse und Portfolio-Analytics.</p>
        <p>Enthält Funktionen für:</p>
        <ul>
          <li>ETF Master Data Management</li>
          <li>Holdings & Allocations</li>
          <li>Overlap Analysis</li>
          <li>Portfolio Exposure Calculation</li>
          <li>ETF Similarity Search</li>
        </ul>
        <p><em>Nur öffentliche Daten. Keine Anlageberatung.</em></p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { healthService } from '../services/api.js'

const apiUrl = ref(import.meta.env.VITE_API_URL || 'http://localhost:8000')
const apiKey = ref(localStorage.getItem('api_key') || '')
const healthStatus = ref('unknown')
const databaseStatus = ref('unknown')
const lastHealthCheck = ref('-')

const saveSettings = () => {
  localStorage.setItem('api_url', apiUrl.value)
  alert('Settings saved!')
}

const saveAPIKey = () => {
  if (!apiKey.value) {
    alert('Please enter an API key')
    return
  }
  localStorage.setItem('api_key', apiKey.value)
  alert('API Key saved!')
}

const checkHealth = async () => {
  try {
    const response = await healthService.checkHealth()
    healthStatus.value = response.data.status
    databaseStatus.value = response.data.database
    lastHealthCheck.value = new Date(response.data.timestamp).toLocaleString()
  } catch (error) {
    healthStatus.value = 'error'
    databaseStatus.value = error.message
    lastHealthCheck.value = new Date().toLocaleString()
  }
}

onMounted(() => {
  checkHealth()
})
</script>

<style scoped>
.settings {
  background: white;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

h2 {
  margin-bottom: 2rem;
}

.settings-section {
  margin-bottom: 2rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid #eee;
}

.settings-section:last-child {
  border-bottom: none;
}

h3 {
  margin-bottom: 1rem;
  color: #333;
}

.setting-item {
  margin-bottom: 1.5rem;
}

label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.setting-value {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.input {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

.hint {
  font-size: 0.85rem;
  color: #999;
  margin-top: 0.5rem;
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
}

.btn-secondary:hover {
  background: #777;
}

.btn-danger {
  background: #d32f2f;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: #b71c1c;
}

.btn-danger:disabled {
  background: #e57373;
  cursor: not-allowed;
}

.etf-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.select-all-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-weight: 600;
  cursor: pointer;
}

.etf-count {
  font-size: 0.85rem;
  color: #999;
}

.etf-list {
  border: 1px solid #eee;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
  margin-bottom: 1rem;
}

.etf-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid #f5f5f5;
}

.etf-row:last-child {
  border-bottom: none;
}

.etf-row:hover {
  background: #fafafa;
}

.etf-ticker {
  font-family: monospace;
  font-weight: 600;
  width: 70px;
  flex-shrink: 0;
}

.etf-name {
  flex: 1;
  font-size: 0.9rem;
}

.etf-provider {
  font-size: 0.8rem;
  color: #999;
  width: 80px;
  text-align: right;
  flex-shrink: 0;
}

.etf-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.success-msg {
  color: #388e3c;
  font-size: 0.9rem;
}

.error-msg {
  color: #d32f2f;
  font-size: 0.9rem;
}

.admin-badge {
  display: inline-block;
  background: #d32f2f;
  color: white;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  vertical-align: middle;
  margin-left: 0.4rem;
  letter-spacing: 0.04em;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.info-item {
  background: #f9f9f9;
  padding: 1rem;
  border-radius: 4px;
}

.info-item strong {
  display: block;
  margin-bottom: 0.5rem;
  color: #333;
}

.info-item span {
  font-family: monospace;
}

.healthy {
  color: #4caf50;
  font-weight: 600;
}

.unhealthy {
  color: #d32f2f;
  font-weight: 600;
}

.about-text {
  background: #f9f9f9;
  padding: 1.5rem;
  border-radius: 4px;
  line-height: 1.6;
}

.about-text p {
  margin-bottom: 0.5rem;
}

.about-text ul {
  margin-left: 1.5rem;
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
}

.about-text li {
  margin-bottom: 0.25rem;
}
</style>
