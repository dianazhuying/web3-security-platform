/**
 * ICE Intelligence — Background Service Worker (Manifest V3)
 *
 * 职责: 调用后端 check_context 接口, 做轻量缓存, 向 popup 提供渲染数据。
 * 通信: popup.html 通过 chrome.runtime.sendMessage({type:'GET_CONTEXT'}) 获取缓存结果。
 */
"use strict";

// 生产 / 本地调试两个环境的接口地址
const API_BASE = "https://www.iceintel.xyz/api/v1";
const LOCAL_BASE = "http://localhost:8000/api/v1";

// 轻量缓存: 域名/地址 -> 上下文结果 (MVP 仅内存缓存)
const cache = new Map();
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 分钟

/**
 * 检测生产 API 可达性, 不可达时回退本地调试地址 (开发用)。
 */
async function pickBase() {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 2500);
    await fetch(`${API_BASE}/stats`, { method: "HEAD", signal: ctrl.signal });
    clearTimeout(timer);
    return API_BASE;
  } catch {
    return LOCAL_BASE;
  }
}

/**
 * 调用 check_context 接口。
 * @param {string} query 域名 / ENS / 0x 地址 / 协议头 URL
 */
async function checkContext(query) {
  const q = (query || "").trim();
  if (!q) {
    return { matched: false, count: 0, max_severity: null, incidents: [] };
  }

  const cached = cache.get(q);
  if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
    return cached.data;
  }

  const base = await pickBase();
  const url = `${base}/extension/check_context?query=${encodeURIComponent(q)}`;
  const resp = await fetch(url, { method: "GET" });
  if (!resp.ok) {
    throw new Error(`check_context ${resp.status}`);
  }
  const data = await resp.json();
  cache.set(q, { ts: Date.now(), data });
  return data;
}

// popup / content 发来的消息统一路由
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "GET_CONTEXT") {
    checkContext(msg.query)
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: String(err && err.message || err) }));
    return true; // 异步 sendResponse
  }
  if (msg && msg.type === "GET_STATUS") {
    sendResponse({ ok: true, cacheSize: cache.size });
  }
  return false;
});