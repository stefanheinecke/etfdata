<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">Analytics</h1>
      <p class="page-subtitle">Portfolio exposure breakdown and per-ETF risk metrics in one call.</p>
    </div>
    <div v-if="!hasApiKey" class="cta-banner">
      <div class="cta-text">
        <strong>An API key is required to run analytics.</strong>
        <span>Get yours for free in 10 seconds.</span>
      </div>
      <button class="cta-btn" @click="showApiKeyModal = true">Get Free API Key</button>
    </div>
    <div class="ana-tabs">
      <button v-for="t in tabs" :key="t.id" :class="['ana-tab',{active:activeTab===t.id}]" @click="activeTab=t.id">
        <span>{{ t.icon }}</span> {{ t.label }}
      </button>
    </div>

    <!-- EXPOSURE -->
    <div v-if="activeTab==='exposure'">
      <div class="card" style="margin-bottom:1.5rem">
        <h2 class="card-title">Portfolio Exposure</h2>
        <p style="font-size:.875rem;color:var(--text-muted);margin-bottom:1rem">Define a portfolio (ETF ID + weight%) to analyse sector, country and currency exposure.</p>
        <div v-for="(item,i) in portfolio" :key="i" style="display:flex;gap:.5rem;margin-bottom:.5rem;align-items:center">
          <select class="input" v-model="item.etf_id" style="flex:2">
            <option value="">Select ETF...</option>
            <option v-for="e in allEtfs" :key="e.id" :value="e.id">{{ e.ticker }} - {{ e.name }}</option>
          </select>
          <input class="input" type="number" v-model.number="item.weight" placeholder="Weight %" style="flex:1;max-width:120px" min="0" max="100" />
          <button class="btn btn-outline" @click="portfolio.splice(i,1)" style="flex-shrink:0">✕</button>
        </div>
        <div style="display:flex;gap:.75rem;margin-top:.75rem;align-items:center;flex-wrap:wrap">
          <button class="btn btn-outline" @click="portfolio.push({etf_id:'',weight:0})">+ Add ETF</button>
          <button class="btn btn-primary" @click="runExposure" :disabled="exposureLoading || !portfolio.some(p=>p.etf_id)">
            {{ exposureLoading ? 'Calculating...' : 'Analyse Exposure' }}
          </button>
          <label style="font-size:.8rem;color:var(--text-muted);margin-left:auto">Risk-free rate</label>
          <input class="input" type="number" v-model.number="riskFreeRate" min="0" max="20" step="0.5"
            style="width:72px;padding:.3rem .5rem;font-size:.875rem" />
          <span style="font-size:.8rem;color:var(--text-muted)">% p.a.</span>
        </div>
      </div>
      <!-- GoETF Portfolio Score - quick feedback below builder -->
      <div v-if="portfolioScoreLoading" style="margin-bottom:1.5rem;padding:1rem 1.25rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);font-size:.875rem;color:var(--text-muted)">Computing GoETF Portfolio Score…</div>
      <div v-if="portfolioScoreResult" class="card" style="margin-bottom:1.5rem">
        <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap;margin-bottom:1rem">
          <h3 class="card-title" style="margin:0">GoETF Portfolio Score</h3>
          <span class="score-badge score-lg" :class="scoreBadgeClass(portfolioScoreResult.portfolio_score)">
            {{ portfolioScoreResult.portfolio_score?.toFixed(1) }}
          </span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:.75rem;margin-bottom:1rem">
          <div class="stat-box">
            <div class="stat-label">Base Score</div>
            <div class="stat-value">{{ portfolioScoreResult.base_score?.toFixed(1) }}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Overlap Penalty</div>
            <div class="stat-value" style="color:#ef4444">−{{ portfolioScoreResult.overlap_penalty?.toFixed(2) }}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Diversification Bonus</div>
            <div class="stat-value" style="color:#0b6aa5">+{{ portfolioScoreResult.allocation_bonus?.toFixed(2) }}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Avg Holdings Overlap</div>
            <div class="stat-value" :class="portfolioScoreResult.avg_overlap_pct > 50 ? 'cell-red' : portfolioScoreResult.avg_overlap_pct > 20 ? 'cell-yellow' : 'cell-green'">
              {{ portfolioScoreResult.avg_overlap_pct?.toFixed(1) }}%
            </div>
          </div>
        </div>
        <div v-if="portfolioScoreResult.pairwise_overlaps?.length" style="margin-bottom:1rem">
          <div style="font-size:.8rem;font-weight:600;color:var(--text-muted);margin-bottom:.5rem">Holdings Overlap by Pair</div>
          <div v-for="ov in portfolioScoreResult.pairwise_overlaps" :key="ov.etf_a_id+ov.etf_b_id" style="display:flex;align-items:center;gap:.75rem;margin-bottom:.4rem">
            <span style="font-size:.85rem;font-weight:600;color:var(--green-600)">{{ ov.etf_a_ticker }}</span>
            <span style="font-size:.75rem;color:var(--text-muted)">↔</span>
            <span style="font-size:.85rem;font-weight:600;color:var(--green-600)">{{ ov.etf_b_ticker }}</span>
            <div class="alloc-track" style="flex:1;max-width:180px"><div class="alloc-fill" :style="{width:Math.min(ov.weight_overlap_pct,100)+'%',background:ov.weight_overlap_pct>50?'#ef4444':ov.weight_overlap_pct>20?'#ca8a04':'#0b6aa5'}"></div></div>
            <span style="font-size:.85rem;font-weight:600">{{ ov.weight_overlap_pct?.toFixed(1) }}%</span>
          </div>
        </div>
        <div v-if="portfolioScoreResult.tip" class="tip-box">
          <span class="tip-icon">💡</span>
          <div>
            <strong style="color:var(--green-600)">{{ portfolioScoreResult.tip.with_ticker }}</strong>
            has lower holdings overlap than <strong style="color:var(--green-600)">{{ portfolioScoreResult.tip.replace_ticker }}</strong>.
            Using <strong style="color:var(--green-600)">{{ portfolioScoreResult.tip.with_ticker }}</strong>
            instead would increase your portfolio score to <strong>{{ portfolioScoreResult.tip.new_score }}</strong>
            (<span style="color:#0b6aa5">+{{ portfolioScoreResult.tip.improvement }}</span>).
            <div style="font-size:.8rem;color:var(--text-muted);margin-top:.2rem">{{ portfolioScoreResult.tip.reason }}</div>
          </div>
        </div>
        <div v-else-if="portfolioScoreResult.tip === null" style="font-size:.8rem;color:var(--text-muted)">No higher-scoring alternative cleared the +0.1 threshold.</div>
        <p style="font-size:.7rem;color:var(--text-muted);margin-top:.75rem;margin-bottom:0">
          Base = weighted avg of individual GoETF Scores &nbsp;·&nbsp; Overlap Penalty: max −2 pts for 100% overlap &nbsp;·&nbsp; Bonus: portfolio country diversification vs individual weighted avg
          &nbsp;<button class="meth-link" @click="navigateTo('methodology')">→ Methodology</button>
        </p>
      </div>
      <div v-if="exposureError" class="error-box" style="margin-bottom:1rem">{{ exposureError }}</div>
      <div v-if="exposureResult" class="grid-3">
        <div class="card" v-for="group in exposureGroups" :key="group.label">
          <h3 class="card-title">{{ group.label }}</h3>
          <div class="alloc-bars">
            <div v-for="[k,v] in group.entries" :key="k" class="alloc-row">
              <span class="alloc-label">{{ k }}</span>
              <div class="alloc-track"><div class="alloc-fill" :style="{width:Math.min(v,100)+'%'}"></div></div>
              <span class="alloc-pct">{{ Number(v).toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Portfolio Risk Metrics -->
      <div v-if="portfolioRiskResult">

        <!-- Portfolio-level summary -->
        <div v-if="portfolioSummary" class="card" style="margin-top:1.5rem">
          <h3 class="card-title" style="margin-bottom:1rem">Portfolio Summary <span style="font-size:.75rem;font-weight:400;color:var(--text-muted)">(weighted average across ETFs)</span></h3>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:.75rem">
            <div class="stat-box">
              <div class="stat-label">1Y Return</div>
              <div class="stat-value" :class="signClass(portfolioSummary.ann_return)">{{ fmtPct(portfolioSummary.ann_return) }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Volatility</div>
              <div class="stat-value" :class="volClass(portfolioSummary.volatility)">{{ fmtPct(portfolioSummary.volatility) }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Sharpe Ratio</div>
              <div class="stat-value" :class="sharpeClass(portfolioSummary.sharpe_ratio)">{{ portfolioSummary.sharpe_ratio !== null ? portfolioSummary.sharpe_ratio.toFixed(2) : '—' }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Max Drawdown</div>
              <div class="stat-value" :class="ddClass(portfolioSummary.max_drawdown)">{{ fmtPct(portfolioSummary.max_drawdown) }}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Avg HHI</div>
              <div class="stat-value" :class="hhiClass(portfolioSummary.hhi)">{{ portfolioSummary.hhi.toFixed(0) }}</div>
            </div>
          </div>
          <p style="font-size:.7rem;color:var(--text-muted);margin-top:.75rem;margin-bottom:0">
            Weighted by portfolio allocation &nbsp;·&nbsp; Rf = {{ riskFreeRate }}% &nbsp;·&nbsp; Volatility is a weighted average (not true portfolio volatility, which requires correlation data)
          </p>
        </div>

        <!-- Per-ETF breakdown -->
        <div class="card" style="margin-top:1rem;padding:0;overflow:hidden">
          <div style="padding:1rem 1.25rem;border-bottom:1px solid var(--border)">
            <h3 class="card-title" style="margin:0">Per-ETF Risk Breakdown</h3>
          </div>
          <div class="table-wrap">
          <table class="risk-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>1Y Return</th>
                <th>Volatility</th>
                <th>Sharpe</th>
                <th>Max Drawdown</th>
                <th>HHI</th>
                <th># Holdings</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in portfolioRiskResult" :key="row.etf_id">
                <td><strong style="color:var(--green-600)">{{ row.ticker }}</strong></td>
                <td :class="signClass(row.ann_return)">{{ fmtPct(row.ann_return) }}</td>
                <td :class="volClass(row.volatility)">{{ fmtPct(row.volatility) }}</td>
                <td :class="sharpeClass(row.sharpe_ratio)">{{ row.sharpe_ratio !== null ? row.sharpe_ratio : '—' }}</td>
                <td :class="ddClass(row.max_drawdown)">{{ fmtPct(row.max_drawdown) }}</td>
                <td :class="hhiClass(row.hhi)">{{ row.hhi !== null ? row.hhi.toFixed(0) : '—' }}</td>
                <td>{{ row.num_holdings?.toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="padding:.6rem 1.25rem;font-size:.72rem;color:var(--text-muted);border-top:1px solid var(--border)">
          Rf = {{ riskFreeRate }}% &nbsp;·&nbsp; HHI: Herfindahl-Hirschman Index (0-10,000; lower = more diversified)
        </div>
      </div>
      </div>    </div>

    <!-- RISK METRICS -->
    <div v-if="activeTab==='risk'">
      <div class="card" style="margin-bottom:1.5rem;display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
        <h2 class="card-title" style="margin:0">Risk Metrics</h2>
        <label style="font-size:.8rem;color:var(--text-muted);margin-left:auto">Risk-free rate</label>
        <input class="input" type="number" v-model.number="riskRfRate" min="0" max="20" step="0.5"
          style="width:72px;padding:.3rem .5rem;font-size:.875rem" />
        <span style="font-size:.8rem;color:var(--text-muted)">% p.a.</span>
        <button class="btn btn-outline" style="font-size:.875rem" @click="runRiskMetrics" :disabled="riskLoading">
          {{ riskLoading ? 'Loading…' : '↻ Recalculate' }}
        </button>
      </div>
      <div v-if="riskError" class="error-box" style="margin-bottom:1rem">{{ riskError }}</div>
      <div v-if="riskResult" class="card" style="padding:0;overflow:hidden">
        <div style="padding:.75rem 1.25rem;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center">
          <h3 class="card-title" style="margin:0">{{ riskResult.length }} ETF{{ riskResult.length !== 1 ? 's' : '' }}</h3>
          <span style="font-size:.75rem;color:var(--text-muted)">Rf = {{ riskRfRate }}% &nbsp;·&nbsp; Click column header to sort</span>
        </div>
        <div class="table-wrap">
          <table class="risk-table">
            <thead>
              <tr>
                <th class="sortable-th" @click="toggleRiskSort('ticker')">Ticker <span class="sort-arrow">{{ riskSortKey==='ticker' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('ann_return')">1Y Return <span class="sort-arrow">{{ riskSortKey==='ann_return' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('volatility')">Volatility <span class="sort-arrow">{{ riskSortKey==='volatility' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('sharpe_ratio')">Sharpe <span class="sort-arrow">{{ riskSortKey==='sharpe_ratio' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('max_drawdown')">Max Drawdown <span class="sort-arrow">{{ riskSortKey==='max_drawdown' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('hhi')">HHI <span class="sort-arrow">{{ riskSortKey==='hhi' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th class="sortable-th" @click="toggleRiskSort('num_holdings')">Holdings <span class="sort-arrow">{{ riskSortKey==='num_holdings' ? (riskSortDir==='asc'?'↑':'↓') : '' }}</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in riskSorted" :key="row.etf_id">
                <td><strong style="color:var(--green-600)">{{ row.ticker }}</strong></td>
                <td :class="signClass(row.ann_return)">{{ fmtPct(row.ann_return) }}</td>
                <td :class="volClass(row.volatility)">{{ fmtPct(row.volatility) }}</td>
                <td :class="sharpeClass(row.sharpe_ratio)">{{ row.sharpe_ratio !== null ? row.sharpe_ratio : '—' }}</td>
                <td :class="ddClass(row.max_drawdown)">{{ fmtPct(row.max_drawdown) }}</td>
                <td :class="hhiClass(row.hhi)">{{ row.hhi !== null ? row.hhi.toFixed(0) : '—' }}</td>
                <td>{{ row.num_holdings?.toLocaleString() ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="padding:.6rem 1.25rem;font-size:.72rem;color:var(--text-muted);border-top:1px solid var(--border)">
          HHI: Herfindahl-Hirschman Index (0-10,000; lower = more diversified)
        </div>
      </div>
    </div>

    <!-- GOETF SCORE -->
    <div v-if="activeTab==='goetf'">
      <div class="card" style="margin-bottom:1.5rem;display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
        <div>
          <h2 class="card-title" style="margin:0">GoETF Score</h2>
          <p style="font-size:.8rem;color:var(--text-muted);margin:.2rem 0 0">Composite 1-10 score based on 8 risk &amp; diversification metrics, percentile-ranked across all ETFs</p>
          <button class="meth-link" @click="navigateTo('methodology')">ℹ How is this calculated?</button>
        </div>
        <label style="font-size:.8rem;color:var(--text-muted);margin-left:auto">Risk-free rate</label>
        <input class="input" type="number" v-model.number="goetfRfRate" min="0" max="20" step="0.5"
          style="width:72px;padding:.3rem .5rem;font-size:.875rem" />
        <span style="font-size:.8rem;color:var(--text-muted)">% p.a.</span>
        <button class="btn btn-outline" style="font-size:.875rem" @click="runGoetfScores" :disabled="goetfLoading">
          {{ goetfLoading ? 'Loading…' : '↻ Recalculate' }}
        </button>
      </div>
      <div v-if="goetfError" class="error-box" style="margin-bottom:1rem">{{ goetfError }}</div>
      <div v-if="goetfResult" class="card" style="padding:0;overflow:hidden">
        <div style="padding:.75rem 1.25rem;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center">
          <h3 class="card-title" style="margin:0">{{ goetfResult.length }} ETF{{ goetfResult.length !== 1 ? 's' : '' }}</h3>
          <span style="font-size:.75rem;color:var(--text-muted)">Rf = {{ goetfRfRate }}% &nbsp;·&nbsp; Click column header to sort</span>
        </div>
        <div class="table-wrap">
          <table class="risk-table">
            <thead>
              <tr>
                <th class="sortable-th" @click="toggleGoetfSort('goetf_score')">
                  <span class="col-label" :data-tip="`Absolute quality score (1–10) based on fixed reference ranges for each metric — not a ranking against other ETFs. A score of 7+ means genuinely good by general standards; it does not change when new ETFs are added to the universe.\n\n✅ Good quality: ≥ 7\n🟡 Average: 5–7\n🔴 Below standard: ≤ 4`">Score <span class="col-i">i</span></span>
                  <span class="sort-arrow">{{ goetfSortKey==='goetf_score' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span>
                </th>
                <th class="sortable-th" @click="toggleGoetfSort('ticker')">Ticker <span class="sort-arrow">{{ goetfSortKey==='ticker' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span></th>
                <th>Name</th>
                <th class="sortable-th" @click="toggleGoetfSort('sortino')">
                  <span class="col-label" :data-tip="`How much return you get relative to losses. Only bad days count against you — good days are not penalised. Higher is better.\n\n✅ Good: > 1.0\n🟡 OK: 0.5–1.0\n🔴 Poor: < 0.3`">Sortino <span class="col-i">i</span></span>
                  <span class="sort-arrow">{{ goetfSortKey==='sortino' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span>
                </th>
                <th class="sortable-th" @click="toggleGoetfSort('calmar')">
                  <span class="col-label" :data-tip="`How much annual return you earned vs. the worst crash the ETF ever had. High value = steady gains with shallow losses. Higher is better.\n\n✅ Good: > 0.5\n🟡 OK: 0.2–0.5\n🔴 Poor: < 0.1`">Calmar <span class="col-i">i</span></span>
                  <span class="sort-arrow">{{ goetfSortKey==='calmar' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span>
                </th>
                <th class="sortable-th" @click="toggleGoetfSort('cvar')">
                  <span class="col-label" :data-tip="`How bad things get on the worst 5% of days, scaled to a yearly number. Think: expected loss in a really bad year. Less negative = better.\n\n✅ Low risk: > −20%\n🟡 Moderate: −20% to −40%\n🔴 High risk: < −40%`">CVaR 95% <span class="col-i">i</span></span>
                  <span class="sort-arrow">{{ goetfSortKey==='cvar' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span>
                </th>
                <th class="sortable-th" @click="toggleGoetfSort('hit_ratio')">
                  <span class="col-label" :data-tip="`How often the ETF ends a day in positive territory. More green days = more consistent growth. Higher is better.\n\n✅ Consistent: > 55%\n🟡 Average: 50–55%\n🔴 Erratic: < 48%`">Hit Ratio <span class="col-i">i</span></span>
                  <span class="sort-arrow">{{ goetfSortKey==='hit_ratio' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span>
                </th>
                <th class="sortable-th" @click="toggleGoetfSort('hhi')">
                  <span class="col-label" :data-tip="`Measures how concentrated the ETF is in its top holdings. 10,000 = everything in one stock. Lower = more spread out.\n\n✅ Diversified: < 200\n🟡 Moderate: 200–800\n🔴 Concentrated: > 1,000`">HHI <span class="col-i">i</span></span>
                  <span class="sort-arrow">{{ goetfSortKey==='hhi' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span>
                </th>
                <th class="sortable-th" @click="toggleGoetfSort('effective_n')">
                  <span class="col-label" :data-tip="`The 'real' number of meaningful holdings. Even 500 stocks can act like 20 if a few giants dominate. Higher = more balanced.\n\n✅ Diversified: > 100\n🟡 Moderate: 20–100\n🔴 Concentrated: < 10`">Eff. N <span class="col-i">i</span></span>
                  <span class="sort-arrow">{{ goetfSortKey==='effective_n' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span>
                </th>
                <th class="sortable-th" @click="toggleGoetfSort('geo_div')">
                  <span class="col-label" :data-tip="`How evenly the ETF is spread across countries. 100% = perfectly global, 0% = single country. Higher = less geographic risk.\n\n✅ Global: > 60%\n🟡 Regional: 20–60%\n🔴 Single-country: < 20%`">Geo Div <span class="col-i">i</span></span>
                  <span class="sort-arrow">{{ goetfSortKey==='geo_div' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span>
                </th>
                <th class="sortable-th" @click="toggleGoetfSort('max_underwater')">
                  <span class="col-label" :data-tip="`How long investors had to wait to break even after the ETF's worst crash. Shorter = more resilient. Lower is better.\n\n✅ Fast recovery: < 250 days\n🟡 Moderate: 250–500 days\n🔴 Slow: > 500 days`">Max UW <span class="col-i">i</span></span>
                  <span class="sort-arrow">{{ goetfSortKey==='max_underwater' ? (goetfSortDir==='asc'?'↑':'↓') : '' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in goetfSorted" :key="row.etf_id">
                <td>
                  <span v-if="row.goetf_score != null" class="score-badge" :class="scoreBadgeClass(row.goetf_score)">{{ row.goetf_score.toFixed(1) }}</span>
                  <span v-else class="score-badge score-na">N/A</span>
                </td>
                <td><strong style="color:var(--green-600)">{{ row.ticker }}</strong></td>
                <td style="font-size:.8rem;color:var(--text-muted);max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ row.name }}</td>
                <td :class="sortinoClass(row.sortino)">{{ row.sortino != null ? row.sortino.toFixed(2) : '—' }}</td>
                <td :class="calmarClass(row.calmar)">{{ row.calmar != null ? row.calmar.toFixed(2) : '—' }}</td>
                <td :class="cvarClass(row.cvar)">{{ row.cvar != null ? row.cvar.toFixed(1) + '%' : '—' }}</td>
                <td :class="hitClass(row.hit_ratio)">{{ row.hit_ratio != null ? (row.hit_ratio * 100).toFixed(1) + '%' : '—' }}</td>
                <td :class="hhiClass(row.hhi)">{{ row.hhi != null ? row.hhi.toFixed(0) : '—' }}</td>
                <td :class="effNClass(row.effective_n)">{{ row.effective_n != null ? row.effective_n.toFixed(0) : '—' }}</td>
                <td :class="geodivClass(row.geo_div)">{{ row.geo_div != null ? (row.geo_div * 100).toFixed(1) + '%' : '—' }}</td>
                <td :class="uwClass(row.max_underwater)">{{ row.max_underwater != null ? row.max_underwater + 'd' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="padding:.5rem 1.25rem;border-top:1px solid var(--border);font-size:.7rem;color:var(--text-muted)">
          Hover any <strong>ⓘ</strong> column header for metric details &nbsp;·&nbsp; Score = absolute quality score against fixed benchmarks — independent of how many ETFs are tracked &nbsp;·&nbsp; Not investment advice.
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { etfService, analyticsService, scoreService } from '../services/api.js'

const showApiKeyModal = inject('showApiKeyModal')
const analyticsInitTab = inject('analyticsInitTab', ref(null))
const navigateTo = inject('navigateTo')
const hasApiKey = ref(!!localStorage.getItem('api_key'))
window.addEventListener('storage', (e) => { if (e.key === 'api_key') hasApiKey.value = !!e.newValue })

const activeTab = ref('exposure')
const tabs = [
  {id:'exposure',label:'Portfolio Exposure',icon:'🌍'},
  {id:'risk',label:'Risk Metrics',icon:'📊'},
  {id:'goetf',label:'GoETF Score',icon:'⭐'},
]
const allEtfs = ref([])
const etfsLoading = ref(false)

// Exposure
const portfolio = ref([{etf_id:'',weight:50},{etf_id:'',weight:50}])
const exposureLoading = ref(false)
const exposureResult = ref(null)
const exposureError = ref('')
const portfolioRiskResult = ref(null)
const portfolioScoreResult = ref(null)
const portfolioScoreLoading = ref(false)

const portfolioSummary = computed(() => {
  if (!portfolioRiskResult.value?.length) return null
  const p = portfolio.value.filter(x => x.etf_id)
  const totalW = p.reduce((s, x) => s + (x.weight || 0), 0)
  if (!totalW) return null
  let wReturn = 0, wVol = 0, wDD = 0, wHHI = 0
  for (const row of portfolioRiskResult.value) {
    const pw = p.find(x => x.etf_id === row.etf_id)
    const w = pw ? (pw.weight || 0) / totalW : 0
    if (row.ann_return   !== null) wReturn += w * row.ann_return
    if (row.volatility   !== null) wVol    += w * row.volatility
    if (row.max_drawdown !== null) wDD     += w * row.max_drawdown
    if (row.hhi          !== null) wHHI    += w * row.hhi
  }
  const rfDecimal = riskFreeRate.value / 100
  const sharpe = wVol > 0 ? ((wReturn - rfDecimal) / wVol).toFixed(2) : null
  return { ann_return: wReturn, volatility: wVol, sharpe_ratio: sharpe !== null ? Number(sharpe) : null, max_drawdown: wDD, hhi: wHHI }
})

const exposureGroups = computed(() => {
  if (!exposureResult.value) return []
  const r = exposureResult.value
  return [
    {label:'Sectors',entries:Object.entries(r.sectors||{}).sort((a,b)=>b[1]-a[1]).slice(0,8)},
    {label:'Countries',entries:Object.entries(r.countries||{}).sort((a,b)=>b[1]-a[1]).slice(0,8)},
    {label:'Currencies',entries:Object.entries(r.currencies||{}).sort((a,b)=>b[1]-a[1])},
  ].filter(g=>g.entries.length)
})

async function loadETFs() {
  etfsLoading.value=true
  try { const r=await etfService.getETFs(0,50); allEtfs.value=r.data } catch(e){console.error(e)} finally{etfsLoading.value=false}
}
async function runExposure() {
  exposureLoading.value=true; exposureError.value=''; exposureResult.value=null; portfolioRiskResult.value=null; portfolioScoreResult.value=null
  const p=portfolio.value.filter(x=>x.etf_id)
  try {
    const r = await analyticsService.calculateExposure(p, null, riskFreeRate.value / 100)
    exposureResult.value = r.data
    portfolioRiskResult.value = r.data.risk_metrics ?? null
    if (p.length >= 1) {
      portfolioScoreLoading.value = true
      try {
        const sr = await scoreService.getPortfolioScore(p, riskFreeRate.value / 100)
        portfolioScoreResult.value = sr.data
      } catch(e) { console.warn('Portfolio score failed:', e.message) }
        finally { portfolioScoreLoading.value = false }
    }
  } catch(e){exposureError.value=e.response?.data?.detail||e.message} finally{exposureLoading.value=false}
}
// Risk-free rate (used for portfolio Sharpe in summary)
const riskFreeRate = ref(4.0)     // % per year

// GoETF Score tab
const goetfRfRate = ref(4.0)
const goetfLoading = ref(false)
const goetfResult = ref(null)
const goetfError = ref('')
const goetfSortKey = ref('goetf_score')
const goetfSortDir = ref('desc')

const goetfSorted = computed(() => {
  if (!goetfResult.value) return []
  return [...goetfResult.value].sort((a, b) => {
    let va = a[goetfSortKey.value], vb = b[goetfSortKey.value]
    if (va === null || va === undefined) va = goetfSortDir.value === 'asc' ? Infinity : -Infinity
    if (vb === null || vb === undefined) vb = goetfSortDir.value === 'asc' ? Infinity : -Infinity
    if (typeof va === 'string') return goetfSortDir.value === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
    return goetfSortDir.value === 'asc' ? va - vb : vb - va
  })
})

function toggleGoetfSort(key) {
  if (goetfSortKey.value === key) goetfSortDir.value = goetfSortDir.value === 'asc' ? 'desc' : 'asc'
  else { goetfSortKey.value = key; goetfSortDir.value = 'desc' }
}

async function runGoetfScores() {
  goetfLoading.value = true; goetfError.value = ''; goetfResult.value = null
  try {
    const r = await scoreService.getEtfScores([], goetfRfRate.value / 100)
    goetfResult.value = r.data
  } catch (e) {
    goetfError.value = e.response?.data?.detail || e.message
  } finally { goetfLoading.value = false }
}

const scoreBadgeClass = (s) => s >= 7 ? 'score-high' : s >= 5 ? 'score-mid' : s >= 3.5 ? 'score-low' : 'score-poor'
const sortinoClass = (v) => v == null ? '' : v >= 1.0 ? 'cell-green' : v >= 0.5 ? 'cell-yellow' : 'cell-red'
const calmarClass  = (v) => v == null ? '' : v >= 0.5 ? 'cell-green' : v >= 0.2 ? 'cell-yellow' : 'cell-red'
const cvarClass    = (v) => v == null ? '' : v > -20  ? 'cell-green' : v > -40  ? 'cell-yellow' : 'cell-red'
const hitClass     = (v) => v == null ? '' : v >= 0.55 ? 'cell-green' : v >= 0.48 ? 'cell-yellow' : 'cell-red'
const hhiClass     = (v) => v == null ? '' : v < 200  ? 'cell-green' : v < 1000 ? 'cell-yellow' : 'cell-red'
const effNClass    = (v) => v == null ? '' : v >= 100 ? 'cell-green' : v >= 20  ? 'cell-yellow' : 'cell-red'
const geodivClass  = (v) => v == null ? '' : v >= 0.6 ? 'cell-green' : v >= 0.2 ? 'cell-yellow' : 'cell-red'
const uwClass      = (v) => v == null ? '' : v < 250  ? 'cell-green' : v < 500  ? 'cell-yellow' : 'cell-red'

// Risk Metrics tab
const riskSelectedEtfs = ref([])
const riskRfRate = ref(4.0)
const riskLoading = ref(false)
const riskResult = ref(null)
const riskError = ref('')
const riskSortKey = ref('ticker')
const riskSortDir = ref('asc')

const riskSorted = computed(() => {
  if (!riskResult.value) return []
  return [...riskResult.value].sort((a, b) => {
    let va = a[riskSortKey.value], vb = b[riskSortKey.value]
    if (va === null || va === undefined) va = riskSortDir.value === 'asc' ? Infinity : -Infinity
    if (vb === null || vb === undefined) vb = riskSortDir.value === 'asc' ? Infinity : -Infinity
    if (typeof va === 'string') return riskSortDir.value === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
    return riskSortDir.value === 'asc' ? va - vb : vb - va
  })
})

function toggleRiskSort(key) {
  if (riskSortKey.value === key) riskSortDir.value = riskSortDir.value === 'asc' ? 'desc' : 'asc'
  else { riskSortKey.value = key; riskSortDir.value = 'asc' }
}

async function runRiskMetrics() {
  riskLoading.value = true; riskError.value = ''; riskResult.value = null
  try {
    const tickers = riskSelectedEtfs.value.length
      ? riskSelectedEtfs.value.map(id => allEtfs.value.find(e => e.id === id)?.ticker).filter(Boolean)
      : []
    const r = await etfService.getRiskMetrics(tickers, riskRfRate.value / 100)
    riskResult.value = r.data
  } catch (e) {
    riskError.value = e.response?.data?.detail || e.message
  } finally {
    riskLoading.value = false
  }
}
const fmtPct = v => v !== null && v !== undefined ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '—'
const signClass = v  => v === null ? '' : v >= 0 ? 'cell-green' : 'cell-red'
const volClass  = v  => v === null ? '' : v < 12 ? 'cell-green' : v < 22 ? 'cell-yellow' : 'cell-red'
const sharpeClass = v => v === null ? '' : v >= 1 ? 'cell-green' : v >= 0 ? 'cell-yellow' : 'cell-red'
const ddClass   = v  => v === null ? '' : v > -10 ? 'cell-green' : v > -20 ? 'cell-yellow' : 'cell-red'

onMounted(() => {
  loadETFs()
  runRiskMetrics()
  runGoetfScores()
  if (analyticsInitTab.value) { activeTab.value = analyticsInitTab.value; analyticsInitTab.value = null }
})
</script>

<style scoped>
.cta-banner{display:flex;align-items:center;justify-content:space-between;gap:1rem;background:linear-gradient(135deg,#667eea15,#764ba215);border:1.5px solid #667eea55;border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.5rem;flex-wrap:wrap}
.cta-text{display:flex;flex-direction:column;gap:.2rem;font-size:.9rem}
.cta-text strong{color:var(--text)}
.cta-text span{color:var(--text-muted)}
.cta-btn{padding:.55rem 1.2rem;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;border-radius:8px;font-weight:700;font-size:.875rem;cursor:pointer;white-space:nowrap;flex-shrink:0}
.cta-btn:hover{opacity:.9}
.risk-table{width:100%;border-collapse:collapse;font-size:.8rem}
.risk-table thead tr{background:var(--bg-3)}
.risk-table th,.risk-table td{padding:.5rem .65rem;text-align:left;border-bottom:1px solid var(--border)}
.risk-table tbody tr:hover{background:var(--bg-3)}
.sortable-th{cursor:pointer;user-select:none;white-space:nowrap}
.stat-box{background:var(--bg-3);border-radius:10px;padding:.75rem 1rem;display:flex;flex-direction:column}
.stat-box .stat-value{font-size:1.25rem}
.sortable-th:hover{color:var(--green-600)}
.sort-arrow{margin-left:.25rem;font-size:.7rem}
.cell-green{color:#16a34a;font-weight:600}
.cell-yellow{color:#ca8a04;font-weight:600}
.cell-red{color:#ef4444;font-weight:600}
.table-wrap{overflow-x:auto}
.ana-tabs{display:flex;gap:.5rem;margin-bottom:1.5rem;flex-wrap:wrap}
.ana-tab{background:none;border:1px solid var(--border);cursor:pointer;padding:.5rem 1.1rem;border-radius:8px;font-size:.875rem;font-weight:500;color:var(--text-muted);transition:all .15s;display:flex;align-items:center;gap:.35rem;font-family:inherit}
.ana-tab:hover{border-color:var(--green-400);color:var(--green-700);background:var(--bg-3)}
.ana-tab.active{background:var(--green-500);border-color:var(--green-500);color:#fff}
.etf-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:1rem}
.etf-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem;box-shadow:var(--shadow)}
.etf-card-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem}
.etf-ticker{font-size:1rem;font-weight:700;color:var(--green-600)}
.etf-name{font-size:.875rem;color:var(--text-muted)}
.alloc-bars{display:flex;flex-direction:column;gap:.5rem}
.alloc-row{display:flex;align-items:center;gap:.75rem}
.alloc-label{width:100px;font-size:.8rem;color:var(--text-2);flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.alloc-track{flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden}
.alloc-fill{height:100%;background:var(--green-500);border-radius:4px;transition:width .4s}
.alloc-pct{width:45px;text-align:right;font-size:.8rem;font-weight:600;color:var(--text)}
.meth-link{background:none;border:none;padding:0;cursor:pointer;font-size:.76rem;color:var(--green-700);text-decoration:underline;margin-top:.2rem;display:inline-block}
.meth-link:hover{color:var(--green-800)}
.score-badge{display:inline-block;padding:.2rem .55rem;border-radius:6px;font-size:.85rem;font-weight:700;min-width:2.4rem;text-align:center}
.score-badge.score-lg{font-size:1.5rem;padding:.35rem .9rem;border-radius:10px}
.score-high{background:#dcfce7;color:#166534}
.score-mid{background:#fef9c3;color:#854d0e}
.score-low{background:#ffedd5;color:#9a3412}
.score-poor{background:#fee2e2;color:#b91c1c}
.score-na{background:var(--bg-3);color:var(--text-muted)}
[data-theme="dark"] .score-high{background:#052e16;color:#86efac}
[data-theme="dark"] .score-mid{background:#2d1b00;color:#fde68a}
[data-theme="dark"] .score-low{background:#3d1a00;color:#fdba74}
[data-theme="dark"] .score-poor{background:#3d0000;color:#fca5a5}
.tip-box{display:flex;gap:.75rem;align-items:flex-start;background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:.85rem 1rem;margin-top:.5rem}
.tip-icon{font-size:1.2rem;flex-shrink:0}

/* ── Column header tooltips ───────────────────────────────────── */
.col-label{
  display:inline-flex;align-items:center;gap:.2rem;
  cursor:help;
  text-decoration:underline;
  text-decoration-style:dotted;
  text-underline-offset:3px;
  text-decoration-color:var(--text-muted,#aaa);
  position:relative;
  font-weight:600;
}
.col-label:hover{color:var(--primary,#1585c8)}
.col-i{
  display:inline-flex;align-items:center;justify-content:center;
  width:13px;height:13px;border-radius:50%;
  font-size:.6rem;font-weight:700;font-style:italic;
  background:var(--bg-3,#e8edf2);color:var(--text-muted,#888);
  flex-shrink:0;line-height:1;
}
.col-label::after{
  content:attr(data-tip);
  position:absolute;top:calc(100% + 8px);left:0;
  min-width:210px;max-width:250px;
  background:#1e293b;color:#f1f5f9;
  font-size:.73rem;font-weight:400;line-height:1.6;
  padding:.65rem .85rem;border-radius:8px;
  white-space:pre-line;
  text-align:left;
  box-shadow:0 4px 20px rgba(0,0,0,.4);
  pointer-events:none;opacity:0;transition:opacity .15s;
  z-index:300;
  text-decoration:none;
  font-style:normal;
}
.col-label:hover::after{opacity:1}
thead th:nth-last-child(-n+3) .col-label::after{left:auto;right:0}
</style>
