"""攻击链条服务.

根据事件现有字段生成 1→2 纵向编号的攻击步骤骨架:
1. 攻击入口    — 涉及链 + 合约/程序地址, 凭证=链上浏览器 URL (复用 contract_path.resolve_path).
2. 利用技术    — 攻击根因 + 特征码 SIG, 凭证=首个有效的可信溯源 URL.

处置与缓解、资金转移与影响不纳入攻击链条: user_advisory / project_advisory 已在面板
"处置建议"模块单独展示, 损失金额已在左侧事件列表展示, 均避免重复. 若未来 provider 能
将真实攻击逐步复现写入 incidents.attack_steps, 则该存库值优先, 仅在存库值为空时才动态
生成此骨架. 缓存 __cache 按 incident.id 避免同一请求重复计算.
"""
from __future__ import annotations

from typing import Any

from app.models import Incident
from app.schemas import AttackStepOut

from app.services.contract_path import resolve_path

__cache: dict[int, list[AttackStepOut]] = {}


def _valid_trace_url(incident: Incident) -> str:
    """取事件的首个有效溯源 URL 作为凭证 (兼容 dynamic list 与已物化 list)."""
    sources = getattr(incident, "trace_sources", None)
    if hasattr(sources, "all"):  # dynamic list → 物化
        sources = sources.all()
    for s in sources or []:
        url = (s.url or "").strip()
        if url:
            return url
    return ""


def default_attack_steps(incident: Incident) -> list[AttackStepOut]:
    """按现有字段构造 2 步攻击链条骨架. 纯函数, 只读 incident, 不落库."""
    cid = getattr(incident, "id", None)
    if cid is not None and cid in __cache:
        return __cache[cid]

    chain = incident.chain or ""
    address = (incident.contract_address or "").strip()

    # 步骤1 凭证: 合约/程序地址的链上浏览器 URL (复用捕捉路径解析, valid 才有)
    entry_url = ""
    if address and not address.startswith("DefiLlama#"):
        pr = resolve_path(address, chain)
        entry_url = pr.browser_url if pr.status == "valid" else ""

    trace_url = _valid_trace_url(incident)

    steps: list[dict[str, Any]] = []

    # 1. 攻击入口
    if address and entry_url:
        entry_desc = f"攻击者以 {address[:14]}… 为入口合约/程序地址展开攻击, 涉及公链 {chain or '未知'}."
    elif address:
        entry_desc = f"攻击入口指向合约/程序地址 {address}, 涉及公链 {chain or '未知'}, 暂未收录链上浏览器凭证."
    else:
        entry_desc = f"该事件未收录具体合约/程序地址, 涉及公链 {chain or '未知'}."
    steps.append(
        {
            "seq": 1,
            "title": "攻击入口",
            "desc": entry_desc,
            "chain": chain,
            "ref_url": entry_url,
            "confidence": 0.9,
        }
    )

    # 2. 利用技术 (根因 + 特征码 SIG)
    root_text = (incident.root_cause_text or "").strip()
    sig = (incident.sig_val or "").strip()
    tech_desc = root_text or "暂无明确根因描述"
    if sig:
        tech_desc = f"{tech_desc} (特征匹配: {sig})"
    steps.append(
        {
            "seq": 2,
            "title": "利用技术",
            "desc": "攻击手法推断: " + tech_desc,
            "chain": chain,
            "ref_url": trace_url,
            "confidence": 0.85,
        }
    )

    out = [AttackStepOut(**s) for s in steps]
    # 仅缓存有 id 的持久化事件 (进程内命中, 避免链上并发重复计算)
    if cid is not None:
        __cache[cid] = out
    return out