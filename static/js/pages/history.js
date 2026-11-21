/** 对话历史页：分页；admin 可按用户过滤。 */

import { apiFetch, showToast } from "../api.js";
import { getUser, navigate } from "../router.js";

const PAGE_SIZE = 10;

const state = {
  page: 1,
  total: 0,
  items: [],
  users: [],
  userId: "", // "" = 全部（admin）或仅自己（user）
  loading: false,
};

export async function renderHistory(container) {
  const user = getUser();
  const isAdmin = user && user.role === "admin";

  container.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">知识库问答</div>
        <nav>
          <a href="#/chat">对话</a>
          <a href="#/history" class="active">历史</a>
          <a href="#/admin" id="nav-admin" ${isAdmin ? "" : "hidden"}>管理</a>
        </nav>
        <div class="spacer"></div>
        <button class="btn btn-sm" id="btn-logout" type="button">退出登录</button>
      </aside>
      <div class="main">
        <header class="topbar">
          <h2>对话历史</h2>
          <span class="muted">${escapeHtml(user ? user.nickname || user.username : "")}</span>
        </header>
        <div class="content">
          <div class="toolbar">
            ${
              isAdmin
                ? `<label class="muted" style="margin:0;font-weight:400">用户</label>
                   <select id="user-filter" style="width:auto">
                     <option value="">全部用户</option>
                   </select>`
                : `<span class="muted">仅显示自己的对话</span>`
            }
            <span class="spacer"></span>
            <span class="muted" id="total-label"></span>
          </div>
          <div class="card" id="history-list">加载中…</div>
          <div class="toolbar" style="justify-content:center;margin-top:1rem">
            <button class="btn btn-sm" id="prev-page" type="button">上一页</button>
            <span class="muted" id="page-label"></span>
            <button class="btn btn-sm" id="next-page" type="button">下一页</button>
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

  if (isAdmin) {
    const sel = container.querySelector("#user-filter");
    sel.addEventListener("change", () => {
      state.userId = sel.value;
      state.page = 1;
      loadPage();
    });
    try {
      const data = await apiFetch("/api/users?page=1&page_size=100");
      state.users = data.items || [];
      sel.innerHTML =
        `<option value="">全部用户</option>` +
        state.users
          .map(
            (u) =>
              `<option value="${u.id}">${escapeHtml(u.nickname || u.username)}（${escapeHtml(u.username)}）</option>`
          )
          .join("");
    } catch (e) {
      showToast(e.message, "error");
    }
  }

  container.querySelector("#prev-page").addEventListener("click", () => {
    if (state.page > 1) {
      state.page -= 1;
      loadPage();
    }
  });
  container.querySelector("#next-page").addEventListener("click", () => {
    if (state.page * PAGE_SIZE < state.total) {
      state.page += 1;
      loadPage();
    }
  });

  await loadPage();
}

async function loadPage() {
  const list = document.getElementById("history-list");
  const prev = document.getElementById("prev-page");
  const next = document.getElementById("next-page");
  if (!list) return;
  state.loading = true;
  if (prev) prev.disabled = true;
  if (next) next.disabled = true;
  list.innerHTML = `<div class="empty">加载中…</div>`;

  try {
    const params = new URLSearchParams({ page: String(state.page), page_size: String(PAGE_SIZE) });
    if (state.userId) params.set("user_id", state.userId);
    const data = await apiFetch(`/api/chat/history?${params}`);
    state.items = data.items || [];
    state.total = data.total || 0;
    renderList();
  } catch (e) {
    list.innerHTML = `<div class="empty">${escapeHtml(e.message || "加载失败")}</div>`;
    showToast(e.message, "error");
  } finally {
    state.loading = false;
    if (prev) prev.disabled = state.page <= 1;
    if (next) next.disabled = state.page * PAGE_SIZE >= state.total;
  }
}

function renderList() {
  const list = document.getElementById("history-list");
  const totalLabel = document.getElementById("total-label");
  const pageLabel = document.getElementById("page-label");
  if (!list) return;

  const pages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
  if (totalLabel) totalLabel.textContent = `共 ${state.total} 条`;
  if (pageLabel) pageLabel.textContent = `第 ${state.page} / ${pages} 页`;

  if (state.items.length === 0) {
    list.innerHTML = `<div class="empty">暂无历史记录</div>`;
    return;
  }

  list.innerHTML = state.items
    .map((m) => {
      const when = m.created_at ? new Date(m.created_at).toLocaleString("zh-CN") : "";
      const sources = m.sources || [];
      const files = [...new Set(sources.map((s) => s.file_name).filter(Boolean))];
      const fileTags = files
        .map((f) => `<span class="badge badge-user">${escapeHtml(f)}</span>`)
        .join(" ");
      return `
        <article class="history-item">
          <div class="history-meta muted">
            <span>${when}</span>
            <span>·</span>
            <span>#${m.id}</span>
            ${files.length ? `<span style="margin-left:auto">${fileTags}</span>` : ""}
          </div>
          <div class="history-q"><strong>问：</strong>${escapeHtml(m.question)}</div>
          <div class="history-a"><strong>答：</strong>${escapeHtml(truncate(m.answer, 400))}</div>
          ${
            files.length
              ? `<div class="history-files muted" style="font-size:0.8rem;margin-top:0.35rem">引用：${files.map(escapeHtml).join("、")}</div>`
              : `<div class="muted" style="font-size:0.8rem;margin-top:0.35rem">未命中引用</div>`
          }
        </article>`;
    })
    .join("");
}

function truncate(s, n) {
  const str = String(s || "");
  return str.length > n ? `${str.slice(0, n)}…` : str;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
