"""慢雾 (SlowMist) 可信追溯来源适配器.

真实来源
--------
慢雾通过官网 (https://www.slowmist.com) 发布情报与研报、通过慢雾区 (Hacked/Slops)
发布复盘专栏。这些内容**没有稳定的公开搜索 API**, 站内搜索页是 HTML 且结构不指定,
从中自动解析出"确认真实存在的文章 URL"并不可靠。

降级策略
--------
遵循 "宁缺毋假": 仅当能确认某 URL 是真实存在的文章时才返回; 无法可靠确认时返回 ``[]``。
本适配器尽力尝试站内搜索页抓取 (429/5xx 由基类捕获并降级), 但对搜索页返回的内容
不做脆弱的 HTML 正则解析以拼装假链接, 因此默认返回空列表。
"""
from __future__ import annotations

from datetime import datetime, timezone

from .base import Provider, http_get, quoted

_SEARCH_TPL = "https://www.slowmist.com/?s={q}"


class SlowmistProvider(Provider):
    """慢雾 Zone 复盘 / 研报来源 (POST_MORTEM, L2)."""

    name = "Slowmist"
    provider_type = "POST_MORTEM"
    category = "L2"
    reliability_score = 0.75

    def fetch(self, event) -> list[dict]:
        project = (getattr(event, "project_name", "") or "").strip()
        if not project:
            return []
        url = _SEARCH_TPL.format(q=quoted(project))
        # 尝试抓取一次, 校验站点可达性; 429/5xx 会抛异常由基类降级为 []
        http_get(url, timeout=15)
        # 搜索页为文章列表且无稳定唯一 URL 可确认, 宁缺毋假, 返回空
        return []