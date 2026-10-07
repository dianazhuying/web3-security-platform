"""Provider 抽象基类: 定义统一抓取接口与"安全降级"模板方法.

设计要点
--------
- ``fetch(event)`` 由各适配器实现, 返回候选来源字典列表:
  ``{"provider_name", "provider_type", "category", "title", "url", "reliability_score"}``。
- ``collect_for(event)`` 是模板方法: 包裹 ``fetch`` 的 try/except,
  任何抓取异常均以 ``logger.warning`` 记录并 ``return []``——**安全降级**,
  绝不把异常抛给管道, 保证整条 trace pipeline 可持续运行。
- 各安全团队 (慢雾 / Beosin / PeckShield) 没有稳定公开 API, 真实抓取遵循
  "尽力而为 + 宁缺毋假": 只有在能确认真实存在的文章 URL 时才返回来源,
  否则返回空列表, 绝不通过字符串拼接臆造链接。

工具函数
--------
- ``http_get`` / ``http_get_json``: 基于标准库 ``urllib.request`` 的轻量抓取,
  内置自定义 User-Agent 与超时; 429 / 5xx 会抛出 ``HTTPError`` 以触发上层降级。
"""
from __future__ import annotations

import logging
import urllib.request
from abc import ABC, abstractmethod
from urllib.parse import quote

logger = logging.getLogger(__name__)

# 部分站点会拦截纯脚本 UA; 使用较常规的 UA 以尽量拿到内容
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "Web3SecurityDashboard/1.0 trace-pipeline"
)
DEFAULT_TIMEOUT = 15  # 秒


def http_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """标准库 urllib 抓取网页文本; 429 / 5xx 抛 HTTPError 由调用方降级."""
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_get_json(url: str, timeout: int = DEFAULT_TIMEOUT):
    """抓取并反序列化 JSON 响应."""
    import json

    return json.loads(http_get(url, timeout))


def quoted(value: str) -> str:
    """URL 编码查询词, 供站内搜索 URL 使用."""
    return quote((value or "").strip())


class Provider(ABC):
    """可信追溯来源抓取器基类.

    子类需设置 ``name`` 以及来源元信息默认值, 并实现 ``fetch``:
    - ``name``: provider 展示名
    - ``provider_type``: ALERT / POST_MORTEM / FORENSICS / ONCHAIN_EVIDENCE
    - ``category``: L1 / L2 / L3 / L4 (追溯层级)
    - ``reliability_score``: 未显式打分时使用的默认确信度基线
    """

    name: str = "base"
    provider_type: str = "ALERT"
    category: str = "L1"
    reliability_score: float = 0.65

    @abstractmethod
    def fetch(self, event) -> list[dict]:
        """抓取候选来源; 仅返回确认真实存在的 URL 候选, 否则返回 []."""

    def collect_for(self, event) -> list[dict]:
        """模板方法: 抓取 + 安全降级. 任何异常都不外抛, 仅告警并返回 []."""
        try:
            items = self.fetch(event) or []
        except Exception as exc:  # noqa: BLE001 - 抓取异常必须降级而非打断管道
            logger.warning(
                "[trace:provider] %s 抓取失败, 安全降级为空: %s", self.name, exc
            )
            return []
        # 补全来源元信息默认值 (子类可用 fetch 返回的自定义值覆盖)
        out: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            merged = dict(item)
            merged.setdefault("provider_name", self.name)
            merged.setdefault("provider_type", self.provider_type)
            merged.setdefault("category", self.category)
            merged.setdefault("reliability_score", self.reliability_score)
            merged.setdefault("title", "")
            merged.setdefault("url", "")
            out.append(merged)
        return out