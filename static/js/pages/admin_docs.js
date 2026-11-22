/** 管理端文档：上传、分页列表、2s 轮询、勾选批量删除、failed 重传。 */

import { apiFetch, showToast } from "../api.js";
import { getUser, navigate } from "../router.js";

const POLL_MS = 2000;
const PAGE_SIZES = [10, 20, 50];

const state = {
  kbs: [],
  kbId: null,
  docs: [],
  timer: 0,
  page: 1,
  pageSize: 10,
  selected: new Set(), // 勾选的 doc id
};

export async function renderAdminDocs(container) {
  const user = getUser();
  container.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">管理后台</div>
        <nav>
          <a href="#/admin">看板</a>
          <a href="#/admin/kb">知识库</a>
          <a href="#/admin/docs" class="active">文档</a>
          <a href="#/admin/users">用户</a>
          <a href="#/chat">对话</a>
          <a href="#/history">历史</a>
        </nav>
        <div class="spacer"></div>
        <button class="btn btn-sm" id="btn-logout" type="button">退出登录</button>
      </aside>
      <div class="main">
        <header class="topbar">
          <h2>文档管理</h2>
          <span class="muted">${escapeHtml(user ? user.nickname || user.username : "")}</span>
        </header>
        <div class="content">
          <div class="toolbar docs-toolbar">
            <div class="docs-toolbar-row">
              <label class="field-label">知识库</label>
              <select id="kb-select"></select>
              <button class="btn btn-primary" id="btn-upload" type="button">上传文档</button>
              <input type="file" id="file-input" accept=".txt,.md,.pdf,.docx" multiple hidden />
              <span class="muted upload-hint">支持 txt/md/pdf/docx，单个 ≤50MB</span>
            </div>
            <div class="docs-toolbar-row" id="batch-row" hidden>
              <button class="btn btn-sm btn-danger" id="btn-batch-del" type="button">
                删除选中（<span id="sel-count">0</span>）
              </button>
              <span class="muted">勾选后可一键删除</span>
            </div>
          </div>
          <div class="card" id="doc-table">加载中…</div>
          <div class="toolbar docs-pager" id="doc-pager" hidden>
            <label class="field-label">每页</label>
            <select id="page-size">
              ${PAGE_SIZES.map(
                (n) => `<option value="${n}" ${n === state.pageSize ? "selected" : ""}>${n}</option>`
              ).join("")}
            </select>
            <span class="spacer"></span>
            <button class="btn btn-sm" id="prev-page" type="button">上一页</button>
            <span class="muted" id="page-label"></span>
            <button class="btn btn-sm" id="next-page" type="button">下一页</button>
          </div>
        </div>
      </div>
    </div>
  `;

  container.querySelector("#btn-logout").addEventListener("click", () => {
    stopPoll();
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("login");
  });

  const kbSelect = container.querySelector("#kb-select");
  const fileInput = container.querySelector("#file-input");

  container.querySelector("#btn-upload").addEventListener("click", () => fileInput.click());
  container.querySelector("#prev-page").addEventListener("click", () => {
    if (state.page > 1) {
      state.page -= 1;
      renderTable();
    }
  });
  container.querySelector("#next-page").addEventListener("click", () => {
    if (state.page * state.pageSize < state.docs.length) {
      state.page += 1;
      renderTable();
    }
  });
  container.querySelector("#page-size").addEventListener("change", (e) => {
    state.pageSize = Number(e.target.value);
    state.page = 1;
    renderTable();
  });
  container.querySelector("#btn-batch-del").addEventListener("click", batchDelete);

  try {
    const data = await apiFetch("/api/knowledge-bases");
    state.kbs = data.items || [];
    if (state.kbs.length === 0) {
      kbSelect.innerHTML = `<option value="">（无知识库）</option>`;
      document.getElementById("doc-table").innerHTML = `<div class="empty">请先创建知识库</div>`;
      return;
    }
    kbSelect.innerHTML = state.kbs
      .map((k) => `<option value="${k.id}">${escapeHtml(k.name)}</option>`)
      .join("");
    state.kbId = state.kbs[0].id;
  } catch (e) {
    showToast(e.message, "error");
    return;
  }

  kbSelect.addEventListener("change", () => {
    state.kbId = Number(kbSelect.value);
    state.page = 1;
    state.selected.clear();
    refresh();
  });

  fileInput.addEventListener("change", async () => {
    const files = [...fileInput.files];
    fileInput.value = "";
    if (!files.length || !state.kbId) return;
    const hint = document.querySelector(".upload-hint");
    hint.textContent = "上传中…";
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append("kb_id", String(state.kbId));
        fd.append("file", file);
        await apiFetch("/api/documents", { method: "POST", body: fd, toast: true });
      }
      showToast(`已提交 ${files.length} 个文件，后台向量化中`, "success");
      await refresh();
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      hint.textContent = "支持 txt/md/pdf/docx，单个 ≤50MB";
    }
  });

  await refresh();
}

async function refresh() {
  if (!state.kbId) return;
  try {
    const data = await apiFetch(`/api/documents?kb_id=${state.kbId}`);
    state.docs = data.items || [];
    // 清掉已不存在的勾选
    const ids = new Set(state.docs.map((d) => d.id));
    for (const id of [...state.selected]) {
      if (!ids.has(id)) state.selected.delete(id);
    }
    const maxPage = Math.max(1, Math.ceil(state.docs.length / state.pageSize));
    if (state.page > maxPage) state.page = maxPage;
    renderTable();
    if (state.docs.some((d) => d.status === "pending" || d.status === "processing")) {
      startPoll();
    } else {
      stopPoll();
    }
  } catch (e) {
    showToast(e.message, "error");
  }
}

function startPoll() {
  if (state.timer) return;
  state.timer = window.setInterval(() => {
    refresh();
  }, POLL_MS);
}

function stopPoll() {
  if (state.timer) {
    window.clearInterval(state.timer);
    state.timer = 0;
  }
}

function pageDocs() {
  const start = (state.page - 1) * state.pageSize;
  return state.docs.slice(start, start + state.pageSize);
}

function renderTable() {
  const el = document.getElementById("doc-table");
  const pager = document.getElementById("doc-pager");
  const batchRow = document.getElementById("batch-row");
  if (!el) return;

  if (state.docs.length === 0) {
    el.innerHTML = `<div class="empty">暂无文档</div>`;
    if (pager) pager.hidden = true;
    if (batchRow) batchRow.hidden = true;
    updateSelCount();
    return;
  }

  if (pager) pager.hidden = false;
  if (batchRow) batchRow.hidden = false;

  const total = state.docs.length;
  const pages = Math.max(1, Math.ceil(total / state.pageSize));
  const pageLabel = document.getElementById("page-label");
  if (pageLabel) pageLabel.textContent = `第 ${state.page} / ${pages} 页 · 共 ${total} 份`;
  const prev = document.getElementById("prev-page");
  const next = document.getElementById("next-page");
  if (prev) prev.disabled = state.page <= 1;
  if (next) next.disabled = state.page * state.pageSize >= total;

  const rows = pageDocs();
  const offset = (state.page - 1) * state.pageSize;
  const allChecked = rows.length > 0 && rows.every((d) => state.selected.has(d.id));

  el.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th style="width:36px">
            <input type="checkbox" id="check-all" ${allChecked ? "checked" : ""}
                   title="全选本页" style="width:auto;margin:0" />
          </th>
          <th>序号</th><th>文件名</th><th>类型</th><th>大小</th><th>状态</th>
          <th>分块</th><th>错误</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        ${rows
          .map((d, i) => {
            const badge =
              d.status === "completed"
                ? "badge-completed"
                : d.status === "failed"
                  ? "badge-failed"
                  : d.status === "processing"
                    ? "badge-processing"
                    : "badge-pending";
            const statusText =
              d.status === "processing" ? "处理中" : d.status === "pending" ? "排队中" : d.status;
            return `
            <tr>
              <td>
                <input type="checkbox" class="row-check" data-id="${d.id}"
                       ${state.selected.has(d.id) ? "checked" : ""}
                       style="width:auto;margin:0" />
              </td>
              <td>${offset + i + 1}</td>
              <td>${escapeHtml(d.filename)}</td>
              <td>${escapeHtml(d.file_type)}</td>
              <td class="muted">${formatSize(d.file_size)}</td>
              <td><span class="badge ${badge}">${statusText}</span></td>
              <td>${d.chunk_count || "—"}</td>
              <td class="muted err-cell" title="${escapeHtml(d.error_msg || "")}">${escapeHtml(d.error_msg || "")}</td>
              <td class="ops-cell">
                ${
                  d.status === "failed"
                    ? `<button class="btn btn-sm" data-act="retry" data-id="${d.id}">重传</button>`
                    : ""
                }
                <button class="btn btn-sm btn-danger" data-act="del" data-id="${d.id}">删除</button>
              </td>
            </tr>`;
          })
          .join("")}
      </tbody>
    </table>`;

  const checkAll = el.querySelector("#check-all");
  if (checkAll) {
    checkAll.addEventListener("change", () => {
      rows.forEach((d) => {
        if (checkAll.checked) state.selected.add(d.id);
        else state.selected.delete(d.id);
      });
      renderTable();
    });
  }
  el.querySelectorAll(".row-check").forEach((cb) => {
    cb.addEventListener("change", () => {
      const id = Number(cb.dataset.id);
      if (cb.checked) state.selected.add(id);
      else state.selected.delete(id);
      updateSelCount();
      // 同步全选框
      const all = el.querySelector("#check-all");
      if (all) {
        all.checked = rows.every((d) => state.selected.has(d.id));
      }
    });
  });

  el.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.id);
      if (btn.dataset.act === "del") {
        if (!window.confirm("删除该文档及其向量分块？")) return;
        try {
          await apiFetch(`/api/documents/${id}`, { method: "DELETE" });
          state.selected.delete(id);
          showToast("已删除", "success");
          await refresh();
        } catch (e) {
          showToast(e.message, "error");
        }
      } else if (btn.dataset.act === "retry") {
        showToast("请选择原文件重新上传", "info");
        document.getElementById("file-input").click();
      }
    });
  });

  updateSelCount();
}

function updateSelCount() {
  const el = document.getElementById("sel-count");
  if (el) el.textContent = String(state.selected.size);
  const btn = document.getElementById("btn-batch-del");
  if (btn) btn.disabled = state.selected.size === 0;
}

async function batchDelete() {
  const n = state.selected.size;
  if (!n) return;
  const ok = window.confirm(
    `确认删除选中的 ${n} 份文档？\n\n将同时删除物理文件与向量分块，不可恢复。`
  );
  if (!ok) return;
  const btn = document.getElementById("btn-batch-del");
  if (btn) btn.disabled = true;
  let done = 0;
  let failed = 0;
  for (const id of [...state.selected]) {
    try {
      await apiFetch(`/api/documents/${id}`, { method: "DELETE", toast: false });
      done += 1;
      state.selected.delete(id);
    } catch {
      failed += 1;
    }
  }
  showToast(
    failed ? `删除完成 ${done} 份，失败 ${failed} 份` : `已删除 ${done} 份文档`,
    failed ? "error" : "success"
  );
  await refresh();
}

function formatSize(n) {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
