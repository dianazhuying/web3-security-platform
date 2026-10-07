# 数据选择与可信规则 (Data Selection Rules)

> 规定哪些来源被收录为可信追溯报告、何时排除，及与既有人工纠错的关系。与 `trace-pipeline.md` 配套。

---

## 1. 收录资格

一个来源仅当满足 **全部** 条件才收录为 `trace_source`：

1. **可访问**：`url` 非空且通过可访问性校验（阶段二可选：HEAD/GET 200），杜绝垃圾/404 目标。
2. **来源可信**：`provider_name` 在受信白名单内（慢雾/Beosin/PeckShield/DefiLlama/官方链浏览器等）；未认证域名 `reliability_score` 上限 0.7。
3. **得分达标**：`reliability_score ≥ 0.50`；低于 0.50 的记录只入审计日志，不落库。
4. **去重**：`(provider_name, url)` 不重复。

## 2. 排除/降级规则

- **已知假阳性匹配**（项目名相似但时间窗不符）→ 降级至 0.5 或拒绝。
- **同一 provider 重复搬运**（如转发的转推）→ 只保留原始首发者。
- **笼统列表页**（如 DefiLlama /hacks 首页、通用 tag 聚合）→ 不作为 L3/L4 证据，仅作 L1 基线锚点。
- **付费墙 / 需登录 > 2 步的页面** → 降级为"暂未收录凭证"。

## 3. 来源优先级（同事实多源时）

```
链上凭证(ONCHAIN_EVIDENCE) > 深度分析(FORENSICS) > 复盘快讯(POST_MORTEM) > 警报(ALERT)
```

依此决定前端默认展示与 `reliability_score` 同分时的取舍。

## 4. 与前端/既有系统衔接

- 空 `url`（无有效来源）→ 前端渲染禁用态「暂未收录凭证」，**绝不生成 404 链接**。
- 前端「追溯报告完整度」筛选的档位（none/≥1/≥2/≥3/≥4）基于**有 `url` 且 `reliability_score≥0.50`** 的等级计数。
- **人工纠错优先**：`incident_corrections` 中 `accepted` 的记录优先于本管道数据，管道不对其覆盖。

## 5. 审计与可观测

- 每次抓取写入 `logs/*.log`：拉取数、去重数、匹配命中率、平均置信度、被拒来源及原因。
- 暴露 `/api/v1/admin/fetch-status` 查看最近管道执行摘要与异常。