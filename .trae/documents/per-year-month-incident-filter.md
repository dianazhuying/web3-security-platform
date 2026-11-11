# 事件按 年份 / 月份 筛选

## Context

用户希望界面上能按**年份**与**月份**查看 Web3 安全事件。

现状与障碍:
- `Incident` 模型仅有 `fetched_at`(抓取时间)。1176 条 DefiLlama 真实事件为**同一批次抓取**,`fetched_at` 完全相同,无法按其区分年月。
- Render 线上已有 **1427 条存量数据**,`Base.metadata.create_all` 不会给已存在的表加列。
- 但数据源 DefiLlama 每条自带 `date`(Unix 秒级时间戳,即**真实事件发生时间**),可据此补充「事件发生时间」列。

确认的决策(用户已答复):
- 交互形态:**两个独立下拉** — 年份下拉(含「全部年份」)+ 月份下拉(含「全部月份」),互不限制,可单独看全年,或按月/年月组合过滤,可与现有类别/状态/关键词筛选叠加。
- 接受新增 `occurred_at` 列 + 存量回填;列表默认排序改为**按事件发生时间倒序**(比当前的抓取时间更合理)。

## 改动方案

### 1. 数据模型 — `backend/app/models.py`
`Incident` 新增事件发生时间列(反映 DefiLlama `date`):
```python
occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=_utcnow)
```
放在 `fetched_at` 附近。

### 2. 抓取映射 — `backend/app/services/fetcher.py`
`_build_from_defillama` 中,把 `row["date"]`(Unix 秒)解析为 `datetime` 写入 `occurred_at`:
```python
occurred_at = datetime.fromtimestamp(int(row.get("date")), tz=timezone.utc) if row.get("date") else None
```
入参加入 `Incident(... occurred_at=occurred_at ...)`。(`datetime` 已 import。)

### 3. 种子对齐 — `backend/app/services/seed.py`
`build_base_incident` 给模拟事件也设 `occurred_at=BASE_FETCH_TIME`,避免本地种子产生 NULL(影响排序)。若 `Incident(...)` 默认值已足够则无需显式传,但显式更明确。

### 4. 查询过滤 — `backend/app/crud.py`
`list_incidents` 增加 `year` / `month` 可选参数,并调整排序:
```python
def list_incidents(db, *, category="ALL", status="ALL", q=None, year=None, month=None, page=1, page_size=20):
    if year:
        filters.append(extract("year", Incident.occurred_at) == int(year))
    if month:
        filters.append(extract("month", Incident.occurred_at) == int(month))
    # 排序改为同一批事件本身的时间倒序
    .order_by(Incident.occurred_at.desc().nullslast(), Incident.id.desc())
```
`from sqlalchemy import extract, func, or_, select`。注:`nullslast()` 在 SQLite 与 PostgreSQL 均支持。

### 5. API 参数 — `backend/app/api/incidents.py`
`list_incidents` 增加:
```python
year: Optional[int] = Query(default=None, ge=2000, le=2100, description="按事件发生年份过滤, e.g. 2023"),
month: Optional[int] = Query(default=None, ge=1, le=12, description="按事件发生月份过滤, e.g. 5"),
```
透传给 `crud.list_incidents`。

### 6. 数据库迁移 + 存量回填 — `backend/app/services/migrate.py`(新文件)
幂等操作,供启动调用:
- 用 `sqlalchemy.inspect(engine)` 检查 `incidents` 是否已有 `occurred_at` 列;没有则 `ALTER TABLE incidents ADD COLUMN occurred_at TIMESTAMP`。
- 若存在 `occurred_at IS NULL` 的行,从 DefiLlama 拉全量数据,建立 `external_id -> date` 映射,逐条 `UPDATE incidents SET occurred_at=... WHERE external_id=... AND occurred_at IS NULL`,分批 commit。
- 提供 `run_migrate(db, engine)` 与 `backfill_occurred_at(db)` 两个函数。

**调用点**: `backend/app/main.py` 的 `lifespan`,在建表之后、seed 之前插入:
```python
from app.services.migrate import run_migrate
...
Base.metadata.create_all(bind=engine)
run_migrate(engine)          # 加列 + 回填存量 occurred_at
...
```
(回填仅在存在 NULL 行时触发一次,不影响后续冷启动耗时。)

### 7. 前端 — `frontend/index.html`
- 筛选行(`<div class="flex flex-wrap items-center gap-3">`)内、状态下拉之后新增两个下拉框,样式复用现有的 `riskCategoryFilter`/`statusFilter`(`bg-panel border border-line ...`):
  - `yearFilter`:`<option value="ALL">全部年份</option>` + 静态生成 `2013`~`2026`
  - `monthFilter`:`<option value="ALL">全部月份</option>` + `1月`~`12月`
- `currentFilters` 增加 `year: "ALL"`, `month: "ALL"`。
- `filterIncidents()` 读取两个下拉值写入 `currentFilters`。
- `loadIncidents()` 请求参数增加:
```js
if (currentFilters.year !== "ALL") params.year = currentFilters.year;
if (currentFilters.month !== "ALL") params.month = currentFilters.month;
```
- 年份/月份非全部时,可在列表项/计数处提示当前筛选,非必需。

## 关键文件

- 修改:`backend/app/models.py`、`backend/app/services/fetcher.py`、`backend/app/services/seed.py`、`backend/app/crud.py`、`backend/app/api/incidents.py`、`backend/app/main.py`、`frontend/index.html`
- 新增:`backend/app/services/migrate.py`

## 验证

1. **本地**:`cd backend && .\.venv\Scripts\python.exe run.py`,打开 http://localhost:8000
   - 查看日志确认 `run_migrate` 打印加列/回填结果。
   - 下拉选择某年/某月,确认列表数、已加载/共 T 计数随之变化,且与其它筛选可叠加。
   - `curl "http://localhost:8000/api/v1/incidents?year=2023&month=9&page_size=5"` 返回正常。
2. **语法/字段超限回归**:用真实 DefiLlama 数据跑一遍 `_build_from_defillama`,确认 `occurred_at` 解析正确、无其它字段超限(复用此前验证脚本)。
3. **线上**:commit + push,Render 重建后:
   - `curl "https://web3-security.onrender.com/api/v1/incidents?year=2012"` 应返回当年事件(from 源码最早 2013)。
   - `curl ".../incidents?month=1"` 返回 1 月事件。
   - 前端下拉可按年月过滤,总数正确。