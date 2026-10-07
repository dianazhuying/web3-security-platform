"""Pydantic Schema: API 请求 / 响应模型."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TraceSourceOut(BaseModel):
    """可信追溯来源 (多源抓取管道产出)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    provider_name: str
    provider_type: str
    category: str
    title: str
    url: str
    reliability_score: float


class TraceLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    level: str
    name: str
    url: str
    description: str
    sort_order: int


class IncidentSummary(BaseModel):
    """列表项摘要."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    title: str
    chain: str
    project_name: str
    contract_type: str
    severity: str
    status: str
    risk_class: str
    loss_amount_text: str
    loss_usd: float
    fetched_at: datetime


class IncidentOut(BaseModel):
    """事件完整详情."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    title: str
    chain: str
    project_name: str
    contract_type: str
    contract_address: str
    loss_amount_text: str
    loss_usd: float
    remark: str
    severity: str
    status: str
    source_origin: str
    risk_class: str
    root_cause_id: str
    root_cause_text: str
    sig_desc: str
    sig_val: str
    user_advisory: str
    project_advisory: str
    fetched_at: datetime
    trace_links: list[TraceLinkOut] = []
    trace_sources: list[TraceSourceOut] = []


class IncidentListResponse(BaseModel):
    total: int
    total_count: int
    page: int
    page_size: int
    items: list[IncidentSummary]


class FetchResult(BaseModel):
    """抓取执行结果 (真实数据源可能返回 0 起新事件)."""

    inserted_count: int
    source: str
    incident: Optional[IncidentOut] = None
    source_error: Optional[str] = None


class FetchStatusOut(BaseModel):
    """定时任务执行状态 (最近执行日志 + 下次执行时间)."""

    scheduler_running: bool
    fetch_interval_seconds: int
    retry_times: int
    last_run_at: Optional[datetime] = None
    last_status: str
    last_detail: str = ""
    next_run_at: Optional[datetime] = None


class CorrectionCreate(BaseModel):
    """提交纠错请求体."""

    field_name: str = Field(default="", max_length=64, description="需要纠正的字段名")
    suggested_value: str = Field(..., max_length=2000, description="建议的更正值")
    reason: str = Field(default="", max_length=2000, description="纠错原因/证据说明")
    submitted_by: str = Field(default="", max_length=128, description="提交人标识")


class CorrectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    field_name: str
    suggested_value: str
    reason: str
    submitted_by: str
    status: str
    created_at: datetime


class CategoryCount(BaseModel):
    name: str
    count: int


class StatsOut(BaseModel):
    """看板统计."""

    total_incidents: int
    total_loss_usd: float
    confirmed_count: int
    investigating_count: int
    correction_count: int
    category_distribution: list[CategoryCount]
    severity_distribution: list[CategoryCount]
    last_fetch_at: Optional[datetime] = None
