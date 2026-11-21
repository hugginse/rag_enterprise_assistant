/** 登录页：表单 → 存 token → 按角色跳转。 */

import { apiFetch, showToast } from "../api.js";
import { setAuth, navigate, getToken } from "../router.js";

const EYE_SVG = `
<svg viewBox="0 0 24 24" width="18" height="18" fill="none"
     stroke="currentColor" stroke-width="2" stroke-linecap="round"
     stroke-linejoin="round" aria-hidden="true">
  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"></path>
  <circle cx="12" cy="12" r="3"></circle>
</svg>`;

const EYE_OFF_SVG = `
<svg viewBox="0 0 24 24" width="18" height="18" fill="none"
     stroke="currentColor" stroke-width="2" stroke-linecap="round"
     stroke-linejoin="round" aria-hidden="true">
  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94
           M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19
           m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
  <line x1="1" y1="1" x2="23" y2="23"></line>
</svg>`;

export async function renderLogin(container) {
  // 已登录则直接跳走
  if (getToken()) {
    navigate("chat");
    return;
  }

  container.innerHTML = `
    <div class="login-wrap">
      <form class="card login-card" id="login-form" novalidate>
        <h1>企业知识库问答</h1>
        <p class="muted">请登录以继续</p>
        <label>用户名
          <input name="username" autocomplete="username" required
                 placeholder="admin 或 user" spellcheck="false" />
        </label>
        <label>密码
          <span class="pw-wrap">
            <input name="password" type="password" autocomplete="current-password"
                   required placeholder="请输入密码" id="login-password" />
            <button type="button" class="pw-toggle" id="pw-toggle"
                    aria-label="显示密码" title="显示密码">${EYE_SVG}</button>
          </span>
        </label>
        <button type="submit" class="btn btn-primary btn-block" id="login-btn">登录</button>
        <p class="muted login-hint">演示账号：admin/admin123 · user/user123</p>
      </form>
    </div>
  `;

  const form = container.querySelector("#login-form");
  const btn = container.querySelector("#login-btn");
  const userInput = form.elements.namedItem("username");
  const passInput = form.elements.namedItem("password");
  const toggle = container.querySelector("#pw-toggle");
  userInput.focus();

  toggle.addEventListener("click", () => {
    const showing = passInput.type === "text";
    passInput.type = showing ? "password" : "text";
    toggle.innerHTML = showing ? EYE_SVG : EYE_OFF_SVG;
    toggle.setAttribute("aria-label", showing ? "显示密码" : "隐藏密码");
    toggle.title = showing ? "显示密码" : "隐藏密码";
    passInput.focus();
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = String(userInput.value || "").trim();
    const password = String(passInput.value || "");

    if (!username || !password) {
      showToast("请输入用户名和密码", "error");
      return;
    }

    btn.disabled = true;
    btn.textContent = "登录中…";
    try {
      const data = await apiFetch("/api/auth/login", {
        method: "POST",
        body: { username, password },
        toast: false, // 统一在下方处理
      });
      setAuth(data.token, data.user);
      showToast("登录成功", "success");
      navigate(data.user.role === "admin" ? "admin" : "chat");
    } catch (err) {
      showToast(err.message || "登录失败", "error");
      passInput.value = "";
      passInput.focus();
    } finally {
      btn.disabled = false;
      btn.textContent = "登录";
    }
  });
}
