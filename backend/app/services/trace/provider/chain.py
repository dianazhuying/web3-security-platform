"""区块浏览器 TxHash / 合约地址可信追溯适配器.

来源
----
基于事件 ``contract_address`` 按链名/地址前缀映射到各链官方浏览器 (Ethereum/Etherscan、
Solana/Solscan 等), 作为链上凭证 (ONCHAIN_EVIDENCE, L4)。

守卫与降级
----------
- 只对**确认为真实地址格式**的输入生成浏览器链接;
- 对 DefiLlama 抓取来源的假占位 ``DefiLlama#<id>`` 直接跳过 (`宁缺毋假`), 不据此拼接链接;
- ``reliability_score`` 交由 matcher 结合候选偏置修正, 默认给 0.7;
- 无法识别的地址返回空列表, 不臆造 URL。
"""
from __future__ import annotations

import re

from .base import Provider

# 判定规则的顺序: 地址前缀 → (链, 浏览器 URL 模板)
_EXPLORERS = [
    # EVM 系: 标准 0x 40 位十六进制 → Etherscan
    ("0x", "https://etherscan.io/address/{addr}"),
    # 其它常见 EVM 链 0x 地址也可通用 Etherscan 链接留空; 此处只保证主链确定性
]

_HEX40 = re.compile(r"^0x[0-9a-fA-F]{40}$")
# Solana 主网上账户地址为 base58, 常见以 1/2/3/4/5... 开头, 长度 32-44
_BASE58_OK = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


class ChainProvider(Provider):
    """区块浏览器 TxHash / 合约地址来源 (ONCHAIN_EVIDENCE, L4)."""

    name = "ChainExplorer"
    provider_type = "ONCHAIN_EVIDENCE"
    category = "L4"
    reliability_score = 0.7

    def fetch(self, event) -> list[dict]:
        addr = (getattr(event, "contract_address", "") or "").strip()
        if not addr:
            return []
        # 跳过 DefiLlama 抓取来源的占位地址 (DefiLlama#<id>), 不据此臆造链接
        if addr.startswith("DefiLlama#"):
            return []
        explorer_url = self._explorer_url(addr)
        if not explorer_url:
            return []
        title = f"链上凭证 · 合约地址查看 ({addr})"
        return [
            {
                "title": title,
                "url": explorer_url,
            }
        ]

    @staticmethod
    def _explorer_url(addr: str) -> str:
        """按地址格式返回可确认真实的浏览器 URL; 无法确认返回 None."""
        addr = addr.strip()
        if _HEX40.match(addr):
            return _EXPLORERS[0][1].format(addr=addr)
        if _BASE58_OK.match(addr) and addr[0] in "12345":
            # Solana 地址 (base58, 常见开头 1-5) → Solscan
            return "https://solscan.io/account/{addr}".format(addr=addr)
        return None