/** 手写 hash 路由：未登录跳 login；非 admin 访问 admin 弹回 #/chat。 */

const ROUTES = {
  login: { title: "登录", admin: false, auth: false },
  chat: { title: "对话", admin: false, auth: true },
  history: { title: "历史", admin: false, auth: true },
  admin: { title: "管理看板", admin: true, auth: true },
  "admin/kb": { title: "知识库管理", admin: true, auth: true },
  "admin/docs": { title: "文档管理", admin: true, auth: true },
  "admin/users": { title: "用户管理", admin: true, auth: true },
};

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "") || "login";
  return raw.split("?")[0];
}

export function getToken() {
  return localStorage.getItem("token");
}

export function getUser() {
  try {
    return JSON.parse(localStorage.getItem("user") || "null");
  } catch {
    return null;
  }
}

export function setAuth(token, user) {
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

export function navigate(path) {
  const p = path.replace(/^#\/?/, "");
  location.hash = `#/${p}`;
}

/** 返回当前路由 key（如 "admin/kb"） */
export function currentRoute() {
  return parseHash();
}

/**
 * 注册页面渲染器：pages 是 { routeKey: renderFn(container) }
 */
export function startRouter(pages) {
  async function resolve() {
    let key = parseHash();
    const meta = ROUTES[key];
    const container = document.getElementById("app");

    if (!meta) {
      navigate("login");
      return;
    }

    if (meta.auth && !getToken()) {
      navigate("login");
      return;
    }

    if (!meta.auth && getToken() && key === "login") {
      navigate("chat");
      return;
    }

    if (meta.admin) {
      const user = getUser();
      if (!user || user.role !== "admin") {
        navigate("chat");
        return;
      }
    }

    document.title = `${meta.title} · 企业知识库问答`;

    const render = pages[key];
    if (!render) {
      container.innerHTML = `<div class="page-missing">页面未实现：${key}</div>`;
      return;
    }
    container.innerHTML = "";
    await render(container);
  }

  window.addEventListener("hashchange", resolve);
  resolve();
  return { resolve };
}
