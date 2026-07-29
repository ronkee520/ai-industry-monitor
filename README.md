# AI Industry Monitor

## AI产业与大模型商业化监测 Dashboard

> **面向研究人员的公开在线 AI 产业数据终端**

[![Update & Deploy](https://github.com/ronkee520/ai-industry-monitor/actions/workflows/update-deploy.yml/badge.svg?branch=main)](https://github.com/ronkee520/ai-industry-monitor/actions/workflows/update-deploy.yml)

> 🌐 **在线访问 Dashboard**：https://ronkee520.github.io/ai-industry-monitor/

---

## 项目定位

**AI Industry Monitor** 是一个开源的 AI 产业监测 Dashboard。它持续跟踪全球大模型商业化、Token 经济、AI 算力、云厂商资本开支和相关产业链数据，并以公开网页的形式呈现在 GitHub Pages 上。

### 与 Bloomberg Terminal 的区别

| | Bloomberg | AI Industry Monitor |
|---|---|---|
| 费用 | $24,000+/年 | 免费 |
| 登录 | 需要 | 不需要 |
| VPN | 部分功能需要 | 不需要 |
| 数据范围 | 全金融市场 | AI 产业链 |
| 自动更新 | ❌ (人工查询) | ✅ (Mon & Fri 09:00 BJT) |
| 数据溯源 | ✅ | ✅ (每条数据有 source_url, source_tier, evidence_status) |
| 可分享 | ❌ | ✅ (静态页面，可复制链接) |

---

## 监测范围

```
┌─────────────────────────────────────────┐
│  AI Industry Monitor                    │
│                                         │
│  Tab 1  总览 / AI Cycle  ← 默认首页     │
│  Tab 2  Token 经济                      │
│  Tab 3  商业化                          │
│  Tab 4  AI 算力 & 云 CAPEX              │
│  Tab 5  方法论与数据                    │
│                                         │
│  第二期: AI产业链 · 投资研究              │
└─────────────────────────────────────────┘
```

### 覆盖公司

**海外 (9)**: OpenAI, Anthropic, Google DeepMind, xAI, Meta AI, Mistral AI, Cohere, Amazon AI, Microsoft AI

**国内 (12)**: DeepSeek, 阿里通义千问, 字节豆包, 百度文心, 腾讯混元, 智谱AI, 月之暗面(Kimi), 科大讯飞星火, MiniMax, 百川智能, 零一万物, 上海AI Lab

---

## 快速开始

### 环境要求

- Python 3.10+
- Git
- 无其他依赖（项目使用 Python 标准库 + 原生 HTML/CSS/JS）

### 本地运行

```bash
# 1. 克隆项目
git clone https://github.com/ronkee520/ai-industry-monitor.git
cd ai-industry-monitor

# 2. 跳过网络采集，仅用本地数据构建
python scripts/run_all.py --project-root . --skip-fetch

# 3. 本地预览
cd _site
python -m http.server 8080
# 浏览器打开 http://localhost:8080
```

### 在线预览（本地文件）

```bash
# 直接构建站点
python scripts/build_site.py --project-root .
# 双击 _site/index.html 即可在浏览器中查看
```

### 运行测试

```bash
python -m unittest discover -s tests -v
```

---

## GitHub Pages 部署

### 第一步：推送到 GitHub

```bash
git remote add origin https://github.com/ronkee520/ai-industry-monitor.git
git push -u origin main
```

### 第二步：启用 GitHub Pages

1. 打开仓库 **Settings → Pages**
2. **Source** 选择 **GitHub Actions**
3. 保存

### 第三步：触发首次部署

1. 打开仓库 **Actions** 标签
2. 选择 **Update & Deploy AI Industry Monitor**
3. 点击 **Run workflow** → 勾选 `skip_fetch: true`（首次部署建议跳过网络采集）
4. 等待 workflow 完成

### 第四步：访问站点

部署成功后，站点 URL 为：

```
https://ronkee520.github.io/ai-industry-monitor/
```

### 自动更新时间

| 触发方式 | 时间 |
|---------|------|
| 定时-周一 | 北京时间 **09:00** (UTC 01:00) |
| 定时-周五 | 北京时间 **09:00** (UTC 01:00) |
| 手动触发 | 随时通过 Actions → Run workflow |
| Push 触发 | 当 `config/` `data/manual/` `scripts/` `web/` 变更时 |

### 初次部署注意事项

- 首次部署建议使用 `skip_fetch: true`，因为部分数据源可能需要网络访问
- 如果自动采集失败，workflow 会自动回退到 `data/manual/` 中的数据
- 所有 sample 数据都有明确标记，真实数据需要在 `data/manual/` 中手动填入

---

## 数据更新

### 自动更新（推荐）

GitHub Actions 每周一和周五自动运行。流程：

```
数据采集 → 数据校验 → 构建 dashboard JSON → 构建 _site → 部署 GitHub Pages
```

### 手动更新特定模块

```bash
# 只更新 Token 定价
python scripts/collect_token_pricing.py --project-root .

# 只更新商业化指标
python scripts/collect_business_metrics.py --project-root .

# 只更新 GPU 价格
python scripts/collect_gpu_pricing.py --project-root .
```

### 手动编辑数据

部分数据（如 ARR、融资、半导体财务）难以全自动采集，可直接编辑 `data/manual/` 中的 JSON 文件，然后 commit 到 main 分支触发自动部署。

---

## 项目结构

```
ai-industry-monitor/
├── config/          # 公司/模型/数据源/指标体系 配置
├── data/
│   ├── manual/      # 人工采集的半静态数据
│   ├── automated/   # 脚本产出的最新快照
│   └── history/     # 时序历史 (JSON Lines)
├── scripts/         # Python 数据采集与构建脚本
├── web/             # 前端 HTML/CSS/JS
├── tests/           # 单元测试
└── _site/           # 构建产物 (gitignored)
```

---

## 公共 API

部署后可通过以下 JSON API 访问结构化数据：

| 端点 | 说明 |
|------|------|
| `/api/index.json` | API 目录（自描述） |
| `/api/dashboard.json` | 全量快照 |
| `/api/overview.json` | 总览 + AI Cycle 评分 |
| `/api/token-pricing.json` | Token 价格数据 |
| `/api/business.json` | 商业化指标 |
| `/api/gpu-pricing.json` | GPU 价格 |
| `/api/health.json` | 系统健康状态 |

---

## 数据来源与分级

### 来源等级

| Tier | 类型 | 示例 |
|------|------|------|
| **T1** | 一手官方 | 公司官网定价页、季报/年报、交易所公告、监管文件 |
| **T2** | 权威媒体/公开研究 | Reuters, Bloomberg, 公开研究机构报告 |
| **T3** | 聚合/自媒体 | RSS聚合、行业博客（仅用于发现，不自动写入正式指标） |

### 证据状态

`official_pricing` · `company_disclosure` · `media_report` · `public_snapshot` · `estimate` · `sample` · `missing` · `manual_required`

---

## 重要提示

- 本 Dashboard 使用公开可获取的数据源，不对数据准确性做保证
- 自动抓取的定价页面可能因网站改版而失效，会标记为 `stale_fallback` 或 `manual_required`
- **所有标记为 `sample` 或 `confidence: "missing"` 的数据点不应被引用为正式数据**
- 商业化指标（ARR/融资/估值）需要从可靠来源手动核验后填入
- 本项目仅用于产业研究参考，**不构成投资建议**

---

## 贡献

欢迎提交 Issue 和 Pull Request。

- Bug 修复: 请直接提交 PR
- 新功能: 请先开 Issue 讨论
- 数据更新: 请附带来源链接和核验截图

---

## 数据声明

- **sample 数据不代表真实结论** — 所有 `confidence: "sample"` 的数据仅用于开发演示和结构验证
- **missing ≠ 0** — `value: null` 的数据点表示不可用，不会被显示为 0
- **pending_review 新闻不进入正式指标** — RSS 新闻仅进入待复核池
- **不构成投资建议** — 本 Dashboard 为公开数据研究工具，所有结论请回到原始来源核验
- **数据溯源** — 每条指标记录包含 `source_url`、`source_tier`(1-3)、`evidence_status`
- **口径不可比** — ARR ≠ 年收入、训练 Token ≠ 推理 Token、不同币种不混排

## License

MIT License — 详见 [LICENSE](LICENSE)
