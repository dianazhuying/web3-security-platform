/**
 * ICE Intelligence — Popup 渲染逻辑
 *
 * 从 background 获取 check_context 结果, 按 max_severity 分级着色,
 * 提供跳转至 iceintel.xyz 对应详情的链接; matched=false 时展示干净空态。
 */
"use strict";

const DETAIL_BASE = "https://www.iceintel.xyz";
const $ = (id) => document.getElementById(id);

/**
 * 获取当前活动标签 URL, 提取待检测上下文。
 * 优先用完整 URL (含 https:// 域名); 若为白名单站点则回退到地址片段。
 */
async function resolveQuery() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = (tab && tab.url) || "";
    if (url.startsWith("http")) return url;
    const addr = url.match(/0x[a-fA-F0-9]{6,}/);
    return addr ? addr[0] : url;
  } catch {
    return "";
  }
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function renderIncident(inc) {
  const sev = inc.severity || "err";
  const sig = inc.sig ? `<span class="code">${escapeHtml(inc.sig)}</span>` : "";
  const root = inc.root_cause
    ? `<div class="kv"><span class="lbl">根因</span>${escapeHtml(inc.root_cause)}</div>` : "";
  return `
    <div class="item">
      <div class="row-top">
        <span class="sev ${sev}">${sev}</span>
        <span class="incident-title" title="${escapeHtml(inc.title)}">${escapeHtml(inc.title)}</span>
      </div>
      <div class="meta">
        ${root}
        ${sig ? `<div class="kv"><span class="lbl">特征</span>${sig}</div>` : ""}
      </div>
      <div class="goto">
        <a href="${DETAIL_BASE}/?id=${inc.id}" target="_blank" rel="noopener noreferrer">查看详情 ↗</a>
      </div>
    </div>`;
}

function showEmpty() {
  $("loading").style.display = "none";
  $("error").style.display = "none";
  $("empty").style.display = "block";
  $("list").innerHTML = "";
  $("matchTag").style.display = "none";
}

function render(data) {
  $("loading").style.display = "none";
  $("error").style.display = "none";
  if (!data || data.matched !== true || !Array.isArray(data.incidents) || data.incidents.length === 0) {
    showEmpty();
    return;
  }
  $("empty").style.display = "none";
  $("list").innerHTML = data.incidents.map(renderIncident).join("");

  const sev = data.max_severity || "err";
  const tag = $("matchTag");
  tag.style.display = "inline-block";
  tag.className = "match-tag " + (["Critical", "High"].includes(sev) ? "danger" : "safe");
  tag.textContent = `${sev} · ${data.count} 起事件`;
}

async function init() {
  const query = await resolveQuery();
  try {
    const resp = await chrome.runtime.sendMessage({ type: "GET_CONTEXT", query });
    if (resp && resp.ok) {
      render(resp.data);
    } else {
      $("loading").style.display = "none";
      $("error").style.display = "block";
      $("error").textContent = "检测失败: " + ((resp && resp.error) || "未知错误");
    }
  } catch (e) {
    $("loading").style.display = "none";
    $("error").style.display = "block";
    $("error").textContent = "无法连接后台服务, 请刷新后重试";
  }
}

document.addEventListener("DOMContentLoaded", init);