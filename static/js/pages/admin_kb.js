/** 管理端知识库：CRUD + 成员勾选授权弹窗。 */

import { apiFetch, showToast } from "../api.js";
import { getUser, navigate } from "../router.js";

const state = {
  kbs: [],
  users: [],
  members: [], // 当前弹窗库的成员
  modalKbId: null,
};

export async function renderAdminKb(container) {
  const user = getUser();
  container.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">管理后台</div>
        <nav>
          <a href="#/admin">看板</a>
          <a href="#/admin/kb" class="active">知识库</a>
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
          <h2>知识库管理</h2>
          <span class="muted">${escapeHtml(user ? user.nickname || user.username : "")}</span>
        </header>
        <div class="content">
          <div class="toolbar">
            <button class="btn btn-primary" id="btn-create" type="button">新建知识库</button>
            <span class="spacer"></span>
          </div>
          <div class="card" id="kb-table">加载中…</div>
        </div>
      </div>
    </div>
    <div id="modal-root"></div>
  `;

  container.querySelector("#btn-logout").addEventListener("click", () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("login");
  });
  container.querySelector("#btn-create").addEventListener("click", () => openKbModal(null));

  await loadAll();
}

async function loadAll() {
  try {
    const [kbs, users] = await Promise.all([
      apiFetch("/api/knowledge-bases"),
      apiFetch("/api/users?page=1&page_size=100"),
    ]);
    state.kbs = kbs.items || [];
    state.users = users.items || [];
    renderTable();
  } catch (e) {
    showToast(e.message, "error");
    const el = document.getElementById("kb-table");
    if (el) el.innerHTML = `<div class="empty">${escapeHtml(e.message)}</div>`;
  }
}

function renderTable() {
  const el = document.getElementById("kb-table");
  if (!el) return;
  if (state.kbs.length === 0) {
    el.innerHTML = `<div class="empty">暂无知识库</div>`;
    return;
  }
  el.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>序号</th><th>名称</th><th>描述</th><th>状态</th><th>创建时间</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        ${state.kbs
          .map(
            (k, i) => `
          <tr>
            <td>${i + 1}</td>
            <td>${escapeHtml(k.name)}</td>
            <td class="muted">${escapeHtml(k.description || "")}</td>
            <td>${k.status === 1 ? '<span class="badge badge-completed">启用</span>' : '<span class="badge badge-failed">停用</span>'}</td>
            <td class="muted">${k.created_at ? new Date(k.created_at).toLocaleString("zh-CN") : ""}</td>
            <td>
              <button class="btn btn-sm" data-act="members" data-id="${k.id}">成员</button>
              <button class="btn btn-sm" data-act="edit" data-id="${k.id}">编辑</button>
              <button class="btn btn-sm btn-danger" data-act="del" data-id="${k.id}">删除</button>
            </td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;

  el.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.id);
      const act = btn.dataset.act;
      if (act === "edit") openKbModal(id);
      else if (act === "members") openMembersModal(id);
      else if (act === "del") deleteKb(id);
    });
  });
}

function openKbModal(id) {
  const kb = id ? state.kbs.find((k) => k.id === id) : null;
  const root = document.getElementById("modal-root");
  root.innerHTML = `
    <div class="modal-backdrop" id="kb-backdrop">
      <div class="modal" role="dialog" aria-modal="true">
        <h3>${kb ? "编辑知识库" : "新建知识库"}</h3>
        <label>名称
          <input id="kb-name" maxlength="128" value="${escapeHtml(kb ? kb.name : "")}" required />
        </label>
        <label>描述
          <textarea id="kb-desc" rows="3" maxlength="2000">${escapeHtml(kb ? kb.description || "" : "")}</textarea>
        </label>
        <div class="modal-actions">
          <button class="btn" id="kb-cancel" type="button">取消</button>
          <button class="btn btn-primary" id="kb-save" type="button">保存</button>
        </div>
      </div>
    </div>`;

  const close = () => {
    root.innerHTML = "";
  };
  root.querySelector("#kb-cancel").addEventListener("click", close);
  root.querySelector("#kb-backdrop").addEventListener("click", (e) => {
    if (e.target.id === "kb-backdrop") close();
  });
  root.querySelector("#kb-save").addEventListener("click", async () => {
    const name = root.querySelector("#kb-name").value.trim();
    const description = root.querySelector("#kb-desc").value.trim();
    if (!name) {
      showToast("请输入名称", "error");
      return;
    }
    try {
      if (kb) {
        await apiFetch(`/api/knowledge-bases/${kb.id}`, {
          method: "PUT",
          body: { name, description },
        });
      } else {
        await apiFetch("/api/knowledge-bases", {
          method: "POST",
          body: { name, description },
        });
      }
      showToast("已保存", "success");
      close();
      await loadAll();
    } catch (e) {
      showToast(e.message, "error");
    }
  });
}

async function deleteKb(id) {
  const kb = state.kbs.find((k) => k.id === id);
  const ok = window.confirm(
    `删除知识库「${kb ? kb.name : id}」？\n\n将级联删除：文档记录与文件、向量库、全部会话与消息、成员关系。此操作不可恢复。`
  );
  if (!ok) return;
  try {
    await apiFetch(`/api/knowledge-bases/${id}`, { method: "DELETE" });
    showToast("已删除", "success");
    await loadAll();
  } catch (e) {
    showToast(e.message, "error");
  }
}

async function openMembersModal(kbId) {
  const kb = state.kbs.find((k) => k.id === kbId);
  const root = document.getElementById("modal-root");
  root.innerHTML = `
    <div class="modal-backdrop" id="mem-backdrop">
      <div class="modal" role="dialog" aria-modal="true">
        <h3>成员授权 · ${escapeHtml(kb ? kb.name : "")}</h3>
        <div id="mem-list" class="muted">加载中…</div>
        <div class="modal-actions">
          <button class="btn" id="mem-close" type="button">关闭</button>
          <button class="btn btn-primary" id="mem-save" type="button">保存授权</button>
        </div>
      </div>
    </div>`;

  const close = () => {
    root.innerHTML = "";
  };
  root.querySelector("#mem-close").addEventListener("click", close);
  root.querySelector("#mem-backdrop").addEventListener("click", (e) => {
    if (e.target.id === "mem-backdrop") close();
  });

  try {
    const data = await apiFetch(`/api/knowledge-bases/${kbId}/members`);
    state.members = data || [];
    renderMemberChecks(root, kbId);
  } catch (e) {
    root.querySelector("#mem-list").innerHTML = escapeHtml(e.message);
    return;
  }

  root.querySelector("#mem-save").addEventListener("click", async () => {
    const checked = new Set(
      [...root.querySelectorAll("input[name=mem]:checked")].map((i) => Number(i.value))
    );
    const current = new Set(state.members.map((m) => m.user_id));
    try {
      for (const uid of checked) {
        if (!current.has(uid)) {
          await apiFetch(`/api/knowledge-bases/${kbId}/members`, {
            method: "POST",
            body: { user_id: uid },
          });
        }
      }
      for (const uid of current) {
        if (!checked.has(uid)) {
          await apiFetch(`/api/knowledge-bases/${kbId}/members/${uid}`, {
            method: "DELETE",
          });
        }
      }
      showToast("成员已更新（user 端列表即时生效）", "success");
      close();
    } catch (e) {
      showToast(e.message, "error");
    }
  });
}

function renderMemberChecks(root, kbId) {
  const memberIds = new Set(state.members.map((m) => m.user_id));
  const list = root.querySelector("#mem-list");
  if (state.users.length === 0) {
    list.innerHTML = `<div class="empty">暂无用户</div>`;
    return;
  }
  list.innerHTML = state.users
    .map(
      (u) => `
    <label class="mem-row" style="display:flex;align-items:center;gap:0.5rem;padding:0.4rem 0;cursor:pointer">
      <input type="checkbox" name="mem" value="${u.id}" ${memberIds.has(u.id) ? "checked" : ""}
             style="width:auto;margin:0" />
      <span>${escapeHtml(u.nickname || u.username)}</span>
      <span class="muted">（${escapeHtml(u.username)}）</span>
      <span class="badge ${u.role === "admin" ? "badge-admin" : "badge-user"}" style="margin-left:auto">${u.role}</span>
    </label>`
    )
    .join("");
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
