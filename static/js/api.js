/** fetch 封装与 SSE 解析器。
 *
 * - 自动带 token
 * - 读流前先检查状态码（非 2xx 解析 JSON 错误并 toast）
 * - 401 跳登录
 * - 统一 toast
 * - SSE：fetch + ReadableStream 解析 event:/data: 帧
 */

/** 开发期静态在 5173、API 在 8000；同源部署（#9）时为空前缀。 */
export const API_BASE =
  location.port === "5173" ? `${location.protocol}//${location.hostname}:8000` : "";

function url(path) {
  if (/^https?:\/\//i.test(path)) return path;
  return API_BASE + (path.startsWith("/") ? path : `/${path}`);
}

export function getToken() {
  return localStorage.getItem("token");
}

export function clearAuth() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

export function showToast(message, type = "info", duration = 3200) {
  const root = document.getElementById("toast-root");
  if (!root) return;
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = String(message);
  root.appendChild(el);
  window.setTimeout(() => {
    el.classList.add("toast-hide");
    window.setTimeout(() => el.remove(), 320);
  }, duration);
}

function handle401() {
  clearAuth();
  if (location.hash !== "#/login") {
    location.hash = "#/login";
  }
}

async function readErrorDetail(resp) {
  try {
    const data = await resp.json();
    const d = data.detail;
    if (typeof d === "string") return d;
    if (d != null) return JSON.stringify(d);
    if (data.message) return String(data.message);
  } catch {
    /* non-JSON body */
  }
  return `请求失败 (${resp.status})`;
}

/**
 * 统一 JSON API 调用。
 * @param {string} path
 * @param {{method?:string, body?:any, headers?:object, toast?:boolean}} options
 */
export async function apiFetch(path, options = {}) {
  const { method = "GET", body, headers = {}, toast = true } = options;
  const finalHeaders = { ...headers };
  const token = getToken();
  if (token) finalHeaders.Authorization = `Bearer ${token}`;

  let payload;
  if (body instanceof FormData) {
    payload = body;
  } else if (body != null) {
    payload = typeof body === "string" ? body : JSON.stringify(body);
    if (!finalHeaders["Content-Type"] && !finalHeaders["content-type"]) {
      finalHeaders["Content-Type"] = "application/json";
    }
  }

  const resp = await fetch(url(path), { method, headers: finalHeaders, body: payload });

  if (resp.status === 401) {
    handle401();
    const msg = "登录已过期，请重新登录";
    if (toast) showToast(msg, "error");
    const err = new Error(msg);
    err.status = 401;
    throw err;
  }

  // 读 body 前先检查状态码
  if (!resp.ok) {
    const detail = await readErrorDetail(resp);
    if (toast) showToast(detail, "error");
    const err = new Error(detail);
    err.status = resp.status;
    throw err;
  }

  if (resp.status === 204) return null;
  const text = await resp.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/**
 * SSE 请求：先检查状态码，再逐帧解析 event:/data:。
 * @param {string} path
 * @param {{method?:string, body?:any, headers?:object}} options
 * @param {(event: string, data: any) => void} onEvent
 */
export async function sseFetch(path, options = {}, onEvent) {
  const { method = "POST", body, headers = {} } = options;
  const finalHeaders = { Accept: "text/event-stream", ...headers };
  const token = getToken();
  if (token) finalHeaders.Authorization = `Bearer ${token}`;
  if (body != null && !finalHeaders["Content-Type"]) {
    finalHeaders["Content-Type"] =
      typeof body === "string" ? "application/json" : "application/json";
  }

  const payload = body == null ? undefined : typeof body === "string" ? body : JSON.stringify(body);
  const resp = await fetch(url(path), { method, headers: finalHeaders, body: payload });

  if (resp.status === 401) {
    handle401();
    const err = new Error("登录已过期，请重新登录");
    err.status = 401;
    throw err;
  }

  // 读流前先检查状态码：非 2xx → 解析 JSON 错误并 toast（不进入流解析）
  if (!resp.ok) {
    const detail = await readErrorDetail(resp);
    showToast(detail, "error");
    const err = new Error(detail);
    err.status = resp.status;
    throw err;
  }

  if (!resp.body) {
    const err = new Error("浏览器不支持流式响应");
    throw err;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let eventName = "message";
  let dataLines = [];

  const flush = () => {
    if (dataLines.length === 0 && eventName === "message") {
      eventName = "message";
      return;
    }
    const raw = dataLines.join("\n");
    dataLines = [];
    const name = eventName;
    eventName = "message";
    let parsed = raw;
    try {
      parsed = JSON.parse(raw);
    } catch {
      /* keep string */
    }
    onEvent(name, parsed);
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let newlineIdx;
    while ((newlineIdx = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newlineIdx).replace(/\r$/, "");
      buffer = buffer.slice(newlineIdx + 1);

      if (line === "") {
        flush();
        continue;
      }
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
      // 忽略 id:/retry:/注释行
    }
  }
  // 尾部残留
  if (buffer.length > 0) {
    const line = buffer.replace(/\r$/, "");
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  flush();
}
