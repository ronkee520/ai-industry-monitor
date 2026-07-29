# 定价数据录入工作流

## 流程概览

```
自动抓取候选 → 人工核验 → 填入模板 → 导入 → 构建 → 部署
```

## 步骤详解

### 1. 自动抓取候选价格

```bash
python scripts/collect_pricing_candidates.py --project-root . --verbose
```

输出文件：
- `data/manual/pricing_candidates.json` — 结构化候选数据
- `data/manual/pricing_candidates.csv`  — Excel 可打开的预览表

### 2. 查看候选价格

打开 `pricing_candidates.csv`，查看每行的 `input_price_per_m_candidate` 和 `output_price_per_m_candidate` 列。

⚠️ **候选价格很可能是错误的**。自动提取只是辅助，必须人工核验。

重点关注 `extraction_status` 列：
- `parsed` / `partial` — 自动提取到数字，但需要验证
- `ambiguous` — 无法匹配到具体价格
- `js_rendered` — 页面是动态渲染的
- `failed` / `blocked` — 访问失败

### 3. 人工打开 source_url 核验

打开每行的 `source_url`，找到对应模型的标准 API 定价档位。

核验时确认：
- 模型名称是否匹配
- 定价档位（通常是标准按需/standard）
- 币种（USD 或 CNY）
- 是否有缓存命中折扣价

### 4. 填入模板

打开 `data/manual/manual_pricing_template.csv`，在对应行填入：

- `input_price_per_m` — 输入价格
- `output_price_per_m` — 输出价格
- `cached_input_price_per_m` — 缓存输入价格（可选）
- `currency` — USD 或 CNY
- `as_of_date` — 核验日期（如 2026-07-29）

没填价格的模型会在下一步被跳过。

### 5. 导入正式数据

先预览（不写文件）：

```bash
python scripts/update_manual_pricing.py --project-root . --template data/manual/manual_pricing_template.csv --dry-run
```

确认无误后正式导入：

```bash
python scripts/update_manual_pricing.py --project-root . --template data/manual/manual_pricing_template.csv
```

效果：
- 有价格 → `confidence: verified`
- 无价格 → `confidence: manual_required`（保持不变）

### 6. 重建站点

```bash
python scripts/run_all.py --project-root . --skip-fetch
```

### 7. 提交部署

```bash
git add data/manual/
git commit -m "data: verified token pricing for [模型名]"
git push
```

GitHub Actions 会自动部署。

## 数据质量标准

- ✅ `confidence: verified` — 已人工从官方定价页核验
- ⚠️ `confidence: candidate` — 自动提取，未核验
- ⚠️ `confidence: manual_required` — 需要人工录入
- ❌ `confidence: missing` — 无可用数据
- ❌ `confidence: sample` — 不在正式数据中

## 重要提示

- 自动提取的数字**绝对不要**不经验证直接使用
- missing ≠ 0
- 不同币种的横向比较使用 `config/companies.json` 中的 fx_rate
- 混合成本公式：`blended = input × 0.65 + output × 0.35`
