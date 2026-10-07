"""智能处置建议收敛引擎 (convergence).

触发条件
--------
某事件至少存在一个 ``reliability_score >= W_s`` 的高置信度来源, 且漏洞类型已确证
(存在非空 ``root_cause_text``, 且至少有 POST_MORTEM/FORENSICS 记载或 L3/L4 层级来源佐证),
则自动生成/更新结构化的处置建议 (用户侧 ``user_advisory`` + 项目侧 ``project_advisory``)。

不覆盖人工纠错
-------------
若 ``incident_corrections`` 中已存在针对 ``user_advisory`` / ``project_advisory`` 的
``accepted`` 记录, 对应字段将以人工纠错为准, 引擎不写盖。
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.models import Incident, IncidentCorrection, TraceSource

logger = logging.getLogger(__name__)

#: 高置信度来源阈值 W_s
HIGH_CONFIDENCE = 0.9
#: 确证漏洞类型所需的来源类型/层级 (任一命中即可)
PROOF_TYPES = {"POST_MORTEM", "FORENSICS"}
PROOF_LEVELS = {"L3", "L4"}

#: 引擎可写写的建议字段 (受 corrections 保护)
ADVISORY_FIELDS = ("user_advisory", "project_advisory")


def _existing_accepted_fields(db, incident_id: int) -> set[str]:
    """返回该事件已有人工 accepted 覆盖的建议字段集合."""
    rows = db.scalars(
        select(IncidentCorrection.field_name).where(
            IncidentCorrection.incident_id == incident_id,
            IncidentCorrection.status == "accepted",
            IncidentCorrection.field_name.in_(ADVISORY_FIELDS),
        )
    ).all()
    return set(rows)


def _build_user_advisory(incident: Incident) -> str:
    return (
        f"经多源高置信度证据确证，该事件漏洞类型为“{incident.root_cause_text}”。"
        f"如曾与 {incident.project_name} 交互，请立即停止并撤销相关合约授权，"
        "警惕以同类手法伪装的钓鱼站点与高仿链接。"
    )


def _build_project_advisory(incident: Incident) -> str:
    return (
        f"项目方应针对确证漏洞类型“{incident.root_cause_text}”启动事件响应："
        "暂停受影响合约函数，完成代码审计与修复，并评估资金影响与补偿方案。"
    )


def converge_incident(db, incident: Incident) -> dict:
    """对单个事件执行收敛, 返回该事件产生的动作计数."""
    result = {"user_generated": 0, "project_generated": 0, "blocked": 0}

    high_srcs = db.scalars(
        select(TraceSource).where(
            TraceSource.event_id == incident.id,
            TraceSource.reliability_score >= HIGH_CONFIDENCE,
        )
    ).all()
    if not high_srcs:
        return result

    confirmed = bool(incident.root_cause_text) and any(
        s.provider_type in PROOF_TYPES or s.category in PROOF_LEVELS for s in high_srcs
    )
    if not confirmed:
        return result

    protected = _existing_accepted_fields(db, incident.id)

    # 用户侧与项目侧建议独立判定: 被人工纠错 accepted 锁定的字段不写盖
    if "user_advisory" not in protected:
        incident.user_advisory = _build_user_advisory(incident)
        result["user_generated"] = 1
    else:
        result["blocked"] += 1
    if "project_advisory" not in protected:
        incident.project_advisory = _build_project_advisory(incident)
        result["project_generated"] = 1
    else:
        result["blocked"] += 1
    return result


def converge_incidents(db) -> dict:
    """收敛所有携带高置信度来源的事件, 生成/更新处置建议. 返回全局统计."""
    stats = {
        "scanned": 0,
        "high_confidence": 0,
        "confirmed": 0,
        "user_generated": 0,
        "project_generated": 0,
        "blocked": 0,
    }
    event_ids = db.scalars(
        select(TraceSource.event_id)
        .where(TraceSource.reliability_score >= HIGH_CONFIDENCE)
        .distinct()
    ).all()
    for eid in event_ids:
        incident = db.get(Incident, eid)
        if incident is None:
            continue
        stats["scanned"] += 1
        r = converge_incident(db, incident)
        if r["user_generated"] or r["project_generated"] or r["blocked"]:
            stats["high_confidence"] += 1
            if r["user_generated"] or r["project_generated"]:
                stats["confirmed"] += 1
        stats["user_generated"] += r["user_generated"]
        stats["project_generated"] += r["project_generated"]
        stats["blocked"] += r["blocked"]

    if stats["user_generated"] or stats["project_generated"]:
        db.commit()
        logger.info("[convergence] 收敛完成: 高置信 %s, 确证 %s, 用户建议生成 %s, 项目建议生成 %s, 受纠错保护跳过 %s",
                    stats["high_confidence"], stats["confirmed"],
                    stats["user_generated"], stats["project_generated"], stats["blocked"])
    return stats


if __name__ == "__main__":
    """冒烟测试: 内存 SQLite 校验收敛与纠错保护."""
    from sqlalchemy import create_engine

    from app.database import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker

    db = sessionmaker(bind=engine)()

    inc = Incident(
        external_id="defillama-conv1", title="Conv X attack", chain="Ethereum",
        project_name="ConvX", contract_address="0x" + "2" * 40,
        severity="高", status="已确认", risk_class="智能合约技术风险",
        root_cause_text="Reentrancy", user_advisory="", project_advisory="",
    )
    db.add(inc)
    db.flush()
    # 高置信 POST_MORTEM 证据
    db.add(TraceSource(event_id=inc.id, provider_name="Slowmist", provider_type="POST_MORTEM",
                       category="L3", title="PM", url="https://example.com/pm", reliability_score=0.95))
    db.commit()

    s = converge_incidents(db)
    assert s["user_generated"] == 1 and s["project_generated"] == 1, s
    assert "Reentrancy" in inc.user_advisory and "Reentrancy" in inc.project_advisory

    # 加一个人工 accepted correction 锁定 user_advisory → 引擎不再覆盖该字段
    prev_user = inc.user_advisory
    db.add(IncidentCorrection(incident_id=inc.id, field_name="user_advisory",
                              suggested_value="人工审核值", reason="x", submitted_by="t",
                              status="accepted"))
    db.commit()
    s2 = converge_incidents(db)
    assert s2["user_generated"] == 0 and s2["blocked"] == 1, s2
    assert inc.user_advisory == prev_user  # 受纠错保护, 保持不被引擎覆盖
    db.close()
    print("convergence smoke OK")