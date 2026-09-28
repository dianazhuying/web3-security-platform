"""历史事件种子数据: 首次启动时填充 200 起模拟事件 (幂等)."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Incident, IncidentTraceLink
from app.reference_data import BASE_FETCH_TIME, REAL_WORLD_PROJECTS, RISK_CLASSES, SOURCES, STATUSES

BASE_COUNT = 200


def _tx_hashes(i: int, chain: str) -> tuple[str, str]:
    """按公链生成合约地址 / 交易哈希 (与前端原型格式一致)."""
    tx_sol = f"5x9A82376b321a3b21900001878705a212376b321a3b2190000{i}"
    tx_eth = f"0x{i:04x}878705a212376b321a3b21908712390123901{i}"
    if chain == "Solana":
        return tx_sol[:32], tx_sol
    return tx_eth[:32], tx_eth


def build_base_incident(i: int) -> Incident:
    """构造第 i 起历史事件 (确定性生成)."""
    p = REAL_WORLD_PROJECTS[(i - 1) % len(REAL_WORLD_PROJECTS)]
    r = RISK_CLASSES[(i - 1) % len(RISK_CLASSES)]
    s = SOURCES[(i - 1) % len(SOURCES)]
    slug = p[0].lower().replace(" ", "-")
    tweet_id = f"1783920193810{100 + i}"
    address, tx_hash = _tx_hashes(i, p[1])
    has_l3 = i % 7 != 0
    loss_w = i * 110 + 200  # 单位: 万美元

    return Incident(
        external_id=f"inc_{i}",
        title=f"{p[0]} - {r[2]}",
        chain=p[1],
        project_name=p[0],
        contract_type=p[2],
        contract_address=address,
        loss_amount_text=f"约 {loss_w} 万美元",
        loss_usd=loss_w * 10000,
        remark="管理私钥被社交工程诱骗泄露",
        severity="极高" if i % 3 == 0 else ("高" if i % 2 == 0 else "中"),
        status=STATUSES[(i - 1) % len(STATUSES)],
        source_origin=s[0],
        risk_class=r[0],
        root_cause_id=r[1],
        root_cause_text=r[2],
        sig_desc="权限控制 / 交易模式与状态更新异常",
        sig_val=f"sig_pattern_{i}_flashloan_or_privkey",
        user_advisory=f"检查对 {p[0]} 的授权状态，暂缓参与该协议极高风险交易。",
        project_advisory="立即暂停相关合约函数，多签隔离权限并配合链上追踪。",
        fetched_at=BASE_FETCH_TIME,
        trace_links=[
            IncidentTraceLink(
                level="L1 警报现场",
                name=f"{s[0].split(' ')[0]} 关于 {p[0]} 的首发 X 警报推文",
                url=f"https://x.com/PeckShieldAlert/status/{tweet_id}",
                description=f"推文 ID: #{tweet_id}",
                sort_order=0,
            ),
            IncidentTraceLink(
                level="L2 技术快讯",
                name=f"{p[0]} 漏洞与攻击复盘分析",
                url=f"https://slowmist.com/post-mortem/2026-{slug}-incident.html",
                description="技术快讯: 攻击路径与漏洞逻辑拆解",
                sort_order=1,
            ),
            IncidentTraceLink(
                level="L3 深度分析",
                name=f"{p[0]} 资金流向与洗钱链路追踪研报" if has_l3 else "暂未收录该层级研报",
                url=f"https://trmlabs.com/reports/{slug}-analysis" if has_l3 else "",
                description="Chainalysis / TRM 资金追查研报" if has_l3 else "小规模事件未触发第三方深度研报",
                sort_order=2,
            ),
            IncidentTraceLink(
                level="L4 链上凭证",
                name=f"{p[1]} 黑客攻击交易凭证 (TxHash)",
                url=f"https://solscan.io/tx/{tx_hash}" if p[1] == "Solana" else f"https://etherscan.io/tx/{tx_hash}",
                description=f"交易哈希: {tx_hash[:20]}...",
                sort_order=3,
            ),
        ],
    )


def seed_incidents(db: Session, count: int = BASE_COUNT) -> int:
    """若事件表为空则填充历史事件, 返回实际写入数量."""
    existing = db.scalar(select(func.count()).select_from(Incident)) or 0
    if existing > 0:
        return 0
    for i in range(1, count + 1):
        db.add(build_base_incident(i))
    db.commit()
    return count
