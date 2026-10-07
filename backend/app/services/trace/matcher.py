"""事件 ↔ 来源匹配与置信度打分 (matcher).

匹配优先级 (从强到弱)
--------------------
1. 交易哈希 TxHash 完全一致          → 1.00
2. 攻击合约地址一致                 → 0.90
3. 项目名精确匹配 + 时间窗吻合      → 0.85
4. 项目别名/归一化完全匹配          → 0.70
5. 仅关键词弱相关 (需人工复核)      → 0.50

打分说明
--------
``score_event_source(event, candidate)`` 返回 0.5–1.0:
- 候选含 ``match_hint`` 时按其显式计分;
- 否则按 ``provider_type`` 给定基线: ONCHAIN_EVIDENCE=0.9 / FORENSICS=0.85 /
  POST_MORTEM=0.75 / ALERT=0.65;
- 候选自带的 ``reliability_score`` 作为**上界修正**(最终得分不超过该值).

阈值
----
``THRESHOLD = 0.5``; 低于阈值的事件来源不绑定到 trace_sources。
"""
from __future__ import annotations

import re

#: 接受阈值: 低于此值的候选不写入 trace_sources
THRESHOLD = 0.5

#: provider_type 基线得分
PROVIDER_BASELINE = {
    "ONCHAIN_EVIDENCE": 0.9,
    "FORENSICS": 0.85,
    "POST_MORTEM": 0.75,
    "ALERT": 0.65,
}

# 常见项目名后缀, 归一化时去除, 便于别名匹配
_SUFFIXES = (
    "protocol",
    "finance",
    "fi",
    "defi",
    "swap",
    "dex",
    "labs",
    "foundation",
    "dao",
    "network",
    "bridge",
)


def normalize_name(name: str) -> str:
    """项目名归一化: 小写 + 去标点/空格 + 去常见后缀 (做别名/模糊匹配用)."""
    if not name:
        return ""
    s = str(name).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    for suffix in _SUFFIXES:
        if s.endswith(suffix) and len(s) > len(suffix):
            s = s[: -len(suffix)]
    return s


def is_acceptable(score: float) -> bool:
    """得分是否达到绑定阈值."""
    return float(score) >= THRESHOLD


def score_event_source(event, candidate: dict) -> float:
    """对单个候选打分, 返回 0.5–1.0 的置信度."""
    match_hint = candidate.get("match_hint")
    if match_hint:
        hint = str(match_hint).strip().lower()
        if hint in ("txhash", "tx_hash", "tx-hash"):
            score = 1.0
        elif hint in ("contract", "address", "contract_address"):
            score = 0.9
        elif hint in ("exact", "exact_match", "project"):
            score = 0.85
        elif hint in ("alias", "normalized"):
            score = 0.7
        else:
            score = 0.5
    else:
        # 按来源类型基线; 未知名类型视为弱相关
        ptype = str(candidate.get("provider_type", "")).upper()
        score = PROVIDER_BASELINE.get(ptype, 0.5)

    score = min(max(score, 0.5), 1.0)
    # 候选自带 reliability_score 作为上界修正
    own = candidate.get("reliability_score")
    if isinstance(own, (int, float)) and own < score:
        score = float(own)
        score = min(max(score, 0.5), 1.0)
    return score