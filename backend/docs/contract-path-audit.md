# 合约地址捕捉路径自检 (Contract Address Capture-Path Audit)

> 让项目自查每条事件的 `contract_address` 是否能被解析为**该链正确的**区块浏览器链接（"捕捉路径"），输出有效/错配/缺失三类诊断，并通过日志、API、前端三路呈现。核心实现见 `backend/app/services/contract_path.py`。

---

## 1. 判定模型

对事件 `(chain, contract_address)` 做**格式 + 链映射**的静态校验（不做网络请求）：

1. `chain` 可含多链（逗号拼接），先经 `CHAIN_ALIASES` 做同链异名归一化，得到「事件链集合」。
2. `contract_address` 按格式归纳为一种运行环境：EVM `0x`(40 位 16 进制) / Solana base58(32–44 位) / other。
3. 依据地址格式与事件声明链，解析出浏览器归属链及对应 `BROWSER_TEMPLATES` URL。

| 状态 | 含义 | 判定条件 |
|---|---|---|
| `valid` | 捕捉路径正确 | 能解析出浏览器 URL，且浏览器归属链 ∈ 事件链集合 |
| `misassigned` | 被指错链 | 能解析出 URL，但归属链 ∉ 事件链集合（常见于裸 `0x` 地址匹配不到受支持链） |
| `missing` | 无捕捉路径 | 占位地址 / 格式非受支持环境 / 链不受支持，无法生成浏览器 URL |

### `fail_type` 原因分类

| fail_type | 说明 |
|---|---|
| `ok` | 解析成功，状态为 `valid` |
| `no_address` | `contract_address` 为空 |
| `placeholder` | 占位地址（`DefiLlama#*`、`ext_fetched_*` 等），非真实链上地址 |
| `format_unknown` | 地址格式既非 EVM `0x` 也非 Solana base58 |
| `chain_unknown` | `0x` 地址但事件 `chain` 无法归一化到受支持 EVM 链（默认回退 Etherscan，记为错配） |
| `chain_mismatch` | base58 地址（疑似 Solana）但事件 `chain` 未含 Solana |

### EVM 多链地址的归属解析

`0x` 地址理论上可部署于任意 EVM 链。判定取「事件声明了哪些 EVM 链」：

- 声明含 Ethereum → 归属 Etherscan；
- 否则取声明链中**字母序首个**（保证确定性）；
- 均未声明受支持 EVM 链 → 默认 Etherscan，记为 `misassigned`。

## 2. 三路输出

### (1) 后端日志（运维监控）

- **应用启动**：`main.py` lifespan 启动时打印巡检汇总。
- **定时抓取**：`scheduler.py` 每次 `run_fetch_job` 执行追溯/收敛后打印汇总。

典型日志（真实线上现状，大量占位地址故 valid=0 属正常，非 bug）：

```
合约捕捉路径巡检: 共1383条 | 正确0 错配0 缺失1383 | 按原因 {'placeholder': 1177, 'format_unknown': 206}
```

### (2) API 接口（按链筛选 / 集成调用）

**`GET /api/v1/admin/contract-path-audit`**

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chain` | string | 否 | 按事件 `chain` 关键词过滤（可含多链，子串匹配） |

返回结构：

```json
{
  "total": 1383,
  "counts": { "valid": 0, "misassigned": 0, "missing": 1383 },
  "fail_breakdown": { "placeholder": 1177, "format_unknown": 206 },
  "items": [
    {
      "incident_id": 1,
      "external_id": "...",
      "project_name": "...",
      "chain": "Ethereum",
      "contract_address": "0x...",
      "status": "valid",
      "fail_type": "ok",
      "resolved_chain": "ethereum",
      "browser_url": "https://etherscan.io/address/0x...",
      "hint": "解析为 ethereum 浏览器"
    }
  ]
}
```

字段含义：`status`（valid/misassigned/missing）、`fail_type`（见上表）、`resolved_chain`（解析出的浏览器归属链规范键）、`browser_url`（生成的浏览器链接，missing 时为空）、`hint`（人类可读原因）。

> 注：路由前缀由 `config.API_PREFIX` 控制，默认 `/api/v1`；本地为 `/api/v1`，若环境配置不同请以实际前缀为准。

### (3) 前端页面（用户体验）

- 事件详情接口 `GET /api/v1/incidents/{id}` 注入 `contract_path_valid`（`true`/`false`，无地址时为 `false`）。
- 详情区「核心合约/程序地址」行据此显示徽标：绿色「捕捉路径有效」/ 琥珀色「捕捉路径异常」。

> 说明：地址→徽标依据后端 `contract_path_valid`；地址→链接跳转仍沿用现有前端轻量链映射，二者在个别场景（如多链 `0x` 地址）可能有轻微不一致，属已知可接受项。

## 3. 本地快速验证

```powershell
# 后端启动后，查看巡检日志汇总
cd backend
.\.venv\Scripts\python.exe run.py

# 或用接口直接查询某链巡检结果（PowerShell）
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/admin/contract-path-audit" -Method Get
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/admin/contract-path-audit?chain=Ethereum" -Method Get

# 单条事件详情里查看 contract_path_valid 字段
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/incidents/1" -Method Get
```

## 4. 支持的公链与浏览器

支持 29 条公链归一化与浏览器映射（完整见 `contract_path.py` 的 `CHAIN_ALIASES` / `BROWSER_TEMPLATES`）。核心映射示例：

| 规范链键 | 常见别名 | 浏览器 |
|---|---|---|
| ethereum | eth, ethereum mainnet | etherscan.io |
| bsc | bnb chain, binance smart chain | bscscan.com |
| arbitrum | arbitrum one, arbitrum nova | arbiscan.io |
| optimism | op mainnet | optimistic.etherscan.io |
| polygon | matic | polygonscan.com |
| base | base mainnet | basescan.org |
| zksync | zksync era | explorer.zksync.io |
| solana | solana mainnet | solscan.io |
| tron | tron trx | tronscan.org |
| bitcoin | btc | mempool.space |
| sui / aptos / near / ton | ... | suiscan / aptoslabs / nearblocks / tonscan |

如需新增链，在 `CHAIN_ALIASES` 加别名、`BROWSER_TEMPLATES` 加模板，并在 `EVM_CHAINS` 登记 EVM 链键即可。

## 5. 运维建议

- `valid=0` 且大量 `placeholder` 通常反映数据源（如 DefiLlama）只下发占位地址，属源数据现状；可结合数据清洗或补全真实地址接口排查。
- `misassigned` 出现时优先核查该事件的 `chain` 标注是否被写错（例如裸 `0x` 未声明链）。
- 巡检为**静态校验**，不探测浏览器可达性；如需验证链接可访问，请单独集成健康检查。