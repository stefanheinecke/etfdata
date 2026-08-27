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
          <p class="meth-sub">A composite rating that measures an ETF's risk-adjusted return quality and portfolio diversification against fixed quality benchmarks.</p>
        </div>
      </div>

      <!-- How it works -->
      <div class="card meth-card">
        <h3 class="card-title">How it works</h3>
        <ol class="meth-steps">
          <li><strong>Compute raw metrics</strong>: 8 metrics are calculated for each ETF from its price history, holdings, and country allocations.</li>
          <li><strong>Benchmark normalization</strong>: each metric is mapped to a 0-1 quality score using a fixed worst-to-best reference range. The direction (higher/lower is better) is taken into account, and values outside the range are capped.</li>
          <li><strong>Weighted score</strong>: normalized metric scores are combined using fixed weights. The resulting 0-1 value is scaled to 1-10.</li>
        </ol>
        <div class="meth-formula-box">
          <code>metric_score<sub>i</sub> = clamp((value<sub>i</sub> − worst<sub>i</sub>) ÷ (best<sub>i</sub> − worst<sub>i</sub>), 0, 1)</code>
          <code>raw = Σ (weight<sub>i</sub> × metric_score<sub>i</sub>)</code>
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
          Risk-free rate is configurable (default 4% p.a. ≈ Swiss SARON). All price-history metrics use daily log-returns from available close price data. Fixed benchmark ranges make scores stable when the ETF universe changes.
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
          <p class="meth-comp-desc">For every pair of ETFs, GoETF adds the smaller weight of each shared holding. The resulting weight overlap is then averaged across pairs, giving greater influence to pairs with larger portfolio allocations.</p>
          <div class="meth-formula-box meth-formula-sm">
            <code>pair_overlap = Σ min(weight<sub>a</sub>, weight<sub>b</sub>)</code>
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
          <p class="meth-comp-desc">GoETF first combines country exposures using the portfolio allocations. It compares that portfolio diversity with the allocation-weighted average diversity of the individual ETFs. Only an improvement produces a bonus.</p>
          <div class="meth-formula-box meth-formula-sm">
            <code>geo_div = 1 − (country HHI ÷ 10,000)</code>
            <code>bonus = max(0, portfolio_geo_div − avg_individual_geo_div)</code>
          </div>
        </div>
      </div>

      <!-- Overlap example -->
      <div class="card meth-card meth-example-card">
        <h3 class="card-title">Overlap calculation example</h3>
        <p class="meth-example-intro">Only shared holdings contribute to overlap. For each shared security, the smaller ETF weight is counted once. Holdings that appear in only one ETF contribute 0%.</p>
        <div class="meth-example-grid">
          <div>
            <div class="table-wrap">
              <table class="meth-table meth-example-table">
                <thead>
                  <tr>
                    <th>Shared holding</th>
                    <th>ETF A</th>
                    <th>ETF B</th>
                    <th>Contribution</th>
                  </tr>
                </thead>
                <tbody>
                  <tr><td>Apple</td><td>8%</td><td>5%</td><td>min(8%, 5%) = 5%</td></tr>
                  <tr><td>Microsoft</td><td>6%</td><td>9%</td><td>min(6%, 9%) = 6%</td></tr>
                  <tr><td>Nvidia</td><td>4%</td><td>4%</td><td>min(4%, 4%) = 4%</td></tr>
                  <tr><td colspan="3"><strong>Pair overlap</strong></td><td><strong>15%</strong></td></tr>
                </tbody>
              </table>
            </div>
            <p class="meth-example-note">The separate <code>overlap_percent</code> value shown by the analytics endpoint counts common securities by number. The portfolio penalty uses the weight-based figure above.</p>
          </div>
          <div class="meth-example-copy">
            <p><strong>With three ETFs</strong></p>
            <p>Assume allocations of A = 50%, B = 30%, and C = 20%, with pair overlaps of A/B = 20%, A/C = 10%, and B/C = 40%.</p>
            <div class="meth-formula-box meth-formula-sm">
              <code>pair weight = (allocation<sub>a</sub> + allocation<sub>b</sub>) ÷ 2</code>
              <code>A/B: 40% · A/C: 35% · B/C: 25%</code>
              <code>avg = (20×40 + 10×35 + 40×25) ÷ 100 = 21.5%</code>
              <code>penalty = (21.5 ÷ 100) × 2 = 0.43 points</code>
            </div>
            <p>The average overlap is therefore <strong>21.5%</strong>, producing a <strong>0.43-point deduction</strong>. With only two ETFs, there is one pair, so the average equals that pair's overlap.</p>
          </div>
        </div>
      </div>

      <!-- Diversification bonus example -->
      <div class="card meth-card meth-example-card">
        <h3 class="card-title">Diversification bonus example</h3>
        <p class="meth-example-intro">The bonus measures the improvement created by combining ETFs. It is not based on the number of ETFs; it is based on how evenly the combined portfolio is distributed across countries.</p>
        <div class="meth-example-grid">
          <div class="meth-example-copy">
            <p><strong>Step 1: Combine country exposures</strong></p>
            <p>For a simplified example, suppose ETF A is 60% US and 40% other countries, while ETF B is 100% Japan. With a 60% allocation to ETF A and 40% to ETF B, the combined portfolio is 36% US, 24% other countries, and 40% Japan. Here, the 24% is temporarily treated as one bucket only to keep the arithmetic short.</p>
            <div class="meth-formula-box meth-formula-sm">
              <code>US: 60% × 60% = 36%</code>
              <code>Japan: 40% × 100% = 40%</code>
              <code>Other countries: 60% × 40% = 24%</code>
            </div>
          </div>
          <div class="meth-example-copy">
            <p><strong>Step 2: Compare diversity scores</strong></p>
            <p>When the 24% bucket is treated as one category, the 36% US, 40% Japan, and 24% other-country distribution has an HHI of 3,472. ETF A's illustrative diversity is 0.480, while ETF B's is 0 because it is concentrated in one country:</p>
            <div class="meth-formula-box meth-formula-sm">
              <code>country HHI = (0.36² + 0.40² + 0.24²) × 10,000 = 3,472</code>
              <code>portfolio_geo_div = 1 − (3,472 ÷ 10,000) = 0.653</code>
              <code>ETF A geo_div = 1 − (0.60² + 0.40²) = 0.480</code>
              <code>ETF B geo_div = 1 − 1.00² = 0.000</code>
              <code>avg_individual_geo_div = (60% × 0.480) + (40% × 0.000) = 0.288</code>
              <code>bonus = max(0, 0.653 − 0.288) = +0.365</code>
            </div>
            <p>Under this simplified bucket assumption, the portfolio is more geographically diverse than its weighted individual baseline, so <strong>0.37 points</strong> are added to the score after rounding.</p>
          </div>
        </div>
        <div class="meth-example-footnote"><strong>Important:</strong> The live calculation does not combine all “other countries” into one bucket. If the 24% were split equally across four actual countries, the HHI would be <code>(0.36² + 0.40² + 4×0.06²) × 10,000 = 3,256</code> and <code>geo_div = 0.674</code>, instead of 0.653. Splitting weights across more countries therefore increases geographic diversity. ETF A's individual diversity would also need to be recalculated from its full country breakdown. <strong>No bonus example:</strong> if the combined portfolio diversity were 0.250 instead, <code>max(0, 0.250 − 0.288) = 0</code>. Diversity cannot reduce the score through this component; only the overlap penalty can do that.</div>
      </div>

      <!-- Final formula -->
      <div class="card meth-card meth-final-card">
        <h3 class="card-title">Final Formula</h3>
        <div class="meth-formula-box meth-formula-lg">
          <code>Portfolio Score = clamp(base − penalty + bonus, 1, 10)</code>
        </div>
        <p style="font-size:.85rem;color:var(--text-muted);margin-top:.75rem;margin-bottom:0">The score is clamped to the range 1-10. A perfectly diversified, non-overlapping portfolio of high-scoring ETFs can reach a score close to 10.</p>
      </div>

      <!-- Portfolio Insight -->
      <div class="card meth-card">
        <h3 class="card-title">💡 Portfolio Insight</h3>
        <p style="font-size:.875rem;color:var(--text)">After computing the portfolio score, the engine tests one ETF at a time against each alternative ETF in the tracked universe and estimates the resulting portfolio score. If any tested alternative improves the score by more than 0.1 pts, the strongest outcome is shown.</p>
        <div style="margin-top:.75rem;display:flex;flex-direction:column;gap:.3rem">
          <div class="meth-tip-row"><span class="meth-tip-key">Scope</span><span>One ETF is changed at a time; all others remain unchanged.</span></div>
          <div class="meth-tip-row"><span class="meth-tip-key">Threshold</span><span>Minimum improvement of +0.1 pts required to show an insight.</span></div>
          <div class="meth-tip-row"><span class="meth-tip-key">Universe</span><span>All ETFs tracked in GoETF are considered as candidates.</span></div>
        </div>
      </div>
    </div>

    <!-- Disclaimer -->
    <div class="card" style="background:var(--bg-3);border-color:var(--border)">
      <p style="font-size:.8rem;color:var(--text-muted);margin:0;line-height:1.7">
        <strong>Note:</strong> GoETF Scores are quantitative summaries derived from historical data and fixed reference benchmarks. They are provided for informational purposes only and do not constitute investment advice or an invitation to buy or sell any ETF. Past performance and historical statistics are not indicative of future results. Score values depend on the available data history, the risk-free rate, and the benchmark ranges defined by GoETF.
      </p>
    </div>
  </div>
</template>

<script setup>
</script>

<style scoped>
.page {
  --green-50: rgba(15, 76, 129, 0.07);
  --green-100: rgba(15, 76, 129, 0.1);
  --green-200: rgba(15, 76, 129, 0.2);
  --green-400: #2f85c8;
  --green-500: #0f4c81;
  --green-600: #1a6ab8;
  --green-700: #0a3a66;
}
.meth-page { max-width: 960px; margin: 0 auto; }
.meth-section { margin-bottom: 2.75rem; }
.meth-section-head { display: flex; align-items: flex-start; gap: 1rem; margin-bottom: 1.35rem; }
.meth-badge {
  display: flex; align-items: center; justify-content: center;
  min-width: 48px; height: 48px; border-radius: 10px;
  background: var(--green-100); color: var(--green-700);
  font-size: .85rem; font-weight: 800; flex-shrink: 0;
}
[data-theme="dark"] .meth-badge { background: #082d5e; color: #7ec8e3; }
.meth-badge-port { background: rgba(0, 201, 167, .14); color: #008a74; }
[data-theme="dark"] .meth-badge-port { background: #0c2340; color: #38bdf8; }
.meth-title { font-size: clamp(1.35rem, 2.2vw, 1.75rem); font-weight: 700; color: var(--text); margin: 0 0 .2rem; letter-spacing: -.02em; }
.meth-sub { font-size: .92rem; color: var(--text-muted); margin: 0; line-height: 1.65; }
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
.meth-table { width: 100%; border-collapse: collapse; font-size: .84rem; }
.meth-table thead tr { background: var(--bg-3); }
.meth-table th { padding: .68rem .95rem; text-align: left; border-bottom: 1px solid var(--border); font-size: .74rem; color: var(--text-muted); font-weight: 600; letter-spacing: .06em; text-transform: uppercase; }
.meth-table td { padding: .72rem .95rem; border-bottom: 1px solid var(--border); color: var(--text); vertical-align: top; line-height: 1.55; }
.meth-table tbody tr:hover { background: var(--bg-3); }
.meth-weight { font-weight: 700; color: var(--text); white-space: nowrap; }
.meth-dir { font-weight: 600; font-size: .78rem; white-space: nowrap; }
.meth-up { color: #1a6ab8; }
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
.meth-range-pos { color: #1a6ab8 !important; }
[data-theme="dark"] .meth-range-neg { color: #f87171 !important; }
[data-theme="dark"] .meth-range-pos { color: #93d5f0 !important; }
.meth-comp-desc { font-size: .82rem; color: var(--text-muted); line-height: 1.5; margin-bottom: 0; flex: 1; }
.meth-final-card { border-color: var(--green-400) !important; }
.meth-tip-row { display: flex; gap: .75rem; font-size: .82rem; color: var(--text); align-items: baseline; }
.meth-tip-key { font-weight: 600; min-width: 80px; color: var(--text-muted); flex-shrink: 0; }
.meth-example-card { background: var(--bg-2, var(--surface)); }
.meth-example-intro { font-size: .875rem; color: var(--text-muted); line-height: 1.55; margin: -.35rem 0 1rem; }
.meth-example-grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(260px, .9fr); gap: 1.25rem; align-items: start; }
.meth-example-table { font-size: .78rem; }
.meth-example-table th, .meth-example-table td { padding: .55rem .65rem; }
.meth-example-note { font-size: .72rem; color: var(--text-muted); line-height: 1.5; margin: .65rem 0 0; }
.meth-example-note code { font-family: monospace; }
.meth-example-copy { font-size: .82rem; color: var(--text); line-height: 1.55; }
.meth-example-copy p { margin: 0 0 .65rem; }
.meth-example-copy .meth-formula-box { margin: .75rem 0; }
.meth-example-copy .meth-formula-box code { font-size: .76rem; }
.meth-example-footnote { margin-top: 1rem; padding-top: .75rem; border-top: 1px solid var(--border); font-size: .78rem; color: var(--text-muted); line-height: 1.55; }
.meth-example-footnote code { font-family: monospace; }
.table-wrap { overflow-x: auto; }
@media (max-width: 640px) {
  .meth-section-head { flex-direction: column; }
  .meth-table th:nth-child(4), .meth-table td:nth-child(4) { display: none; }
  .meth-example-grid { grid-template-columns: 1fr; }
  .meth-example-table th:nth-child(4), .meth-example-table td:nth-child(4) { display: table-cell; }
}
</style>
