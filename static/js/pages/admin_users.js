/** 管理端用户：分页列表、创建、改角色/昵称、重置密码、禁用。 */

import { apiFetch, showToast } from "../api.js";
import { getUser, navigate } from "../router.js";

const state = {
  page: 1,
  pageSize: 20,
  total: 0,
  items: [],
};

export async function renderAdminUsers(container) {
  const me = getUser();
  container.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">管理后台</div>
        <nav>
          <a href="#/admin">看板</a>
          <a href="#/admin/kb">知识库</a>
          <a href="#/admin/docs">文档</a>
          <a href="#/admin/users" class="active">用户</a>
          <a href="#/chat">对话</a>
          <a href="#/history">历史</a>
        </nav>
        <div class="spacer"></div>
        <button class="btn btn-sm" id="btn-logout" type="button">退出登录</button>
      </aside>
      <div class="main">
        <header class="topbar">
          <h2>用户管理</h2>
          <span class="muted">${escapeHtml(me ? me.nickname || me.username : "")}</span>
        </header>
        <div class="content">
          <div class="toolbar">
            <button class="btn btn-primary" id="btn-create" type="button">新建用户</button>
            <span class="spacer"></span>
            <span class="muted" id="total-label"></span>
          </div>
          <div class="card" id="user-table">加载中…</div>
          <div class="toolbar" style="justify-content:center;margin-top:1rem">
            <button class="btn btn-sm" id="prev-page" type="button">上一页</button>
            <span class="muted" id="page-label"></span>
            <button class="btn btn-sm" id="next-page" type="button">下一页</button>
          </div>
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
  container.querySelector("#btn-create").addEventListener("click", () => openUserModal(null));
  container.querySelector("#prev-page").addEventListener("click", () => {
    if (state.page > 1) {
      state.page -= 1;
      loadPage();
    }
  });
  container.querySelector("#next-page").addEventListener("click", () => {
    if (state.page * state.pageSize < state.total) {
      state.page += 1;
      loadPage();
    }
  });

  await loadPage();
}

async function loadPage() {
  const el = document.getElementById("user-table");
  try {
    const data = await apiFetch(
      `/api/users?page=${state.page}&page_size=${state.pageSize}`
    );
    state.items = data.items || [];
    state.total = data.total || 0;
    renderTable();
  } catch (e) {
    el.innerHTML = `<div class="empty">${escapeHtml(e.message)}</div>`;
    showToast(e.message, "error");
  }
}

function renderTable() {
  const el = document.getElementById("user-table");
  const totalLabel = document.getElementById("total-label");
  const pageLabel = document.getElementById("page-label");
  const pages = Math.max(1, Math.ceil(state.total / state.pageSize));
  if (totalLabel) totalLabel.textContent = `共 ${state.total} 人`;
  if (pageLabel) pageLabel.textContent = `第 ${state.page} / ${pages} 页`;
  document.getElementById("prev-page").disabled = state.page <= 1;
  document.getElementById("next-page").disabled = state.page * state.pageSize >= state.total;

  if (state.items.length === 0) {
    el.innerHTML = `<div class="empty">暂无用户</div>`;
    return;
  }

  const me = getUser();
  el.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>ID</th><th>用户名</th><th>昵称</th><th>角色</th><th>状态</th><th>创建时间</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        ${state.items
          .map((u) => {
            const isSelf = me && u.id === me.id;
            return `
            <tr>
              <td>${u.id}</td>
              <td>${escapeHtml(u.username)}</td>
              <td>${escapeHtml(u.nickname || "")}</td>
              <td><span class="badge ${u.role === "admin" ? "badge-admin" : "badge-user"}">${u.role}</span></td>
              <td>${u.status === 1 ? '<span class="badge badge-completed">启用</span>' : '<span class="badge badge-failed">禁用</span>'}</td>
              <td class="muted">${u.created_at ? new Date(u.created_at).toLocaleString("zh-CN") : ""}</td>
              <td>
                <button class="btn btn-sm" data-act="edit" data-id="${u.id}" ${isSelf ? "disabled title='不能修改自己'" : ""}>编辑</button>
                <button class="btn btn-sm" data-act="pwd" data-id="${u.id}" ${isSelf ? "disabled" : ""}>重置密码</button>
                <button class="btn btn-sm ${u.status === 1 ? "btn-danger" : ""}"
                        data-act="toggle" data-id="${u.id}" ${isSelf ? "disabled" : ""}>
                  ${u.status === 1 ? "禁用" : "启用"}
                </button>
              </td>
            </tr>`;
          })
          .join("")}
      </tbody>
    </table>`;

  el.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.id);
      const u = state.items.find((x) => x.id === id);
      if (btn.dataset.act === "edit") openUserModal(u);
      else if (btn.dataset.act === "pwd") resetPassword(u);
      else if (btn.dataset.act === "toggle") toggleUser(u);
    });
  });
}

function openUserModal(user) {
  const root = document.getElementById("modal-root");
  const isNew = !user;
  root.innerHTML = `
    <div class="modal-backdrop" id="u-backdrop">
      <div class="modal">
        <h3>${isNew ? "新建用户" : "编辑用户"}</h3>
        ${
          isNew
            ? `<label>用户名
              <input id="u-name" placeholder="字母数字下划线" pattern="[a-zA-Z0-9_]+" required />
            </label>
            <label>初始密码
              <input id="u-pwd" type="password" placeholder="至少 6 位" required />
            </label>`
            : `<p class="muted">${escapeHtml(user.username)}</p>`
        }
        <label>昵称
          <input id="u-nick" value="${escapeHtml(user ? user.nickname || "" : "")}" maxlength="64" />
        </label>
        <label>角色
          <select id="u-role">
            <option value="user" ${user && user.role === "user" ? "selected" : ""}>普通用户</option>
            <option value="admin" ${user && user.role === "admin" ? "selected" : ""}>管理员</option>
          </select>
        </label>
        <div class="modal-actions">
          <button class="btn" id="u-cancel" type="button">取消</button>
          <button class="btn btn-primary" id="u-save" type="button">保存</button>
        </div>
      </div>
    </div>`;

  const close = () => (root.innerHTML = "");
  root.querySelector("#u-cancel").addEventListener("click", close);
  root.querySelector("#u-backdrop").addEventListener("click", (e) => {
    if (e.target.id === "u-backdrop") close();
  });
  root.querySelector("#u-save").addEventListener("click", async () => {
    try {
      if (isNew) {
        const username = root.querySelector("#u-name").value.trim();
        const password = root.querySelector("#u-pwd").value;
        const nickname = root.querySelector("#u-nick").value.trim();
        const role = root.querySelector("#u-role").value;
        if (!username || !password) {
          showToast("请填写用户名和密码", "error");
          return;
        }
        await apiFetch("/api/users", {
          method: "POST",
          body: { username, password, nickname, role },
        });
      } else {
        const nickname = root.querySelector("#u-nick").value.trim();
        const role = root.querySelector("#u-role").value;
        await apiFetch(`/api/users/${user.id}`, {
          method: "PUT",
          body: { nickname, role },
        });
      }
      showToast("已保存", "success");
      close();
      await loadPage();
    } catch (e) {
      showToast(e.message, "error");
    }
  });
}

async function resetPassword(user) {
  const pwd = window.prompt(`重置「${user.username}」的密码（至少 6 位）：`);
  if (pwd == null) return;
  if (pwd.length < 6) {
    showToast("密码至少 6 位", "error");
    return;
  }
  try {
    await apiFetch(`/api/users/${user.id}/password`, {
      method: "PUT",
      body: { password: pwd },
    });
    showToast("密码已重置", "success");
  } catch (e) {
    showToast(e.message, "error");
  }
}

async function toggleUser(user) {
  const disabling = user.status === 1;
  if (disabling && !window.confirm(`禁用用户「${user.username}」？其存量 token 将立即失效。`)) {
    return;
  }
  try {
    await apiFetch(`/api/users/${user.id}`, {
      method: "PUT",
      body: { status: disabling ? 0 : 1 },
    });
    showToast(disabling ? "已禁用" : "已启用", "success");
    await loadPage();
  } catch (e) {
    showToast(e.message, "error");
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
