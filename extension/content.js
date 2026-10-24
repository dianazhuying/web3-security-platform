/**
 * ICE Sentinel — Content Script
 *
 * 注入白名单站点 (Etherscan / Solscan), 提取当前页面上下文并上报 background。
 * TODO: 后续扩展 DeFi 域名白名单 (避免在 manifest 使用 <all_urls> 导致商店审核风险)。
 */
"use strict";

/**
 * 从 Etherscan JSON-RPC / Solscan URL 中提取 0x 合约/交易地址。
 */
function pickAddressFromUrl(url) {
  if (!url) return "";
  // 尝试从路径中提取 0x 开头的地址片段
  const m = url.match(/0x[a-fA-F0-9]{6,}/);
  return m ? m[0] : "";
}

// 页面加载完成后, 将当前上下文发送给 background 预热缓存
(function init() {
  const url = location.href || "";
  const query = url.startsWith("http") ? url : pickAddressFromUrl(url);
  if (!query) return;
  try {
    chrome.runtime.sendMessage({ type: "GET_CONTEXT", query }, () => {
      // 结果仅用于缓存预热, popup 打开时会再次按需拉取
    });
  } catch {
    /* background 未就绪时静默忽略 */
  }
})();