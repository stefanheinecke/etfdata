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
      <button :class="['tab-btn', { active: activeTab === 'etfeditor' }]" @click="switchToEditor">ETF Editor</button>
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
        Stored in <strong>sessionStorage</strong>, cleared automatically when you close the browser tab.
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
        <span>✓ Admin secret verified, operations unlocked.</span>
        <button class="btn btn-outline" style="font-size:.8rem;padding:.35rem .75rem" @click="logout">Log out</button>
      </div>
    </div>

    <!-- Admin operations -->
    <div class="grid-2" style="margin-bottom:1.5rem">
      <div class="card">
        <h3 class="card-title">Create New API Key</h3>
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">Generate a new API key. Copy it - it won't be shown again.</p>
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
          <div>
            <button class="btn btn-outline" style="width:100%" @click="triggerRefreshPrices" :disabled="!adminVerified || refreshPricesLoading">
              {{ refreshPricesLoading ? 'Refreshing…' : '🔄 Refresh Prices (latest close)' }}
            </button>
            <p style="font-size:.75rem;color:var(--text-muted);margin-top:.3rem">Fetches the latest closing prices for all ETFs from EODHD (upserts last 7 days).</p>
            <div v-if="refreshPricesLoading && refreshPricesProgress" style="margin-top:.4rem;font-size:.8rem;color:var(--text-muted);display:flex;align-items:center;gap:.4rem">
              <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--primary);animation:pulse 1s infinite"></span>
              {{ refreshPricesProgress }}
            </div>
          </div>
          <div>
            <button class="btn btn-outline" style="width:100%" @click="triggerBackfillSymbols" :disabled="!adminVerified || backfillLoading">
              {{ backfillLoading ? 'Backfilling…' : '🔗 Backfill EODHD Symbols' }}
            </button>
            <p style="font-size:.75rem;color:var(--text-muted);margin-top:.3rem">One-time setup: links existing ETFs to their EODHD symbol so daily price refresh works. Run once after upgrading.</p>
          </div>
        </div>
        <div v-if="refreshPricesResult" class="success-msg" style="margin-top:.75rem">{{ refreshPricesResult }}</div>
        <div v-if="refreshPricesError" class="error-box" style="margin-top:.75rem">{{ refreshPricesError }}</div>
        <div v-if="backfillResult" class="success-msg" style="margin-top:.75rem">{{ backfillResult }}</div>
        <div v-if="backfillError" class="error-box" style="margin-top:.75rem">{{ backfillError }}</div>
        <div v-if="dbResult" class="success-msg" style="margin-top:.75rem">{{ dbResult }}</div>
        <div v-if="dbError" class="error-box" style="margin-top:.75rem">{{ dbError }}</div>
      </div>
    </div>

    <!-- Import ETF -->
    <div class="card" style="margin-bottom:1.5rem">
      <h2 class="card-title">Import ETF</h2>
      <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">
        Provide an EODHD symbol (e.g. <code>EIMI.SW</code>, <code>SWDA.LSE</code>) to import or refresh an ETF.
        All metadata (name, ISIN, TER, benchmark, holdings) is fetched automatically from EODHD.
        Use a USD-denominated listing (e.g. <code>.SW</code>) to store prices in USD.
      </p>
      <div style="margin-bottom:.75rem">
        <label class="label">EODHD Symbol</label>
        <input class="input" v-model="importSymbol" placeholder="e.g. EIMI.SW or SWDA.LSE" style="text-transform:uppercase" />
      </div>
      <div style="margin-bottom:.75rem">
        <label class="label">ISIN <span style="font-weight:400;color:var(--text-muted)">(optional, fetched from EODHD automatically; enter manually if EODHD doesn't return it)</span></label>
        <input class="input" v-model="importIsin" placeholder="e.g. IE00BKM4GZ66" style="text-transform:uppercase" />
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
      <label class="label">Holdings CSV <span style="font-weight:400;color:var(--text-muted)">(optional, EODHD holdings used if not provided)</span></label>
      <input type="file" accept=".csv" class="input" style="margin-bottom:.75rem" @change="e => importCsvFile = e.target.files[0]" />
      <button class="btn btn-primary" @click="importETF" :disabled="!adminVerified || !importSymbol || importLoading" style="width:100%">
        {{ importLoading ? 'Importing…' : 'Import ETF' }}
      </button>
      <div v-if="importError" class="error-box" style="margin-top:.75rem">{{ importError }}</div>
      <div v-if="importResult" class="success-msg" style="margin-top:.75rem">
        ✓ {{ importResult.name }} ({{ importResult.ticker }}) imported: {{ importResult.holdings }} holdings, {{ importResult.allocations }} allocations.
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
        <div class="log-meta">{{ logsData.total }} total &nbsp;|&nbsp; showing {{ logsData.offset + 1 }}-{{ Math.min(logsData.offset + logsData.limit, logsData.total) }}</div>
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
        GoETF.ch is for <strong>informational purposes only</strong>; none of the data constitutes investment advice.
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
                <option v-for="e in valuesEtfList" :key="e.id" :value="e.id">{{ e.ticker }} - {{ e.name }}</option>
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

    <!-- ETF Editor Tab -->
    <template v-if="activeTab === 'etfeditor'">

      <!-- Selector -->
      <div class="card" style="margin-bottom:1.5rem">
        <h2 class="card-title">ETF Editor</h2>
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">Select an ETF to view and edit its metadata and holdings directly in the database.</p>
        <div style="display:flex;gap:.5rem;align-items:center">
          <select class="input" v-model="editorEtfId" style="flex:1">
            <option value="">— select ETF —</option>
            <option v-for="e in editorEtfList" :key="e.id" :value="e.id">{{ e.ticker }} - {{ e.name }}</option>
          </select>
          <button class="btn btn-outline" @click="loadEditorEtfList" title="Refresh list">↻</button>
          <button class="btn btn-primary" @click="loadEditorData" :disabled="!editorEtfId || editorLoading">
            {{ editorLoading ? 'Loading…' : 'Load' }}
          </button>
        </div>
        <div v-if="editorError" class="error-box" style="margin-top:.75rem">{{ editorError }}</div>
      </div>

      <!-- Metadata editor -->
      <div v-if="editorEtf" class="card" style="margin-bottom:1.5rem">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
          <h2 class="card-title" style="margin:0">Metadata: {{ editorEtf.ticker }}</h2>
          <button class="btn btn-primary" @click="saveMetadata" :disabled="metaSaving">
            {{ metaSaving ? 'Saving…' : 'Save Metadata' }}
          </button>
        </div>
        <div v-if="metaSaveError" class="error-box" style="margin-bottom:.75rem">{{ metaSaveError }}</div>
        <div v-if="metaSaveOk" class="success-msg" style="margin-bottom:.75rem">✓ Metadata saved successfully.</div>

        <div class="editor-grid">
          <div>
            <label class="label">Name</label>
            <input class="input" v-model="editMeta.name" />
          </div>
          <div>
            <label class="label">ISIN</label>
            <input class="input" v-model="editMeta.isin" placeholder="e.g. IE00BKM4GZ66" style="text-transform:uppercase" />
          </div>
          <div>
            <label class="label">TER %</label>
            <input class="input" type="number" step="0.001" min="0" v-model.number="editMeta.ter" placeholder="e.g. 0.18" />
          </div>
          <div>
            <label class="label">Currency</label>
            <input class="input" v-model="editMeta.currency" placeholder="USD" style="text-transform:uppercase" maxlength="3" />
          </div>
          <div>
            <label class="label">Provider</label>
            <input class="input" v-model="editMeta.provider" placeholder="iShares" />
          </div>
          <div>
            <label class="label">Domicile (ISO-2)</label>
            <input class="input" v-model="editMeta.domicile" placeholder="IE" style="text-transform:uppercase" maxlength="2" />
          </div>
          <div>
            <label class="label">Fund Size (USD)</label>
            <input class="input" type="number" step="1000000" v-model.number="editMeta.fund_size" placeholder="e.g. 20000000000" />
          </div>
          <div>
            <label class="label">Dividend Policy</label>
            <select class="input" v-model="editMeta.dividend_policy">
              <option value="">— unknown —</option>
              <option value="Accumulating">Accumulating</option>
              <option value="Distributing">Distributing</option>
            </select>
          </div>
          <div style="grid-column:1/-1">
            <label class="label">Benchmark Index</label>
            <input class="input" v-model="editMeta.benchmark" placeholder="e.g. MSCI Emerging Markets IMI Index" />
          </div>
        </div>
      </div>

      <!-- Holdings editor -->
      <div v-if="editorEtf" class="card">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
          <h2 class="card-title" style="margin:0">Holdings ({{ editorHoldings.length }})</h2>
          <button class="btn btn-outline" @click="showAddHolding = !showAddHolding; if(!showAddHolding) resetNewHolding()">
            {{ showAddHolding ? 'Cancel' : '+ Add Holding' }}
          </button>
        </div>

        <!-- Add holding form -->
        <div v-if="showAddHolding" style="margin-bottom:1rem;padding:1rem;background:var(--bg-2);border-radius:var(--radius);border:1px solid var(--border)">
          <div class="editor-grid" style="margin-bottom:.75rem">
            <div>
              <label class="label">ISIN / ID</label>
              <input class="input" v-model="newHolding.instrument_isin" placeholder="IE00B4L5YC18" />
            </div>
            <div>
              <label class="label">Name</label>
              <input class="input" v-model="newHolding.instrument_name" placeholder="Apple Inc" />
            </div>
            <div>
              <label class="label">Weight %</label>
              <input class="input" type="number" step="0.0001" min="0" v-model.number="newHolding.weight" placeholder="2.5" />
            </div>
            <div>
              <label class="label">Sector</label>
              <input class="input" v-model="newHolding.sector" placeholder="Technology" />
            </div>
            <div>
              <label class="label">Country (ISO-2)</label>
              <input class="input" v-model="newHolding.country" placeholder="US" style="text-transform:uppercase" maxlength="2" />
            </div>
          </div>
          <div style="display:flex;gap:.5rem;align-items:center">
            <button class="btn btn-primary" @click="addHolding" :disabled="addHoldingLoading || !newHolding.instrument_isin || !newHolding.instrument_name || newHolding.weight == null">
              {{ addHoldingLoading ? 'Adding…' : 'Add Holding' }}
            </button>
          </div>
          <div v-if="addHoldingError" class="error-box" style="margin-top:.5rem">{{ addHoldingError }}</div>
        </div>

        <div v-if="holdingsError" class="error-box" style="margin-bottom:.75rem">{{ holdingsError }}</div>

        <div class="log-table-wrap">
          <table class="log-table">
            <thead>
              <tr>
                <th>ISIN / ID</th>
                <th>Name</th>
                <th style="text-align:right">Weight %</th>
                <th>Sector</th>
                <th>Country</th>
                <th style="text-align:center">Actions</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="h in editorHoldings" :key="h.id">
                <tr v-if="editingHoldingId !== h.id">
                  <td class="td-mono">{{ h.instrument_isin }}</td>
                  <td>{{ h.instrument_name }}</td>
                  <td style="text-align:right;font-variant-numeric:tabular-nums">{{ Number(h.weight).toFixed(4) }}</td>
                  <td>{{ h.sector || '—' }}</td>
                  <td>{{ h.country || '—' }}</td>
                  <td style="text-align:center;white-space:nowrap">
                    <button class="btn-icon" @click="startEditHolding(h)" title="Edit">✎</button>
                    <button class="btn-icon btn-icon-danger" @click="deleteHolding(h.id)" title="Delete">✕</button>
                  </td>
                </tr>
                <tr v-else style="background:var(--bg-2)">
                  <td><input class="input input-sm" v-model="editHolding.instrument_isin" /></td>
                  <td><input class="input input-sm" v-model="editHolding.instrument_name" /></td>
                  <td><input class="input input-sm" type="number" step="0.0001" v-model.number="editHolding.weight" style="text-align:right" /></td>
                  <td><input class="input input-sm" v-model="editHolding.sector" /></td>
                  <td><input class="input input-sm" v-model="editHolding.country" style="text-transform:uppercase" maxlength="2" /></td>
                  <td style="text-align:center;white-space:nowrap">
                    <button class="btn-icon btn-icon-save" @click="saveHolding(h.id)" title="Save">✓</button>
                    <button class="btn-icon" @click="editingHoldingId = null" title="Cancel">✕</button>
                  </td>
                </tr>
              </template>
              <tr v-if="editorHoldings.length === 0">
                <td colspan="6" style="text-align:center;padding:2rem;color:var(--text-muted)">No holdings data found for this ETF.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </template><!-- /etfeditor tab -->

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

function switchToEditor() {
  activeTab.value = 'etfeditor'
  if (editorEtfList.value.length === 0) loadEditorEtfList()
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
const refreshPricesLoading = ref(false)
const refreshPricesProgress = ref('')   // "5 of 12 — SWDA"
const refreshPricesResult = ref('')
const refreshPricesError = ref('')
const backfillLoading = ref(false)
const backfillResult = ref('')
const backfillError = ref('')

const importSymbol = ref('')
const importName = ref('')
const importTer = ref(null)
const importIsin = ref('')
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
      importIsin.value.trim().toUpperCase() || null,
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

async function triggerRefreshPrices() {
  refreshPricesLoading.value = true
  refreshPricesProgress.value = ''
  refreshPricesResult.value = ''
  refreshPricesError.value = ''
  try {
    const { data } = await adminService.refreshPrices(adminSecret.value)
    const jobId = data.job_id

    // Poll for progress every 900 ms
    await new Promise((resolve, reject) => {
      const interval = setInterval(async () => {
        try {
          const { data: job } = await adminService.refreshPricesStatus(adminSecret.value, jobId)
          if (job.total > 0) {
            const ticker = job.current_ticker ? ` — ${job.current_ticker}` : ''
            refreshPricesProgress.value = `${job.done} of ${job.total}${ticker}`
          }
          if (job.status === 'done') {
            clearInterval(interval)
            const errors = job.errors?.length ? ` (${job.errors.length} error(s))` : ''
            refreshPricesResult.value = `✓ ${job.total_rows_upserted} rows upserted across ${job.etfs?.length ?? 0} ETF(s).${errors}`
            if (job.errors?.length) refreshPricesError.value = job.errors.join(', ')
            resolve()
          } else if (job.status === 'error') {
            clearInterval(interval)
            reject(new Error(job.errors?.[0] || 'Unknown error'))
          }
        } catch (e) {
          clearInterval(interval)
          reject(e)
        }
      }, 900)
    })
  } catch(e) {
    refreshPricesError.value = e.response?.data?.detail || e.message
  } finally {
    refreshPricesLoading.value = false
    refreshPricesProgress.value = ''
  }
}

async function triggerBackfillSymbols() {
  backfillLoading.value = true; backfillResult.value = ''; backfillError.value = ''
  try {
    const r = await adminService.backfillEodhdSymbols(adminSecret.value)
    const d = r.data
    backfillResult.value = `✓ ${d.updated?.length ?? 0} ETF(s) linked to EODHD symbols, ${d.skipped?.length ?? 0} skipped.`
  } catch(e) {
    backfillError.value = e.response?.data?.detail || e.message
  } finally {
    backfillLoading.value = false
  }
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

// ─── ETF Editor ───────────────────────────────────────────────
const editorEtfList = ref([])
const editorEtfId = ref('')
const editorLoading = ref(false)
const editorError = ref('')
const editorEtf = ref(null)
const editorHoldings = ref([])

const editMeta = ref({})
const metaSaving = ref(false)
const metaSaveError = ref('')
const metaSaveOk = ref(false)

const editingHoldingId = ref(null)
const editHolding = ref({})
const holdingsError = ref('')

const showAddHolding = ref(false)
const newHolding = ref({ instrument_isin: '', instrument_name: '', weight: null, sector: '', country: '' })
const addHoldingLoading = ref(false)
const addHoldingError = ref('')

async function loadEditorEtfList() {
  try {
    const r = await etfService.getETFs(0, 200)
    editorEtfList.value = r.data
  } catch (e) { console.error('Failed to load ETF list for editor', e) }
}

async function loadEditorData() {
  editorLoading.value = true
  editorError.value = ''
  editorEtf.value = null
  editorHoldings.value = []
  editingHoldingId.value = null
  showAddHolding.value = false
  try {
    const [etfR, holdingsR] = await Promise.all([
      etfService.getETFById(editorEtfId.value),
      etfService.getHoldings(editorEtfId.value),
    ])
    editorEtf.value = etfR.data
    editorHoldings.value = holdingsR.data
    editMeta.value = {
      name:             editorEtf.value.name,
      isin:             editorEtf.value.isin || '',
      ter:              editorEtf.value.ter != null ? Number(editorEtf.value.ter) : null,
      currency:         editorEtf.value.currency,
      provider:         editorEtf.value.provider,
      domicile:         editorEtf.value.domicile,
      fund_size:        editorEtf.value.fund_size,
      dividend_policy:  editorEtf.value.dividend_policy || '',
      benchmark:        editorEtf.value.benchmark || '',
    }
  } catch (e) {
    editorError.value = e.response?.data?.detail || e.message
  } finally {
    editorLoading.value = false
  }
}

async function saveMetadata() {
  metaSaving.value = true
  metaSaveError.value = ''
  metaSaveOk.value = false
  try {
    const payload = { ...editMeta.value }
    if (!payload.isin) payload.isin = null
    if (!payload.benchmark) payload.benchmark = null
    if (!payload.dividend_policy) payload.dividend_policy = null
    if (payload.ter === '') payload.ter = null
    await adminService.updateETF(adminSecret.value, editorEtfId.value, payload)
    metaSaveOk.value = true
    // Refresh the ETF list so the name change shows in the selector
    await loadEditorEtfList()
    setTimeout(() => metaSaveOk.value = false, 3000)
  } catch (e) {
    metaSaveError.value = e.response?.data?.detail || e.message
  } finally {
    metaSaving.value = false
  }
}

function startEditHolding(h) {
  editingHoldingId.value = h.id
  editHolding.value = {
    instrument_isin:  h.instrument_isin,
    instrument_name:  h.instrument_name,
    weight:           Number(h.weight),
    sector:           h.sector || '',
    country:          h.country || '',
  }
}

async function saveHolding(holdingId) {
  holdingsError.value = ''
  try {
    const r = await adminService.updateHolding(adminSecret.value, editorEtfId.value, holdingId, editHolding.value)
    const idx = editorHoldings.value.findIndex(h => h.id === holdingId)
    if (idx !== -1) editorHoldings.value[idx] = r.data
    editingHoldingId.value = null
  } catch (e) {
    holdingsError.value = e.response?.data?.detail || e.message
  }
}

async function deleteHolding(holdingId) {
  if (!confirm('Delete this holding? This cannot be undone.')) return
  holdingsError.value = ''
  try {
    await adminService.deleteHolding(adminSecret.value, editorEtfId.value, holdingId)
    editorHoldings.value = editorHoldings.value.filter(h => h.id !== holdingId)
  } catch (e) {
    holdingsError.value = e.response?.data?.detail || e.message
  }
}

function resetNewHolding() {
  newHolding.value = { instrument_isin: '', instrument_name: '', weight: null, sector: '', country: '' }
  addHoldingError.value = ''
}

async function addHolding() {
  addHoldingLoading.value = true
  addHoldingError.value = ''
  try {
    const r = await adminService.addHolding(adminSecret.value, editorEtfId.value, newHolding.value)
    editorHoldings.value.push(r.data)
    showAddHolding.value = false
    resetNewHolding()
  } catch (e) {
    addHoldingError.value = e.response?.data?.detail || e.message
  } finally {
    addHoldingLoading.value = false
  }
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
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .3; } }
.tab-bar { display: flex; gap: 0; margin-bottom: 1.5rem; border-bottom: 2px solid var(--border); }
.tab-btn { background: none; border: none; border-bottom: 2px solid transparent; margin-bottom: -2px; padding: .6rem 1.25rem; font-size: .9rem; font-weight: 500; color: var(--text-muted); cursor: pointer; transition: color .15s, border-color .15s; border-radius: var(--radius-sm) var(--radius-sm) 0 0; }
.tab-btn:hover { color: var(--text); background: var(--bg-2); }
.tab-btn.active { color: var(--green-600); border-bottom-color: var(--green-600); }
[data-theme="dark"] .tab-btn.active { color: #2d9ee0; border-bottom-color: #2d9ee0; }
.key-row { display: flex; gap: .5rem; align-items: center; }
.key-row .input { flex: 1; }
.success-msg { background: var(--green-50); border: 1px solid var(--green-200); border-radius: var(--radius-sm); padding: .75rem 1rem; color: var(--green-700); font-size: .875rem; margin-top: .75rem; }
[data-theme="dark"] .success-msg { background: #041a33; border-color: #0d3b72; color: #93d5f0; }
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
.method-POST { color: #0b6aa5; font-weight: 700; font-family: monospace; }
.method-DELETE { color: #dc2626; font-weight: 700; font-family: monospace; }
.method-PUT,.method-PATCH { color: #d97706; font-weight: 700; font-family: monospace; }
.cell-green { color: #0b6aa5; font-weight: 600; }
.cell-red { color: #dc2626; font-weight: 600; }
.log-meta { font-size: .8rem; color: var(--text-muted); }
.log-pagination { display: flex; align-items: center; gap: 1rem; margin-top: .75rem; font-size: .875rem; }
.detail-chip { display: inline-block; font-family: monospace; font-size: .72rem; background: var(--bg-3); border: 1px solid var(--border); border-radius: 4px; padding: 0 .4rem; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: middle; margin-right: .2rem; }
.body-chip { color: #7c3aed; cursor: help; }
.editor-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: .75rem; }
.td-mono { font-family: monospace; font-size: .82rem; }
.btn-icon { background: none; border: 1px solid var(--border); border-radius: 4px; padding: .2rem .45rem; cursor: pointer; font-size: .85rem; color: var(--text-muted); transition: background .12s, color .12s; margin: 0 .1rem; }
.btn-icon:hover { background: var(--bg-2); color: var(--text); }
.btn-icon-danger:hover { background: #fef2f2; color: #dc2626; border-color: #fca5a5; }
.btn-icon-save:hover { background: #e1f3ff; color: #0b6aa5; border-color: #93d5f0; }
[data-theme="dark"] .btn-icon-danger:hover { background: #2d0707; color: #f87171; border-color: #7f1d1d; }
[data-theme="dark"] .btn-icon-save:hover { background: #041a33; color: #2d9ee0; border-color: #0d3b72; }
.input-sm { padding: .2rem .4rem; font-size: .82rem; height: auto; min-height: unset; }
</style>
