# Trace 模块架构设计文档

> 可信追溯报告子系统 `backend/app/services/trace/`。从多源安全团队抓取真实证据，按事件精准绑定为可溯源报告，并驱动智能处置建议收敛。
> 配套规则文档：`docs/trace-pipeline.md`、`docs/data-selection-rules.md`。

## 1. 总体架构与数据流

```
定时任务 (APScheduler, 每小时)
      │
      ▼
run_fetch_job ──► run_fetch(db)            # 1. DefiLlama 事件全量/增量入库 (已存在, 不覆盖)
      │
      ├─► run_trace_pipeline(db)           # 2. 抓取→提取→匹配→写库 trace_sources
      │       provider 抓取候选
      │          │  优先级: TxHash > 合约地址 > 项目名(别名归一化)
      │          ▼
      │       matcher.score_event_source   # 置信度 0.5–1.0, 低于 THRESHOLD(0.5) 丢弃
      │          ▼
      │       (provider_name, url) 去重 → 幂等 upsert trace_sources
      │
      └─► converge_incidents(db)           # 3. 高置信(≥0.9)确证后生成处置建议 (不覆盖人工纠错)
```

## 2. 模块职责

| 文件 | 职责 |
|------|------|
| `provider/base.py` | `Provider` 抽象基类：`collect_for(event)` 模板方法，抓取异常安全降级返回 `[]`，绝不崩管道；内置 urllib 抓取（UA + timeout） |
| `provider/slowmist.py` | 慢雾 Zone，`POST_MORTEM(L2)`，无法确认真实 URL 时返回空（宁缺毋假） |
| `provider/beosin.py` | Beosin，`ALERT(L1)` |
| `provider/peckshield.py` | PeckShield，`ALERT(L1)` |
| `provider/chain.py` | 区块浏览器 TxHash 适配器，`ONCHAIN_EVIDENCE(L4)`，按地址前缀映射 Etherscan/Solscan |
| `provider/__init__.py` | 装配并导出 `PROVIDERS` 列表 |
| `matcher.py` | `normalize_name` 别名归一化；`score_event_source` 置信度打分；`is_acceptable(≥0.5)` |
| `pipeline.py` | 编排：拉 DefiLlama 全量 → 映射库内 incident → 评分 → 去重 → 幂等 upsert（含统计） |
| `convergence.py` | 收敛引擎：高置信 + 类型确证 → 生成 `user_advisory`/`project_advisory`，受纠错保护 |

## 3. 数据模型

`TraceSource`（新表 `trace_sources`）：`id` / `event_id`(FK incidents) / `provider_name` / `provider_type`(ALERT·POST_MORTEM·FORENSICS·ONCHAIN_EVIDENCE) / `category`(L1–L4) / `title` / `url` / `reliability_score`(float)。

`Incident.trace_sources` 为 dynamic list（`lazy="dynamic"`），便于按置信度/类型查询收敛；`Incident.trace_links`（旧固定 4 级）保留兼容。

## 4. 关键设计决策

- **宁缺毋假**：安全团队无稳定公开 API，provider 仅在能确认真实 URL 时产出候选，杜绝假链接/404。
- **置信度阈值**：`THRESHOLD=0.5`；高置信边界 `0.9`（收敛触发阈值 `HIGH_CONFIDENCE`）。
- **幂等 upsert**：去重键 `(provider_name, url)`；已存在 `(event_id, provider_name, url)` 跳过，不放大数据。
- **人工纠错优先**：`incident_corrections` 中 `accepted` 的 `user_advisory`/`project_advisory` 字段被锁定，收敛引擎不写盖。
- **健壮性**：网络/单 provider/单事件异常均隔离计入统计，主流程与调度器不中断。

## 5. 接口与验证

- 手动触发：`POST /api/v1/admin/fetch-trigger`（DefiLlama 抓取，返回 `inserted_count/source/source_error`）。
- 状态：`GET /api/v1/admin/fetch-status`（含每轮追溯与收敛摘要）。
- 冒烟：`convergence.py` 与 `pipeline.py` 内置内存 SQLite 自测（生成建议 / 纠错保护 / 去重 / 幂等）。