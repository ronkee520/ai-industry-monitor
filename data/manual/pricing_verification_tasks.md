# 定价核验任务清单

> 每个任务需打开 source_url，在官方定价页找到对应模型的标准 API 价格，填入 `data/manual/manual_pricing_template.csv`。

## 填写规范

每百万 tokens 价格（per 1M tokens）。如果官网单位为其他（如 per 1K tokens），先转为 /1M。

| 字段 | 说明 | 示例 |
|------|------|------|
| `input_price_per_m` | 输入价格/百万tokens | `2.50` |
| `output_price_per_m` | 输出价格/百万tokens | `10.00` |
| `cached_input_price_per_m` | 缓存输入价（可选，无则留空） | `1.25` |
| `currency` | `USD` 或 `CNY` | `USD` |
| `as_of_date` | 核验日期 | `2026-07-29` |

⚠️ 注意区分：标准按需价 ≠ Batch价 ≠ 缓存命中价 ≠ 长上下文价

---

## 🥇 第一批（优先核验）

### 1. OpenAI GPT-4o
- **source_url**: https://platform.openai.com/docs/pricing
- **model_id**: `gpt4o`
- **company_id**: `openai`
- **currency**: USD
- **注意事项**: 找到 GPT-4o（非 mini）标准档位。截图保留 proof。

### 2. OpenAI GPT-4o Mini
- **source_url**: https://platform.openai.com/docs/pricing
- **model_id**: `gpt4o_mini`
- **company_id**: `openai`
- **currency**: USD
- **注意事项**: 同页面，GPT-4o Mini 的 input/output。

### 3. Anthropic Claude Opus 4
- **source_url**: https://www.anthropic.com/pricing
- **model_id**: `claude_opus4`
- **company_id**: `anthropic`
- **currency**: USD
- **注意事项**: 页面可能有 Claude Opus / Sonnet / Haiku 多列。选 Opus 标准档。

### 4. Anthropic Claude Sonnet 4
- **source_url**: https://www.anthropic.com/pricing
- **model_id**: `claude_sonnet4`
- **company_id**: `anthropic`
- **currency**: USD

### 5. Google Gemini 2.5 Pro
- **source_url**: https://ai.google.dev/pricing
- **model_id**: `gemini25_pro`
- **company_id**: `google`
- **currency**: USD
- **注意事项**: Gemini 有阶梯定价（≤200K 和 >200K）。选用 ≤200K 的标准按需价。

### 6. Google Gemini 2.5 Flash
- **source_url**: https://ai.google.dev/pricing
- **model_id**: `gemini25_flash`
- **company_id**: `google`
- **currency**: USD

### 7. DeepSeek V3
- **source_url**: https://api-docs.deepseek.com/quick_start/pricing
- **model_id**: `deepseek_v3`
- **company_id**: `deepseek`
- **currency**: USD
- **注意事项**: 注意区分缓存命中（cache hit）和缓存未命中。选标准 API 调用（非缓存命中）价格。

### 8. DeepSeek R1
- **source_url**: https://api-docs.deepseek.com/quick_start/pricing
- **model_id**: `deepseek_r1`
- **company_id**: `deepseek`
- **currency**: USD
- **注意事项**: R1 是推理模型，有 reasoning tokens 单独计费。选标准 API 调用价格。

---

## 🥈 第二批

### 9. 阿里 Qwen3-Max
- **source_url**: https://help.aliyun.com/zh/model-studio/model-pricing
- **model_id**: `qwen3_max`
- **company_id**: `alibaba`
- **currency**: CNY（元/百万tokens）
- **注意事项**: 阿里云百炼国内版以人民币计价。可能存在 DashScope 国际版（USD），不要混淆。

### 10. 字节豆包 Seed 2.0
- **source_url**: https://www.volcengine.com/docs/84458/1585097
- **model_id**: `doubao_seed20`
- **company_id**: `bytedance`
- **currency**: CNY
- **注意事项**: 火山方舟页面为 JS 动态渲染，可能需打开浏览器开发者工具确认。

### 11. 百度 ERNIE 4.0
- **source_url**: https://cloud.baidu.com/product-s/qianfan.html
- **model_id**: `ernie4`
- **company_id**: `baidu`
- **currency**: CNY
- **注意事项**: 百度千帆定价结构复杂（含免费额度/按量/包月），选用标准按量计费价格。

### 12. 腾讯混元 Turbo
- **source_url**: https://cloud.tencent.com/product/hunyuan
- **model_id**: `hunyuan_turbo`
- **company_id**: `tencent`
- **currency**: CNY
- **注意事项**: 需先确认具体定价页 URL 和当前可用模型名称。腾讯混元可能已更新模型代际。

### 13. 智谱 GLM-4
- **source_url**: https://bigmodel.cn/pricing
- **model_id**: `glm4`
- **company_id**: `zhipu`
- **currency**: CNY
- **注意事项**: 智谱定价页为 JS 动态渲染。

### 14. 月之暗面 Kimi K2
- **source_url**: https://platform.kimi.com/
- **model_id**: `kimi_k2`
- **company_id**: `moonshot`
- **currency**: CNY
- **注意事项**: Kimi 开放平台。

---

## 🥉 第三批

### 15. Mistral Large 2
- **source_url**: https://mistral.ai/technology/
- **model_id**: `mistral_large`
- **company_id**: `mistral`
- **currency**: USD

### 16. Cohere Command R+
- **source_url**: https://cohere.com/pricing
- **model_id**: `command_r_plus`
- **company_id**: `cohere`
- **currency**: USD

### 17. Amazon Nova Pro
- **source_url**: https://aws.amazon.com/bedrock/pricing/
- **model_id**: `amazon_nova_pro`
- **company_id**: `amazon`
- **currency**: USD
- **注意事项**: Bedrock 定价按区域和吞吐量（on-demand / provisioned）分层。选 on-demand 标准档。

---

## 填表步骤

1. 打开 `data/manual/manual_pricing_template.csv`
2. 在对应行的 `input_price_per_m` 和 `output_price_per_m` 列填入价格
3. 有缓存输入价则填 `cached_input_price_per_m`
4. 填 `currency`（USD 或 CNY）
5. 填 `as_of_date`（核验日期，如 `2026-07-29`）
6. 保存 CSV

## 导入命令

填完第一批后：

```bash
# 预览
python scripts/update_manual_pricing.py --project-root . --template data/manual/manual_pricing_template.csv --dry-run

# 正式导入
python scripts/update_manual_pricing.py --project-root . --template data/manual/manual_pricing_template.csv

# 重建
python scripts/run_all.py --project-root . --skip-fetch
```
