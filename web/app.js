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
      manual_required: "tag manual" };
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
    const map = { ok: "tag verified", partial: "tag manual", skipped: "tag stale", error: "tag error" };
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
      // file:// CORS fallback
      if (err.message.includes("Failed to fetch") || err.name === "TypeError") {
        throw new Error(
          "无法加载 API 数据。\n\n" +
          "本地文件预览请运行：\n" +
          "  cd _site && python -m http.server 8080\n" +
          "然后访问 http://localhost:8080"
        );
      }
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
        <code>python scripts/run_all.py --project-root .</code>
      </section>`;
    }
  }

  // ── Header ─────────────────────────────────────────────────────
  function renderHeader(D) {
    const m = D.meta || {};
    const h = D.health || {};
    const el = document.getElementById("header-meta");
    const state = h.status || "unknown";
    el.innerHTML = `<span class="snapshot-status status-${esc(state)}"><i></i>${esc(state)}</span>
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

    const isSample = c.insufficient_data || c.sample_based || c.confidence === "low";
    const hasRisk = c.risk_crowding_score != null;

    app.innerHTML = `
      ${pageHero("ALLOCATION INTELLIGENCE", "AI 产业景气与风险总览", "把模型经济、商业化、算力资本开支与市场价格信号放进同一研究框架。", "公开数据 · 可追溯 · 每周更新")}
      ${isSample ? renderSampleWarning(c) : ""}

      <!-- Stage Card -->
      <section class="section">
        <article class="card stage-card">
          <span class="stage-label ${isSample ? 'sample-stage' : ''}">当前阶段 · ${esc(c.stage_label || "—")}</span>
          <h2>AI 产业周期：${esc(c.stage_label || "数据不足")}</h2>
          <p class="lead">${esc(stageDescription(c.stage_id))}</p>
          <div class="stage-scores">
            <div class="score-item"><b>${esc(fmtNum(c.industry_development_score, 1))}</b>产业发展强度 / 100</div>
            <div class="score-item"><b>${hasRisk ? esc(fmtNum(c.risk_crowding_score, 1)) : "待完善"}</b>风险拥挤度 ${!hasRisk ? "(第一期暂用中性值)" : ""}</div>
            <div class="score-item"><b>${esc(c.confidence || "—")}</b>评分置信度</div>
            <div class="score-item"><b>${esc(c.missing_factor_count || 0)}</b>缺失因子</div>
          </div>
        </article>
      </section>

      <!-- Factor Scores -->
      <section class="section">
        <div class="section-head"><h2>三项产业因子 + 风险 Overlay</h2><p>${c.confidence === 'low' ? '⚠️ 当前为 proxy_v1 初步信号，不是投资结论' : ''}</p></div>
        <div class="grid-2">
          ${renderFactorCard("技术成熟度", c.factor_scores?.technology_maturity, "Token降价速度·模型能力·开源生态·多模态")}
          ${renderFactorCard("商业化兑现度", c.factor_scores?.commercialization, "ARR轨迹·Token用量·企业采纳·披露覆盖")}
          ${renderFactorCard("资本投入强度", c.factor_scores?.capital_investment, "CSP Capex·GPU供需·数据中心·融资")}
          <article class="card">
            <h3>估值/市场拥挤度 Overlay</h3>
            <p class="subtitle">AI股票估值·ETF资金流·市场情绪·价基背离</p>
            <div class="bar-list">
              <div class="bar-row">
                <div class="bar-label">风险拥挤度</div>
                <div class="bar-track"><div class="bar-fill" style="width:${hasRisk ? c.risk_crowding_score : 0}%;background:var(--warn)"></div></div>
                <div class="bar-value">${hasRisk ? fmtNum(c.risk_crowding_score, 0) + " / 100" : "待数据完善"}</div>
              </div>
            </div>
            <p style="font-size:11px;color:var(--muted);margin-top:8px">${esc(c.risk_note || "第二期实现自动化风险Overlay。")}</p>
          </article>
        </div>
      </section>

      <!-- KPIs -->
      <section class="section">
        <div class="section-head"><h2>关键指标</h2></div>
        <div class="kpi-grid">
          ${kpiCard("监测公司", k.companies)}
          ${kpiCard("有定价模型", k.models_with_pricing)}
          ${kpiCard("数据源健康", h.source_success_rate || "0/0")}
          ${kpiCard("ARR披露数", k.arr_disclosures)}
          ${kpiCard("Sample记录", h.pricing_sample, "⚠️")}
          ${kpiCard("Missing记录", (h.pricing_missing || 0) + (h.business_missing || 0))}
          ${kpiCard("新闻待复核", n.length)}
          ${kpiCard("数据覆盖", c.data_coverage?.pricing_real + c.data_coverage?.business_real, "条真实记录")}
        </div>
      </section>

      <!-- Alerts -->
      ${renderHealthWarnings(h)}
      ${renderNewsPreview(n)}
      ${renderDataBoundary()}
    `;
  }

  function renderSampleWarning(c) {
    return `<div class="warning-banner sample-warn">
      <span class="warning-icon">⚠️</span>
      <div><b>当前阶段判断为初步代理信号，不代表投资结论。</b>
      评分方法: ${esc(c.score_method || "proxy_v1")}；置信度: ${esc(c.confidence)}；缺失因子: ${c.missing_factor_count}。
      ${esc(c.limitations || "缺失数据保持为空，不以估算值伪装为事实。")}</div>
    </div>`;
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

  function renderHealthWarnings(h) {
    if (!h || !h.warnings || !h.warnings.length) return "";
    return `<section class="section"><div class="warning-banner info">
      <span class="warning-icon">ℹ️</span>
      <div>${h.warnings.map(w => esc(w)).join("<br>")}</div>
    </div></section>`;
  }

  function renderNewsPreview(n) {
    if (!n || !n.length) return "";
    const items = n.slice(0, 5).map(x => `<div class="news-item">
      <div class="news-title">${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>` : esc(x.title)}</div>
      <div class="news-meta">${esc(x.publisher || "—")} · ${esc(fmtDateShort(x.published_at))}<br><span class="tag t3">待复核</span></div>
    </div>`).join("");
    return `<section class="section"><div class="card">
      <h3>最新待复核新闻</h3><div class="news-list">${items}</div>
      <p class="subtitle" style="margin-top:8px">新闻来自 RSS，仅用于发现，不自动写入正式指标。</p>
    </div></section>`;
  }

  function renderDataBoundary() {
    return `<section class="section"><article class="card">
      <h3>数据边界</h3>
      <p>${[
        "T1 = 公司官网/IR/交易所/监管/官方定价页",
        "T2 = 权威媒体和公开可引用的行业研究",
        "T3 = RSS/聚合新闻（仅用于发现，不自动写入正式指标）",
        "sample = 仅用于开发演示的示例数据，不应被引用",
        "missing = 数据不可用，value = null"
      ].map(x => esc(x)).join("<br>")}</p>
    </article></section>`;
  }

  function stageDescription(id) {
    const m = {
      tech_validation: "技术路线探索期。Token价格处于高位，商业模式未成形，资本投入相对谨慎。",
      infra_expansion: "Capex快速增长，GPU供不应求，Token价格开始快速下降。基础设施层持续受益。",
      commercialization: "ARR加速增长，Token使用量爆发，部分公司实现盈利。技术成熟与商业闭环共振。",
      valuation_crowding: "⚠️ 估值处于高位，资金拥挤。需警惕基本面与价格的背离。这不代表产业更成熟。",
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
    const realRecords = records.filter(r => r.confidence !== "sample" && r.value != null);
    const sampleRecords = records.filter(r => r.confidence === "sample");
    const blendedRecords = records.filter(r => r.blended_cost_usd != null);
    const cheapest = blendedRecords.length ? blendedRecords.reduce((a, b) => (a.blended_cost_usd < b.blended_cost_usd ? a : b)) : null;
    const costs = blendedRecords.map(r => r.blended_cost_usd).sort((a, b) => a - b);
    const median = costs.length ? costs[Math.floor(costs.length / 2)] : null;

    app.innerHTML = `
      ${pageHero("MODEL ECONOMICS", "Token 经济", "比较主流模型的输入、输出与标准化混合成本，跟踪推理价格曲线。", `${realRecords.length} 条有效记录`)}
      ${sampleRecords.length ? `<div class="warning-banner sample-warn"><span class="warning-icon">⚠️</span><div><b>${sampleRecords.length} 条定价记录为 SAMPLE 数据。</b>这些数值是结构示例，不应被引用为真实价格。</div></div>` : ""}

      <section class="section">
        <div class="kpi-grid">
          ${kpiCard("价格记录", records.length)}
          ${kpiCard("真实记录", realRecords.length)}
          ${kpiCard("Sample记录", sampleRecords.length, sampleRecords.length ? "⚠️ 示例数据" : "")}
          ${kpiCard("最低混合成本", cheapest ? fmtUSD(cheapest.blended_cost_usd) : "—", cheapest ? esc(cheapest.company_name + " · " + cheapest.metric_name.slice(0,30)) : sampleRecords.length ? "⚠️ sample only" : "")}
          ${kpiCard("中位混合成本", median ? fmtUSD(median) : "—", sampleRecords.length && !realRecords.length ? "⚠️ sample only" : "")}
        </div>
      </section>

      <!-- Blended Cost Chart -->
      <section class="section">
        <div class="section-head"><h2>标准化混合成本 (USD / 百万总 Tokens)</h2><p>input×0.65 + output×0.35 · sample 数据用虚线标记</p></div>
        <div class="card">
          ${renderBarChart(blendedRecords, "blended_cost_usd", r => `${r.company_name} · ${r.model_id}`, r => {
            if (r.blended_cost_usd == null) return "—";
            const tag = r.confidence === "sample" ? ' <span class="bar-tag">[SAMPLE]</span>' : "";
            return fmtUSD(r.blended_cost_usd) + tag;
          }, r => r.region === "domestic" ? "domestic" : "", r => r.confidence === "sample" ? "sample-bar" : "")}
          <p class="subtitle">${esc(tp.methodology?.blended_formula || "")}</p>
        </div>
      </section>

      <!-- Filterable Table -->
      <section class="section">
        <div class="section-head"><h2>价格明细</h2></div>
        <div class="card">
          <div class="controls">
            <select id="token-region"><option value="">全部地区</option><option value="domestic">国内</option><option value="overseas">海外</option></select>
            <select id="token-confidence"><option value="">全部状态</option><option value="sample">⚠️ Sample</option><option value="missing">Missing</option><option value="verified">Verified</option></select>
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
      <section class="section"><div class="section-head"><h2>历史趋势</h2><p>同一指标的每日快照；价格未变化时曲线保持水平</p></div>
        <div class="card"><div class="controls"><select id="history-model">${records.map(r=>`<option value="${esc(r.metric_id)}">${esc(r.company_name)} · ${esc(r.model_id)}</option>`).join("")}</select><button class="button" id="download-token-csv">导出当前价格 CSV</button></div><div id="history-chart" class="history-chart"></div></div>
      </section>
    `;

    wireTokenTable(records);
    wireHistoryChart(D.history?.token_pricing || [], records);
    document.getElementById("download-token-csv")?.addEventListener("click",()=>downloadCsv("token-pricing.csv",records));
    makeSortable("token-table");
  }

  function wireHistoryChart(history, records) {
    const select=document.getElementById("history-model"), host=document.getElementById("history-chart");
    if(!select||!host) return;
    const draw=()=>{
      const points=history.filter(x=>x.metric_id===select.value && (x.blended_cost_usd??x.value)!=null).sort((a,b)=>a.date.localeCompare(b.date));
      if(points.length<2){host.innerHTML='<div class="empty-state">至少需要两个不同日期的有效快照后才显示趋势。</div>';return;}
      const vals=points.map(x=>Number(x.blended_cost_usd??x.value)), min=Math.min(...vals), max=Math.max(...vals), range=max-min||1;
      const coords=vals.map((v,i)=>`${30+i*(740/Math.max(vals.length-1,1))},${170-(v-min)/range*130}`).join(" ");
      host.innerHTML=`<svg viewBox="0 0 800 210" role="img" aria-label="价格历史趋势"><line x1="30" y1="170" x2="770" y2="170" stroke="var(--line)"/><polyline fill="none" stroke="var(--accent)" stroke-width="3" points="${coords}"/><text x="30" y="195">${esc(points[0].date)}</text><text x="690" y="195">${esc(points.at(-1).date)}</text><text x="35" y="25">最高 ${fmtUSD(max)} · 最低 ${fmtUSD(min)}</text></svg>`;
    };
    select.addEventListener("change",draw); draw();
  }

  function downloadCsv(filename, rows) {
    if(!rows.length) return;
    const keys=["company_name","model_id","input_per_m","output_per_m","blended_cost_usd","currency","as_of_date","confidence","source_url"];
    const q=v=>'"'+String(v??"").replace(/"/g,'""')+'"';
    const csv='\ufeff'+[keys.join(","),...rows.map(r=>keys.map(k=>q(r[k])).join(","))].join("\n");
    const a=document.createElement("a"); a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"})); a.download=filename; a.click(); URL.revokeObjectURL(a.href);
  }

  function renderBarChart(rows, valField, labelFn, fmtFn, cls, barCls) {
    if (!rows.length) return `<div class="empty-state"><h3>暂无数据</h3><p>等待数据采集或手动填入 data/manual/。</p></div>`;
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
        <td>${sourceLink(r.source_url, r.source_name)}<br><small>${esc(r.note || "").slice(0,80)}</small></td>
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
    const withValue = records.filter(r => r.value != null);
    const missing = records.filter(r => r.value == null);

    app.innerHTML = `
      ${pageHero("COMMERCIALIZATION", "商业化进程", "分口径观察 ARR、年化收入、融资与估值，避免把不同性质的指标混为一谈。", `${withValue.length}/${records.length} 条已披露`)}
      ${missing.length ? `<div class="warning-banner missing-data"><span class="warning-icon">📊</span><div><b>${missing.length} 条商业化指标数据缺失(value=null)。</b>请在 data/manual/business_metrics.json 中填入真实数据。</div></div>` : ""}

      <section class="section">
        <div class="kpi-grid">
          ${kpiCard("商业指标总计", records.length)}
          ${kpiCard("有数据", withValue.length)}
          ${kpiCard("缺失", missing.length, missing.length ? "value=null" : "")}
          ${kpiCard("最高ARR", withValue.filter(r => r.metric_id?.startsWith("arr")).length ? fmtUSD(Math.max(...withValue.filter(r => r.metric_id?.startsWith("arr")).map(r => r.value)), 1) + "B" : "—")}
        </div>
      </section>

      <!-- Business Table -->
      <section class="section">
        <div class="section-head"><h2>商业化指标明细</h2><p>ARR、年化收入、年度收入、融资额分开展示，不合并口径。未披露≠0。</p></div>
        <div class="card">
          <div class="table-wrap"><table id="biz-table">
            <thead><tr>
              <th data-key="company_name">公司</th><th data-key="metric_name">指标</th><th data-key="metric_id">类型</th>
              <th data-key="value">数值</th><th data-key="unit">单位</th><th data-key="period">期间</th>
              <th data-key="confidence">可信度</th><th data-key="freshness">新鲜度</th><th>来源</th>
            </tr></thead>
            <tbody>${records.map(r => `<tr>
              <td>${badgeRegion(r.region)} <strong>${esc(r.company_name)}</strong></td>
              <td>${esc(r.metric_name)}</td>
              <td>${esc(r.metric_id?.split("::")[0] || "—")}</td>
              <td class="num">${fmtValue(r.value)} ${esc(r.unit || "")}</td>
              <td>${esc(r.unit || "—")}</td>
              <td>${esc(r.period || "—")}</td>
              <td>${badgeConfidence(r.confidence)}</td>
              <td>${badgeFreshness(r.freshness)}</td>
              <td>${sourceLink(r.source_url, r.source_name)}<br><small>${esc((r.note || "").slice(0,100))}</small></td>
            </tr>`).join("")}</tbody>
          </table></div>
        </div>
      </section>
    `;

    makeSortable("biz-table");
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

    app.innerHTML = `
      ${pageHero("INFRASTRUCTURE", "AI 算力与云 CAPEX", "从 GPU 即时租赁价格与云厂商资本开支两端观察基础设施景气。", `${gpu.length} 条 GPU 价格 · ${capex.length} 条 CAPEX`)}
      <section class="section">
        <div class="section-head"><h2>GPU 按需价格</h2><p>统一为 USD / GPU·小时；不同实例规模、区域和可用性不能直接等同</p></div>

        <div class="warning-banner info">
          <span class="warning-icon">📡</span>
          <div>优先展示可重复解析的官方按需价；无法结构化的页面仍保留状态监控。正式采购成本需核对区域、税费和合约折扣。</div>
        </div>

        ${gpu.length ? `<div class="card" style="margin-bottom:14px">
          <h3>GPU 价格记录 (${gpu.filter(g => g.value != null).length})</h3>
          ${renderBarChart(gpu.filter(g => g.value != null), "value", r => `${r.provider || r.source_name} · ${r.gpu_model || r.metric_name}`, r => fmtUSD(r.value, 2))}
          <div class="table-wrap"><table>
            <thead><tr><th>平台</th><th>GPU</th><th>显存</th><th>USD/GPU·h</th><th>口径</th><th>时间</th><th>来源</th></tr></thead>
            <tbody>${gpu.map(g => `<tr>
              <td><strong>${esc(g.provider || g.source_name)}</strong></td>
              <td>${esc(g.gpu_model || g.metric_name)}</td><td>${g.vram_gb ? esc(g.vram_gb) + " GB" : "—"}</td>
              <td class="num">${g.value != null ? fmtUSD(g.value, 2) : "—"}</td><td>${esc(g.price_type || g.unit || "—")}</td>
              <td>${esc(fmtDateShort(g.as_of_date || g.collected_at))}</td><td>${sourceLink(g.source_url, g.source_name)}</td>
            </tr>`).join("")}</tbody>
          </table></div>
        </div>` : `<div class="empty-state" style="margin-bottom:14px"><h3>暂无 GPU 源状态</h3><p>请先运行 python scripts/collect_gpu_pricing.py --project-root .</p></div>`}
      </section>

      <section class="section">
        <div class="section-head"><h2>云厂商 CAPEX</h2><p>SEC 10-K XBRL 实际值；公司整体CAPEX，不等同于纯AI投入</p></div>
        ${capex.length ? `<div class="card">
          ${renderBarChart(capex.slice().sort((a,b)=>(b.value||0)-(a.value||0)), "value", r => `${r.company_name} · ${r.period}`, r => fmtUSD(r.value, 1)+"B")}
          <div class="table-wrap"><table><thead><tr><th>公司</th><th>期间</th><th>CAPEX</th><th>XBRL口径</th><th>截至</th><th>来源</th></tr></thead><tbody>
          ${capex.map(r=>`<tr><td><strong>${esc(r.company_name)}</strong></td><td>${esc(r.period)}</td><td class="num">${fmtUSD(r.value,3)}B</td><td>${esc(r.xbrl_concept||"—")}</td><td>${esc(r.as_of_date)}</td><td>${sourceLink(r.filing_url||r.source_url,"SEC filing")}</td></tr>`).join("")}
          </tbody></table></div></div>` : `<div class="empty-state"><h3>等待 SEC 数据</h3><p>下一次联网采集将自动补齐四大CSP年度CAPEX。</p></div>`}
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
      <section class="section"><div class="section-head"><h2>AI 产业链结构</h2><p>需求 → 设计 → 制造/设备 → 系统/云 → 模型与应用</p></div>
        <div class="chain-flow">
          <div><b>模型与应用</b><span>OpenAI · Anthropic · 国内模型厂商</span></div><i>←</i>
          <div><b>云与系统</b><span>Microsoft · Amazon · Google · Meta</span></div><i>←</i>
          <div><b>GPU / ASIC / 网络</b><span>NVIDIA · AMD · Broadcom</span></div><i>←</i>
          <div><b>制造与设备</b><span>TSMC · ASML · 封装 · HBM</span></div>
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>核心公司财务趋势</h2><p>${esc(sc.note || "")}</p></div>
        <div class="kpi-grid">${kpiCard("SEC财务记录", rows.length)}${kpiCard("覆盖公司", current.length)}${kpiCard("最新营收最高", current.length ? fmtUSD(Math.max(...current.map(r=>r.value||0)),1)+"B" : "—")}${kpiCard("平均毛利率", current.filter(r=>r.gross_margin_pct!=null).length ? fmtNum(current.filter(r=>r.gross_margin_pct!=null).reduce((s,r)=>s+r.gross_margin_pct,0)/current.filter(r=>r.gross_margin_pct!=null).length,1)+"%" : "—")}</div>
        <div class="card">${renderBarChart(current.slice().sort((a,b)=>(b.value||0)-(a.value||0)),"value",r=>`${r.company_name} · ${r.period}`,r=>fmtUSD(r.value,1)+"B")}
        <div class="table-wrap"><table id="supply-table"><thead><tr><th data-key="company_name">公司</th><th data-key="period">期间</th><th data-key="value">营收 USD B</th><th data-key="gross_margin_pct">毛利率</th><th>口径</th><th>来源</th></tr></thead><tbody>
        ${rows.map(r=>`<tr><td><strong>${esc(r.company_name)}</strong></td><td>${esc(r.period)}</td><td class="num">${fmtNum(r.value,3)}</td><td class="num">${r.gross_margin_pct==null?"—":fmtNum(r.gross_margin_pct,1)+"%"}</td><td>${esc(r.xbrl_concept||"—")}</td><td>${sourceLink(r.source_url,"SEC Companyfacts")}</td></tr>`).join("")}
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
      <div class="warning-banner info"><span class="warning-icon">🧭</span><div><b>资产配置信号层。</b>价格趋势只反映市场行为，需与产业周期、盈利和估值共同判断；本页不构成投资建议。</div></div>
      <section class="section"><div class="section-head"><h2>AI 资产观察池</h2><p>免费日线来自 Yahoo Finance；交易前应以持牌行情源复核</p></div>
        <div class="kpi-grid">${kpiCard("观察标的",all.length)}${kpiCard("行情覆盖",rows.length)}${kpiCard("近1月上涨",rows.filter(r=>(r.return_1m_pct||0)>0).length)}${kpiCard("高波动标的",rows.filter(r=>(r.volatility_1y_pct||0)>50).length)}</div>
        <div class="card"><div class="table-wrap"><table id="market-table"><thead><tr><th data-key="symbol">代码</th><th data-key="name">公司/ETF</th><th>产业角色</th><th data-key="close">收盘</th><th data-key="return_1w_pct">1周</th><th data-key="return_1m_pct">1月</th><th data-key="return_3m_pct">3月</th><th data-key="return_ytd_pct">YTD</th><th data-key="drawdown_52w_pct">距52周高点</th><th data-key="volatility_1y_pct">年化波动</th><th>来源</th></tr></thead><tbody>
        ${all.map(w=>{const r=bySymbol[w.symbol]||{}; return `<tr><td><strong>${esc(w.symbol)}</strong></td><td>${esc(w.name)}</td><td>${esc(w.role)}</td><td class="num">${r.close==null?"—":fmtNum(r.close,2)} ${esc(r.currency||"")}</td><td class="num ${pctClass(r.return_1w_pct)}">${fmtPct(r.return_1w_pct)}</td><td class="num ${pctClass(r.return_1m_pct)}">${fmtPct(r.return_1m_pct)}</td><td class="num ${pctClass(r.return_3m_pct)}">${fmtPct(r.return_3m_pct)}</td><td class="num ${pctClass(r.return_ytd_pct)}">${fmtPct(r.return_ytd_pct)}</td><td class="num ${pctClass(r.drawdown_52w_pct)}">${fmtPct(r.drawdown_52w_pct)}</td><td class="num">${r.volatility_1y_pct==null?"—":fmtNum(r.volatility_1y_pct,1)+"%"}</td><td>${r.source_url?sourceLink(r.source_url,"Yahoo Finance"):badgeConfidence("missing")}</td></tr>`}).join("")}
        </tbody></table></div></div>
      </section>
      <section class="section"><article class="card"><h3>仍需专业数据接口的字段</h3><p>一致预期盈利、Forward P/E、EV/EBITDA、ETF申赎资金流和机构持仓变化。目前保持缺失，不使用网页猜测值替代。</p></article></section>`;
    makeSortable("market-table");
  }

  // ═══════════════════════════════════════════════════════════════
  // TAB 7: Methodology & Data
  // ═══════════════════════════════════════════════════════════════
  function renderMethodology(D) {
    const h = D.health || {};
    const m = D.meta || {};
    const methods = D.methodology || {};
    const o = D.overview || {};
    const c = o.cycle || {};
    const runs = (D.history?.runs || []).slice(-10).reverse();

    app.innerHTML = `
      ${pageHero("RESEARCH GOVERNANCE", "方法论与数据", "披露数据边界、来源层级、评分限制和流水线状态，让每个结论都可核查。", "透明口径 · 审计留痕")}
      <section class="section">
        <div class="section-head"><h2>项目说明</h2></div>
        <div class="method-grid">
          <article class="method-card">
            <h3>公开数据研究终端</h3>
            <p>AI Industry Monitor 是一个开源的 AI 产业监测 Dashboard，以公开网页的形式呈现在 GitHub Pages 上。</p>
            <p>持续跟踪全球大模型商业化、Token 经济、AI 算力、云厂商资本开支和相关产业链数据。</p>
            <p><strong>不构成投资建议。</strong></p>
          </article>
          <article class="method-card">
            <h3>数据使用原则</h3>
            <ul>
              <li>新闻 ≠ 正式数据 — RSS 仅进入待复核池</li>
              <li>Sample 数据仅用于开发演示</li>
              <li>Missing 数据的 value = null，不写作 0</li>
              <li>ARR、年化收入、年度收入分开展示，不合并</li>
            </ul>
          </article>
        </div>
      </section>

      <section class="section">
        <div class="section-head"><h2>数据口径</h2></div>
        <div class="method-grid">
          <article class="method-card">
            <h3>Token 混合成本</h3>
            <p>${esc(methods?.sample_policy || "")}</p>
            <p><code>blended_cost = input × 0.65 + output × 0.35</code></p>
            <p>CNY 定价按 fx_rate 转 USD。不含 Batch/缓存/长上下文/工具调用/企业折扣。</p>
          </article>
          <article class="method-card">
            <h3>商业化指标</h3>
            <p>ARR、annualized revenue、年度收入分别保留原始标签。</p>
            <p>科技集团通常不单独披露基础模型 ARR。未披露≠0。</p>
          </article>
          <article class="method-card">
            <h3>来源分级</h3>
            <ul>
              <li><span class="tag t1">T1</span> 公司官网/IR/交易所/监管/官方定价页</li>
              <li><span class="tag t2">T2</span> 权威媒体和公开可引用的行业研究</li>
              <li><span class="tag t3">T3</span> RSS/聚合新闻，仅用于发现</li>
            </ul>
          </article>
          <article class="method-card">
            <h3>AI Cycle 评分体系</h3>
            <p>${esc(methods?.cycle_note || "")}</p>
            <p>第一阶段: ${esc(c.stages_reference?.map(s => s.label_zh).join(" → ") || "技术验证 → 基础设施扩张 → 商业化兑现 → 估值拥挤 → 周期调整")}</p>
          </article>
        </div>
      </section>

      <!-- Health -->
      <section class="section">
        <div class="section-head"><h2>系统健康</h2></div>
        <div class="card">
          <div class="grid-3">
            <div>${kpiCard("系统状态", h.status)}</div>
            <div>${kpiCard("数据源成功率", h.source_success_rate || "—")}</div>
            <div>${kpiCard("生成时间", fmtDate(h.generated_at))}</div>
            <div>${kpiCard("定价记录", h.pricing_total)}</div>
            <div>${kpiCard("Sample 记录", h.pricing_sample, h.pricing_sample ? "⚠️" : "")}</div>
            <div>${kpiCard("定价缺失", h.pricing_missing)}</div>
            <div>${kpiCard("商业指标", h.business_total)}</div>
            <div>${kpiCard("商业缺失", h.business_missing)}</div>
            <div>${kpiCard("GPU价格", h.gpu_records)}</div>
            <div>${kpiCard("CAPEX记录", h.capex_records)}</div>
            <div>${kpiCard("产业链财务", h.supply_chain_records)}</div>
            <div>${kpiCard("行情覆盖", h.market_records)}</div>
          </div>
          ${h.warnings?.length ? `<div class="warning-banner info" style="margin-top:12px"><span class="warning-icon">ℹ️</span><div>${h.warnings.map(w => esc(w)).join("<br>")}</div></div>` : ""}
        </div>
      </section>

      <!-- API Directory -->
      <section class="section">
        <div class="section-head"><h2>JSON API 目录</h2></div>
        <div class="card">
          <table class="api-table">
            <thead><tr><th>端点</th><th>说明</th></tr></thead>
            <tbody id="api-tbody">
              <tr><td colspan="2" class="empty-state">API 目录加载中…</td>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Run Log -->
      <section class="section">
        <div class="section-head"><h2>部署与调度</h2></div>
        <div class="card">
          <p><strong>自动更新</strong>: 每周一、周五 09:00 (Asia/Shanghai) · GitHub Actions 定时触发</p>
          <p><strong>手动更新</strong>: <code>python scripts/run_all.py --project-root .</code></p>
          <p><strong>本地预览</strong>: <code>cd _site && python -m http.server 8080</code></p>
          <p><strong>最新快照</strong>: ${esc(m.generated_at)}</p>
          <p><strong>数据策略</strong>: ${esc(m.data_policy)}</p>
          ${runs.length ? `<div class="table-wrap" style="margin-top:16px"><table><thead><tr><th>运行时间</th><th>状态</th><th>耗时</th><th>采集阶段</th></tr></thead><tbody>${runs.map(r=>`<tr><td>${esc(fmtDate(r.generated_at))}</td><td>${badgeStatus(r.status)}</td><td>${esc(r.elapsed_seconds)}s</td><td>${esc(Object.entries(r.phases||{}).map(([k,v])=>`${k}:${v}`).join(" · "))}</td></tr>`).join("")}</tbody></table></div>` : `<p class="empty-state">尚无完整网络采集运行日志；下一次定时或手动全量更新后自动生成。</p>`}
        </div>
      </section>
    `;

    // Load API index
    fetch(ROOT + "api/index.json").then(r => r.json()).then(api => {
      const tbody = document.getElementById("api-tbody");
      if (!tbody) return;
      tbody.innerHTML = (api.endpoints || []).map(e => `<tr>
        <td><code>./api/${esc(e.path).replace("./", "")}</code></td>
        <td>${esc(e.description)}</td>
      </tr>`).join("") || `<tr><td colspan="2">暂无端点</td></tr>`;
    }).catch(() => {
      const tbody = document.getElementById("api-tbody");
      if (tbody) tbody.innerHTML = `<tr><td colspan="2" class="empty-state">API 目录加载失败</td></tr>`;
    });
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
