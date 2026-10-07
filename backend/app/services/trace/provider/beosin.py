"""Beosin (Beosin Alert) 可信追溯来源适配器.

真实来源
--------
Beosin 通过官网博客 (https://beosin.com/blog) / Beosin Alert 账号发布预警与复盘文章,
并无公开、稳定的机器可读 API; 文章正文 URL 无法自动可靠确认。

降级策略
--------
"宁缺毋假": 仅在能确认真实存在的文章 URL 时才返回; 无法确认即返回 ``[]``。
本适配器尽力尝试站内搜索页抓取 (429/5xx 由基类捕获并降级), 但不对搜索页做
脆弱的 HTML 解析来拼装假链接, 因此默认返回空列表。
"""
from __future__ import annotations

from .base import Provider, http_get, quoted

_SEARCH_TPL = "https://beosin.com/blog/?s={q}"


class BeosinProvider(Provider):
    """Beosin 预警 + 复盘来源 (ALERT / POST_MORTEM, L1/L2)."""

    name = "Beosin"
    provider_type = "ALERT"
    category = "L1"
    reliability_score = 0.65

    def fetch(self, event) -> list[dict]:
        project = (getattr(event, "project_name", "") or "").strip()
        if not project:
            return []
        url = _SEARCH_TPL.format(q=quoted(project))
        http_get(url, timeout=15)
        # 无稳定唯一文章 URL 可确认, 宁缺毋假, 返回空
        return []