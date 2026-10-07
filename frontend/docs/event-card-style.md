# 事件卡片组件样式规范（Event Card Component）

> 对应前端 `frontend/index.html` 中「最新安全事件」列表的卡片（`renderIncidentList()`）。
> 三行高密度结构 + 固定宽度截断 + 悬停 Tooltip + 点击复制，全列表高度一致，**不使用任何文本相似度计算**。
> 更新于 2026-10-08（400px 侧边栏 · 三行卡片 · 字段固定截断 · 复制交互）。

## 1. 布局容器（侧边栏宽度）

- 左侧列表容器固定宽度 **400px**：`lg:w-[400px] lg:min-w-[400px] lg:flex-none`。
- 外层主分析区在 lg 下切换为 flex（`lg:flex lg:items-start`），右侧深度面板 `flex-1 min-w-0` 自适应余量。
- 列表滚动区：`max-h-[460px] overflow-y-auto`，卡片纵向 `space-y-2`。
- 卡片本体：`p-2.5 rounded-lg border space-y-1.5 overflow-hidden`（`overflow-hidden` 兜底防子元素溢出破坏布局）。

## 2. 卡片字段结构与文案规则（严格固定）

| 行 | 内容 | 格式 | 截断/防挤压 |
|----|------|------|-----------|
| L1 | 事件名称 | `事件：{title}` | `flex-1 min-w-0 max-w-[260px] truncate` |
| L2 | 项目与损失 | `项目：{project_name}` ＋ `│` ＋ `💰 损失约 $1,234` | 项目 `max-w-[130px] truncate`；损失 `flex-shrink:0; whitespace-nowrap` 永远完整 |
| L2 | 状态 Tag | `{status}` | `flex-shrink:0; whitespace-nowrap; margin-left:8px`，绝不挤压/遮盖 |
| L3 | 属性归类 | `公链：{chain}` ＋ `│` ＋ `协议：{contract_type}` | 公链/协议各 `max-w-[100px] truncate` |

- **文案前缀**：每行带明确中文前缀（`事件`/`项目`/`损失`/`公链`/`协议`），不依赖上下文推断。
- **损失金额**：取 `loss_usd`（数值）——有效且 >0 → `💰 损失约 $1,234`（千分位抹零）；否则 → `损失约 未知`。
- **协议取值**：`contract_type`（后端 `IncidentSummary` 直接输出），缺失兜底 `未知类型`。
- **禁则**：不得通过文本相似度/模糊匹配隐藏或重排字段；字段完全由后端数据直接驱动。

## 3. 固定宽度截断规则

- 所有可变长文本的容器均为 `flex-1 min-w-0`，可自由收缩。
- 事件名 `max-w-[260px]`、项目名 `max-w-[130px]`、公链/协议各 `max-w-[100px]`，超长一律 `truncate` 显示 `...`。
- 损失金额、状态 Tag、前缀标签（`项目：`/`│`/`公链：`/`协议：`）均 `flex-shrink:0` + `whitespace-nowrap`，**永远完整展示**。

## 4. 交互增强

- **悬停 Tooltip**：`title`、`project_name`、`chain`、`contract_type` 四个可截断文本节点均挂 `title` 属性（原生浏览器气泡），Hover 显示完整无截断字符串；不被卡片 `overflow-hidden` 裁剪。
- **点击复制**：上述节点挂 `data-copy="{完整值}"`，事件委托捕获（`e.stopPropagation()` 避免误触选中详情），复制成功 Toast 提示 `已复制: {前48字符}...`。
- 其余：`cursor-pointer`；Hover `bg-[#F3F4F6] border-[#E5E7EB]`；列表首条 `NEW` + `animate-highlightNew`；点击 `selectIncident(id)` 同步选中态 2px 金色左边条。

## 5. 视觉 Token（跟随 Light 设计规范）

- 卡片底色 `#FFFFFF`（选中 `#F3F4F6`）；描边 `#E5E7EB`。
- 文字层级：
  - L1 事件名：`text-xs font-semibold`，主文字 `#1F2937`。
  - L2 前缀/损失：`text-inkMuted`（`#9CA3AF`）；项目值 `text-inkSecondary`（`#6B7280`）+ `font-medium`。
  - L2 状态：`text-[10px] text-gold/90 font-mono`。
  - L3 前缀 `text-inkMuted`，值 `text-inkSecondary font-medium`。
- 徽标：`极高` = `bg-gold/10 text-gold border-gold/30`；`高` = 灰底 `bg-[#F3F4F6] text-inkSecondary border-line`（均 `shrink-0`）。

## 6. 校验要点

- 后端列表接口持续包含 `title / project_name / chain / contract_type / status / loss_usd`。
- 回归项：首页 HTTP 200、列表接口 200 无 404；长标题/项目名/公链/协议截断出省略号；金额与状态 Tag 不挤压、不遮盖；Hover 显示完整原文；点击字段复制成功且不误触选中。
