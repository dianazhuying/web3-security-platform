"""攻击链条服务.

根据事件现有字段生成攻击入口单步:
1. 攻击入口 — 涉及链 + 合约/程序地址, 凭证=链上浏览器 URL (复用 contract_path.resolve_path).

利用技术、资金转移与影响、处置与缓解均不纳入攻击链条: 攻击根因/特征码已在详情面板
展示, 损失金额已在左侧事件列表展示, user_advisory / project_advisory 已在"处置建议"
模块单独展示, 均避免重复. 若未来 provider 能将真实攻击逐步复现写入 incidents.attack_steps,
则该存库值优先, 仅在存库值为空时才动态生成此骨架.
"""
from __future__ import annotations

from app.models import Incident
from app.schemas import AttackStepOut

from app.services.contract_path import resolve_path

__cache: dict[int, list[AttackStepOut]] = {}


def default_attack_steps(incident: Incident) -> list[AttackStepOut]:
    """按现有字段构造攻击入口单步骨架. 纯函数, 只读 incident, 不落库."""
    cid = getattr(incident, "id", None)
    if cid is not None and cid in __cache:
        return __cache[cid]

    chain = incident.chain or ""
    address = (incident.contract_address or "").strip()

    # 凭证: 合约/程序地址的链上浏览器 URL (复用捕捉路径解析, valid 才有)
    entry_url = ""
    if address and not address.startswith("DefiLlama#"):
        pr = resolve_path(address, chain)
        entry_url = pr.browser_url if pr.status == "valid" else ""

    if address and entry_url:
        entry_desc = f"攻击者以 {address[:14]}… 为入口合约/程序地址展开攻击, 涉及公链 {chain or '未知'}."
    elif address:
        entry_desc = f"攻击入口指向合约/程序地址 {address}, 涉及公链 {chain or '未知'}, 暂未收录链上浏览器凭证."
    else:
        entry_desc = f"该事件未收录具体合约/程序地址, 涉及公链 {chain or '未知'}."

    out = [
        AttackStepOut(
            seq=1,
            title="攻击入口",
            desc=entry_desc,
            chain=chain,
            ref_url=entry_url,
            confidence=0.9,
        )
    ]
    # 仅缓存有 id 的持久化事件 (进程内命中, 避免链上并发重复计算)
    if cid is not None:
        __cache[cid] = out
    return out