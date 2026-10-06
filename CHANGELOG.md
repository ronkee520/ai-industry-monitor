# Changelog

## [Unreleased] — 方法论审计与稳健性增强

### Added
- 首页新增产业发展强度历史序列，并明确方法版本变化可能造成口径断点。
- 评分展开区新增五组权重情景、加权几何平均和九组阶段阈值敏感性检验。
- 新增缺失子因子权重放大、周期调整预警有效覆盖范围、阈值校准状态和资本投入非线性解读。
- 构建阶段写入可抓取的静态摘要，并增加学术引用元数据、项目引用方式和全站投资免责声明。

### Changed
- ARR与短期年化运行率分别标准化后合成，不再直接相加；企业客户披露少于3家公司时自动退出计分。
- Token价格趋势同时考虑价格变化幅度与降价广度，避免只报告模型等权中位数。
- 将“市场拥挤代理”更名为“价格动量/过热代理”，避免把纯价格指标误解为完整估值与资金拥挤度。
- 证据完整度从45/40/15主观加权改为三维等权几何平均，并明确它不是统计置信概率。
- 来源等级扩展为可执行的T1/T2/T3纳入规则，补充Tokenizer、CAPEX拆分和产业链双重计数边界。

## [Unreleased] — 产品化界面与实时模型雷达

### Added
- 加入最新模型自动发现：每次更新从公开 API 目录提取重点厂商最近模型、上下文和市场价格，并在 Token 经济页展示。
- 补入 GPT-6 Astra、GPT-6.1 Sol、GPT-6 Luna、Claude 5.5、Gemini 3.8 Flash、Grok 4.7 与 DeepSeek V4 系列的官方价格基线。

### Changed
- 移除界面中的开发说明、示例警告、手工维护路径和阶段性评述，改为面向最终用户的指标与空状态。
- 新闻模块改为“AI 产业动态”；“方法论与数据”精简为“数据与来源”，只保留口径、来源和更新状态。

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
- 全站升级为机构研究终端视觉体系：深色品牌头部、页面级研究标题、强化 KPI/表格层级、涨跌色彩与移动端适配。
- Windows 原子文件替换增加短暂占用重试，避免索引器或安全扫描导致偶发构建失败。

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
