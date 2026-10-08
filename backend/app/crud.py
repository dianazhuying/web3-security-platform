"""数据库查询封装."""
from typing import Optional

from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.orm import Session

from app.models import Incident, IncidentTraceLink

# 信源等级筛选: 按 L1-L4 中存在可点击链接(url非空)的等级数 (0-4)
# 键 "0"-"4" 对应前端 L0-L4 语义 (L0=无可点击信源/未验证, Ln=达到该等级及以上);
# 旧键 none/g1-g4 保留兼容。
VALID_REPORT = {"none": 0, "g1": 1, "g2": 2, "g3": 3, "g4": 4, "0": 0, "1": 1, "2": 2, "3": 3, "4": 4}

# 生态分类: 以太坊生态(EVM 系) / Solana 生态 -> 具体公链映射
# 未列入的链归入「其他生态」; EVM/SOLANA 集合尽量完整覆盖库内别名。
ECOSYSTEM_LABELS = {"EVM": "以太坊生态", "SOLANA": "Solana生态", "OTHER": "其他生态"}
EVM_CHAINS = {
    "Ethereum", "Arbitrum", "Optimism", "Base", "Linea", "Blast", "zkSync Era", "Polygon",
    "Polygon zkEVM", "Scroll", "Metis", "Mantle", "Starknet", "Berachain", "Sei", "Story",
    "BounceBit", "Mode", "Cronos", "Celo", "Abstract", "Fantom", "Fuse", "Avalanche",
    "BNB Chain", "BSC", "Binance Smart Chain", "Binance", "BNB", "Sonic", "Supra",
    "Polygon zkEVM", "Klaytn", "Conflux", "Elastos", "Heco", "Huobi Eco Chain",
    "Loopring", "MegaETH", "Hyperliquid L1", "Taiko", "RISE", "Saga", "TAC", "0G",
    "Unichain", "ZIGChain", "Citrea", "Nesa", "Mezo", "Monad", "ICON", "BOB",
}
SOLANA_CHAINS = {"Solana", "Meter"}  # Meter 为 Solana 系(Solana VM 兼容), 一并归入 Solana 生态


def _chain_match(field, value: str):
    """构造「公链 value 作为逗号拼接多链的成员或被精确匹配」的条件."""
    c = value.strip()
    return or_(
        field == c,
        field.like(f"{c},%"),
        field.like(f"%,{c}"),
        field.like(f"%,{c},%"),
    )


def _ecosystem_condition(field, ecosystem: str):
    """按生态过滤: EVM / SOLANA 命中集合内任一链; OTHER 则为既不含 EVM 也不含 SOLANA 链."""
    def members(mem_set: set[str]) -> or_:
        return or_(*[_chain_match(field, m) for m in mem_set])

    if ecosystem == "EVM":
        return members(EVM_CHAINS)
    if ecosystem == "SOLANA":
        return members(SOLANA_CHAINS)
    # OTHER: 不命中 EVM 也不命中 SOLANA
    return and_(
        ~members(EVM_CHAINS),
        ~members(SOLANA_CHAINS),
    )


def list_incidents(
    db: Session,
    *,
    category: str = "ALL",
    status: str = "ALL",
    q: Optional[str] = None,
    chain: Optional[str] = None,
    ecosystem: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    report: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Incident]]:
    """联合筛选: 风险大类 + 状态 + 关键词 + 公链/生态 + 年份/月份 + 追溯报告完整度, 按事件发生时间倒序分页."""
    filters = []
    if category and category != "ALL":
        filters.append(Incident.risk_class == category)
    if status and status != "ALL":
        filters.append(Incident.status == status)
    if year:
        filters.append(extract("year", Incident.occurred_at) == int(year))
    if month:
        filters.append(extract("month", Incident.occurred_at) == int(month))
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Incident.title.ilike(pattern),
                Incident.project_name.ilike(pattern),
                Incident.chain.ilike(pattern),
            )
        )
    if chain:
        # 公链筛选: chain 为逗号拼接的多链字符串, 精确等于 或 作为集合成员被包含
        filters.append(_chain_match(Incident.chain, chain))
    if ecosystem and ecosystem != "ALL":
        filters.append(_ecosystem_condition(Incident.chain, ecosystem))
    if report:
        target = VALID_REPORT.get(report)
        if target is not None:
            # 该事件有可点击链接的追溯等级数
            report_cnt = (
                select(func.count(func.distinct(IncidentTraceLink.level)))
                .where(
                    IncidentTraceLink.incident_id == Incident.id,
                    IncidentTraceLink.url != "",
                )
                .scalar_subquery()
            )
            filters.append(report_cnt == target if target == 0 else report_cnt >= target)

    total = db.scalar(
        select(func.count()).select_from(Incident).where(*filters)
    ) or 0

    items = db.scalars(
        select(Incident)
        .where(*filters)
        .order_by(Incident.occurred_at.desc().nullslast(), Incident.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return total, items


def get_chains(db: Session, limit: int = 30, ecosystem: Optional[str] = None) -> list[str]:
    """返回事件中涉及的独立公链列表 (按事件数倒序, 取前 limit 条).

    chain 字段为逗号拼接的多链字符串, 需拆分后按单个公链聚合计数.
    ecosystem: 可选 EVM/SOLANA, 仅返回该生态下的公链 (用于前端联动).
    """
    conds = [Incident.chain.isnot(None), Incident.chain != ""]
    rows = db.execute(
        select(func.count().label("cnt"), Incident.chain)
        .where(*conds)
        .group_by(Incident.chain)
        .order_by(func.count().desc())
    ).all()
    counts: dict[str, int] = {}
    for row in rows:
        for part in row.chain.split(","):
            p = part.strip()
            if not p or "…" in p or len(p) < 2:
                # 滤除源数据残缺链名 (含省略号/单字符碎片), 避免污染公链下拉
                continue
            counts[p] = counts.get(p, 0) + 1
    # 生态过滤(在拆分后的单链层面): 只保留属于目标生态的链
    if ecosystem in ("EVM", "SOLANA"):
        mem = EVM_CHAINS if ecosystem == "EVM" else SOLANA_CHAINS
        counts = {k: v for k, v in counts.items() if k in mem}
    elif ecosystem == "OTHER":
        counts = {k: v for k, v in counts.items() if k not in EVM_CHAINS and k not in SOLANA_CHAINS}
    top = sorted(counts.items(), key=lambda kv: (kv[0].casefold(), kv[0]))
    return [name for name, _n in top[:limit]]
