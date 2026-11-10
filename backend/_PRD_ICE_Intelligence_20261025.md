# PRD — ICE Intelligence. Web3 安全事件分析平台

> 产品需求文档（Product Requirements Document）
> 版本：v1.0 · 状态：核心平台已实现 + 浏览器插件进行中 · 更新日期：2026-10-25

---

## 目录

1. [项目背景与产品定位](#1-项目背景与产品定位)
2. [事件抓取与分析管道](#2-事件抓取与分析管道)
3. [前端与核心 UI 交互规范](#3-前端与核心-ui-交互规范)
4. [可信追溯与收敛引擎](#4-可信追溯与收敛引擎)
5. [浏览器插件 ICE Intelligence](#5-浏览器插件-ice-intelligence)
6. [架构、部署与运行](#6-架构部署与运行)

---

## 1. 项目背景与产品定位

### 1.1 背景

Web3 领域全网安全事件（Rug Pull、私钥泄露、跨链桥攻击、预言机操纵、共因性灾难等）频发。安全研究者与普通用户缺少一个**全网聚合、信源可溯源、能主动告警**的事件情报终端。现有来源分散、口径不一、无统一严重度与追溯体系。

### 1.2 产品定位

**ICE Intelligence**（Intrusion Countermeasure Electronics）是一款**全网 Web3 安全事件抓取、分析与威胁情报终端**。

- **全网聚合**：Provider 适配器多源抓取，覆盖主流公链，按规范流水线去重入库。
- **可信追溯**：L1–L4 四级信源，链路可溯源，结论可信。
- **主动告警**：浏览器插件对用户浏览的链上地址/域名做实时威胁检测与高危横幅告警。
- **开放协作**：社区纠错沉淀集体智慧，人工修正结果不被自动流程覆盖。

### 1.3 核心价值

| 维度 | 说明 |
| --- | --- |
| 全网聚合 | 覆盖全网主流公链安全事件，早发现突破口 |
| 可信追溯 | L1 警报 / L2 快讯 / L3 研报 / L4 链上凭证 |
| 主动告警 | 插件实时检测 + 网页高危红色 Banner 横幅 |
| 开放纠错 | 社区提交更正，accepted 字段被自动流程锁定 |

### 1.4 目标用户

| 用户 | 场景 |
| --- | --- |
| 安全研究员 | 事件复盘、根因/特征分析、信源追查 |
| 项目方 | 自查合约/站点是否被标记为风险 |
| 普通用户 | 浏览 Etherscan 等区块浏览器时查看地址是否涉险 |

---

## 2. 事件抓取与分析管道

采用 `fetch → extract → match → filter → deduplicate → idempotent upsert` 流水线，多 Provider 适配器继承抽象基类，封装错误处理与请求参数。

| 规则 | 说明 |
| --- | --- |
| Provider 缺稳定公共 API | 返回空结果（而非无效 URL），保证数据准确性 |
| 单源失败 | 隔离 + 记录日志，不中断整体流程 |
| 去重 | 按 `(provider_name, url)` 去重 |
| 幂等 upsert | 按 `(event_id, provider_name, url)` 避免重复 |
| 定时任务 | APScheduler 每小时增量抓取 + 重试机制 |

---

## 3. 前端与核心 UI 交互规范

### 3.1 视觉规范（Minimal High-Definition Light Mode）

- **色板 token**：页面背景 `#F8F9FA` / 卡片 `#FFFFFF` / 边框 `#E5E7EB` / 主文字 `#1F2937` / 次要 `#6B7280` / 辅助 `#9CA3AF` / 品牌强调 `#2563EB`。
- 全局明亮背景；蓝色用于激活态/关键高亮；文字层级=标题深灰/正文中灰/提示浅灰。
- 布局：无侧边栏全宽内容区（顶部全局操作区 + 主内容卡片式大留白）。

### 3.2 事件库与联合筛选

- 列表筛选：风险类别、状态（进行中/已确认/已缓解/白帽拦截/调查中）、关键词、公链（两级生态分组：以太坊 EVM → Solana → 其他，组内字母升序）、年份/月份、信源等级。
- 公链列表过滤残缺链名碎片，仅保留完整有效公链。
- 信源等级筛选需同时覆盖 `trace_links.level` 与 `trace_sources.category`，任一击中即命中。
- 列表计数：`共 X 起`，滚动到底部加载更多，接口返回真实 `total_count`。

### 3.3 详情研判

- 展示事件完整信息；追溯信源按 URL 去重合并，取最高信源等级作为整体等级。
- 攻击入口/根因/特征/核心合约地址/处置建议等平铺字段。
- 合约捕捉路径巡检：为合约地址生成链上浏览器 URL。

### 3.4 导出

- PRD 与文档可导出为 Markdown，命名格式：`{项目名}-PRD-{日期}.md`。

---

## 4. 可信追溯与收敛引擎

| 等级 | 含义 |
| --- | --- |
| L1 | 警报 |
| L2 | 快讯 |
| L3 | 研报 |
| L4 | 链上凭证 |

- **匹配优先级**：TxHash(1.0) > 合约地址(0.9) > 项目名+时间窗(0.85) > 归一化别名(0.7) > 弱关联(0.5)。
- **收敛引擎**：`reliability_score ≥ 0.9` 且 L3/L4 资料确认根因时才输出处置建议，保证自动化建议质量。
- **社区纠错**：`incident_corrections` 中 accepted 字段被自动流程锁定跳过，不覆盖人工修正。

---

## 5. 浏览器插件 ICE Intelligence

### 5.1 概述

Chrome Manifest V3 扩展，实现上下文检测与网页端主动高危告警。

### 5.2 核心接口（check_context）

```
GET /api/v1/extension/check_context?query=<地址|域名>
```

- 含 `.` 且 `0x` 前缀（ENS 如 vitalik.eth）或带 `https://` → 剥协议按域名匹配；纯 `0x` → 按链上地址匹配。
- 命中：

```json
{ "matched": true, "count": 1, "max_severity": "High",
  "incidents": [{ "id": 1, "title": "...", "severity": "High", "root_cause": "...", "sig": "..." }] }
```

- 未命中（空态，必填）：

```json
{ "matched": false, "count": 0, "max_severity": null, "incidents": [] }
```

- `severity`/`max_severity` 枚举严格限定大小写：`Low | Medium | High | Critical`。

### 5.3 插件能力

| 能力 | 说明 |
| --- | --- |
| Popup 检测 | 对当前页面地址/域名调用 check_context，按 max_severity 分级渲染，未命中干净空态，跳转平台详情 |
| Content 脚本注入 | 识别 Etherscan/BSCScan/PolygonScan/SolanaScan 页面 `/address/0x…` 地址或域名 |
| 高危 Banner | 地址判定为 High/Critical 时页顶注入红色警示横幅（含风险文案 + 点击跳转详情）；页面安全静默 |
| 通信 | background 调 check_context + 5 分钟缓存；popup 经 `chrome.runtime.sendMessage` 获取数据；fetch 带 5s AbortController 超时，异常静默降级 |
| 安全 | 禁止 Shadow DOM；Banner 为 body 直接子元素 + 高特异性选择器 + z-index 999999；文案用 textContent 渲染防 XSS；SPA 用 500ms 轮询 location.href（不 hook pushState）；同一地址 5 分钟去重；重载后旧页面发送消息用 try/catch 吞掉 `Extension context invalidated` |

### 5.4 插件视觉

- 主色品牌蓝 `#2563EB`，背景 `#F8F9FA`；高危红 `#EF4444`。
- 根据 max_severity 统一分级着色，Critical/High 醒目高亮。

---

## 6. 架构、部署与运行

### 6.1 技术栈

- **前端**：单 HTML + Tailwind CSS（无 npm / 无 build）。
- **后端**：Python FastAPI + SQLAlchemy ORM；启动自动建表 + 幂等迁移（SQLite 本地 / PostgreSQL 生产）。
- **调度**：APScheduler 每小时定时抓取 + 启动数据源自检与合约捕捉路径巡检。
- **部署**：Render；前端与 API 同端口（`/` 静态兜底，`/api/*` 走接口）。

### 6.2 CORS

- 显式 `allow_origin_regex=r"chrome-extension://.*"`，支持浏览器插件跨域（勿用 `allow_origins=["chrome-extension://*"]`）。

### 6.3 运行方式

- 本地启动：`cd backend && .\.venv\Scripts\python.exe run.py`
- 本地访问：http://localhost:8000
- 插件加载：`chrome://extensions` → 开发者模式 → 加载已解压 `extension/` 目录
- 生产：https://www.iceintel.xyz

---

## 附：当前里程碑

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| M1 | 抓取管道 + 事件库 + 联合筛选 + 详情研判 + 统计看板 | 已完成 |
| M2 | 可信追溯体系（L1–L4）+ 收敛引擎 + 社区纠错 | 已完成 |
| M3 | 浏览器插件（popup 检测 + 高危 Banner） | 进行中 |
| M4 | 多链/域名扩展（official_domains 白名单 + 多区块浏览器） | 进行中 |

---

*本 PRD 依据已实现的源代码与架构逻辑编写，供下载/导出与后续迭代参考。*