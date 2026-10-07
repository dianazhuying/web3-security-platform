# 可信追溯报告 · 数据管道 (Trace Pipeline)

> 阶段二核心组件。从多源安全团队抓取真实证据，按事件精准绑定为 L1–L4 可信追溯报告，并以置信度打分 + 交叉印证收敛保证可信。

---

## 1. 目标与输入

- **目标**：为每条 `incident` 生成/合并一组 `trace_sources`（可信追溯来源集合），替代早期拼接的假链接。
- **输入源**（可插拔 provider）：
  - `slowmist` — 慢雾 Zone 研报 / 推文
  - `beosin` — Beosin Alert 预警 + 复盘文章
  - `peckshield` — PeckShield Alert 推文
  - `chain` — 各链浏览器 Tx / 合约 (etherscan / solscan / polygonscan…)
  - `defillama` — DefiLlama Hacks 记录（基线锚点）

## 2. 追溯分类 L1–L4 与 provider_type

| 层 | 语义 | provider_type | 示例来源 |
|----|------|---------------|----------|
| L1 | 警报现场 | `ALERT` | PeckShield / Beosin 首发预警 |
| L2 | 技术快讯 | `POST_MORTEM` | 慢雾 / Beosin 复盘快讯 |
| L3 | 深度分析 | `FORENSICS` | 链上资金追踪研报 / 审计方结案 |
| L4 | 链上凭证 | `ONCHAIN_EVIDENCE` | Etherscan / Solscan Tx 与合约 |

## 3. 抓取与归一化流程

```
provider 拉取 → 原始记录归一化 → 去重(dedupe by source_url) → 事件匹配(matcher)
      → 置信度打分(scorer) → 交叉印证收敛(consensus) → 幂等写库(upsert trace_sources)
```

- **去重键**：`(provider_name, url)` 唯一。
- **匹配键优先级**：攻击 `TxHash` > 攻击合约地址 > 项目名（归一化别名）。
- **幂等**：以 `trace_sources` 的 `(event_id, provider_name, category)` 感知重复，upsert 不放大。

## 4. 置信度打分模型 (0.5 – 1.0)

`reliability_score` 表示该来源与事件匹配的确信度。

| 匹配证据 | 得分 |
|----------|------|
| 攻击交易哈希完全一致 | 1.00 |
| 攻击合约地址一致 | 0.90 |
| 项目名精确匹配 + 时间窗吻合 | 0.85 |
| 项目别名/归一化完全匹配 | 0.70 |
| 仅关键词弱相关(需人工复核) | 0.50 |

- 得分随匹配强度向上取，不累加。
- 多条独立来源命中同一事实时不因数量通胀分数，只用于**交叉印证收敛**。

## 5. 交叉印证收敛机制

- 同一事件存在 >1 个 provider 的独立来源时，视为**多源印证**，在 `trace_sources` 上标记 `corroborated=true` 语义。
- **冲突处理**：不同来源对同一字段（如损失金额/时间）不一致时——
  1. 取 `reliability_score` 最高来源为准；
  2. 同分时取来源链较权威者（FORENSICS/链上 > POST_MORTEM > ALERT）；
  3. 仍冲突则保留 `title` 差异并记入日志，供阶段三个人工复核。
- **收敛出口**：某事件至少一个来源 `reliability_score ≥ 0.85` 即视为"具备可信追溯报告"；`≥0.85` 的来源数 ≥2 升为"多源交叉印证"。

## 6. 调度与写入

- 并入现有 APScheduler，每小时增量执行。
- 写入 `trace_sources` 表（见数据模型），`Incident.trace_sources` dynamic list。
- 不覆盖 `incident_corrections`（人工纠错优先）。