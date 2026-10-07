"""可信追溯抓取适配器: 统一导出 PROVIDERS 列表供 pipeline 编排."""
from __future__ import annotations

from .base import Provider, http_get, http_get_json
from .beosin import BeosinProvider
from .chain import ChainProvider
from .peckshield import PeckShieldProvider
from .slowmist import SlowmistProvider

#: pipeline 遍历抓取的所有 provider 适配器 (顺序即优先级/展示顺序)
PROVIDERS: list[Provider] = [
    SlowmistProvider(),
    BeosinProvider(),
    PeckShieldProvider(),
    ChainProvider(),
]

__all__ = [
    "Provider",
    "PROVIDERS",
    "SlowmistProvider",
    "BeosinProvider",
    "PeckShieldProvider",
    "ChainProvider",
    "http_get",
    "http_get_json",
]