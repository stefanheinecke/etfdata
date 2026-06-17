<template>
  <div class="page meth-page">
    <div class="page-header">
      <h1 class="page-title">Score Methodology</h1>
      <p class="page-subtitle">How GoETF Scores are calculated for individual ETFs and portfolios.</p>
    </div>

    <!-- ETF Score -->
    <div class="meth-section">
      <div class="meth-section-head">
        <span class="meth-badge">1-10</span>
        <div>
          <h2 class="meth-title">GoETF Score: Individual ETF</h2>
          <p class="meth-sub">A composite rating that measures an ETF's risk-adjusted return quality and portfolio diversification, relative to all other ETFs in the GoETF universe.</p>
        </div>
      </div>

      <!-- How it works -->
      <div class="card meth-card">
        <h3 class="card-title">How it works</h3>
        <ol class="meth-steps">
          <li><strong>Compute raw metrics</strong>: 8 metrics are calculated for each ETF from its price history, holdings, and country allocations.</li>
          <li><strong>Percentile rank</strong>: each metric is ranked percentile-wise across all ETFs in the universe (0 = worst, 1 = best). The direction (higher/lower is better) is taken into account.</li>
          <li><strong>Weighted score</strong>: percentile ranks are combined using fixed weights. The resulting 0-1 value is scaled to 1-10.</li>
        </ol>
        <div class="meth-formula-box">
          <code>raw = Σ (weight<sub>i</sub> × percentile_rank<sub>i</sub>)</code>
          <code>GoETF Score = 1 + raw × 9</code>
        </div>
      </div>

      <!-- Metrics table -->
      <div class="card meth-card" style="padding:0;overflow:hidden">
        <div style="padding:1rem 1.25rem;border-bottom:1px solid var(--border)">
          <h3 class="card-title" style="margin:0">The 8 Metrics</h3>
        </div>
        <div class="table-wrap">
          <table class="meth-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Weight</th>
                <th>Direction</th>
                <th>Data source</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Sortino Ratio</strong></td>
                <td class="meth-weight">20%</td>
                <td class="meth-dir meth-up">↑ Higher</td>
                <td class="meth-src">Price history</td>
                <td>Like the Sharpe ratio but only penalises downside volatility below the risk-free rate. Annualised excess return ÷ downside deviation.</td>
              </tr>
              <tr>
                <td><strong>Calmar Ratio</strong></td>
                <td class="meth-weight">15%</td>
                <td class="meth-dir meth-up">↑ Higher</td>
                <td class="meth-src">Price history</td>
                <td>Annualised return divided by the absolute max drawdown. Rewards ETFs that recover quickly from losses.</td>
              </tr>
              <tr>
                <td><strong>CVaR 95%</strong></td>
                <td class="meth-weight">15%</td>
                <td class="meth-dir meth-up">↑ Less negative</td>
                <td class="meth-src">Price history</td>
                <td>Conditional Value at Risk: the average of the worst 5% of daily log-returns (annualised). Measures tail-risk severity.</td>
              </tr>
              <tr>
                <td><strong>HHI</strong></td>
                <td class="meth-weight">10%</td>
                <td class="meth-dir meth-down">↓ Lower</td>
                <td class="meth-src">Holdings</td>
                <td>Herfindahl-Hirschman Index of holdings concentration: Σw² × 10,000. Ranges from ~0 (highly diversified) to 10,000 (single holding).</td>
              </tr>
              <tr>
                <td><strong>Effective N</strong></td>
                <td class="meth-weight">10%</td>
                <td class="meth-dir meth-up">↑ Higher</td>
                <td class="meth-src">Holdings</td>
                <td>1 ÷ Σw². The effective number of equally-weighted positions the ETF is equivalent to. High = more diversified.</td>
              </tr>
              <tr>
                <td><strong>Geo Diversity</strong></td>
                <td class="meth-weight">10%</td>
                <td class="meth-dir meth-up">↑ Higher</td>
                <td class="meth-src">Allocations</td>
                <td>1 − (country HHI ÷ 10,000). Derived from the country allocation breakdown. 0 = single country, ~1 = perfectly spread.</td>
              </tr>
              <tr>
                <td><strong>Hit Ratio</strong></td>
                <td class="meth-weight">10%</td>
                <td class="meth-dir meth-up">↑ Higher</td>
                <td class="meth-src">Price history</td>
                <td>Fraction of trading days where the ETF posted a positive return. Captures consistency of positive performance.</td>
              </tr>
              <tr>
                <td><strong>Max Underwater</strong></td>
                <td class="meth-weight">10%</td>
                <td class="meth-dir meth-down">↓ Lower</td>
                <td class="meth-src">Price history</td>
                <td>Maximum consecutive trading days the ETF spent below its previous all-time high price. Captures recovery speed.</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="padding:.6rem 1.25rem;font-size:.72rem;color:var(--text-muted);border-top:1px solid var(--border)">
          Risk-free rate is configurable (default 4% p.a. ≈ Swiss SARON). All price-history metrics use daily log-returns from available close price data.
        </div>
      </div>
    </div>

    <!-- Portfolio Score -->
    <div class="meth-section">
      <div class="meth-section-head">
        <span class="meth-badge meth-badge-port">1-10</span>
        <div>
          <h2 class="meth-title">Portfolio GoETF Score</h2>
          <p class="meth-sub">A portfolio-level score that rewards low overlap between ETFs and broad geographic diversification, while penalising redundant positions.</p>
        </div>
      </div>

      <div class="meth-component-grid">
        <!-- Base -->
        <div class="card meth-comp-card">
          <div class="meth-comp-top">
            <span class="meth-comp-icon">⚖️</span>
            <h3 class="meth-comp-title">Base Score</h3>
            <span class="meth-comp-range">1-10</span>
          </div>
          <p class="meth-comp-desc">Weighted average of the individual GoETF Scores of all ETFs in the portfolio, using their portfolio weights.</p>
          <div class="meth-formula-box meth-formula-sm">
            <code>base = Σ (w<sub>i</sub> × GoETF_Score<sub>i</sub>)</code>
          </div>
        </div>
        <!-- Overlap Penalty -->
        <div class="card meth-comp-card">
          <div class="meth-comp-top">
            <span class="meth-comp-icon">🔗</span>
            <h3 class="meth-comp-title">Overlap Penalty</h3>
            <span class="meth-comp-range meth-range-neg">0 to −2</span>
          </div>
          <p class="meth-comp-desc">For every pair of ETFs, the weight overlap is computed as Σ min(w<sub>a</sub>, w<sub>b</sub>) across shared holdings (0-100%). The weighted average pairwise overlap drives the penalty: 100% identical overlap costs 2 score points.</p>
          <div class="meth-formula-box meth-formula-sm">
            <code>penalty = (avg_weight_overlap_% ÷ 100) × 2</code>
          </div>
        </div>
        <!-- Diversification Bonus -->
        <div class="card meth-comp-card">
          <div class="meth-comp-top">
            <span class="meth-comp-icon">🌍</span>
            <h3 class="meth-comp-title">Diversification Bonus</h3>
            <span class="meth-comp-range meth-range-pos">0 to +1</span>
          </div>
          <p class="meth-comp-desc">If the combined portfolio achieves greater geographic diversity (lower country HHI) than the weighted average of its individual ETFs, the improvement is added as a bonus.</p>
          <div class="meth-formula-box meth-formula-sm">
            <code>bonus = max(0, portfolio_geo_div − avg_individual_geo_div)</code>
          </div>
        </div>
      </div>

      <!-- Final formula -->
      <div class="card meth-card meth-final-card">
        <h3 class="card-title">Final Formula</h3>
        <div class="meth-formula-box meth-formula-lg">
          <code>Portfolio Score = clamp(base − penalty + bonus, 1, 10)</code>
        </div>
        <p style="font-size:.85rem;color:var(--text-muted);margin-top:.75rem;margin-bottom:0">The score is clamped to the range 1-10. A perfectly diversified, non-overlapping portfolio of high-scoring ETFs can reach a score close to 10.</p>
      </div>

      <!-- Swap Tip -->
      <div class="card meth-card">
        <h3 class="card-title">💡 Swap Tip</h3>
        <p style="font-size:.875rem;color:var(--text)">After computing the portfolio score, the engine tries every single-ETF replacement: each ETF in the portfolio is temporarily swapped for each alternative ETF in the universe, and the resulting portfolio score is estimated. If any swap improves the score by more than 0.1 pts, the best one is returned as a suggestion.</p>
        <div style="margin-top:.75rem;display:flex;flex-direction:column;gap:.3rem">
          <div class="meth-tip-row"><span class="meth-tip-key">Scope</span><span>One ETF replaced at a time; all others remain unchanged.</span></div>
          <div class="meth-tip-row"><span class="meth-tip-key">Threshold</span><span>Minimum improvement of +0.1 pts required to surface a tip.</span></div>
          <div class="meth-tip-row"><span class="meth-tip-key">Universe</span><span>All ETFs tracked in GoETF are considered as candidates.</span></div>
        </div>
      </div>
    </div>

    <!-- Disclaimer -->
    <div class="card" style="background:var(--bg-3);border-color:var(--border)">
      <p style="font-size:.8rem;color:var(--text-muted);margin:0;line-height:1.7">
        <strong>Note:</strong> GoETF Scores are quantitative summaries derived from historical data. They are provided for informational purposes only and do not constitute investment advice or a recommendation to buy or sell any ETF. Past performance and historical statistics are not indicative of future results. Score values depend on the available data history and the composition of the current GoETF ETF universe.
      </p>
    </div>
  </div>
</template>

<script setup>
</script>

<style scoped>
.meth-page { max-width: 900px; margin: 0 auto; }
.meth-section { margin-bottom: 2.5rem; }
.meth-section-head { display: flex; align-items: flex-start; gap: 1rem; margin-bottom: 1.25rem; }
.meth-badge {
  display: flex; align-items: center; justify-content: center;
  min-width: 48px; height: 48px; border-radius: 10px;
  background: var(--green-100); color: var(--green-700);
  font-size: .85rem; font-weight: 800; flex-shrink: 0;
}
[data-theme="dark"] .meth-badge { background: #082d5e; color: #7ec8e3; }
.meth-badge-port { background: #e0f2fe; color: #0369a1; }
[data-theme="dark"] .meth-badge-port { background: #0c2340; color: #38bdf8; }
.meth-title { font-size: 1.25rem; font-weight: 700; color: var(--text); margin: 0 0 .2rem; }
.meth-sub { font-size: .875rem; color: var(--text-muted); margin: 0; line-height: 1.55; }
.meth-card { margin-bottom: 1rem; }
.meth-steps { padding-left: 1.25rem; margin: 0 0 1rem; display: flex; flex-direction: column; gap: .5rem; }
.meth-steps li { font-size: .875rem; color: var(--text); line-height: 1.5; }
.meth-formula-box {
  display: flex; flex-direction: column; gap: .35rem;
  background: var(--bg-3); border: 1px solid var(--border);
  border-radius: 8px; padding: .75rem 1rem;
}
.meth-formula-box code {
  font-family: monospace; font-size: .85rem; color: var(--green-700); display: block;
}
[data-theme="dark"] .meth-formula-box code { color: #93d5f0; }
.meth-formula-sm { margin-top: .75rem; }
.meth-formula-lg .meth-formula-box { padding: 1rem 1.25rem; }
.meth-formula-lg code { font-size: 1rem; }
.meth-table { width: 100%; border-collapse: collapse; font-size: .82rem; }
.meth-table thead tr { background: var(--bg-3); }
.meth-table th { padding: .6rem 1rem; text-align: left; border-bottom: 1px solid var(--border); font-size: .75rem; color: var(--text-muted); font-weight: 600; }
.meth-table td { padding: .65rem 1rem; border-bottom: 1px solid var(--border); color: var(--text); vertical-align: top; line-height: 1.5; }
.meth-table tbody tr:hover { background: var(--bg-3); }
.meth-weight { font-weight: 700; color: var(--text); white-space: nowrap; }
.meth-dir { font-weight: 600; font-size: .78rem; white-space: nowrap; }
.meth-up { color: #0b6aa5; }
.meth-down { color: #ef4444; }
[data-theme="dark"] .meth-up { color: #93d5f0; }
[data-theme="dark"] .meth-down { color: #f87171; }
.meth-src { font-size: .75rem; color: var(--text-muted); white-space: nowrap; }
.meth-component-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
.meth-comp-card { display: flex; flex-direction: column; }
.meth-comp-top { display: flex; align-items: center; gap: .6rem; margin-bottom: .6rem; }
.meth-comp-icon { font-size: 1.1rem; flex-shrink: 0; }
.meth-comp-title { font-size: .95rem; font-weight: 600; color: var(--text); margin: 0; flex: 1; }
.meth-comp-range { font-size: .75rem; font-weight: 700; color: var(--green-700); white-space: nowrap; }
[data-theme="dark"] .meth-comp-range { color: #93d5f0; }
.meth-range-neg { color: #ef4444 !important; }
.meth-range-pos { color: #0b6aa5 !important; }
[data-theme="dark"] .meth-range-neg { color: #f87171 !important; }
[data-theme="dark"] .meth-range-pos { color: #93d5f0 !important; }
.meth-comp-desc { font-size: .82rem; color: var(--text-muted); line-height: 1.5; margin-bottom: 0; flex: 1; }
.meth-final-card { border-color: var(--green-400) !important; }
.meth-tip-row { display: flex; gap: .75rem; font-size: .82rem; color: var(--text); align-items: baseline; }
.meth-tip-key { font-weight: 600; min-width: 80px; color: var(--text-muted); flex-shrink: 0; }
.table-wrap { overflow-x: auto; }
@media (max-width: 640px) {
  .meth-section-head { flex-direction: column; }
  .meth-table th:nth-child(4), .meth-table td:nth-child(4) { display: none; }
}
</style>
