/** 登录页（M3 #3 完整实现；骨架先可登录）。 */

import { apiFetch, showToast } from "../api.js";
import { setAuth, navigate } from "../router.js";

export async function renderLogin(container) {
  container.innerHTML = `
    <div class="login-wrap">
      <form class="card login-card" id="login-form">
        <h1>企业知识库问答</h1>
        <p class="muted">请登录以继续</p>
        <label>用户名
          <input name="username" autocomplete="username" required placeholder="admin" />
        </label>
        <label>密码
          <input name="password" type="password" autocomplete="current-password" required placeholder="••••••" />
        </label>
        <button type="submit" class="btn btn-primary btn-block">登录</button>
      </form>
    </div>
  `;

  const form = container.querySelector("#login-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const username = String(fd.get("username") || "").trim();
    const password = String(fd.get("password") || "");
    const btn = form.querySelector("button");
    btn.disabled = true;
    try {
      const data = await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setAuth(data.token, data.user);
      showToast("登录成功", "success");
      navigate(data.user.role === "admin" ? "admin" : "chat");
    } catch (err) {
      showToast(err.message || "登录失败", "error");
    } finally {
      btn.disabled = false;
    }
  });
}
