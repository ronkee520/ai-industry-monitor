# Changelog

## [Unreleased] — 全量数据与研究增强

### Added
- 新增 OpenRouter 公开模型目录、Yahoo Finance 行情、Lambda GPU 按需价格和 SEC Companyfacts 采集器。
- 新增 AI 产业链、投资研究两大页面，以及 GPU/CAPEX、半导体财务、观察池收益与波动率视图。
- 新增 Token 定价历史图、CSV 导出、10 个静态 JSON API 端点和流水线运行审计日志。
- 补入 OpenAI、Anthropic 商业化/融资信息，以及微软、Alphabet、Meta、NVIDIA、AMD、Broadcom 的官方财务基线。

### Changed
- AI Cycle 改为 `proxy_v1` 初步信号并固定为低置信度，明确披露尚未覆盖的模型能力、Token 用量、估值和 ETF 资金流。
- 来源健康页增加 GPU、CAPEX、产业链财务和行情覆盖统计。
- 公司范围扩展到 NVIDIA、AMD 和 Broadcom，共 24 家。

## [Unreleased] — Automation reliability

### Fixed
- 修复 GPU 采集器完成抓取后返回未定义 `summary` 的异常，并增加非 dry-run 回归测试。
- 补齐 `hunyuan_turbo` 的手工定价占位记录，恢复模板、候选数据和正式数据的跨文件一致性。
- AI Cycle 在定价/商业化/CAPEX 数据不足时现在输出“数据不足”，不再将默认中性分误展示为“基础设施扩张期”。
- 新闻历史按 URL + 发布时间去重，避免每次运行重复追加。

### Changed
- 定时/手动工作流将自动数据、历史和新闻写回 `main`，保留审计轨迹并防止 60 天无活动停用定时任务。
- 取消会掩盖代码错误的全量 `--skip-fetch` 回退；外部来源失败由采集器标记为 `partial`，未处理程序异常则使 CI 显式失败。

## [Unreleased] — 第一期 MVP

### Added — Step 2: 项目骨架
- 目录结构：`config/`, `data/manual/`, `data/automated/`, `data/history/`, `data/news/`, `scripts/`, `tests/`, `web/`, `.github/workflows/`
- 配置文件：`companies.json` (21家), `models.json` (20个), `sources.json` (21个数据源), `metrics_catalog.json`, `cycle_factors.json`, `watchlist.json`
- 数据文件：`token_pricing.json`, `business_metrics.json`, `supply_chain_finance.json`
- `README.md`, `CHANGELOG.md`, `LICENSE`, `.gitignore`

### Added — Step 3: 共享工具函数
- `scripts/_shared.py` — 14个工具函数：`resolve_project_root`, `load_json`, `atomic_write`, `append_jsonl`, `read_jsonl`, `now_shanghai`, `today_shanghai`, `hash_content`, `fetch_url`, `blended_cost`, `normalize_currency`, `freshness`, `normalized_metric`, `visible_text`

### Added — Step 4: 数据流水线
- `scripts/collect_token_pricing.py` — 并发抓取14个模型定价页，记录source_state
- `scripts/collect_gpu_pricing.py` — 抓取3个GPU定价源状态
- `scripts/collect_news.py` — RSS新闻发现→去重→待复核池
- `scripts/collect_business_metrics.py` — Manual数据状态检查
- `scripts/build_dashboard.py` — 合并所有数据、计算AI Cycle评分、追加历史JSONL
- `scripts/build_site.py` — 生成 `_site/` 多路径站点+7个JSON API端点
- `scripts/run_all.py` — 编排器（采集→构建dashboard→构建站点）

### Added — Step 4.5: 部署前修复
- 修复 `blended_cost_usd` 计算逻辑（`metric_id` 包含判断→`metric_category` 分类判断+input/output明细回退）
- 修复 `dry_run=True` 时不再访问真实网络（4个采集器提前返回）
- 修复 `health` 与 `cycle data_coverage` 口径不一致（`ZeroDivisionError` + 统一 `len(sources)`）
- 清理 `__pycache__/` 并确认 `.gitignore` 覆盖

### Added — Step 5: 前端 Dashboard
- `web/index.html` — HTML骨架，支持 `{{ROOT_PREFIX}}` 和 `{{ASSET_PREFIX}}` 模板变量
- `web/styles.css` — 完整设计系统（蓝色主调、CSS Variables、响应式、打印样式）
- `web/app.js` — 前端渲染引擎（5个Tab路由、DOM渲染、可排序表格、状态标记）
- `web/favicon.svg` — 独立项目图标

### Added — Step 5.5: 多路径页面与模板修复
- `build_site.py` 重写：同时替换 `ROOT_PREFIX` 和 `ASSET_PREFIX`，生成5个页面路径
- 多路径页面：`/`, `/token/`, `/business/`, `/compute/`, `/methodology/`
- 首页 `DASHBOARD_ROOT="./"`, 子页面 `DASHBOARD_ROOT="../"`
- 构建后校验：零残留模板变量

### Added — Step 6: GitHub Actions 部署
- `.github/workflows/update-deploy.yml` — CI/CD流水线
- 触发方式：定时(周一/周五09:00 BJT) + 手动dispatch + push触发
- push触发时自动 `--skip-fetch`，scheduled/manual可以尝试真实网络
- 构建后校验步骤（文件完整性 + 模板变量 + CDN检查）
- README更新：GitHub Pages部署步骤、数据声明

### Planned (后续)
- 真实数据填入 `data/manual/`（Token定价、ARR、融资、GPU价格）
- data-history 分支长期历史持久化
- 第二期：AI产业链 Tab、投资研究 Tab、Risk Overlay 自动化、半导体财务数据
