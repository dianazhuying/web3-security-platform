const API_BASE = 'http://localhost:8000/api/v1/extension';
const CACHE_TTL = 5 * 60 * 1000;

// 【DEBUG_MOCK 开关】：本地测试高危 Banner 渲染与跳转
const DEBUG_MOCK = true;

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'CHECK_CONTEXT') {
    checkContext(request.query)
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
});

async function checkContext(query) {
  if (DEBUG_MOCK) {
    return {
      matched: true,
      incidents: [
        {
          id: 1384,
          severity: "High",
          title: "测试高危威胁 Mock 事件 (Incorrect Share Accounting)",
          project_name: "Etherscan Test Drainer"
        }
      ]
    };
  }

  const cacheKey = `ctx_${query}`;
  const cached = await chrome.storage.local.get(cacheKey);
  if (cached[cacheKey] && (Date.now() - cached[cacheKey].timestamp < CACHE_TTL)) {
    return cached[cacheKey].data;
  }
  
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);
  
  try {
    const res = await fetch(`${API_BASE}/check_context?query=${encodeURIComponent(query)}`, {
      signal: controller.signal
    });
    if (!res.ok) throw new Error('API request failed');
    const data = await res.json();
    await chrome.storage.local.set({ [cacheKey]: { data, timestamp: Date.now() } });
    return data;
  } catch (err) {
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}