<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">Import ETF from Factsheet</h1>
      <p class="page-subtitle">Upload a PDF factsheet to extract ETF metadata and holdings</p>
    </div>

    <!-- Step 1: Upload -->
    <div v-if="step === 'upload'" class="card">
      <h2 class="card-title">Step 1: Upload Factsheet</h2>
      <div class="upload-area" @click="$refs.fileInput.click()" :class="{ 'drag-over': dragOver }">
        <input
          ref="fileInput"
          type="file"
          accept=".pdf"
          @change="handleFileSelect"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="handleFileDrop"
          style="display: none"
        />
        <div class="upload-content">
          <div class="upload-icon">📄</div>
          <p class="upload-text">Click to upload or drag and drop</p>
          <p class="upload-subtext">PDF files only</p>
        </div>
      </div>
      <div v-if="selectedFile" style="margin-top: 1rem">
        <p>Selected: <strong>{{ selectedFile.name }}</strong></p>
        <button class="btn btn-primary" @click="uploadAndExtract" :disabled="extracting">
          {{ extracting ? 'Extracting...' : 'Extract Data' }}
        </button>
      </div>
      <div v-if="extractError" class="error-box" style="margin-top: 1rem">{{ extractError }}</div>
    </div>

    <!-- Step 2: Review & Edit -->
    <div v-if="step === 'review'" class="card">
      <h2 class="card-title">Step 2: Review & Edit Data</h2>
      
      <!-- Metadata Section -->
      <div style="margin-bottom: 2rem">
        <h3 style="font-size: 1rem; font-weight: 600; margin-bottom: 1rem">ETF Metadata</h3>
        <div class="form-grid">
          <div class="form-group">
            <label>ISIN *</label>
            <input v-model="formData.metadata.isin" class="input" placeholder="e.g., LU0136234068" required />
          </div>
          <div class="form-group">
            <label>Name</label>
            <input v-model="formData.metadata.name" class="input" />
          </div>
          <div class="form-group">
            <label>Provider</label>
            <input v-model="formData.metadata.provider" class="input" />
          </div>
          <div class="form-group">
            <label>TER (%)</label>
            <input v-model.number="formData.metadata.ter" class="input" type="number" step="0.01" />
          </div>
          <div class="form-group">
            <label>Benchmark</label>
            <input v-model="formData.metadata.benchmark" class="input" />
          </div>
          <div class="form-group">
            <label>EODHD Symbol <span style="font-weight: 400; color: var(--text-muted)">(optional, for prices)</span></label>
            <input v-model="formData.eodhd_symbol" class="input" placeholder="e.g., SWDA.LSE" style="text-transform: uppercase" />
          </div>
        </div>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.5rem">
          💡 Leave EODHD symbol blank to auto-fetch prices from Yahoo Finance using the ISIN.
        </p>
      </div>

      <!-- Holdings Section -->
      <div>
        <h3 style="font-size: 1rem; font-weight: 600; margin-bottom: 1rem">
          Holdings ({{ formData.holdings.length }})
        </h3>
        <div class="table-wrap">
          <table class="holdings-table">
            <thead>
              <tr>
                <th style="width: 40%">Name</th>
                <th style="width: 20%">ISIN</th>
                <th style="width: 10%; text-align: right">Weight</th>
                <th style="width: 18%">Sector</th>
                <th style="width: 10%">Country</th>
                <th style="width: 5%"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(holding, idx) in formData.holdings" :key="idx">
                <td>
                  <input v-model="holding.instrument_name" class="input-inline" />
                </td>
                <td>
                  <input v-model="holding.instrument_isin" class="input-inline" />
                </td>
                <td style="text-align: right">
                  <input v-model.number="holding.weight" class="input-inline" type="number" step="0.01" />
                </td>
                <td>
                  <input v-model="holding.sector" class="input-inline" />
                </td>
                <td>
                  <input v-model="holding.country" class="input-inline" />
                </td>
                <td style="text-align: center">
                  <button class="btn-delete" @click="formData.holdings.splice(idx, 1)">✕</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div style="display: flex; gap: 1rem; margin-top: 2rem">
        <button class="btn btn-outline" @click="step = 'upload'">← Back</button>
        <button class="btn btn-primary" @click="importETF" :disabled="importing">
          {{ importing ? 'Importing...' : 'Import ETF' }}
        </button>
      </div>
      <div v-if="importError" class="error-box" style="margin-top: 1rem">{{ importError }}</div>
    </div>

    <!-- Step 3: Success -->
    <div v-if="step === 'success'" class="card">
      <div style="text-align: center">
        <div style="font-size: 3rem; margin-bottom: 1rem">✓</div>
        <h2 class="card-title">Import Successful!</h2>
        <p style="color: var(--text-muted); margin-bottom: 1.5rem">
          ETF <strong>{{ successData.isin }}</strong> ({{ successData.name }}) has been imported with 
          <strong>{{ successData.holdings_count }}</strong> holdings.
        </p>
        <div v-if="successData.price_count > 0" style="background: var(--bg-2); border-radius: var(--radius); padding: 1rem; margin-bottom: 1.5rem; font-size: 0.9rem">
          <div style="color: var(--green-600); font-weight: 600; margin-bottom: 0.25rem">📈 Prices Fetched</div>
          <div style="color: var(--text-muted)">{{ successData.price_count }} price points from {{ successData.price_source || 'source unknown' }}</div>
        </div>
        <div v-else-if="successData.price_error" style="background: #fef2f2; border-radius: var(--radius); padding: 1rem; margin-bottom: 1.5rem; font-size: 0.9rem; color: #dc2626">
          ⚠️ {{ successData.price_error }}
        </div>
        <button class="btn btn-primary" @click="resetForm">Import Another ETF</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://etfdata-production.up.railway.app'

const step = ref('upload')
const selectedFile = ref(null)
const dragOver = ref(false)
const extracting = ref(false)
const importing = ref(false)
const extractError = ref('')
const importError = ref('')
const successData = ref(null)

const formData = ref({
  metadata: {
    name: '',
    isin: '',
    provider: '',
    ter: null,
  },
  holdings: [],
  eodhd_symbol: null,
})

function handleFileSelect(event) {
  selectedFile.value = event.target.files[0]
}

function handleFileDrop(event) {
  dragOver.value = false
  const files = event.dataTransfer.files
  if (files.length) {
    selectedFile.value = files[0]
  }
}

async function uploadAndExtract() {
  if (!selectedFile.value) return

  extracting.value = true
  extractError.value = ''

  try {
    const formDataObj = new FormData()
    formDataObj.append('file', selectedFile.value)

    const response = await fetch(`${API_BASE_URL}/admin/etf/upload-factsheet`, {
      method: 'POST',
      body: formDataObj,
    })

    // If response is not OK, try to parse the error
    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`
      try {
        const errorData = await response.json()
        errorMessage = errorData.detail || errorMessage
      } catch (e) {
        // If response is not JSON, try to get text
        try {
          const text = await response.text()
          if (text) {
            errorMessage = text.substring(0, 200) // First 200 chars
          }
        } catch (e2) {}
      }
      throw new Error(errorMessage)
    }

    const data = await response.json()
    
    if (data.status !== 'success') {
      throw new Error(data.message || 'Extraction failed')
    }

    // Populate form with extracted data
    formData.value.metadata = data.metadata
    formData.value.holdings = data.holdings

    step.value = 'review'
  } catch (error) {
    extractError.value = error.message
  } finally {
    extracting.value = false
  }
}

async function importETF() {
  if (!formData.value.metadata.isin) {
    importError.value = 'ISIN is required'
    return
  }

  importing.value = true
  importError.value = ''

  try {
    const response = await fetch(`${API_BASE_URL}/admin/etf/import-data`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(formData.value),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Import failed')
    }

    const result = await response.json()
    successData.value = result.etf
    step.value = 'success'
  } catch (error) {
    importError.value = error.message
  } finally {
    importing.value = false
  }
}

function resetForm() {
  step.value = 'upload'
  selectedFile.value = null
  extractError.value = ''
  importError.value = ''
  successData.value = null
  formData.value = {
    metadata: {
      name: '',
      isin: '',
      provider: '',
      ter: null,
    },
    holdings: [],
    eodhd_symbol: null,
  }
}
</script>

<style scoped>
.page {
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 2rem;
}

.page-title {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
}

.page-subtitle {
  color: var(--text-muted);
  font-size: 0.95rem;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 2rem;
  margin-bottom: 1.5rem;
  box-shadow: var(--shadow);
}

.card-title {
  font-size: 1.3rem;
  font-weight: 600;
  margin-bottom: 1.5rem;
}

.upload-area {
  border: 2px dashed var(--border);
  border-radius: 10px;
  padding: 3rem 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.upload-area:hover {
  border-color: #0f4c81;
  background: rgba(15, 76, 129, 0.05);
}

.upload-area.drag-over {
  border-color: #0f4c81;
  background: rgba(15, 76, 129, 0.1);
}

.upload-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.upload-text {
  font-weight: 600;
  color: var(--text);
  margin-bottom: 0.3rem;
}

.upload-subtext {
  font-size: 0.9rem;
  color: var(--text-muted);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 0.4rem;
}

.input {
  padding: 0.6rem 0.8rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.9rem;
  background: var(--bg-2);
  color: var(--text);
}

.input:focus {
  outline: none;
  border-color: #0f4c81;
  box-shadow: 0 0 0 3px rgba(15, 76, 129, 0.1);
}

.input-inline {
  width: 100%;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 0.8rem;
  background: var(--bg-2);
  color: var(--text);
}

.input-inline:focus {
  outline: none;
  border-color: #0f4c81;
}

.holdings-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.holdings-table thead tr {
  background: var(--bg-3);
}

.holdings-table th,
.holdings-table td {
  padding: 0.6rem 0.8rem;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

.holdings-table tbody tr:hover {
  background: var(--bg-3);
}

.btn {
  padding: 0.6rem 1.2rem;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: #0f4c81;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #1a6ab8;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-outline {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
}

.btn-outline:hover:not(:disabled) {
  background: var(--bg-3);
}

.btn-delete {
  background: none;
  border: none;
  color: #ef4444;
  cursor: pointer;
  font-weight: 600;
  padding: 0;
  font-size: 1rem;
}

.btn-delete:hover {
  color: #dc2626;
}

.table-wrap {
  overflow-x: auto;
  margin-bottom: 1.5rem;
  border: 1px solid var(--border);
  border-radius: 8px;
}

.error-box {
  background: #fee2e2;
  color: #b91c1c;
  padding: 0.8rem 1rem;
  border-radius: 6px;
  font-size: 0.9rem;
  border-left: 4px solid #dc2626;
}

[data-theme="dark"] .error-box {
  background: rgba(220, 38, 38, 0.1);
  color: #fca5a5;
}

[data-theme="dark"] .input,
[data-theme="dark"] .input-inline {
  background: var(--bg-2);
  color: var(--text);
  border-color: var(--border);
}
</style>
