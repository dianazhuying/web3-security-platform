"""Chrome 扩展 (ICE Sentinel) 专用轻量接口.

统一入口 /api/v1/extension/check_context: 按域名 或 链上地址 检索关联安全事件。
匹配策略: incidents.official_domains JSON 白名单为主, project_name 模糊匹配 fallback。
严重度输出统一映射为外部枚举: Low | Medium | High | Critical。
"""
from typing import Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Incident

router = APIRouter()

# 内部中文严重度 → 扩展展示用英文枚举
_SEVERITY_MAP = {
    "极高": "Critical",
    "高": "High",
    "中": "Medium",
    "低": "Low",
}
_SEVERITY_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


def _normalize_severity(raw: Optional[str]) -> Optional[str]:
    """中文严重度 → Low/Medium/High/Critical; 未知或空返回 None."""
    key = (raw or "").strip()
    if key in _SEVERITY_RANK:
        return key
    return _SEVERITY_MAP.get(key)


def _extract_host(query: str) -> Optional[str]:
    """从 query 提取规范化域名 host (去协议头、去端口、转小写); 无法提取返回 None."""
    q = query.strip()
    if "://" not in q:
        q = "//" + q
    host = urlsplit(q).hostname
    return host.lower() if host else None


def _domain_matches(domains: list, host: str) -> bool:
    """host 命中白名单: 全等 或 是某白名单域名的子域."""
    for d in domains or []:
        d = (d or "").strip().lower()
        if not d:
            continue
        if host == d or host.endswith("." + d):
            return True
    return False


def _categorize(query: str) -> str:
    """判定 query 类型: domain / address / unknown."""
    q = query.strip()
    if "://" in q:                       # 显式协议头 → 域名
        return "domain"
    lower = q.lower()
    if lower.startswith("0x"):           # 纯 0x 开头 → 链上地址
        return "address"
    if "." in q:                         # 含点(如 ENS domain) → 域名
        return "domain"
    return "unknown"                     # 其余按域名/项目名兜底处理


@router.get(
    "/extension/check_context",
    response_model=schemas.ExtensionCheckOut,
    summary="Chrome 扩展: 按域名/链上地址检索关联安全事件上下文",
)
def check_context(
    query: str = Query(..., description="待检测上下文, 支持 https:// 前缀/文件名域名/ENS 域名/0x 链上地址"),
    db: Session = Depends(get_db),
) -> schemas.ExtensionCheckOut:
    empty = schemas.ExtensionCheckOut(matched=False, count=0, max_severity=None, incidents=[])
    q = (query or "").strip()
    if not q:
        return empty

    kind = _categorize(q)
    addr = q.lower().strip() if kind == "address" else None
    host = _extract_host(q) if kind == "domain" else None
    host = host or (q.lower() if kind == "unknown" else host)

    # MVP 数据量可控: 内存过滤 (域名 JSON 数组跨库匹配需加载到 Python 判断更稳妥)
    rows = db.scalars(select(Incident).order_by(Incident.id.desc())).all()

    hits: list[tuple[int, Incident]] = []  # (severity_rank, incident)
    for inc in rows:
        matched = False
        if kind == "address":
            caddr = (inc.contract_address or "").strip().lower()
            # 兼容 0x 前缀 / 校验和 / 尾部截断差异
            matched = bool(caddr) and (addr == caddr or addr.endswith(caddr) or caddr in addr)
        elif host:
            matched = _domain_matches(inc.official_domains, host)
            if not matched:
                # fallback: 项目名模糊匹配 (弱相关)
                pn = (inc.project_name or "").lower()
                matched = bool(pn) and (q.lower() in pn or pn in q.lower())
        if not matched:
            continue
        sev = _normalize_severity(inc.severity)
        hits.append((_SEVERITY_RANK.get(sev, 0), inc))

    if not hits:
        return empty

    hits.sort(key=lambda t: t[0], reverse=True)
    output = [
        schemas.ExtensionIncidentMatch(
            id=inc.id,
            title=inc.title,
            severity=_normalize_severity(inc.severity),
            root_cause=inc.root_cause_text or "",
            sig=inc.sig_val or "",
        )
        for _r, inc in hits
    ]
    max_sev = _normalize_severity(hits[0][1].severity)
    return schemas.ExtensionCheckOut(
        matched=True,
        count=len(output),
        max_severity=max_sev,
        incidents=output,
    )