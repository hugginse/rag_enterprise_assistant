/** 管理看板：4 统计卡片 + 手写 SVG 七日问答趋势柱状图（无图表库）。 */

import { apiFetch, showToast } from "../api.js";
import { getUser, navigate } from "../router.js";

export async function renderAdmin(container) {
  const user = getUser();
  container.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">管理后台</div>
        <nav>
          <a href="#/admin" class="active">看板</a>
          <a href="#/admin/kb">知识库</a>
          <a href="#/admin/docs">文档</a>
          <a href="#/admin/users">用户</a>
          <a href="#/chat">对话</a>
          <a href="#/history">历史</a>
        </nav>
        <div class="spacer"></div>
        <button class="btn btn-sm" id="btn-logout" type="button">退出登录</button>
      </aside>
      <div class="main">
        <header class="topbar">
          <h2>管理看板</h2>
          <span class="muted">${escapeHtml(user ? user.nickname || user.username : "")}</span>
        </header>
        <div class="content">
          <div class="stat-grid" id="stat-grid">
            ${["用户数", "知识库", "文档", "问答消息"]
              .map(
                (label) => `
              <div class="card stat-card">
                <h3>${label}</h3>
                <div class="value" data-key="${label}">…</div>
              </div>`
              )
              .join("")}
          </div>
          <div class="card chart-wrap" style="margin-top:1.25rem">
            <h3 style="margin-top:0">近 7 天问答趋势</h3>
            <div id="chart-root"><div class="muted">加载中…</div></div>
          </div>
        </div>
      </div>
    </div>
  `;

  container.querySelector("#btn-logout").addEventListener("click", () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("login");
  });

  try {
    const data = await apiFetch("/api/stats/dashboard");
    fillStats(data);
    renderChart(data.trend || []);
  } catch (e) {
    showToast(e.message || "加载看板失败", "error");
    const grid = document.getElementById("stat-grid");
    if (grid) grid.innerHTML = `<div class="empty">${escapeHtml(e.message || "加载失败")}</div>`;
  }
}

function fillStats(data) {
  const grid = document.getElementById("stat-grid");
  if (!grid) return;
  const map = {
    用户数: data.users,
    知识库: data.kbs,
    文档: data.documents,
    问答消息: data.messages,
  };
  grid.querySelectorAll(".value").forEach((el) => {
    const key = el.getAttribute("data-key");
    el.textContent = String(map[key] ?? "—");
  });
}

/** 手写 SVG 柱状图：含坐标轴、网格、柱、悬停 title */
function renderChart(trend) {
  const root = document.getElementById("chart-root");
  if (!root) return;
  if (!trend.length) {
    root.innerHTML = `<div class="muted">暂无趋势数据</div>`;
    return;
  }

  const W = 720;
  const H = 260;
  const pad = { top: 16, right: 16, bottom: 40, left: 44 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;
  const maxVal = Math.max(1, ...trend.map((t) => t.count));
  // 取整刻度
  const yMax = niceMax(maxVal);
  const barGap = 16;
  const barW = (innerW - barGap * (trend.length - 1)) / trend.length;

  const yTicks = 4;
  let gridLines = "";
  let yLabels = "";
  for (let i = 0; i <= yTicks; i++) {
    const v = Math.round((yMax / yTicks) * i);
    const y = pad.top + innerH - (v / yMax) * innerH;
    gridLines += `<line x1="${pad.left}" y1="${y}" x2="${W - pad.right}" y2="${y}"
      stroke="#e2e8f0" stroke-width="1" ${i === 0 ? "" : 'stroke-dasharray="4 4"'} />`;
    yLabels += `<text x="${pad.left - 8}" y="${y + 4}" text-anchor="end"
      font-size="11" fill="#64748b">${v}</text>`;
  }

  let bars = "";
  let xLabels = "";
  trend.forEach((t, i) => {
    const x = pad.left + i * (barW + barGap);
    const h = yMax > 0 ? (t.count / yMax) * innerH : 0;
    const y = pad.top + innerH - h;
    const label = t.date.slice(5); // MM-DD
    bars += `
      <rect x="${x}" y="${y}" width="${barW}" height="${Math.max(h, t.count > 0 ? 2 : 0)}"
            rx="4" fill="#2563eb" opacity="0.9">
        <title>${t.date}：${t.count} 条问答</title>
      </rect>`;
    if (t.count > 0) {
      bars += `<text x="${x + barW / 2}" y="${y - 5}" text-anchor="middle"
        font-size="11" font-weight="600" fill="#1d4ed8">${t.count}</text>`;
    }
    xLabels += `<text x="${x + barW / 2}" y="${H - 14}" text-anchor="middle"
      font-size="11" fill="#64748b">${label}</text>`;
  });

  root.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="近7天问答趋势柱状图"
         xmlns="http://www.w3.org/2000/svg">
      ${gridLines}
      <!-- Y 轴 -->
      <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${pad.top + innerH}"
            stroke="#94a3b8" stroke-width="1.5" />
      <!-- X 轴 -->
      <line x1="${pad.left}" y1="${pad.top + innerH}" x2="${W - pad.right}"
            y2="${pad.top + innerH}" stroke="#94a3b8" stroke-width="1.5" />
      ${yLabels}
      ${xLabels}
      ${bars}
      <text x="12" y="${pad.top + innerH / 2}" font-size="11" fill="#64748b"
            transform="rotate(-90 12 ${pad.top + innerH / 2})" text-anchor="middle">条数</text>
    </svg>`;
}

function niceMax(v) {
  if (v <= 5) return 5;
  const pow = 10 ** Math.floor(Math.log10(v));
  const n = v / pow;
  const nice = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return nice * pow;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
