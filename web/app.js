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

    const isPreliminary = c.insufficient_data || c.sample_based || c.confidence === "low";
    const hasRisk = c.risk_crowding_score != null;

    app.innerHTML = `
      ${pageHero("ALLOCATION INTELLIGENCE", "AI 产业景气与风险总览", "把模型经济、商业化、算力资本开支与市场价格信号放进同一研究框架。", "公开数据 · 可追溯 · 每周更新")}

      <!-- Stage Card -->
      <section class="section">
        <article class="card stage-card">
          <span class="stage-label ${isPreliminary ? 'sample-stage' : ''}">当前阶段 · ${esc(c.stage_label || "—")}</span>
          <h2>AI 产业周期：${esc(c.stage_label || "数据不足")}</h2>
          <p class="lead">${esc(stageDescription(c.stage_id))}</p>
          <div class="stage-scores">
            <div class="score-item"><b>${esc(fmtNum(c.industry_development_score, 1))}</b>产业发展强度 / 100</div>
            <div class="score-item"><b>${hasRisk ? esc(fmtNum(c.risk_crowding_score, 1)) : "—"}</b>风险拥挤度</div>
            <div class="score-item"><b>${esc(c.confidence || "—")}</b>评分置信度</div>
            <div class="score-item"><b>${esc(c.missing_factor_count || 0)}</b>缺失因子</div>
          </div>
        </article>
      </section>

      <!-- Factor Scores -->
      <section class="section">
        <div class="section-head"><h2>产业周期因子</h2><p>${c.confidence === 'low' ? '当前覆盖有限' : '技术、商业化、资本投入与市场风险联合观察'}</p></div>
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
            ${c.risk_note ? `<p style="font-size:11px;color:var(--muted);margin-top:8px">${esc(c.risk_note)}</p>` : ""}
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
      <section class="section"><div class="section-head"><h2>历史趋势</h2><p>同一指标的每日快照；价格未变化时曲线保持水平</p></div>
        <div class="card"><div class="controls"><select id="history-model">${historyRecords.map(r=>`<option value="${esc(r.metric_id)}">${esc(r.company_name)} · ${esc(r.model_id)}${r.tier === "aggregator_route" ? " · 路由市场" : r.source_tier === 1 ? " · 官方" : ""}</option>`).join("")}</select><select id="history-range" aria-label="历史时间范围"><option value="90">近 90 天</option><option value="180">近 180 天</option><option value="365">近 1 年</option><option value="all" selected>全部历史</option></select><button class="button" id="download-token-csv">导出当前价格 CSV</button></div><div id="history-chart" class="history-chart"></div><p id="history-note" class="history-note"></p></div>
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
      const dots=points.map(p=>`<circle class="history-point" cx="${xAt(p).toFixed(1)}" cy="${yAt(p._value).toFixed(1)}" r="5"><title>${esc(p.date)} · ${esc(fmtUSD(p._value))}</title></circle>`).join("");
      const dateLabels=points.length===1
        ? `<text class="history-date" x="${xAt(points[0])}" y="211" text-anchor="middle">${esc(points[0].date)}</text>`
        : `<text class="history-date" x="${left}" y="211">${esc(points[0].date)}</text><text class="history-date" x="${right}" y="211" text-anchor="end">${esc(points.at(-1).date)}</text>`;
      const summary=points.length===1
        ? `当前 ${fmtUSD(max)} · 仅 1 个有效快照`
        : span===0
          ? `价格未变 ${fmtUSD(max)} · ${points.length} 个快照 · 覆盖 ${coverageDays} 天`
          : `最高 ${fmtUSD(max)} · 最低 ${fmtUSD(min)} · ${points.length} 个快照 · 覆盖 ${coverageDays} 天`;

      host.innerHTML=`<svg viewBox="0 0 800 225" role="img" aria-label="${esc(summary)}">${grid}<text class="history-summary" x="${left}" y="24">${esc(summary)}</text><polyline class="history-line" points="${coords}"/>${dots}${dateLabels}</svg>`;
      const officialAnchor=points.find(p=>p.event_type==="official_price_effective");
      note.textContent=officialAnchor
        ? `历史起点为 ${officialAnchor.date} 的官方发布/价格生效事件；其后连接每日真实快照。`
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
    const withValue = records.filter(r => r.value != null);
    const missing = records.filter(r => r.value == null);

    app.innerHTML = `
      ${pageHero("COMMERCIALIZATION", "商业化进程", "分口径观察 ARR、年化收入、融资与估值，避免把不同性质的指标混为一谈。", `${withValue.length}/${records.length} 条已披露`)}

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
              <td>${sourceLink(r.source_url, r.source_name)}</td>
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

    app.innerHTML = `
      ${pageHero("DATA & SOURCES", "数据与来源", "查看指标口径、来源层级与自动更新状态。", "可追溯 · 定期更新")}
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
            <p>ARR、annualized revenue、年度收入分别保留原始标签。</p>
            <p>科技集团通常不单独披露基础模型 ARR。未披露≠0。</p>
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
            <p>技术成熟度、商业化兑现度、资本投入强度与市场风险共同构成周期观察框架。</p>
            <p>${esc(c.stages_reference?.map(s => s.label_zh).join(" → ") || "技术验证 → 基础设施扩张 → 商业化兑现 → 估值拥挤 → 周期调整")}</p>
          </article>
        </div>
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
