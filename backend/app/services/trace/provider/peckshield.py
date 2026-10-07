"""PeckShield (PeckShield Alert) 可信追溯来源适配器.

真实来源
--------
PeckShield 通过 X (Twitter) @PeckShieldAlert 等账户首发预警与复盘。X 无公开且稳定的
机器可读 API, 其网页/推文无法被可靠自动解析为可回访的文章 URL。

降级策略
--------
"宁缺毋假": 仅在能确认真实存在的文章/推文 URL 时才返回; 无法确认即返回 ``[]``。
本适配器尽力尝试其公开入口抓取 (429/5xx 由基类捕获并降级), 但不臆造 X 状态链接,
因此默认返回空列表。
"""
from __future__ import annotations

from .base import Provider, http_get

# 项目公开站点 (含近期安全事件汇总) 作为尽力可达性探测目标
_SITE = "https://peckshield.com/en/news"


class PeckShieldProvider(Provider):
    """PeckShield 预警来源 (ALERT, L1)."""

    name = "PeckShield"
    provider_type = "ALERT"
    category = "L1"
    reliability_score = 0.65

    def fetch(self, event) -> list[dict]:
        project = (getattr(event, "project_name", "") or "").strip()
        if not project:
            return []
        # 尽力可达性探测; 无法映射到确认的具体来源 URL
        http_get(_SITE, timeout=15)
        # 无法确认唯一文章 URL, 宁缺毋假, 返回空
        return []