(function () {
  let lastUrl = location.href;
  let currentAddress = null;
  let dismissedAddresses = new Set();
  let queryCache = new Map();

  const SEVERITY_RANK = {
    'Low': 1,
    'Medium': 2,
    'High': 3,
    'Critical': 4
  };

  function extractAddress(url) {
    const match = url.match(/\/address\/(0x[a-fA-F0-9]{40})/);
    return match ? match[1].toLowerCase() : null;
  }

  function removeBanner() {
    const existing = document.getElementById('ice-sentinel-banner');
    if (existing) existing.remove();
  }

  function renderBanner(incident, address) {
    removeBanner();
    if (dismissedAddresses.has(address)) return;

    const banner = document.createElement('div');
    banner.id = 'ice-sentinel-banner';
    const severityClass = `severity-${(incident.severity || 'high').toLowerCase()}`;
    banner.classList.add(severityClass);

    const contentDiv = document.createElement('div');
    contentDiv.className = 'banner-content';

    const iconSpan = document.createElement('span');
    iconSpan.className = 'banner-icon';
    iconSpan.textContent = '⚠️';

    const titleSpan = document.createElement('span');
    titleSpan.className = 'banner-title';
    titleSpan.textContent = `[ICE Sentinel] 检测到高风险威胁 (${incident.severity || 'High'}):`;

    const descSpan = document.createElement('span');
    descSpan.className = 'banner-desc';
    descSpan.textContent = incident.title || incident.project_name || '当前合约/地址关联已知安全事件';

    contentDiv.appendChild(iconSpan);
    contentDiv.appendChild(titleSpan);
    contentDiv.appendChild(descSpan);

    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'banner-actions';

    if (incident.id) {
      const detailBtn = document.createElement('a');
      detailBtn.className = 'banner-btn';
      detailBtn.textContent = '查看详情';
      detailBtn.href = `https://www.iceintel.xyz/?id=${incident.id}`;
      detailBtn.target = '_blank';
      actionsDiv.appendChild(detailBtn);
    }

    const closeBtn = document.createElement('button');
    closeBtn.className = 'banner-close';
    closeBtn.textContent = '×';
    closeBtn.title = '关闭提示';
    closeBtn.onclick = () => {
      dismissedAddresses.add(address);
      removeBanner();
    };
    actionsDiv.appendChild(closeBtn);

    banner.appendChild(contentDiv);
    banner.appendChild(actionsDiv);

    document.body.prepend(banner);
  }

  async function checkAndInject() {
    const address = extractAddress(location.href);
    if (!address) {
      currentAddress = null;
      removeBanner();
      return;
    }

    if (address !== currentAddress) {
      currentAddress = address;
    }

    if (dismissedAddresses.has(address)) {
      removeBanner();
      return;
    }

    const now = Date.now();
    if (queryCache.has(address) && (now - queryCache.get(address) < 5 * 60 * 1000)) {
      return;
    }
    queryCache.set(address, now);

    try {
      chrome.runtime.sendMessage(
        { type: 'CHECK_CONTEXT', query: address },
        (response) => {
          if (chrome.runtime.lastError) {
            return;
          }
          if (!response || !response.success || !response.data || !response.data.matched) {
            removeBanner();
            return;
          }

          const incidents = response.data.incidents || [];
          if (incidents.length === 0) {
            removeBanner();
            return;
          }

          let highestIncident = incidents[0];
          let maxRank = SEVERITY_RANK[highestIncident.severity] || 0;

          for (let i = 1; i < incidents.length; i++) {
            const rank = SEVERITY_RANK[incidents[i].severity] || 0;
            if (rank > maxRank) {
              maxRank = rank;
              highestIncident = incidents[i];
            }
          }

          if (maxRank >= SEVERITY_RANK['High']) {
            renderBanner(highestIncident, address);
          } else {
            removeBanner();
          }
        }
      );
    } catch (e) {}
  }

  setInterval(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      checkAndInject();
    }
  }, 500);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkAndInject);
  } else {
    checkAndInject();
  }
})();