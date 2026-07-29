# Changelog

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
