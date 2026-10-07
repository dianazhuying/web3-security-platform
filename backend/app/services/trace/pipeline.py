"""可信追溯报告 · 抓取→提取→匹配→写库管道 (pipeline).

流程
----
1. 从 ``settings.DEFILLAMA_HACKS_URL`` 抓全量事件, 构造候选事件列表;
   同时查询库内已有 incidents 并按 ``external_id`` 建索引用于映射。
2. 对每个已入库事件, 遍历 ``PROVIDERS`` 的 ``collect_for`` 合并候选 →
   ``score_event_source`` → 过滤 ``is_acceptable`` → 按 ``(provider_name, url)``
   去重 (保留最高分)。
3. 幂等 upsert: 命中 ``(event_id, provider_name, url)`` 已存在则跳过
   (计入 ``skipped_existing``), 否则 ``db.add(TraceSource(...))``。
4. ``db.commit()`` 后返回统计。

返回统计结构::
    {"events_processed", "sources_fetched", "sources_matched",
     "deduped", "inserted", "skipped_existing", "failed"}
"""
from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional

from sqlalchemy import select

from app.config import settings
from app.models import Incident, TraceSource
from app.services.trace.matcher import is_acceptable, score_event_source
from app.services.trace.provider import PROVIDERS

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 Web3SecurityDashboard/1.0 trace-pipeline"
_TIMEOUT = 15


def _fetch_defillama_events() -> list[dict]:
    """从 DefiLlama Hacks 公共接口拉取全量事件原始行.

    失败/结构异常由调用方捕获并安全回退为空事件集合, 绝不让网络异常中断管道。
    """
    req = urllib.request.Request(
        settings.DEFILLAMA_HACKS_URL,
        headers={"User-Agent": _UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _external_id_for(row: dict) -> str:
    """与 fetcher 保持一致的 external_id 生成规则: defillama-<id|name>."""
    return str(row.get("defillamaId") or row.get("name") or "").strip()


def _lazy_event(row: dict) -> SimpleNamespace:
    """为未入库的 DefiLlama 事件构造轻量占位对象 (仅作匹配上下文, 无 id)."""
    return SimpleNamespace(
        id=None,
        external_id=_external_id_for(row),
        project_name=str(row.get("name") or ""),
        contract_address="",
        occurred_at=(
            datetime.fromtimestamp(int(row.get("date")), tz=timezone.utc)
            if row.get("date")
            else None
        ),
    )


def run_trace_pipeline(db) -> dict:
    """执行一次可信追溯抓取/匹配/写库, 返回统计字典."""
    stats = {
        "events_processed": 0,
        "sources_fetched": 0,
        "sources_matched": 0,
        "deduped": 0,
        "inserted": 0,
        "skipped_existing": 0,
        "failed": 0,
    }

    # 1. 事件集合: 全量 DefiLlama + 库内 incidents 按 external_id 映射
    by_external_id = {
        inc.external_id: inc for inc in db.scalars(select(Incident)).all()
    }
    rows: list[dict] = []
    try:
        rows = _fetch_defillama_events()
    except Exception as exc:  # noqa: BLE001 - 网络不可用也不打断管道
        logger.warning("[pipeline] DefiLlama 全量抓取失败, 回退到已入库事件: %s", exc)

    events: list = []
    for row in rows:
        ext_id = _external_id_for(row)
        if not ext_id:
            continue
        known = by_external_id.get(f"defillama-{ext_id}")
        events.append(known if known is not None else _lazy_event(row))
    # 若全量源不可用, 至少回退处理已入库事件
    if not events:
        events = list(by_external_id.values())

    stats["events_processed"] = len(events)

    # 2-4. 逐事件收集候选 → 打分 → 过滤 → 去重 → 幂等写库
    for event in events:
        event_id = getattr(event, "id", None)
        if event_id is None:
            # 未入库事件尚无主键可绑来源, 仅计数不算失败
            continue
        try:
            candidates: list[dict] = []
            for provider in PROVIDERS:
                try:
                    candidates.extend(provider.collect_for(event))
                except Exception as exc:  # noqa: BLE001 - 单 provider 失败不影响整条链
                    logger.warning("[pipeline] provider %s 收集来源异常: %s",
                                   provider.name, exc)
            stats["sources_fetched"] += len(candidates)

            scored = []
            for cand in candidates:
                if not isinstance(cand, dict):
                    continue
                cand.setdefault("provider_name", "")
                cand.setdefault("url", "")
                if not cand.get("url"):
                    continue
                cand["reliability_score"] = score_event_source(event, cand)
                if is_acceptable(cand["reliability_score"]):
                    scored.append(cand)
            stats["sources_matched"] += len(scored)

            # 按 (provider_name, url) 去重, 保留最高分
            best: dict[tuple, dict] = {}
            for cand in scored:
                key = (cand.get("provider_name", ""), cand.get("url", ""))
                if key not in best or cand["reliability_score"] > best[key][
                    "reliability_score"
                ]:
                    best[key] = cand
            stats["deduped"] += len(scored) - len(best)

            # 幂等: (event_id, provider_name, url) 已存在则跳过
            existing = {
                (r.provider_name, r.url)
                for r in db.scalars(
                    select(TraceSource).where(TraceSource.event_id == event_id)
                ).all()
            }
            for (pname, url), cand in best.items():
                if (pname, url) in existing:
                    stats["skipped_existing"] += 1
                    continue
                db.add(
                    TraceSource(
                        event_id=event_id,
                        provider_name=pname,
                        provider_type=cand.get("provider_type", ""),
                        category=cand.get("category", ""),
                        title=str(cand.get("title", ""))[:256],
                        url=str(url)[:512],
                        reliability_score=float(cand.get("reliability_score", 0.5)),
                    )
                )
                existing.add((pname, url))
                stats["inserted"] += 1
        except Exception as exc:  # noqa: BLE001 - 单事件异常计入 failed 不中断
            logger.warning("[pipeline] 处理事件 %s 异常: %s", getattr(event, "external_id", "?"), exc)
            db.rollback()
            stats["failed"] += 1

    if stats["inserted"]:
        db.commit()
        logger.info(
            "[pipeline] 本次处理 %s 个事件, 新增 %s 条来源, 跳过 %s 条重复",
            stats["events_processed"], stats["inserted"], stats["skipped_existing"],
        )
    return stats


if __name__ == "__main__":
    """冒烟测试: 不触发真实网络. 用内存 SQLite + mock 注入最小事件与来源,
    验证 import / 模型 / run_trace_pipeline 各分支与幂等 upsert 均不抛异常."""
    import sqlalchemy as sa
    from app.database import Base
    from app.services.trace.provider.base import Provider  # noqa: F401 (类型引用)

    def _smoke() -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        s = sa.orm.sessionmaker(bind=engine, future=True)
        db: Session = s()
        inc = Incident(
            external_id="defillama-smoke1",
            title="Smoke Project attack",
            chain="Ethereum",
            project_name="Smoke",
            contract_address="0x" + "1" * 40,
            severity="高",
            status="已确认",
            risk_class="智能合约技术风险",
        )
        db.add(inc)
        db.commit()

        from unittest import mock

        # 最小事件: 映射到已入库 incident
        fake_rows = [{
            "name": "Smoke",
            "defillamaId": "smoke1",
            "date": 1700000000,
        }]
        # 假 provider: 返回两条(含一重复), 验证去重 + 幂等
        class _FakeProvider:
            name = "ChainExplorer"
            provider_type = "ONCHAIN_EVIDENCE"
            category = "L4"
            reliability_score = 0.7

            def collect_for(self, event):
                url = "https://etherscan.io/address/" + event.contract_address
                news_url = "https://slowmist.com/?s=" + event.project_name
                return [
                    {"provider_name": self.name, "provider_type": self.provider_type,
                     "category": self.category, "title": "a", "url": url,
                     "reliability_score": 0.9},
                    {"provider_name": self.name, "provider_type": self.provider_type,
                     "category": self.category, "title": "a-dup", "url": url,
                     "reliability_score": 0.7},  # 重复 url, 应去重
                    {"provider_name": "Slowmist", "provider_type": "POST_MORTEM",
                     "category": "L2", "title": "b", "url": news_url,
                     "reliability_score": 0.75},
                ]

        import app.services.trace.pipeline as mod

        with mock.patch.object(mod, "_fetch_defillama_events", return_value=fake_rows), \
             mock.patch.object(mod, "PROVIDERS", [_FakeProvider()]):
            stats1 = mod.run_trace_pipeline(db)
            assert stats1["events_processed"] == 1, stats1
            assert stats1["inserted"] == 2, stats1  # etherscan + slowmist, 去重掉重复
            assert stats1["deduped"] >= 1, stats1
            # 第二次运行 → 全部跳过
            stats2 = mod.run_trace_pipeline(db)
            assert stats2["inserted"] == 0 and stats2["skipped_existing"] == 2, stats2
        db.close()
        print("smoke OK: insert=2, skipped_existing=2, deduped>=1, events_processed=1")

    _smoke()
    print("run_trace_pipeline __main__ smoke passed")