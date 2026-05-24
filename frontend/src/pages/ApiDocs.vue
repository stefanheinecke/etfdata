<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">📖 API Reference</h1>
      <p class="page-subtitle">Complete documentation for all ETF Data API endpoints.</p>
    </div>

    <div class="docs-layout">
      <!-- Sidebar -->
      <nav class="docs-nav">
        <div class="docs-nav-section" v-for="group in groups" :key="group.label">
          <div class="docs-nav-label">{{ group.label }}</div>
          <button v-for="ep in group.endpoints" :key="ep.id"
            :class="['docs-nav-item',{active:activeId===ep.id}]" @click="activeId=ep.id">
            <span :class="['method-badge','method-'+ep.method.toLowerCase()]">{{ ep.method }}</span>
            {{ ep.short }}
          </button>
        </div>
      </nav>

      <!-- Content -->
      <div class="docs-content">
        <div v-if="active">
          <div class="ep-header">
            <span :class="['method-badge-lg','method-'+active.method.toLowerCase()]">{{ active.method }}</span>
            <code class="ep-path">{{ active.path }}</code>
          </div>
          <h2 class="ep-title">{{ active.title }}</h2>
          <p class="ep-desc">{{ active.desc }}</p>

          <!-- Auth -->
          <div class="doc-section">
            <h3 class="doc-section-title">Authentication</h3>
            <p class="doc-section-body">All endpoints require an API key passed as a request header:</p>
            <pre>x-api-key: YOUR_API_KEY</pre>
          </div>

          <!-- Parameters -->
          <div v-if="active.params?.length" class="doc-section">
            <h3 class="doc-section-title">Parameters</h3>
            <div class="table-wrap">
              <table>
                <thead><tr><th>Name</th><th>In</th><th>Type</th><th>Required</th><th>Description</th></tr></thead>
                <tbody>
                  <tr v-for="p in active.params" :key="p.name">
                    <td><code>{{ p.name }}</code></td>
                    <td><span class="badge">{{ p.in }}</span></td>
                    <td>{{ p.type }}</td>
                    <td>{{ p.required ? '✓' : '—' }}</td>
                    <td style="color:var(--text-muted)">{{ p.desc }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Request body -->
          <div v-if="active.body" class="doc-section">
            <h3 class="doc-section-title">Request Body</h3>
            <pre>{{ active.body }}</pre>
          </div>

          <!-- Examples -->
          <div class="doc-section">
            <h3 class="doc-section-title">Examples</h3>
            <div class="code-tabs" style="margin-bottom:.75rem">
              <button v-for="lang in langs" :key="lang"
                :class="['code-tab',{active:activeLang===lang}]" @click="activeLang=lang">{{ lang }}</button>
            </div>
            <pre>{{ active.examples[activeLang] }}</pre>
          </div>

          <!-- Response -->
          <div v-if="active.response" class="doc-section">
            <h3 class="doc-section-title">Example Response</h3>
            <pre>{{ active.response }}</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- General info -->
    <div class="card" style="margin-top:2rem">
      <h2 class="card-title">Base URL & Authentication</h2>
      <div class="grid-2">
        <div>
          <p class="label">Base URL</p>
          <pre style="margin-top:.35rem">https://etfdata-production.up.railway.app</pre>
        </div>
        <div>
          <p class="label">Rate Limiting</p>
          <p style="font-size:.875rem;color:var(--text-muted);margin-top:.35rem">Default: 60 requests/minute per API key. Configurable per key via the admin endpoint.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
const BASE = 'https://etfdata-production.up.railway.app'
const langs = ['cURL', 'Python', 'JavaScript']
const activeLang = ref('cURL')
const activeId = ref('list-etfs')

const groups = [
  {
    label: 'ETFs',
    endpoints: [
      { id: 'list-etfs', method: 'GET', short: '/etfs', path: '/etfs',
        title: 'List ETFs', desc: 'Returns a paginated list of all tracked ETFs with optional provider filter.',
        params: [
          {name:'skip',in:'query',type:'integer',required:false,desc:'Number of records to skip (default 0)'},
          {name:'limit',in:'query',type:'integer',required:false,desc:'Max records to return (default 50)'},
          {name:'provider',in:'query',type:'string',required:false,desc:'Filter by provider name'},
        ],
        examples: {
          'cURL': `curl "${BASE}/etfs?limit=10" \\\n  -H "x-api-key: YOUR_KEY"`,
          'Python': `import requests\nr = requests.get("${BASE}/etfs", params={"limit":10},\n    headers={"x-api-key":"YOUR_KEY"})\nprint(r.json())`,
          'JavaScript': `const r = await fetch("${BASE}/etfs?limit=10",\n  {headers:{"x-api-key":"YOUR_KEY"}})\nconsole.log(await r.json())`,
        },
        response: `[\n  {\n    "id": "uuid",\n    "isin": "IE00B4L5Y983",\n    "ticker": "VWRL",\n    "name": "Vanguard FTSE All-World",\n    "provider": "Vanguard",\n    "ter": 0.22,\n    "fund_size": 15000000000,\n    "currency": "EUR"\n  }\n]`,
      },
      { id: 'get-etf', method: 'GET', short: '/etfs/{id}', path: '/etfs/{etf_id}',
        title: 'Get ETF by ID', desc: 'Returns full details of a single ETF.',
        params: [{name:'etf_id',in:'path',type:'UUID',required:true,desc:'The ETF UUID'}],
        examples: {
          'cURL': `curl "${BASE}/etfs/ETF_UUID" \\\n  -H "x-api-key: YOUR_KEY"`,
          'Python': `r = requests.get(f"${BASE}/etfs/{'{ETF_UUID}'}",\n    headers={"x-api-key":"YOUR_KEY"})`,
          'JavaScript': `const r = await fetch(\`${BASE}/etfs/\${id}\`,\n  {headers:{"x-api-key":"YOUR_KEY"}})`,
        },
      },
      { id: 'holdings', method: 'GET', short: '/etfs/{id}/holdings', path: '/etfs/{etf_id}/holdings',
        title: 'Get Holdings', desc: 'Returns all holdings for an ETF on a given date (defaults to latest available date).',
        params: [
          {name:'etf_id',in:'path',type:'UUID',required:true,desc:'The ETF UUID'},
          {name:'date',in:'query',type:'date',required:false,desc:'Date in YYYY-MM-DD format'},
        ],
        examples: {
          'cURL': `curl "${BASE}/etfs/ETF_UUID/holdings" \\\n  -H "x-api-key: YOUR_KEY"`,
          'Python': `r = requests.get(f"${BASE}/etfs/{'{id}'}/holdings",\n    headers={"x-api-key":"YOUR_KEY"})`,
          'JavaScript': `const r = await fetch(\`${BASE}/etfs/\${id}/holdings\`,\n  {headers:{"x-api-key":"YOUR_KEY"}})`,
        },
        response: `[\n  {\n    "id": "uuid",\n    "instrument_isin": "US0378331005",\n    "instrument_name": "Apple Inc.",\n    "weight": 4.23,\n    "country": "US",\n    "sector": "Technology"\n  }\n]`,
      },
      { id: 'allocations', method: 'GET', short: '/etfs/{id}/allocations', path: '/etfs/{etf_id}/allocations',
        title: 'Get Allocations', desc: 'Returns sector, country and currency allocations for an ETF.',
        params: [
          {name:'etf_id',in:'path',type:'UUID',required:true,desc:'The ETF UUID'},
          {name:'type',in:'query',type:'string',required:false,desc:'Filter: sector | country | currency'},
          {name:'date',in:'query',type:'date',required:false,desc:'Date in YYYY-MM-DD format'},
        ],
        examples: {
          'cURL': `curl "${BASE}/etfs/ETF_UUID/allocations?type=sector" \\\n  -H "x-api-key: YOUR_KEY"`,
          'Python': `r = requests.get(f"${BASE}/etfs/{'{id}'}/allocations",\n    params={"type":"sector"},\n    headers={"x-api-key":"YOUR_KEY"})`,
          'JavaScript': `const r = await fetch(\`${BASE}/etfs/\${id}/allocations?type=sector\`,\n  {headers:{"x-api-key":"YOUR_KEY"}})`,
        },
      },
    ]
  },
  {
    label: 'Analytics',
    endpoints: [
      { id: 'overlap-post', method: 'POST', short: '/analytics/overlap', path: '/analytics/overlap',
        title: 'Multi-ETF Overlap', desc: 'Calculates the holdings overlap matrix between multiple ETFs.',
        body: `{\n  "etf_ids": ["uuid-a", "uuid-b", "uuid-c"],\n  "date": "2026-05-24"  // optional\n}`,
        examples: {
          'cURL': `curl -X POST "${BASE}/analytics/overlap" \\\n  -H "x-api-key: YOUR_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"etf_ids":["ID_A","ID_B"]}'`,
          'Python': `r = requests.post("${BASE}/analytics/overlap",\n    json={"etf_ids":["ID_A","ID_B"]},\n    headers={"x-api-key":"YOUR_KEY"})`,
          'JavaScript': `const r = await fetch("${BASE}/analytics/overlap",{\n  method:"POST",\n  headers:{"x-api-key":"YOUR_KEY","Content-Type":"application/json"},\n  body:JSON.stringify({etf_ids:[idA,idB]})\n})`,
        },
        response: `{\n  "matrix": {\n    "uuid-a": {\n      "uuid-b": {"common_count":14,"overlap_percentage":46.7}\n    }\n  },\n  "common_holdings": [\n    {"isin":"US0378331005","name":"Apple Inc."}\n  ]\n}`,
      },
      { id: 'overlap-get', method: 'GET', short: '/analytics/overlap/{a}/{b}', path: '/analytics/overlap/{etf_a}/{etf_b}',
        title: 'Pairwise Overlap', desc: 'Quick overlap calculation between exactly two ETFs.',
        params: [
          {name:'etf_a',in:'path',type:'UUID',required:true,desc:'First ETF UUID'},
          {name:'etf_b',in:'path',type:'UUID',required:true,desc:'Second ETF UUID'},
          {name:'date',in:'query',type:'date',required:false,desc:'Date in YYYY-MM-DD format'},
        ],
        examples: {
          'cURL': `curl "${BASE}/analytics/overlap/UUID_A/UUID_B" \\\n  -H "x-api-key: YOUR_KEY"`,
          'Python': `r = requests.get(f"${BASE}/analytics/overlap/{'{a}'}/{'{b}'}",\n    headers={"x-api-key":"YOUR_KEY"})`,
          'JavaScript': `const r = await fetch(\`${BASE}/analytics/overlap/\${a}/\${b}\`,\n  {headers:{"x-api-key":"YOUR_KEY"}})`,
        },
      },
      { id: 'exposure', method: 'POST', short: '/analytics/exposure', path: '/analytics/exposure',
        title: 'Portfolio Exposure', desc: 'Analyses the combined sector, country and currency exposure of a weighted portfolio of ETFs.',
        body: `{\n  "portfolio": [\n    {"etf_id": "uuid-a", "weight": 60},\n    {"etf_id": "uuid-b", "weight": 40}\n  ]\n}`,
        examples: {
          'cURL': `curl -X POST "${BASE}/analytics/exposure" \\\n  -H "x-api-key: YOUR_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"portfolio":[{"etf_id":"ID_A","weight":60},{"etf_id":"ID_B","weight":40}]}'`,
          'Python': `r = requests.post("${BASE}/analytics/exposure",\n    json={"portfolio":[{"etf_id":"ID_A","weight":60}]},\n    headers={"x-api-key":"YOUR_KEY"})`,
          'JavaScript': `const r = await fetch("${BASE}/analytics/exposure",{\n  method:"POST",\n  headers:{"x-api-key":"YOUR_KEY","Content-Type":"application/json"},\n  body:JSON.stringify({portfolio:[{etf_id:id,weight:100}]})\n})`,
        },
        response: `{\n  "sectors": {"Technology": 28.4, "Healthcare": 12.1},\n  "countries": {"US": 65.2, "DE": 8.3},\n  "currencies": {"USD": 70.1, "EUR": 18.2}\n}`,
      },
      { id: 'similar', method: 'GET', short: '/analytics/similar/{id}', path: '/analytics/similar/{etf_id}',
        title: 'Find Similar ETFs', desc: 'Returns the top N most similar ETFs to a reference ETF based on holdings overlap.',
        params: [
          {name:'etf_id',in:'path',type:'UUID',required:true,desc:'Reference ETF UUID'},
          {name:'top_n',in:'query',type:'integer',required:false,desc:'Number of results (default 5)'},
        ],
        examples: {
          'cURL': `curl "${BASE}/analytics/similar/ETF_UUID?top_n=5" \\\n  -H "x-api-key: YOUR_KEY"`,
          'Python': `r = requests.get(f"${BASE}/analytics/similar/{'{id}'}",\n    params={"top_n":5},\n    headers={"x-api-key":"YOUR_KEY"})`,
          'JavaScript': `const r = await fetch(\`${BASE}/analytics/similar/\${id}?top_n=5\`,\n  {headers:{"x-api-key":"YOUR_KEY"}})`,
        },
      },
    ]
  }
]

const allEndpoints = computed(() => groups.flatMap(g => g.endpoints))
const active = computed(() => allEndpoints.value.find(e => e.id === activeId.value))
</script>

<style scoped>
.docs-layout { display: grid; grid-template-columns: 240px 1fr; gap: 2rem; align-items: start; }
@media(max-width:700px) { .docs-layout { grid-template-columns: 1fr; } }
.docs-nav { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 1rem; position: sticky; top: 80px; }
.docs-nav-section { margin-bottom: 1.25rem; }
.docs-nav-label { font-size: .7rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: .08em; padding: 0 .5rem; margin-bottom: .35rem; }
.docs-nav-item { display: flex; align-items: center; gap: .5rem; width: 100%; background: none; border: none; cursor: pointer; padding: .4rem .5rem; border-radius: 6px; font-size: .8rem; color: var(--text-2); text-align: left; transition: all .15s; font-family: inherit; }
.docs-nav-item:hover { background: var(--bg-3); color: var(--text); }
.docs-nav-item.active { background: var(--green-100); color: var(--green-700); font-weight: 600; }
.docs-content { min-width: 0; }
.ep-header { display: flex; align-items: center; gap: .75rem; margin-bottom: .75rem; }
.ep-path { font-size: 1rem; }
.ep-title { font-size: 1.3rem; font-weight: 700; color: var(--text); margin-bottom: .5rem; }
.ep-desc { color: var(--text-muted); font-size: .9rem; margin-bottom: 1.5rem; line-height: 1.6; }
.doc-section { margin-bottom: 1.5rem; }
.doc-section-title { font-size: .85rem; font-weight: 600; color: var(--text); text-transform: uppercase; letter-spacing: .05em; margin-bottom: .75rem; padding-bottom: .5rem; border-bottom: 1px solid var(--border); }
.doc-section-body { font-size: .875rem; color: var(--text-muted); margin-bottom: .75rem; }
.method-badge { display: inline-block; padding: .1rem .45rem; border-radius: 4px; font-size: .7rem; font-weight: 700; letter-spacing: .03em; }
.method-badge-lg { display: inline-block; padding: .3rem .7rem; border-radius: 6px; font-size: .85rem; font-weight: 700; letter-spacing: .03em; }
.method-get { background: #dbeafe; color: #1d4ed8; }
.method-post { background: #dcfce7; color: #15803d; }
.method-delete { background: #fee2e2; color: #dc2626; }
[data-theme="dark"] .method-get { background: #1e3a8a; color: #93c5fd; }
[data-theme="dark"] .method-post { background: #14532d; color: #86efac; }
.code-tabs { display: flex; gap: .25rem; }
.code-tab { background: none; border: 1px solid var(--border); cursor: pointer; padding: .3rem .75rem; border-radius: 6px; font-size: .8rem; font-weight: 500; color: var(--text-muted); transition: all .15s; font-family: inherit; }
.code-tab.active { background: var(--green-500); border-color: var(--green-500); color: #fff; }
</style>
