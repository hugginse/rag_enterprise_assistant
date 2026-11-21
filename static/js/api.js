/** fetch 封装、SSE 解析、toast（M3 #2 完善；先提供基础能力）。 */

export function getToken() {
  return localStorage.getItem("token");
}

export function showToast(message, type = "info", duration = 3000) {
  const root = document.getElementById("toast-root");
  if (!root) return;
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => {
    el.classList.add("toast-hide");
    setTimeout(() => el.remove(), 300);
  }, duration);
}

export async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const resp = await fetch(path, { ...options, headers });
  if (resp.status === 401) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    if (location.hash !== "#/login") location.hash = "#/login";
    throw new Error("登录已过期");
  }
  if (!resp.ok) {
    let detail = `请求失败 ${resp.status}`;
    try {
      const data = await resp.json();
      if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* ignore */
    }
    const err = new Error(detail);
    err.status = resp.status;
    throw err;
  }
  if (resp.status === 204) return null;
  return resp.json();
}

/** 解析 SSE（fetch + ReadableStream），对每个事件回调 onEvent(event, data) */
export async function sseFetch(path, options, onEvent) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  headers["Content-Type"] = "application/json";

  const resp = await fetch(path, { ...options, headers });
  if (resp.status === 401) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    location.hash = "#/login";
    throw new Error("登录已过期");
  }
  if (!resp.ok) {
    let detail = `请求失败 ${resp.status}`;
    try {
      const data = await resp.json();
      if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* ignore */
    }
    const err = new Error(detail);
    err.status = resp.status;
    throw err;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let event = "message";
  let dataLines = [];

  function dispatch() {
    if (dataLines.length === 0 && event === "message") return;
    const raw = dataLines.join("\n");
    dataLines = [];
    const name = event;
    event = "message";
    try {
      onEvent(name, JSON.parse(raw));
    } catch {
      onEvent(name, raw);
    }
  }

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, idx).replace(/\r$/, "");
      buf = buf.slice(idx + 1);
      if (line === "") {
        dispatch();
        continue;
      }
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
  }
  dispatch();
}
