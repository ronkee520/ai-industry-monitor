/* ═══════════════════════════════════════════════════════════════════
   AI Industry Monitor — Frontend Rendering Engine
   Vanilla JS · Zero dependencies · JSON API driven
   ═══════════════════════════════════════════════════════════════════ */
(() => {
  "use strict";

  // ── Constants ──────────────────────────────────────────────────
  const ROOT = window.DASHBOARD_ROOT || "./";
  const ROUTES = {
    overview:    ["/", "/index.html"],
    token:       ["/token/", "/token", "/token/index.html"],
    business:    ["/business/", "/business", "/business/index.html"],
    compute:     ["/compute/", "/compute", "/compute/index.html"],
    "supply-chain": ["/supply-chain/", "/supply-chain", "/supply-chain/index.html"],
    investment:  ["/investment/", "/investment", "/investment/index.html"],
    methodology: ["/methodology/", "/methodology", "/methodology/index.html"],
  };

  // ── Route Detection ────────────────────────────────────────────
  function detectTab() {
    const p = window.location.pathname.replace(/\/+$/, "") || "/";
    for (const [tab, paths] of Object.entries(ROUTES)) {
      if (paths.some(x => p === x || p.endsWith(x))) return tab;
    }
    return "overview";
  }
  const CURRENT_TAB = detectTab();

  // ── DOM ref ────────────────────────────────────────────────────
  const app = document.getElementById("app");

  // ── Helpers ────────────────────────────────────────────────────
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const fmtNum = (v, d = 1) => {
    if (v == null || !Number.isFinite(Number(v))) return "—";
    return Number(v).toLocaleString("zh-CN", { minimumFractionDigits: d, maximumFractionDigits: d });
  };

  const fmtUSD = (v, d = 3) => {
    if (v == null || !Number.isFinite(Number(v))) return "—";
    return "$" + fmtNum(v, d);
  };

  const fmtPct = v => {
    if (v == null || !Number.isFinite(Number(v))) return "—";
    const n = Number(v);
    return (n >= 0 ? "+" : "") + n.toFixed(1) + "%";
  };

  const pctClass = v => v == null || !Number.isFinite(Number(v)) ? "" : (Number(v) >= 0 ? "positive" : "negative");

  const fmtDate = s => {
    if (!s) return "—";
    try { return new Date(s).toLocaleString("zh-CN", { hour12: false }); }
    catch { return s; }
  };

  const fmtDateShort = s => {
    if (!s) return "—";
    return s.slice(0, 10);
  };

  const sourceLink = (url, label) => url
    ? `<a href="${esc(url)}" target="_blank" rel="noopener" class="source-link">${esc(label || url)} ↗</a>`
    : `<span class="tag missing">来源缺失</span>`;

  // ── Badge renderers ────────────────────────────────────────────
  function badgeConfidence(c) {
    const map = { verified: "tag verified", sample: "tag sample", missing: "tag missing",
      reported: "tag reported", inferred: "tag reported", stale_fallback: "tag stale",
      manual_required: "tag manual", high: "tag verified", medium: "tag reported",
      limited: "tag manual" };
    return `<span class="${map[c] || 'tag missing'}">${esc(c)}</span>`;
  }

  function badgeRegion(r) {
    const map = { domestic: "tag domestic", overseas: "tag overseas", global: "tag" };
    const label = { domestic: "国内", overseas: "海外", global: "全球" };
    return `<span class="${map[r] || 'tag'}">${esc(label[r] || r)}</span>`;
  }

  function badgeFreshness(f) {
    if (!f) return `<span class="tag missing">—</span>`;
    const s = f.status || "missing";
    const map = { fresh: "tag fresh", stale: "tag stale", very_stale: "tag stale", missing: "tag missing" };
    const d = f.age_days != null ? ` (${f.age_days}d)` : "";
    return `<span class="${map[s] || 'tag missing'}">${esc(s)}${d}</span>`;
  }

  function badgeEvidence(e) {
    const map = { official_pricing: "tag verified", company_disclosure: "tag verified",
      media_report: "tag reported", public_snapshot: "tag reported",
      sample: "tag sample", missing: "tag missing", manual_required: "tag manual",
      stale_fallback: "tag stale", ok: "tag verified", error: "tag error",
      partial_dynamic: "tag manual" };
    return `<span class="${map[e] || 'tag missing'}">${esc(e)}</span>`;
  }

  function badgeSourceTier(t) {
    const map = { 1: "tag t1", 2: "tag t2", 3: "tag t3" };
    return `<span class="${map[t] || 'tag missing'}">T${esc(t)}</span>`;
  }

  function badgeStatus(s) {
    const map = { ok: "tag verified", partial: "tag manual", skipped: "tag stale", error: "tag error", stale_fallback: "tag stale" };
    return `<span class="${map[s] || 'tag missing'}">${esc(s || "unknown")}</span>`;
  }

  // ── Value renderer — never show 0 for missing ──────────────────
  function fmtValue(v, nullLabel) {
    if (v === null || v === undefined) return `<span class="tag missing">${nullLabel || "待补充"}</span>`;
    if (typeof v === "number") return fmtNum(v);
    return esc(String(v));
  }

  // ── Data Loader ────────────────────────────────────────────────
  async function loadDashboard() {
    const url = ROOT + "api/dashboard.json";
    try {
      const resp = await fetch(url, { cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    } catch (err) {
      if (err.message.includes("Failed to fetch") || err.name === "TypeError") throw new Error("暂时无法读取最新数据，请稍后刷新页面。");
      throw err;
    }
  }

  // ── Render Entry Point ─────────────────────────────────────────
  async function render() {
    try {
      const D = await loadDashboard();
      renderHeader(D);
      setActiveTab();
      switch (CURRENT_TAB) {
        case "overview":    renderOverview(D); break;
        case "token":        renderToken(D); break;
        case "business":     renderBusiness(D); break;
        case "compute":      renderCompute(D); break;
        case "supply-chain": renderSupplyChain(D); break;
        case "investment":   renderInvestment(D); break;
        case "methodology":  renderMethodology(D); break;
        default:             renderOverview(D);
      }
    } catch (err) {
      app.innerHTML = `<section class="error-state">
        <h3>数据加载失败</h3>
        <p>${esc(err.message).replace(/\n/g,"<br>")}</p>
      </section>`;
    }
  }

  // ── Header ─────────────────────────────────────────────────────
  function renderHeader(D) {
    const m = D.meta || {};
    const h = D.health || {};
    const el = document.getElementById("header-meta");
    const state = h.status || "unknown";
    const stateLabel = { ok: "LIVE", degraded: "PARTIAL", error: "REVIEW", unknown: "UNKNOWN" }[state] || state.toUpperCase();
    const stateTitle = state === "degraded" ? "部分外部来源暂不可用或使用最近一次成功快照；已发布数据仍保留来源与新鲜度标记。" : "数据管线运行状态";
    el.innerHTML = `<span class="snapshot-status status-${esc(state)}" title="${esc(stateTitle)}"><i></i>${esc(stateLabel)}</span>
      <span class="snapshot-copy"><b>最新快照 ${esc(fmtDate(m.generated_at))}</b>
      ${esc(m.schedule || "")}</span>`;
    document.title = m.title || "AI Industry Monitor";
  }

  function setActiveTab() {
    document.querySelectorAll(".tab").forEach(t => {
      t.classList.toggle("active", t.dataset.tab === CURRENT_TAB);
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // TAB 1: Overview / AI Cycle
  // ═══════════════════════════════════════════════════════════════
  function renderOverview(D) {
    const o = D.overview || {};
    const c = o.cycle || {};
    const k = D.kpis || {};
    const h = D.health || {};
    const n = D.news || [];

    const isPreliminary = c.insufficient_data || c.sample_based || c.confidence === "limited";
    const hasRisk = c.risk_crowding_score != null;

    app.innerHTML = `
      ${pageHero("ALLOCATION INTELLIGENCE", "AI 产业景气与风险总览", "把模型经济、商业化、算力资本开支与市场价格信号放进同一研究框架。", "公开数据 · 可追溯 · 每日快照")}

      <!-- Stage Card -->
      <section class="section">
        <article class="card stage-card">
          <span class="stage-label ${isPreliminary ? 'sample-stage' : ''}">当前阶段 · ${esc(c.stage_label || "—")}</span>
          <h2>AI 产业周期：${esc(c.stage_label || "数据不足")}</h2>
          <p class="lead">${esc(c.stage_description || stageDescription(c.stage_id))}</p>
          <div class="stage-scores">
            <div class="score-item"><b>${esc(fmtNum(c.industry_development_score, 1))}</b>产业发展强度 / 100</div>
            <div class="score-item"><b>${hasRisk ? esc(fmtNum(c.risk_crowding_score, 1)) : "—"}</b>市场拥挤代理</div>
            <div class="score-item"><b>${c.confidence_score != null ? esc(fmtNum(c.confidence_score, 1)) : "—"}</b>证据覆盖度 / 100</div>
            <div class="score-item"><b>${esc(c.missing_component_count ?? c.missing_factor_count ?? 0)}</b>缺失子因子</div>
          </div>
        </article>
      </section>

      <!-- Factor Scores -->
      <section class="section">
        <div class="section-head"><h2>产业周期因子</h2><p>技术、商业化、资本投入与市场风险联合观察 · 证据等级 ${esc((c.confidence || "—").toUpperCase())}</p></div>
        <div class="grid-2">
          ${renderFactorCard("技术成熟度", c.factor_scores?.technology_maturity, "Token成本·价格覆盖·百万Token上下文·多模态")}
          ${renderFactorCard("商业化兑现度", c.factor_scores?.commercialization, "ARR/年化收入·活跃用户·企业客户·披露覆盖")}
          ${renderFactorCard("资本投入强度", c.factor_scores?.capital_investment, "CSP CAPEX·披露覆盖·融资·GPU价格趋势")}
          <article class="card">
            <h3>市场价格拥挤度（代理）</h3>
            <p class="subtitle">3个月动量·上涨广度·距52周高点</p>
            <div class="bar-list">
              <div class="bar-row">
                <div class="bar-label">市场拥挤代理</div>
                <div class="bar-track"><div class="bar-fill" style="width:${hasRisk ? c.risk_crowding_score : 0}%;background:var(--warn)"></div></div>
                <div class="bar-value">${hasRisk ? fmtNum(c.risk_crowding_score, 0) + " / 100" : "待数据完善"}</div>
              </div>
            </div>
            ${c.risk_note ? `<p style="font-size:11px;color:var(--muted);margin-top:8px">${esc(c.risk_note)}</p>` : ""}
          </article>
        </div>
        ${renderCycleMethodology(c)}
      </section>

      <!-- KPIs -->
      <section class="section">
        <div class="section-head"><h2>关键指标</h2></div>
        <div class="kpi-grid">
          ${kpiCard("监测公司", k.companies)}
          ${kpiCard("有定价模型", k.models_with_pricing)}
          ${kpiCard("数据源健康", h.source_success_rate || "0/0")}
          ${kpiCard("商业披露", k.business_disclosures ?? k.arr_disclosures)}
          ${kpiCard("GPU价格", h.gpu_records || 0)}
          ${kpiCard("行情覆盖", h.market_records || 0)}
          ${kpiCard("产业动态", n.length)}
          ${kpiCard("数据覆盖", (c.data_coverage?.pricing_real || 0) + (c.data_coverage?.business_real || 0), "条有效记录")}
        </div>
      </section>

      ${renderNewsPreview(n)}
    `;
  }

  function renderFactorCard(title, factor, desc) {
    const score = factor?.score ?? null;
    return `<article class="card">
      <h3>${esc(title)}</h3><p class="subtitle">${esc(desc)} · 权重 ${esc(factor?.weight || "—")}</p>
      <div class="bar-list"><div class="bar-row">
        <div class="bar-label">${esc(title)}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${score != null ? score : 0}%"></div></div>
        <div class="bar-value">${score != null ? fmtNum(score, 0) + " / 100" : "待数据完善"}</div>
      </div></div>
    </article>`;
  }

  function renderCycleMethodology(c) {
    const method=c.methodology||{}, factors=c.factor_scores||{}, risk=c.risk_details||{};
    const factorSections=[
      ["技术成熟度",factors.technology_maturity],
      ["商业化兑现度",factors.commercialization],
      ["资本投入强度",factors.capital_investment],
      ["市场价格拥挤代理",risk],
    ].filter(([,factor])=>factor);
    const confidenceReasons=(c.confidence_reasons||[]).map(x=>`<li>${esc(x)}</li>`).join("");
    const stage=c.stage_decision||{};
    const checks=(stage.checks||[]).map(row=>`<tr class="${row.matched?'method-match':''}">
      <td><strong>${esc(row.label)}</strong></td><td>${esc(row.rule)}</td>
      <td>${row.matched?'<span class="tag verified">本期命中</span>':'<span class="tag missing">未命中</span>'}</td>
    </tr>`).join("");
    const triggers=(stage.deterioration_triggers||[]).map(row=>`<tr>
      <td>${esc(row.label)}</td><td>${esc(row.rule)}</td><td>${row.available?(row.triggered?'<span class="tag error">触发</span>':'<span class="tag verified">未触发</span>'):'<span class="tag missing">数据不可用</span>'}</td>
    </tr>`).join("");
    return `<details class="cycle-methodology">
      <summary><span>评分公式、数据来源与本期完整计算</span><small>展开查看每个原始值、标准化、权重、贡献和阶段判定</small></summary>
      <div class="cycle-method-body">
        <div class="method-callout"><strong>先说结论：</strong>${esc(method.positioning||"")} 本期证据覆盖度为 <b>${esc(fmtNum(c.confidence_score,1))}/100（${esc((c.confidence||"—").toUpperCase())}）</b>。${esc(c.limitations||"")}</div>
        <div class="method-formulas">
          <div><span>产业发展强度</span><b>${esc(method.industry_calculation||"—")}</b><small>${esc(method.industry_formula||"")}</small></div>
          <div><span>市场拥挤代理</span><b>${esc(method.risk_calculation||"—")}</b><small>${esc(method.risk_formula||"")}</small></div>
        </div>
        ${factorSections.map(([title,factor])=>renderCycleFactorBreakdown(title,factor)).join("")}
        <section class="method-subsection">
          <h4>当前阶段如何判定</h4>
          <p class="method-note">按固定优先级判断：${esc(stage.evaluation_order||"—")}。本期命中规则：<strong>${esc(stage.matched_rule||"—")}</strong>。</p>
          <div class="table-wrap"><table class="cycle-method-table"><thead><tr><th>候选阶段</th><th>判定规则</th><th>本期结果</th></tr></thead><tbody>${checks}</tbody></table></div>
        </section>
        <section class="method-subsection">
          <h4>周期调整期的恶化信号</h4>
          <p class="method-note">至少 ${esc(stage.deterioration_required??2)} 项明确触发才进入周期调整期；缺失数据不会被当作“未触发”。本期触发 ${esc(stage.deterioration_trigger_count??0)} 项。</p>
          <div class="table-wrap"><table class="cycle-method-table"><thead><tr><th>信号</th><th>规则</th><th>状态</th></tr></thead><tbody>${triggers}</tbody></table></div>
        </section>
        <section class="method-subsection method-grid-2">
          <div><h4>缺失与归一化规则</h4><p>${esc(method.normalisation||"")}</p><p>${esc(method.missing_policy||"")}</p></div>
          <div><h4>证据覆盖度如何计算</h4><p>${esc(c.confidence_dimensions?.formula||"")}</p><ul><li>可计算子因子覆盖：${esc(fmtNum(c.confidence_dimensions?.component_coverage_pct,1))}%</li><li>T1/T2强证据占比：${esc(fmtNum(c.confidence_dimensions?.strong_evidence_pct,1))}%</li><li>自动数据源成功率：${esc(fmtNum(c.confidence_dimensions?.source_reliability_pct,1))}%</li></ul>${confidenceReasons?`<p>后续增强项：</p><ul>${confidenceReasons}</ul>`:'<p>当前未发现额外降级项。</p>'}</div>
        </section>
        <p class="method-reference">方法设计参考：${method.method_reference?sourceLink(method.method_reference.url,method.method_reference.name):"—"}</p>
      </div>
    </details>`;
  }

  function renderCycleFactorBreakdown(title, factor) {
    const rows=(factor.components||[]).map(item=>{
      const sources=(item.sources||[]).map(s=>`${sourceLink(s.url,s.name)}${s.tier?` ${badgeSourceTier(s.tier)}`:""}`).join("<br>")||'<span class="tag missing">暂无来源</span>';
      return `<tr>
        <td><strong>${esc(item.label)}</strong><small>${esc(item.formula||"")}</small></td>
        <td>${esc(item.raw_display||"—")}<small>样本 ${esc(item.sample_size??0)}</small></td>
        <td class="num">${item.score==null?"—":esc(fmtNum(item.score,1))}</td>
        <td class="num">${item.score==null?"—":esc(fmtNum((item.effective_weight||0)*100,1))+"%"}</td>
        <td class="num">${item.contribution==null?"—":esc(fmtNum(item.contribution,1))}</td>
        <td>${sources}${item.note?`<small>${esc(item.note)}</small>`:""}</td>
      </tr>`;
    }).join("");
    return `<section class="method-subsection"><h4>${esc(title)}：${factor.score==null?"—":esc(fmtNum(factor.score,1))+" / 100"}${factor.contribution!=null?` · 对产业总分贡献 ${esc(fmtNum(factor.contribution,1))}`:""}</h4>
      <div class="table-wrap"><table class="cycle-method-table"><thead><tr><th>子因子与公式</th><th>本期原始值</th><th>分数</th><th>有效权重</th><th>贡献</th><th>来源/说明</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
  }

  function kpiCard(label, value, suffix) {
    return `<article class="kpi-card">
      <div class="kpi-label">${esc(label)}</div>
      <div class="kpi-value">${esc(value ?? "—")}</div>
      <div class="kpi-meta">${esc(suffix || "")}</div>
    </article>`;
  }

  function pageHero(kicker, title, description, meta) {
    return `<section class="page-hero">
      <div><span class="page-kicker">${esc(kicker)}</span><h1>${esc(title)}</h1><p>${esc(description)}</p></div>
      ${meta ? `<span class="page-hero-meta">${esc(meta)}</span>` : ""}
    </section>`;
  }

  function renderNewsPreview(n) {
    if (!n || !n.length) return "";
    const items = n.slice(0, 6).map(x => `<div class="news-item">
      <div class="news-title">${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>` : esc(x.title)}</div>
      <div class="news-meta">${esc(x.publisher || "—")} · ${esc(fmtDateShort(x.published_at))}</div>
    </div>`).join("");
    return `<section class="section"><div class="card">
      <h3>AI 产业动态</h3><div class="news-list">${items}</div>
    </div></section>`;
  }

  function stageDescription(id) {
    const m = {
      tech_validation: "技术路线探索期。Token价格处于高位，商业模式未成形，资本投入相对谨慎。",
      infra_expansion: "Capex快速增长，GPU供不应求，Token价格开始快速下降。基础设施层持续受益。",
      commercialization: "产业发展代理达到55以上且市场拥挤代理低于70；表示技术、商业与资本投入证据较强，不等同于全行业已经盈利。",
      valuation_crowding: "⚠️ 产业发展代理较强，同时市场价格拥挤代理达到70以上。当前未纳入完整估值与ETF申赎，只作为价格风险警戒。",
      cyclical_adjustment: "⚠️ 产能过剩担忧，Capex增速放缓。行业进入出清或再平衡。由边际恶化信号触发。",
      insufficient_data: "当前的真实定价、商业化与资本开支数据覆盖不足，暂不输出产业周期判断。",
    };
    return m[id] || "";
  }

  // ═══════════════════════════════════════════════════════════════
  // TAB 2: Token Economy
  // ═══════════════════════════════════════════════════════════════
  function renderToken(D) {
    const tp = D.token_pricing || {};
    const records = tp.records || [];
    const historyRecords = records.filter(r => r.blended_cost_usd != null);
    const validRecords = records.filter(r => r.value != null);
    const latestModels = tp.latest_models || [];
    const blendedRecords = records.filter(r => r.blended_cost_usd != null);
    const cheapest = blendedRecords.length ? blendedRecords.reduce((a, b) => (a.blended_cost_usd < b.blended_cost_usd ? a : b)) : null;
    const costs = blendedRecords.map(r => r.blended_cost_usd).sort((a, b) => a - b);
    const median = costs.length ? costs[Math.floor(costs.length / 2)] : null;

    app.innerHTML = `
      ${pageHero("MODEL ECONOMICS", "Token 经济", "比较主流模型的输入、输出与标准化混合成本，跟踪模型发布与推理价格曲线。", `${validRecords.length} 条有效价格`)}

      <section class="section">
        <div class="kpi-grid">
          ${kpiCard("价格记录", records.length)}
          ${kpiCard("有效价格", validRecords.length)}
          ${kpiCard("最新模型", latestModels.length, "自动跟踪")}
          ${kpiCard("最低混合成本", cheapest ? fmtUSD(cheapest.blended_cost_usd) : "—", cheapest ? esc(cheapest.company_name + " · " + cheapest.metric_name.slice(0,30)) : "")}
          ${kpiCard("中位混合成本", median ? fmtUSD(median) : "—")}
        </div>
      </section>

      ${latestModels.length ? `<section class="section">
        <div class="section-head"><h2>最新模型动态</h2><p>按公开 API 市场首次收录时间排序</p></div>
        <div class="card"><div class="table-wrap"><table>
          <thead><tr><th>厂商</th><th>模型</th><th>收录日期</th><th>输入 / 1M</th><th>输出 / 1M</th><th>上下文</th><th>来源</th></tr></thead>
          <tbody>${latestModels.map(r => `<tr>
            <td>${badgeRegion(r.region)} <strong>${esc(r.company_name)}</strong></td>
            <td>${esc(r.name || r.provider_model_id)}</td>
            <td>${esc(r.released_at || "—")}</td>
            <td class="num">${fmtUSD(r.input_per_m)}</td>
            <td class="num">${fmtUSD(r.output_per_m)}</td>
            <td class="num">${r.context_window_k ? esc(fmtNum(r.context_window_k, 0)) + "K" : "—"}</td>
            <td>${sourceLink(r.source_url, r.source_name)}</td>
          </tr>`).join("")}</tbody>
        </table></div></div>
      </section>` : ""}

      <!-- Blended Cost Chart -->
      <section class="section">
        <div class="section-head"><h2>标准化混合成本 (USD / 百万总 Tokens)</h2><p>input × 0.65 + output × 0.35</p></div>
        <div class="card">
          ${renderBarChart(blendedRecords, "blended_cost_usd", r => `${r.company_name} · ${r.model_id}`, r => {
            if (r.blended_cost_usd == null) return "—";
            return fmtUSD(r.blended_cost_usd);
          }, r => r.region === "domestic" ? "domestic" : "")}
          <p class="subtitle">${esc(tp.methodology?.blended_formula || "")}</p>
        </div>
      </section>

      <!-- Filterable Table -->
      <section class="section">
        <div class="section-head"><h2>价格明细</h2></div>
        <div class="card">
          <div class="controls">
            <select id="token-region"><option value="">全部地区</option><option value="domestic">国内</option><option value="overseas">海外</option></select>
            <select id="token-confidence"><option value="">全部状态</option><option value="verified">官方核验</option><option value="inferred">市场快照</option><option value="missing">暂无价格</option></select>
            <input id="token-search" type="search" placeholder="搜索公司或模型…">
          </div>
          <div class="table-wrap"><table id="token-table">
            <thead><tr>
              <th data-key="region">地区</th><th data-key="company_name">公司</th><th data-key="model_id">模型</th>
              <th data-key="model_status">状态</th><th data-key="value">价格(原币)</th>
              <th data-key="blended_cost_usd">混合USD</th><th data-key="change_pct">变化</th>
              <th data-key="confidence">可信度</th><th data-key="freshness">新鲜度</th><th>来源</th>
            </tr></thead>
            <tbody id="token-tbody"></tbody>
          </table></div>
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>历史趋势</h2><p>官方价格事件与每日市场快照；价格未变化时曲线保持水平</p></div>
        <div class="card"><div class="controls"><select id="history-model">${historyRecords.map(r=>`<option value="${esc(r.metric_id)}">${esc(r.company_name)} · ${esc(r.tier === "aggregator_route" ? (r.provider_model_id || r.model_id) : r.model_id)}${r.tier === "aggregator_route" ? " · 路由市场" : r.source_tier === 1 ? " · 官方" : ""}</option>`).join("")}</select><select id="history-range" aria-label="历史时间范围"><option value="90">近 90 天</option><option value="180">近 180 天</option><option value="365">近 1 年</option><option value="all" selected>全部历史</option></select><button class="button" id="download-token-csv">导出当前价格 CSV</button></div><div id="history-chart" class="history-chart"></div><p id="history-note" class="history-note"></p></div>
      </section>
    `;

    wireTokenTable(records);
    wireHistoryChart(D.history?.token_pricing || [], records);
    document.getElementById("download-token-csv")?.addEventListener("click",()=>downloadCsv("token-pricing.csv",records));
    makeSortable("token-table");
  }

  function wireHistoryChart(history, records) {
    const select=document.getElementById("history-model"), rangeSelect=document.getElementById("history-range"), host=document.getElementById("history-chart"), note=document.getElementById("history-note");
    if(!select||!rangeSelect||!host||!note) return;
    const draw=()=>{
      // 同一天只保留最后一条有效记录，避免重复点让曲线产生误导。
      const byDate=new Map();
      history.forEach(x=>{
        const rawValue=x.blended_cost_usd??x.value;
        const value=rawValue===null||rawValue==="" ? NaN : Number(rawValue);
        if(x.metric_id===select.value && x.date && Number.isFinite(value)) byDate.set(x.date,{...x,_value:value});
      });
      const allPoints=[...byDate.values()].sort((a,b)=>a.date.localeCompare(b.date));
      if(!allPoints.length){host.innerHTML='<div class="empty-state">该模型目前没有有效价格快照。</div>';note.textContent="";return;}
      const rangeDays=Number(rangeSelect.value);
      const latestMs=Date.parse(`${allPoints.at(-1).date}T00:00:00Z`);
      const cutoffMs=Number.isFinite(rangeDays) ? latestMs-(rangeDays-1)*86400000 : -Infinity;
      const points=allPoints.filter(p=>Date.parse(`${p.date}T00:00:00Z`)>=cutoffMs);

      const vals=points.map(x=>x._value), min=Math.min(...vals), max=Math.max(...vals), span=max-min;
      const left=64, right=770, top=46, bottom=178;
      // 价格不变时给纵轴一个对称范围，让折线显示在图表中央而不是与横轴重合。
      const padding=span===0 ? Math.max(Math.abs(max)*0.08,0.1) : span*0.15;
      const yMin=min-padding, yMax=max+padding;
      const firstMs=Date.parse(`${points[0].date}T00:00:00Z`), lastMs=Date.parse(`${points.at(-1).date}T00:00:00Z`);
      const coverageDays=Math.floor((lastMs-firstMs)/86400000)+1;
      const xAt=p=>points.length===1 || lastMs===firstMs ? (left+right)/2 : left+(Date.parse(`${p.date}T00:00:00Z`)-firstMs)/(lastMs-firstMs)*(right-left);
      const yAt=v=>bottom-(v-yMin)/(yMax-yMin)*(bottom-top);
      const coords=points.map(p=>`${xAt(p).toFixed(1)},${yAt(p._value).toFixed(1)}`).join(" ");
      const gridValues=[yMax,(yMin+yMax)/2,yMin];
      const grid=gridValues.map(v=>{
        const y=yAt(v).toFixed(1);
        return `<line class="history-grid" x1="${left}" y1="${y}" x2="${right}" y2="${y}"/><text class="history-axis-label" x="4" y="${Number(y)+4}">${esc(fmtUSD(v))}</text>`;
      }).join("");
      const eventPoints=points.filter((p,i)=>i===0||i===points.length-1||String(p.event_type||"").includes("change")||String(p.event_type||"").includes("effective"));
      const dots=eventPoints.map(p=>`<circle class="history-point" cx="${xAt(p).toFixed(1)}" cy="${yAt(p._value).toFixed(1)}" r="4"><title>${esc(p.date)} · ${esc(fmtUSD(p._value))}</title></circle>`).join("");
      const dateLabels=points.length===1
        ? `<text class="history-date" x="${xAt(points[0])}" y="211" text-anchor="middle">${esc(points[0].date)}</text>`
        : `<text class="history-date" x="${left}" y="211">${esc(points[0].date)}</text><text class="history-date" x="${right}" y="211" text-anchor="end">${esc(points.at(-1).date)}</text>`;
      const summary=points.length===1
        ? `当前 ${fmtUSD(max)} · 仅 1 个有效快照`
        : span===0
          ? `价格未变 ${fmtUSD(max)} · ${points.length} 个日值 · 覆盖 ${coverageDays} 天`
          : `最高 ${fmtUSD(max)} · 最低 ${fmtUSD(min)} · ${points.length} 个日值 · 覆盖 ${coverageDays} 天`;

      host.innerHTML=`<svg viewBox="0 0 800 225" role="img" aria-label="${esc(summary)}">${grid}<text class="history-summary" x="${left}" y="24">${esc(summary)}</text><polyline class="history-line" points="${coords}"/>${dots}${dateLabels}</svg>`;
      const officialAnchor=points.find(p=>p.event_type==="official_price_effective"||p.event_type==="official_price_reference");
      const hasArchive=points.some(p=>String(p.event_type||"").startsWith("archived_price_"));
      note.textContent=officialAnchor
        ? hasArchive
          ? `历史包含 ${officialAnchor.date} 起的官方生效价格，并衔接公开路由市场逐日变更档案；无变更日延续最近一次已观测价格。`
          : `历史起点为 ${officialAnchor.date} 的官方价格生效事件；在下一次已核验调价前按有效价格区间连续展示。`
        : hasArchive
          ? `该曲线由公开路由市场的逐日价格变更档案重建；无变更日延续最近一次已观测价格，不代表虚构交易波动。`
        : points.length===1
          ? `该指标尚无可核验的更早价格，当前展示首次真实收录；系统将每日追加快照。`
          : `该曲线来自每日真实快照；价格未调整时保持水平。`;
    };
    select.addEventListener("change",draw);
    rangeSelect.addEventListener("change",draw);
    draw();
  }

  function downloadCsv(filename, rows) {
    if(!rows.length) return;
    const keys=["company_name","model_id","input_per_m","output_per_m","blended_cost_usd","currency","as_of_date","confidence","source_url"];
    const q=v=>'"'+String(v??"").replace(/"/g,'""')+'"';
    const csv='\ufeff'+[keys.join(","),...rows.map(r=>keys.map(k=>q(r[k])).join(","))].join("\n");
    const a=document.createElement("a"); a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"})); a.download=filename; a.click(); URL.revokeObjectURL(a.href);
  }

  function renderBarChart(rows, valField, labelFn, fmtFn, cls, barCls) {
    if (!rows.length) return `<div class="empty-state"><h3>当前暂无可用数据</h3></div>`;
    const vals = rows.map(r => Number(r[valField])).filter(v => v != null && Number.isFinite(v));
    const max = Math.max(...vals, 1);
    return `<div class="bar-list">${rows.map(r => {
      const v = Number(r[valField]);
      const w = v != null && Number.isFinite(v) ? Math.max(1, (v / max) * 100) : 0;
      const c = typeof cls === "function" ? cls(r) : "";
      const bc = typeof barCls === "function" ? barCls(r) : "";
      return `<div class="bar-row">
        <div class="bar-label">${esc(typeof labelFn === "function" ? labelFn(r) : r[labelFn])}<small>${esc(r.region === "domestic" ? "国内" : "海外")}</small></div>
        <div class="bar-track"><div class="bar-fill ${c} ${bc}" style="width:${w}%"></div></div>
        <div class="bar-value">${typeof fmtFn === "function" ? fmtFn(r) : fmtUSD(v)}</div>
      </div>`;
    }).join("")}</div>`;
  }

  function wireTokenTable(records) {
    const regionSel = document.getElementById("token-region");
    const confSel = document.getElementById("token-confidence");
    const search = document.getElementById("token-search");
    const tbody = document.getElementById("token-tbody");

    const render = () => {
      const reg = regionSel.value;
      const conf = confSel.value;
      const q = (search.value || "").trim().toLowerCase();
      const rows = records.filter(r =>
        (!reg || r.region === reg) &&
        (!conf || r.confidence === conf || (conf === "missing" && r.value == null)) &&
        (!q || `${r.company_name} ${r.model_id} ${r.metric_name}`.toLowerCase().includes(q))
      );
      tbody.innerHTML = rows.length ? rows.map(r => `<tr>
        <td>${badgeRegion(r.region)}</td>
        <td><strong>${esc(r.company_name)}</strong></td>
        <td>${esc(r.model_id || r.metric_name)}</td>
        <td>${badgeConfidence(r.model_status)}</td>
        <td class="num">${fmtValue(r.value)} ${esc(r.currency || "")}</td>
        <td class="num">${fmtUSD(r.blended_cost_usd)}</td>
        <td class="num ${pctClass(r.change_pct)}">${fmtPct(r.change_pct)}</td>
        <td>${badgeConfidence(r.confidence)} ${badgeEvidence(r.evidence_status)}</td>
        <td>${badgeFreshness(r.freshness)}</td>
        <td>${sourceLink(r.source_url, r.source_name)}</td>
      </tr>`).join("") : `<tr><td colspan="10" class="empty-state">没有匹配数据</td></tr>`;
    };
    regionSel?.addEventListener("change", render);
    confSel?.addEventListener("change", render);
    search?.addEventListener("input", render);
    render();
  }

  // ═══════════════════════════════════════════════════════════════
  // TAB 3: Business / Commercialization
  // ═══════════════════════════════════════════════════════════════
  function renderBusiness(D) {
    const biz = D.business || {};
    const records = biz.records || [];
    const companies = biz.companies || [];
    const withValue = records.filter(r => r.value != null);
    const missing = records.filter(r => r.value == null);
    const byCompany = {};
    records.forEach(r => (byCompany[r.company_id] ||= []).push(r));
    const latestOf = (rows, prefixes) => rows
      .filter(r => prefixes.some(prefix => (r.metric_id || "").startsWith(prefix)))
      .sort((a, b) => String(b.as_of_date || "").localeCompare(String(a.as_of_date || "")))[0];
    const matrixRows = companies.map(company => {
      const rows = byCompany[company.id] || [];
      const cells = {
        runRate: latestOf(rows, ["arr::", "revenue_run_rate::"]),
        revenue: latestOf(rows, ["revenue::"]),
        users: latestOf(rows, ["user_count::"]),
        enterprise: latestOf(rows, ["enterprise_customers::", "high_value_customers::", "specialized_enterprise_customers::"]),
        funding: latestOf(rows, ["funding::"]),
        valuation: latestOf(rows, ["valuation::"]),
      };
      const coverage = Object.values(cells).filter(r => r?.value != null).length;
      const latestDate = rows.reduce((max, r) => String(r.as_of_date || "") > max ? String(r.as_of_date) : max, "");
      return { company, rows, cells, coverage, latestDate };
    }).sort((a, b) => b.coverage - a.coverage || a.company.name.localeCompare(b.company.name, "zh-CN"));

    app.innerHTML = `
      ${pageHero("COMMERCIALIZATION", "商业化进程", "以统一指标矩阵比较模型公司的收入、用户、企业采用、融资与估值；不同口径保留原始定义。", `${companies.length} 家公司 · ${withValue.length} 条有效披露`)}

      <section class="section">
        <div class="kpi-grid">
          ${kpiCard("监测公司", companies.length)}
          ${kpiCard("有效披露", withValue.length)}
          ${kpiCard("T1官方记录", withValue.filter(r => r.source_tier === 1).length)}
          ${kpiCard("有商业采用数据", matrixRows.filter(r => r.cells.users?.value != null || r.cells.enterprise?.value != null).length)}
        </div>
      </section>

      <section class="section">
        <div class="section-head"><h2>公司横向对比矩阵</h2><p>每家公司使用相同列；“未单独披露”不代表数值为0。</p></div>
        <div class="card">
          <div class="controls matrix-controls">
            <select id="business-region"><option value="">全部地区</option><option value="domestic">国内</option><option value="overseas">海外</option></select>
            <input id="business-search" type="search" placeholder="搜索公司或代码">
            <span class="matrix-legend">单元格依次显示：数值 · 期间/口径 · 来源</span>
          </div>
          <div class="table-wrap business-matrix-wrap"><table id="business-matrix" class="business-matrix">
            <thead><tr>
              <th>公司</th><th>ARR / 年化运行率</th><th>财务收入</th><th>活跃用户</th>
              <th>企业客户 / 采用</th><th>最近融资</th><th>最新估值</th><th>覆盖 / 更新</th>
            </tr></thead>
            <tbody>${matrixRows.map(({company, cells, coverage, latestDate}) => `<tr data-region="${esc(company.region)}" data-search="${esc(`${company.name} ${company.name_en || ""} ${company.ticker || ""}`.toLowerCase())}">
              <td class="matrix-company">${badgeRegion(company.region)}<strong>${esc(company.name)}</strong><small>${esc(company.ticker || (company.listed ? "上市集团部门" : "非上市/研究机构"))}</small></td>
              <td>${renderBusinessMetricCell(cells.runRate)}</td>
              <td>${renderBusinessMetricCell(cells.revenue)}</td>
              <td>${renderBusinessMetricCell(cells.users)}</td>
              <td>${renderBusinessMetricCell(cells.enterprise)}</td>
              <td>${renderBusinessMetricCell(cells.funding)}</td>
              <td>${renderBusinessMetricCell(cells.valuation)}</td>
              <td class="matrix-coverage"><strong>${coverage}/6</strong><small>${latestDate ? `更新 ${esc(latestDate)}` : "暂无定量披露"}</small></td>
            </tr>`).join("")}</tbody>
          </table></div>
        </div>
      </section>

      <section class="section">
        <details class="cycle-methodology business-detail">
          <summary><span>逐条原始记录、口径限制与来源</span><small>${records.length} 条记录；用于审计矩阵单元格</small></summary>
          <div class="cycle-method-body"><div class="table-wrap"><table id="biz-table">
            <thead><tr><th data-key="company_name">公司</th><th data-key="metric_name">指标</th><th data-key="value">数值</th><th data-key="period">期间</th><th>证据</th><th>来源与口径</th></tr></thead>
            <tbody>${records.map(r => `<tr><td>${badgeRegion(r.region)} <strong>${esc(r.company_name)}</strong></td><td>${esc(r.metric_name)}</td><td class="num">${renderBusinessValue(r)}</td><td>${esc(r.period || "—")}</td><td>${badgeConfidence(r.confidence)} ${badgeSourceTier(r.source_tier)}</td><td>${sourceLink(r.source_url, r.source_name)}<small class="metric-note">${esc(r.note || "")}</small></td></tr>`).join("")}</tbody>
          </table></div></div>
        </details>
      </section>
    `;

    makeSortable("biz-table");
    const region = document.getElementById("business-region");
    const search = document.getElementById("business-search");
    const filterMatrix = () => {
      const q = (search?.value || "").trim().toLowerCase();
      document.querySelectorAll("#business-matrix tbody tr").forEach(row => {
        row.hidden = !!((region?.value && row.dataset.region !== region.value) || (q && !row.dataset.search.includes(q)));
      });
    };
    region?.addEventListener("change", filterMatrix);
    search?.addEventListener("input", filterMatrix);
  }

  function renderBusinessValue(record) {
    if (!record || record.value == null) return "—";
    const value = Number(record.value);
    if (record.unit === "USD_billion") return `$${fmtNum(value, value < 1 ? 3 : 1)}B`;
    if (record.unit === "EUR_billion") return `€${fmtNum(value, value < 1 ? 3 : 1)}B`;
    if (record.unit === "CNY_billion") return `¥${fmtNum(value, value < 1 ? 3 : 1)}B`;
    if (record.unit === "count") return new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 }).format(value);
    return `${fmtNum(value)} ${esc(record.unit || "")}`;
  }

  function renderBusinessMetricCell(record) {
    if (!record || record.value == null) return `<span class="metric-missing">未单独披露</span>${record?.source_url ? `<small>${sourceLink(record.source_url, "披露边界")}</small>` : ""}`;
    return `<div class="metric-cell" title="${esc(record.note || "")}">
      <strong>${renderBusinessValue(record)}</strong>
      <small>${esc(record.period || "—")} · ${esc(record.metric_name || "")}</small>
      <span>${badgeConfidence(record.confidence)} ${sourceLink(record.source_url, "来源")}</span>
    </div>`;
  }

  // ═══════════════════════════════════════════════════════════════
  // TAB 4: AI Compute & Cloud CAPEX
  // ═══════════════════════════════════════════════════════════════
  function renderCompute(D) {
    const comp = D.compute || {};
    const gpu = comp.gpu || [];
    const capex = comp.capex || [];
    const sources = D.sources || [];
    const gpuSources = sources.filter(s => s.kind && (s.kind.includes("gpu") || s.kind.includes("rental")));
    const pricedGpu = gpu.filter(g => g.value != null);
    const gpuProviders = new Set(pricedGpu.map(g => g.provider).filter(Boolean));
    const gpuModels = new Set(pricedGpu.map(g => g.gpu_model).filter(Boolean));
    const capexCompanies = new Set(capex.filter(r => r.value != null).map(r => r.company_id));

    app.innerHTML = `
      ${pageHero("INFRASTRUCTURE", "AI 算力与云 CAPEX", "从多家GPU云的按需租赁价格与CSP资本开支两端观察基础设施景气；统一口径但保留区域、实例与可用性边界。", `${pricedGpu.length} 条 GPU 价格 · ${capex.length} 条 CAPEX`)}
      <section class="section"><div class="kpi-grid">${kpiCard("GPU供应商",gpuProviders.size)}${kpiCard("GPU型号",gpuModels.size)}${kpiCard("有效价格",pricedGpu.length)}${kpiCard("CAPEX公司",capexCompanies.size)}</div></section>
      <section class="section">
        <div class="section-head"><h2>GPU 按需价格</h2><p>统一为 USD / GPU·小时；对比的是公开展示最低价，不同实例规模、区域、库存、网络和SLA不能直接等同</p></div>

        ${gpu.length ? `<div class="card" style="margin-bottom:14px">
          <h3>GPU 价格记录 (${pricedGpu.length})</h3>
          ${renderBarChart(pricedGpu.slice().sort((a,b)=>(b.value||0)-(a.value||0)).slice(0,20), "value", r => `${r.provider || r.source_name} · ${r.gpu_model || r.metric_name}`, r => fmtUSD(r.value, 2))}
          <div class="table-wrap"><table>
            <thead><tr><th>平台</th><th>GPU</th><th>显存</th><th>USD/GPU·h</th><th>口径</th><th>时间</th><th>来源</th></tr></thead>
            <tbody>${gpu.map(g => `<tr>
              <td><strong>${esc(g.provider || g.source_name)}</strong></td>
              <td>${esc(g.gpu_model || g.metric_name)}</td><td>${g.vram_gb ? esc(g.vram_gb) + " GB" : "—"}</td>
              <td class="num">${g.value != null ? fmtUSD(g.value, 2) : "—"}</td><td>${esc(g.price_type || g.unit || "—")}</td>
              <td>${esc(fmtDateShort(g.as_of_date || g.collected_at))}</td><td>${sourceLink(g.source_url, g.source_name)}</td>
            </tr>`).join("")}</tbody>
          </table></div>
        </div>` : `<div class="empty-state" style="margin-bottom:14px"><h3>当前暂无 GPU 价格</h3></div>`}
      </section>

      <section class="section">
        <div class="section-head"><h2>云厂商 CAPEX</h2><p>SEC 10-K XBRL 实际值；公司整体CAPEX，不等同于纯AI投入</p></div>
        ${capex.length ? `<div class="card">
          ${renderBarChart(capex.slice().sort((a,b)=>(b.value||0)-(a.value||0)), "value", r => `${r.company_name} · ${r.period}`, r => fmtUSD(r.value, 1)+"B")}
          <div class="table-wrap"><table><thead><tr><th>公司</th><th>期间</th><th>CAPEX</th><th>XBRL口径</th><th>截至</th><th>来源</th></tr></thead><tbody>
          ${capex.map(r=>`<tr><td><strong>${esc(r.company_name)}</strong></td><td>${esc(r.period)}</td><td class="num">${fmtUSD(r.value,3)}B</td><td>${esc(r.xbrl_concept||"—")}</td><td>${esc(r.as_of_date)}</td><td>${sourceLink(r.filing_url||r.source_url,"SEC filing")}</td></tr>`).join("")}
          </tbody></table></div></div>` : `<div class="empty-state"><h3>当前暂无 CAPEX 数据</h3></div>`}
      </section>

      <!-- Source Status for GPU-related sources -->
      ${gpuSources.length ? `<section class="section">
        <div class="section-head"><h2>GPU 相关数据源原始状态</h2></div>
        <div class="source-grid">${gpuSources.map(s => `<div class="source-item">
          <div class="source-name">${esc(s.name)}</div>
          <div class="source-status">${badgeEvidence(s.status)} ${s.changed ? '<span class="tag stale">内容变化</span>' : ''} ${s.error ? `<span class="tag error">${esc(s.error)}</span>` : ''}</div>
          <span class="source-url">${sourceLink(s.url, s.url)}</span>
          <small style="color:var(--muted)">${esc(fmtDate(s.checked_at))} · ${esc(s.text_chars || 0)} chars</small>
        </div>`).join("")}</div>
      </section>` : ""}
    `;
  }

  // ═══════════════════════════════════════════════════════════════
  // TAB 5: AI Supply Chain
  // ═══════════════════════════════════════════════════════════════
  function renderSupplyChain(D) {
    const sc = D.supply_chain || {};
    const rows = sc.records || [];
    const latest = {};
    rows.forEach(r => { if (!latest[r.company_id] || r.as_of_date > latest[r.company_id].as_of_date) latest[r.company_id] = r; });
    const current = Object.values(latest);
    app.innerHTML = `
      ${pageHero("VALUE CHAIN", "AI 产业链", "连接模型需求、云基础设施、芯片设计与上游制造，观察利润与投入如何传导。", `${current.length} 家核心公司`)}
      <section class="section"><div class="section-head"><h2>AI 产业链结构</h2><p>供给传导方向：制造/设备/存储 → 芯片与网络 → 系统/云 → 模型与应用</p></div>
        <div class="chain-flow">
          <div><b>制造、设备与存储</b><span>TSMC · ASML · Micron / HBM · 封装</span></div><i>→</i>
          <div><b>GPU / ASIC / 网络</b><span>NVIDIA · AMD · Broadcom · Intel</span></div><i>→</i>
          <div><b>云与系统</b><span>Microsoft · Amazon · Google · Meta</span></div><i>→</i>
          <div><b>模型与应用</b><span>OpenAI · Anthropic · 国内外模型厂商</span></div>
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>核心公司财务趋势</h2><p>${esc(sc.note || "")}</p></div>
        <div class="kpi-grid">${kpiCard("财务记录", rows.length)}${kpiCard("覆盖公司", current.length)}${kpiCard("美元口径最高营收", current.filter(r=>r.currency==="USD").length ? fmtUSD(Math.max(...current.filter(r=>r.currency==="USD").map(r=>r.value||0)),1)+"B" : "—")}${kpiCard("平均毛利率", current.filter(r=>r.gross_margin_pct!=null).length ? fmtNum(current.filter(r=>r.gross_margin_pct!=null).reduce((s,r)=>s+r.gross_margin_pct,0)/current.filter(r=>r.gross_margin_pct!=null).length,1)+"%" : "—")}</div>
        <div class="card"><h3>美元口径公司营收对比</h3>${renderBarChart(current.filter(r=>r.currency==="USD").slice().sort((a,b)=>(b.value||0)-(a.value||0)),"value",r=>`${r.company_name} · ${r.period}`,r=>fmtUSD(r.value,1)+"B")}
        <div class="table-wrap"><table id="supply-table"><thead><tr><th data-key="company_name">公司</th><th data-key="period">期间</th><th data-key="value">营收（原币种）</th><th data-key="gross_margin_pct">毛利率</th><th>产业环节/口径</th><th>来源</th></tr></thead><tbody>
        ${rows.map(r=>`<tr><td><strong>${esc(r.company_name)}</strong></td><td>${esc(r.period)}</td><td class="num">${r.currency==="EUR"?"€":"$"}${fmtNum(r.value,3)}B</td><td class="num">${r.gross_margin_pct==null?"—":fmtNum(r.gross_margin_pct,1)+"%"}</td><td>${esc(r.metric_category||r.xbrl_concept||"—")}<small class="metric-note">${esc(r.note||"")}</small></td><td>${sourceLink(r.source_url,r.source_name||"公司披露")}</td></tr>`).join("")}
        </tbody></table></div></div>
      </section>`;
    makeSortable("supply-table");
  }

  // ═══════════════════════════════════════════════════════════════
  // TAB 6: Investment Research
  // ═══════════════════════════════════════════════════════════════
  function renderInvestment(D) {
    const inv = D.investment || {};
    const market = inv.market || {};
    const rows = market.records || [];
    const watch = inv.watchlist || {};
    const all = [...(watch.foreign || []), ...(watch.domestic || [])];
    const bySymbol = Object.fromEntries(rows.map(r=>[r.symbol,r]));
    app.innerHTML = `
      ${pageHero("MARKET LENS", "投资研究", "用收益、回撤与波动率刻画市场行为，并与产业基本面信号交叉验证。", `${rows.length}/${all.length} 个标的有行情`)}
      <section class="section"><div class="section-head"><h2>AI 资产观察池</h2><p>免费日线来自 Yahoo Finance；交易前应以持牌行情源复核</p></div>
        <div class="kpi-grid">${kpiCard("观察标的",all.length)}${kpiCard("行情覆盖",rows.length)}${kpiCard("近1月上涨",rows.filter(r=>(r.return_1m_pct||0)>0).length)}${kpiCard("高波动标的",rows.filter(r=>(r.volatility_1y_pct||0)>50).length)}</div>
        <div class="card"><div class="table-wrap"><table id="market-table"><thead><tr><th data-key="symbol">代码</th><th data-key="name">公司/ETF</th><th>产业角色</th><th data-key="close">收盘</th><th data-key="return_1w_pct">1周</th><th data-key="return_1m_pct">1月</th><th data-key="return_3m_pct">3月</th><th data-key="return_ytd_pct">YTD</th><th data-key="drawdown_52w_pct">距52周高点</th><th data-key="volatility_1y_pct">年化波动</th><th>来源</th></tr></thead><tbody>
        ${all.map(w=>{const r=bySymbol[w.symbol]||{}; return `<tr><td><strong>${esc(w.symbol)}</strong></td><td>${esc(w.name)}</td><td>${esc(w.role)}</td><td class="num">${r.close==null?"—":fmtNum(r.close,2)} ${esc(r.currency||"")}</td><td class="num ${pctClass(r.return_1w_pct)}">${fmtPct(r.return_1w_pct)}</td><td class="num ${pctClass(r.return_1m_pct)}">${fmtPct(r.return_1m_pct)}</td><td class="num ${pctClass(r.return_3m_pct)}">${fmtPct(r.return_3m_pct)}</td><td class="num ${pctClass(r.return_ytd_pct)}">${fmtPct(r.return_ytd_pct)}</td><td class="num ${pctClass(r.drawdown_52w_pct)}">${fmtPct(r.drawdown_52w_pct)}</td><td class="num">${r.volatility_1y_pct==null?"—":fmtNum(r.volatility_1y_pct,1)+"%"}</td><td>${r.source_url?sourceLink(r.source_url,"Yahoo Finance"):badgeConfidence("missing")}</td></tr>`}).join("")}
        </tbody></table></div></div>
      </section>`;
    makeSortable("market-table");
  }

  // ═══════════════════════════════════════════════════════════════
  // TAB 7: Methodology & Data
  // ═══════════════════════════════════════════════════════════════
  function renderMethodology(D) {
    const h = D.health || {};
    const m = D.meta || {};
    const o = D.overview || {};
    const c = o.cycle || {};
    const runs = (D.history?.runs || []).slice(-10).reverse();
    const sources = D.sources || [];

    app.innerHTML = `
      ${pageHero("DATA & SOURCES", "数据与来源", "完整披露数据字典、来源层级、计算口径、缺失处理、更新时间与可比性边界。", "可追溯 · 可复现 · 可审计")}
      <section class="section">
        <div class="section-head"><h2>数据口径</h2></div>
        <div class="method-grid">
          <article class="method-card">
            <h3>Token 混合成本</h3>
            <p><code>blended_cost = input × 0.65 + output × 0.35</code></p>
            <p>CNY 定价按 fx_rate 转 USD。不含 Batch/缓存/长上下文/工具调用/企业折扣。</p>
          </article>
          <article class="method-card">
            <h3>商业化指标</h3>
            <p>ARR/年化运行率、财务收入、活跃用户、企业采用、融资与估值分别保留原始口径。</p>
            <p>公司公告/IR优先；权威媒体标T2。集团数据不得冒充模型业务，未披露≠0。</p>
          </article>
          <article class="method-card">
            <h3>来源分级</h3>
            <ul>
              <li><span class="tag t1">T1</span> 公司官网/IR/交易所/监管/官方定价页</li>
              <li><span class="tag t2">T2</span> 权威媒体和公开可引用的行业研究</li>
              <li><span class="tag t3">T3</span> 公开聚合目录与新闻源</li>
            </ul>
          </article>
          <article class="method-card">
            <h3>AI Cycle</h3>
            <p>技术成熟度30%、商业化兑现度35%、资本投入强度35%构成产业发展强度；市场拥挤代理独立计算。</p>
            <p>${esc(c.stages_reference?.map(s => s.label_zh).join(" → ") || "技术验证 → 基础设施扩张 → 商业化兑现 → 估值拥挤 → 周期调整")}</p>
          </article>
          <article class="method-card">
            <h3>GPU 与云 CAPEX</h3>
            <p>GPU采用服务商官方公开按需价格，统一为USD/GPU·小时，并保留供应商、型号、显存、价格类型与采集日。</p>
            <p>CAPEX来自公司年报、业绩公告或SEC/IR，均为公司整体口径，并非纯AI支出。</p>
          </article>
          <article class="method-card">
            <h3>产业链财务</h3>
            <p>覆盖GPU/CPU/ASIC、晶圆代工、光刻设备与HBM/存储。收入和毛利率来自公司正式财务披露。</p>
            <p>美元与欧元保留原币种；图表只比较同币种，避免未经说明的汇率换算。</p>
          </article>
          <article class="method-card">
            <h3>市场行情与投资研究</h3>
            <p>公开免费日线用于计算1周/1月/3月/YTD收益、52周回撤与历史波动率，属于T3研究代理。</p>
            <p>不包含机构级Forward P/E、EV/EBITDA、ETF申赎或实时盘口，不作为交易执行数据。</p>
          </article>
          <article class="method-card">
            <h3>时间序列与更新</h3>
            <p>每次成功构建按date+metric_id去重写入历史快照；价格未变化也保留当日真实快照，以支持水平线。</p>
            <p>自动抓取失败时保留上一成功快照并标记stale_fallback；动态官网使用人工核验回退。</p>
          </article>
        </div>
      </section>

      <section class="section">
        <div class="section-head"><h2>全站数据资产地图</h2><p>每个模块的核心字段、首选来源与主要限制</p></div>
        <div class="card"><div class="table-wrap"><table class="source-catalog"><thead><tr><th>模块</th><th>核心数据</th><th>首选来源</th><th>更新方式</th><th>关键边界</th></tr></thead><tbody>
          <tr><td><strong>Token经济</strong></td><td>输入/输出/缓存价、混合成本、历史快照</td><td>模型厂商官方定价页；OpenRouter仅作T3补缺</td><td>每日抓取 + 官方人工核验回退</td><td>标准实时档；不混入Batch、企业折扣和长上下文阶梯</td></tr>
          <tr><td><strong>商业化</strong></td><td>ARR、财务收入、用户、企业采用、融资、估值</td><td>公司官网/IR/交易所；必要时权威媒体</td><td>事件驱动人工核验</td><td>不同会计与运营口径分列；私募估值不等同市值</td></tr>
          <tr><td><strong>算力</strong></td><td>GPU按需价、显存、供应商、CSP CAPEX</td><td>Lambda/RunPod等官方价；公司年报与业绩公告</td><td>价格自动抓取；财报定期更新</td><td>公开展示最低价不代表库存/SLA；CAPEX含非AI投入</td></tr>
          <tr><td><strong>产业链</strong></td><td>营收、毛利率、产业环节</td><td>公司IR、年报、SEC/交易所披露</td><td>财报发布后更新</td><td>公司整体财务，不等同AI业务收入；跨币种不直接比较</td></tr>
          <tr><td><strong>投资研究</strong></td><td>收益、回撤、波动率、上涨广度</td><td>Yahoo Finance公开复权日线</td><td>每日自动</td><td>T3代理；需用持牌行情与估值数据复核</td></tr>
          <tr><td><strong>周期评分</strong></td><td>固定锚点标准化、权重、贡献、阶段规则</td><td>以上各模块；方法参考OECD/EC-JRC复合指标手册</td><td>随数据构建重算</td><td>监测代理指数，不是回测收益模型或外部机构评级</td></tr>
        </tbody></table></div></div>
      </section>

      <section class="section">
        <div class="section-head"><h2>自动数据源运行明细</h2><p>T1/T2/T3是证据来源等级，不是对公司或资产的投资评级</p></div>
        <div class="card"><div class="table-wrap"><table id="source-status-table"><thead><tr><th>数据源</th><th>类型</th><th>状态</th><th>最近检查</th><th>页面变化</th><th>链接</th></tr></thead><tbody>
          ${sources.map(s=>`<tr><td><strong>${esc(s.name||s.source_id)}</strong></td><td>${esc(s.kind||"—")}</td><td>${badgeStatus(s.status)}</td><td>${esc(fmtDate(s.checked_at))}</td><td>${s.changed===true?'<span class="tag manual">已变化</span>':s.changed===false?'<span class="tag verified">未变化</span>':'—'}</td><td>${sourceLink(s.url,"打开来源")}</td></tr>`).join("") || '<tr><td colspan="6" class="empty-state">暂无来源状态记录</td></tr>'}
        </tbody></table></div></div>
      </section>

      <section class="section">
        <div class="section-head"><h2>更新状态</h2><p>${esc(m.schedule || "定期更新")}</p></div>
        <div class="card">
          <div class="grid-3">
            <div>${kpiCard("系统状态", h.status)}</div>
            <div>${kpiCard("数据源成功率", h.source_success_rate || "—")}</div>
            <div>${kpiCard("最新快照", fmtDate(h.generated_at))}</div>
            <div>${kpiCard("定价记录", h.pricing_total)}</div>
            <div>${kpiCard("商业指标", h.business_total)}</div>
            <div>${kpiCard("GPU价格", h.gpu_records)}</div>
            <div>${kpiCard("CAPEX记录", h.capex_records)}</div>
            <div>${kpiCard("产业链财务", h.supply_chain_records)}</div>
            <div>${kpiCard("行情覆盖", h.market_records)}</div>
          </div>
        </div>
      </section>

      <section class="section">
        <div class="section-head"><h2>最近更新</h2></div>
        <div class="card">
          ${runs.length ? `<div class="table-wrap"><table><thead><tr><th>运行时间</th><th>状态</th><th>耗时</th></tr></thead><tbody>${runs.map(r=>`<tr><td>${esc(fmtDate(r.generated_at))}</td><td>${badgeStatus(r.status)}</td><td>${esc(r.elapsed_seconds)}s</td></tr>`).join("")}</tbody></table></div>` : `<p class="empty-state">暂无更新记录</p>`}
        </div>
      </section>
    `;
  }

  // ═══════════════════════════════════════════════════════════════
  // Shared: Sortable Tables
  // ═══════════════════════════════════════════════════════════════
  function makeSortable(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    table.querySelectorAll("th[data-key]").forEach(th => {
      th.addEventListener("click", () => {
        const tbody = table.tBodies[0];
        if (!tbody) return;
        const idx = [...th.parentNode.children].indexOf(th);
        const asc = th.dataset.dir !== "asc";
        th.dataset.dir = asc ? "asc" : "desc";
        [...tbody.rows].sort((a, b) => {
          const av = a.cells[idx]?.textContent.trim() || "";
          const bv = b.cells[idx]?.textContent.trim() || "";
          const an = parseFloat(av.replace(/[^\d.-]/g, ""));
          const bn = parseFloat(bv.replace(/[^\d.-]/g, ""));
          const cmp = Number.isFinite(an) && Number.isFinite(bn) ? an - bn : av.localeCompare(bv, "zh-CN");
          return asc ? cmp : -cmp;
        }).forEach(row => tbody.appendChild(row));
      });
    });
  }

  // ── Bootstrap ──────────────────────────────────────────────────
  render();
})();
