"""ORM 模型: 安全事件、可信追溯链接、社区纠错记录."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Incident(Base):
    """链上安全事件主表."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(256))
    chain: Mapped[str] = mapped_column(String(32), index=True)
    project_name: Mapped[str] = mapped_column(String(128), index=True)
    contract_type: Mapped[str] = mapped_column(String(128), default="")
    contract_address: Mapped[str] = mapped_column(String(128), default="")
    loss_amount_text: Mapped[str] = mapped_column(String(64), default="")
    loss_usd: Mapped[float] = mapped_column(Float, default=0.0)
    remark: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), index=True)  # 极高 / 高 / 中
    status: Mapped[str] = mapped_column(String(16), index=True)  # 已确认 / 调查中
    source_origin: Mapped[str] = mapped_column(String(256), default="")
    risk_class: Mapped[str] = mapped_column(String(128), index=True)
    root_cause_id: Mapped[str] = mapped_column(String(128), default="")
    root_cause_text: Mapped[str] = mapped_column(String(256), default="")
    sig_desc: Mapped[str] = mapped_column(String(256), default="")
    sig_val: Mapped[str] = mapped_column(String(128), default="")
    user_advisory: Mapped[str] = mapped_column(Text, default="")
    project_advisory: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True, default=_utcnow)  # 事件发生时间(可空)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    trace_links: Mapped[list["IncidentTraceLink"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentTraceLink.sort_order",
    )
    corrections: Mapped[list["IncidentCorrection"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )


class IncidentTraceLink(Base):
    """事件的 4 等级可信追溯链接 (L1 警报 / L2 快讯 / L3 研报 / L4 链上凭证)."""

    __tablename__ = "incident_trace_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(256), default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str] = mapped_column(String(256), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    incident: Mapped["Incident"] = relationship(back_populates="trace_links")


class IncidentCorrection(Base):
    """社区纠错提交记录."""

    __tablename__ = "incident_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(64), default="")
    suggested_value: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    submitted_by: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending / accepted / rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    handled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    incident: Mapped["Incident"] = relationship(back_populates="corrections")
