"""合约地址「捕捉路径」服务.

判断一条事件的 ``contract_address`` 是否能被解析为**该链正确的**区块浏览器链接
(即"捕捉路径"是否有效), 供项目自检/巡检, 生成运维诊断报表与前端提示。

判定模型
--------
对事件 (chain, contract_address):
- ``chain`` 可含多个链(逗号拼接)或多链组合; 先做同链异名归一化, 取「该事件涉及的链集合」。
- ``contract_address`` 按其格式归纳为一种运行环境 (EVM 0x / Solana base58 / 其它)。
- ``expected_chain`` = 解析规则唯一确定的链 (例如 0x 归一化后能对应到某个 EVM 主链);
  ``browser`` = 该链对应的官方浏览器模板。
- 状态:
  - ``valid``    : 能解析出浏览器 URL, 且该浏览器归属链 ∈ 事件链集合 (捕捉路径正确)。
  - ``misassigned``: 能解析出浏览器 URL, 但归属链 ∉ 事件链集合 (被指错到别的链, 常见于 0x 地址).
  - ``missing``  : 无法解析出任何浏览器 URL (占位/格式不认识/链不受支持), 无捕捉路径。
- ``fail_type`` 可解释原因, 供前端/日志展示。

注: 此处仅做【格式+链映射】静态校验, 不做网络可达性请求。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Incident

# ---- 链名归一化: 同一条链的多种叫法 → 规范键 (EVM 链键即其浏览器域名主段) ----
CHAIN_ALIASES: dict[str, list[str]] = {
    "ethereum": ["ethereum", "ethereum mainnet", "eth", "ethereum_poa"],
    "bsc": ["bsc", "bnb chain", "binance smart chain", "bnb smart chain", "binance", "bnb"],
    "polygon": ["polygon", "polygon pos", "matic", "polygon_mainnet"],
    "arbitrum": ["arbitrum", "arbitrum one", "arbitrum_one", "arbitrum nova"],
    "optimism": ["optimism", "optimistic", "op mainnet", "op_mainnet"],
    "avalanche": ["avalanche", "avalanche c-chain", "avax", "avalanche_c-chain"],
    "base": ["base", "base mainnet"],
    "blast": ["blast", "blast mainnet"],
    "zkSync": ["zksync", "zksync era", "zksync_era", "zksync era mainnet"],
    "linea": ["linea", "linea mainnet"],
    "scroll": ["scroll", "scroll mainnet"],
    "fantom": ["fantom", "opera", "ftm"],
    "fuse": ["fuse", "fuse network"],
    "solana": ["solana", "solana mainnet"],
    "tron": ["tron", "tron trx", "tronmainnet"],
    "bitcoin": ["bitcoin", "btc", "bitcoin sv"],
    "litecoin": ["litecoin", "ltc"],
    "dogecoin": ["dogecoin", "doge"],
    "cosmos": ["cosmos", "cosmos hub", "cosmoshub"],
    "sui": ["sui", "sui mainnet"],
    "aptos": ["aptos", "aptos mainnet"],
    "near": ["near", "near mainnet"],
    "ton": ["ton", "ton mainnet", "the open network"],
    "eos": ["eos", "eos mainnet"],
    "hedera": ["hedera", "hbar"],
    "cardano": ["cardano", "ada"],
    "stellar": ["stellar", "xlm"],
    "osmosis": ["osmosis"],
    "flow": ["flow", "flow mainnet"],
}
CANON_ALIAS: dict[str, str] = {}
for _canon, _aliases in CHAIN_ALIASES.items():
    for _a in _aliases:
        CANON_ALIAS[_a] = _canon

# 各链官方浏览器 URL 模板 (合约/账户地址). {addr} 为占位.
BROWSER_TEMPLATES: dict[str, str] = {
    "ethereum": "https://etherscan.io/address/{addr}",
    "bsc": "https://bscscan.com/address/{addr}",
    "polygon": "https://polygonscan.com/address/{addr}",
    "arbitrum": "https://arbiscan.io/address/{addr}",
    "optimism": "https://optimistic.etherscan.io/address/{addr}",
    "avalanche": "https://snowtrace.io/address/{addr}",
    "base": "https://basescan.org/address/{addr}",
    "blast": "https://blastscan.io/address/{addr}",
    "zkSync": "https://explorer.zksync.io/address/{addr}",
    "linea": "https://lineascan.build/address/{addr}",
    "scroll": "https://scrollscan.com/address/{addr}",
    "fantom": "https://ftmscan.com/address/{addr}",
    "fuse": "https://explorer.fuse.io/address/{addr}",
    "solana": "https://solscan.io/account/{addr}",
    "tron": "https://tronscan.org/#/address/{addr}",
    "bitcoin": "https://mempool.space/address/{addr}",
    "litecoin": "https://blockchair.com/litecoin/address/{addr}",
    "dogecoin": "https://blockchair.com/dogecoin/address/{addr}",
    "cosmos": "https://www.mintscan.io/cosmos/account/{addr}",
    "sui": "https://suiscan.xyz/mainnet/account/{addr}",
    "aptos": "https://explorer.aptoslabs.com/account/{addr}",
    "near": "https://nearblocks.io/address/{addr}",
    "ton": "https://tonscan.org/address/{addr}",
    "eos": "https://bloks.io/account/{addr}",
    "hedera": "https://hashscan.io/mainnet/account/{addr}",
    "cardano": "https://cardanoscan.io/address/{addr}",
    "stellar": "https://stellar.expert/explorer/mainnet/account/{addr}",
    "osmosis": "https://www.mintscan.io/osmosis/account/{addr}",
    "flow": "https://flowscan.org/account/{addr}",
}

# EVM 兼容链集合 (0x 地址可部署于其上任意一条)
EVM_CHAINS = {
    "ethereum", "bsc", "polygon", "arbitrum", "optimism", "avalanche",
    "base", "blast", "zksync", "linea", "scroll", "fantom", "fuse",
}
SOLANA_CHAINS = {"solana"}

_HEX40 = re.compile(r"^0x[0-9a-fA-F]{40}$")
_BASE58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


@dataclass
class PathResult:
    chain: str          # 事件原始 chain 字段
    address: str        # 原始 contract_address
    status: str         # valid / misassigned / missing
    fail_type: str      # ok / no_address / placeholder / format_unknown / chain_unknown / chain_mismatch
    resolved_chain: str = ""    # 解析出的浏览器归属链 (规范键)
    browser_url: str = ""       # 生成的浏览器 URL (valid/misassigned 时有值)
    hint: str = ""


def _normalize_name(name: str) -> str | None:
    n = (name or "").strip().lower().replace("_", " ")
    n = re.sub(r"\s+", " ", n)
    return CANON_ALIAS.get(n)


def _event_chains(chain_field: str) -> set[str]:
    """把事件 chain 字段(可逗号拼接)归一化成规范链键集合."""
    out: set[str] = set()
    for part in (chain_field or "").split(","):
        p = part.strip()
        if not p:
            continue
        canon = _normalize_name(p)
        if canon:
            out.add(canon)
    return out


def _address_family(addr: str) -> str:
    """按格式归纳地址的运行时环境: evm / solana / other."""
    if _HEX40.match(addr):
        return "evm"
    if _BASE58.match(addr):
        return "solana"
    return "other"


def resolve_path(address: str, chain_field: str) -> PathResult:
    """解析单条事件的「捕捉路径」并判定是否有效."""
    addr = (address or "").strip()
    res = PathResult(chain=chain_field, address=addr, status="missing", fail_type="no_address")
    if not addr:
        return res
    if addr.startswith("DefiLlama#") or addr.startswith("ext_fetched_") or addr.startswith("0x" * 4):
        res.fail_type = "placeholder"
        res.hint = "占位地址, 非真实链上地址, 无捕捉路径"
        return res

    chains = _event_chains(chain_field)
    family = _address_family(addr)
    if family == "other":
        res.fail_type = "format_unknown"
        res.hint = "地址格式无法识别 (非 EVM 0x / Solana base58)"
        return res
    if family == "solana":
        if not (chains & SOLANA_CHAINS):
            res.fail_type = "chain_mismatch"
            res.hint = "base58 地址(疑似 Solana), 但事件 chain 未含 Solana"
            return res
        res.resolved_chain = "solana"
        res.browser_url = BROWSER_TEMPLATES["solana"].format(addr=addr)
        res.status = "valid"
        res.fail_type = "ok"
        return res

    # EVM 0x 地址: 浏览器归属取决于事件声明了哪条 EVM 链
    claimed = chains & EVM_CHAINS
    if not claimed:
        res.fail_type = "chain_unknown"
        res.hint = "0x 地址, 但事件 chain 无法归一化到受支持的 EVM 链, 默认归 Etherscan"
        res.resolved_chain = "ethereum"
        res.browser_url = BROWSER_TEMPLATES["ethereum"].format(addr=addr)
        res.status = "misassigned"
        return res
    # 多链声明时取优先级最高(以太坊优先, 否则按字母) —— 既要正确也要可预测
    resolved = "ethereum" if "ethereum" in claimed else sorted(claimed)[0]
    res.resolved_chain = resolved
    res.browser_url = BROWSER_TEMPLATES[resolved].format(addr=addr)
    res.status = "valid"
    res.fail_type = "ok"
    res.hint = f"解析为 {resolved} 浏览器"
    return res


def audit_incident(insp: Incident) -> PathResult:
    return resolve_path(insp.contract_address, insp.chain)


def audit_contract_paths(db: Session, chain: str | None = None) -> dict:
    """遍历全库(可按事件 chain 关键词过滤)巡检捕捉路径, 返回汇总+清单."""
    stmt = select(Incident)
    if chain:
        stmt = stmt.where(Incident.chain.contains(chain))
    incidents = list(db.scalars(stmt))

    rows = [audit_incident(inc) for inc in incidents]
    counts = {"valid": 0, "misassigned": 0, "missing": 0}
    fail_breakdown: dict[str, int] = {}
    for r in rows:
        counts[r.status] += 1
        fail_breakdown[r.fail_type] = fail_breakdown.get(r.fail_type, 0) + 1

    items = [
        {
            "incident_id": inc.id,
            "external_id": inc.external_id,
            "project_name": inc.project_name,
            "chain": inc.chain,
            "contract_address": inc.contract_address,
            "status": r.status,
            "fail_type": r.fail_type,
            "resolved_chain": r.resolved_chain,
            "browser_url": r.browser_url,
            "hint": r.hint,
        }
        for inc, r in zip(incidents, rows)
    ]

    return {
        "total": len(items),
        "counts": counts,
        "fail_breakdown": fail_breakdown,
        "items": items,
    }


def audit_summary_text(summary: dict) -> str:
    c = summary["counts"]
    f = summary["fail_breakdown"]
    return (
        f"合约捕捉路径巡检: 共{summary['total']}条 | 正确{c['valid']} "
        f"错配{c['misassigned']} 缺失{c['missing']} | 按原因 {f}"
    )