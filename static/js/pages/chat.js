/** 对话页：会话栏 + KB 选择 + 流式问答（引用卡片 / 思考框 / 打字机）。 */

import { apiFetch, sseFetch, showToast } from "../api.js";
import { navigate } from "../router.js";

const state = {
  kbs: [],
  kbId: null,
  sessions: [],
  sessionId: null,
  messages: [], // 已落库历史 {question, answer, sources}
  streaming: false,
  // 流式缓冲（rAF 批量刷新）
  pendingThinking: "",
  pendingDelta: "",
  thinkingOpen: true,
  raf: 0,
};

export async function renderChat(container) {
  container.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">知识库问答</div>
        <nav>
          <a href="#/chat" class="active">对话</a>
          <a href="#/history">历史</a>
          <a href="#/admin" id="nav-admin" hidden>管理</a>
        </nav>
        <div class="spacer"></div>
        <button class="btn btn-sm" id="btn-logout" type="button">退出登录</button>
      </aside>
      <div class="main">
        <header class="topbar">
          <h2>对话</h2>
          <span class="muted" id="user-label"></span>
        </header>
        <div class="chat-layout">
          <section class="session-panel">
            <div class="head">
              <strong>会话</strong>
              <button class="btn btn-sm btn-primary" id="btn-new-session" type="button">新建</button>
            </div>
            <div class="session-list" id="session-list"></div>
          </section>
          <section class="chat-main">
            <div class="chat-toolbar">
              <label class="muted" for="kb-select" style="margin:0;font-weight:400">知识库</label>
              <select id="kb-select"></select>
              <span class="spacer"></span>
            </div>
            <div class="chat-messages" id="chat-messages">
              <div class="empty" id="chat-empty">选择或新建会话，开始提问</div>
            </div>
            <form class="chat-input" id="chat-form">
              <textarea id="chat-question" rows="1" placeholder="输入问题，Enter 发送，Shift+Enter 换行"
                        required></textarea>
              <button class="btn btn-primary" id="btn-send" type="submit">发送</button>
            </form>
          </section>
        </div>
      </div>
    </div>
  `;

  const user = JSON.parse(localStorage.getItem("user") || "null");
  const label = container.querySelector("#user-label");
  if (label && user) label.textContent = `${user.nickname || user.username}（${user.role}）`;
  const navAdmin = container.querySelector("#nav-admin");
  if (navAdmin && user && user.role === "admin") navAdmin.hidden = false;

  container.querySelector("#btn-logout").addEventListener("click", () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("login");
  });

  container.querySelector("#btn-new-session").addEventListener("click", async () => {
    if (!state.kbId) {
      showToast("请先选择知识库", "error");
      return;
    }
    try {
      const s = await apiFetch("/api/chat/sessions", {
        method: "POST",
        body: { kb_id: Number(state.kbId), title: "新会话" },
      });
      await loadSessions();
      selectSession(s.id);
    } catch (e) {
      showToast(e.message, "error");
    }
  });

  const form = container.querySelector("#chat-form");
  const textarea = container.querySelector("#chat-question");
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    ask(textarea);
  });

  const kbSelect = container.querySelector("#kb-select");
  kbSelect.addEventListener("change", async () => {
    state.kbId = Number(kbSelect.value);
    state.sessionId = null;
    state.messages = [];
    renderMessages();
    await loadSessions();
  });

  try {
    await loadKbs();
    await loadSessions();
    if (state.sessions.length > 0) {
      selectSession(state.sessions[0].id);
    } else {
      renderMessages();
    }
  } catch (err) {
    showToast(err.message || "加载失败", "error");
    if (err.status === 401) return;
  }
}

async function loadKbs() {
  const data = await apiFetch("/api/knowledge-bases");
  state.kbs = data.items || [];
  const sel = document.getElementById("kb-select");
  if (!sel) return;
  if (state.kbs.length === 0) {
    sel.innerHTML = `<option value="">（无可用知识库）</option>`;
    state.kbId = null;
    return;
  }
  sel.innerHTML = state.kbs
    .map((k) => `<option value="${k.id}">${escapeHtml(k.name)}</option>`)
    .join("");
  state.kbId = state.kbs[0].id;
  sel.value = String(state.kbId);
}

async function loadSessions() {
  const q = state.kbId ? `?kb_id=${state.kbId}` : "";
  const data = await apiFetch(`/api/chat/sessions${q}`);
  state.sessions = data.items || [];
  renderSessionList();
}

function renderSessionList() {
  const el = document.getElementById("session-list");
  if (!el) return;
  if (state.sessions.length === 0) {
    el.innerHTML = `<div class="empty">暂无会话</div>`;
    return;
  }
  el.innerHTML = state.sessions
    .map(
      (s) => `
      <div class="session-item ${s.id === state.sessionId ? "active" : ""}"
           data-id="${s.id}" title="${escapeHtml(s.title)}">
        <span class="s-title">${escapeHtml(s.title)}</span>
        <span class="s-actions">
          <button type="button" class="icon-btn" data-act="rename" title="重命名">✎</button>
          <button type="button" class="icon-btn" data-act="del" title="删除">✕</button>
        </span>
      </div>`
    )
    .join("");

  el.querySelectorAll(".session-item").forEach((item) => {
    const id = Number(item.dataset.id);
    item.addEventListener("click", (e) => {
      const act = e.target && e.target.dataset ? e.target.dataset.act : null;
      if (act === "rename") {
        e.stopPropagation();
        renameSession(id);
        return;
      }
      if (act === "del") {
        e.stopPropagation();
        deleteSession(id);
        return;
      }
      selectSession(id);
    });
  });
}

async function selectSession(id) {
  state.sessionId = id;
  renderSessionList();
  try {
    const data = await apiFetch(`/api/chat/sessions/${id}/messages`);
    state.messages = (data.items || []).map((m) => ({
      question: m.question,
      answer: m.answer,
      sources: m.sources || [],
    }));
  } catch (e) {
    state.messages = [];
    showToast(e.message, "error");
  }
  renderMessages();
}

async function renameSession(id) {
  const cur = state.sessions.find((s) => s.id === id);
  const title = window.prompt("新会话标题", cur ? cur.title : "");
  if (!title || !title.trim()) return;
  try {
    await apiFetch(`/api/chat/sessions/${id}`, {
      method: "PATCH",
      body: { title: title.trim().slice(0, 64) },
    });
    await loadSessions();
    showToast("已重命名", "success");
  } catch (e) {
    showToast(e.message, "error");
  }
}

async function deleteSession(id) {
  if (!window.confirm("删除该会话及其全部消息？")) return;
  try {
    await apiFetch(`/api/chat/sessions/${id}`, { method: "DELETE" });
    if (state.sessionId === id) {
      state.sessionId = null;
      state.messages = [];
      renderMessages();
    }
    await loadSessions();
    showToast("已删除", "success");
  } catch (e) {
    showToast(e.message, "error");
  }
}

function renderMessages() {
  const box = document.getElementById("chat-messages");
  if (!box) return;
  if (state.messages.length === 0 && !state.streaming) {
    box.innerHTML = `<div class="empty" id="chat-empty">选择或新建会话，开始提问</div>`;
    return;
  }
  box.innerHTML = state.messages.map((m) => messageHtml(m)).join("");
  // 流式占位
  if (state.streaming) {
    box.insertAdjacentHTML("beforeend", streamingPlaceholderHtml());
  }
  box.scrollTop = box.scrollHeight;
}

function messageHtml(m) {
  return `
    <div class="msg-block">
      <div class="msg-user">${escapeHtml(m.question)}</div>
      <div class="msg-assistant">
        ${sourcesHtml(m.sources)}
        ${escapeHtml(m.answer)}
      </div>
    </div>`;
}

function sourcesHtml(sources) {
  if (!sources || sources.length === 0) return "";
  const cards = sources
    .map((s) => {
      const pct = typeof s.score === "number" ? Math.round(s.score * 100) : null;
      return `
        <div class="source-card">
          ${pct != null ? `<span class="score">${pct}%</span>` : ""}
          <div class="file">${escapeHtml(s.file_name || "")}</div>
          <div class="snippet">${escapeHtml(s.snippet || "")}</div>
        </div>`;
    })
    .join("");
  return `<div class="sources"><div class="muted" style="font-size:0.78rem">引用资料</div>${cards}</div>`;
}

function streamingPlaceholderHtml() {
  const thinking = state.pendingThinking;
  const delta = state.pendingDelta;
  const thinkingBlock = thinking
    ? `<details class="thinking-box" ${state.thinkingOpen ? "open" : ""} id="thinking-box">
         <summary>思考过程</summary>
         <div class="thinking-body" id="thinking-body">${escapeHtml(thinking)}</div>
       </details>`
    : `<div class="thinking-box" id="thinking-box"><summary>思考中…</summary>
         <div class="thinking-body muted">正在思考…</div>
       </div>`;
  const answerBlock = delta
    ? escapeHtml(delta)
    : thinking
      ? `<span class="muted">正在思考…</span>`
      : `<span class="muted">正在思考…</span>`;
  return `
    <div class="msg-block" id="stream-block">
      <div class="msg-assistant">
        <div class="sources" id="stream-sources" hidden></div>
        ${thinkingBlock}
        <div id="stream-answer">${answerBlock}</div>
      </div>
    </div>`;
}

function schedulePaint() {
  if (state.raf) return;
  state.raf = requestAnimationFrame(() => {
    state.raf = 0;
    paintStream();
  });
}

function paintStream() {
  const block = document.getElementById("stream-block");
  if (!block) return;
  const box = document.getElementById("chat-messages");
  const nearBottom =
    !box || box.scrollHeight - box.scrollTop - box.clientHeight < 48;

  const thinkingEl = document.getElementById("thinking-body");
  const thinkingBox = document.getElementById("thinking-box");
  if (thinkingEl && state.pendingThinking) {
    thinkingEl.textContent = state.pendingThinking;
    if (thinkingBox) thinkingBox.scrollTop = thinkingBox.scrollHeight;
    // 未显式收起时保持打开
    if (state.thinkingOpen && thinkingBox && thinkingBox.tagName === "DETAILS") {
      thinkingBox.open = true;
    }
  }
  const answerEl = document.getElementById("stream-answer");
  if (answerEl) {
    answerEl.textContent = state.pendingDelta || "";
    answerEl.classList.toggle("muted", !state.pendingDelta);
    if (!state.pendingDelta) answerEl.textContent = "正在思考…";
  }
  if (nearBottom && box) box.scrollTop = box.scrollHeight;
}

async function ask(textarea) {
  if (state.streaming) return;
  const question = String(textarea.value || "").trim();
  if (!question) return;
  if (!state.kbId) {
    showToast("请选择知识库", "error");
    return;
  }

  // 无会话则自动创建
  if (!state.sessionId) {
    try {
      const s = await apiFetch("/api/chat/sessions", {
        method: "POST",
        body: { kb_id: Number(state.kbId), title: question.slice(0, 20) },
      });
      state.sessionId = s.id;
      await loadSessions();
    } catch (e) {
      showToast(e.message, "error");
      return;
    }
  }

  state.streaming = true;
  state.pendingThinking = "";
  state.pendingDelta = "";
  state.thinkingOpen = true;
  textarea.value = "";
  const btn = document.getElementById("btn-send");
  if (btn) btn.disabled = true;

  // 先插入用户消息与流式占位
  const box = document.getElementById("chat-messages");
  const empty = document.getElementById("chat-empty");
  if (empty) empty.remove();
  box.insertAdjacentHTML(
    "beforeend",
    `<div class="msg-block"><div class="msg-user">${escapeHtml(question)}</div></div>` +
      streamingPlaceholderHtml()
  );
  box.scrollTop = box.scrollHeight;

  let sources = [];

  try {
    await sseFetch(
      "/api/chat/ask",
      {
        method: "POST",
        body: { question, kb_id: Number(state.kbId), session_id: state.sessionId },
      },
      (event, data) => {
        if (event === "sources") {
          sources = data.sources || [];
          const el = document.getElementById("stream-sources");
          if (el && sources.length) {
            el.hidden = false;
            el.innerHTML = sources
              .map((s) => {
                const pct = typeof s.score === "number" ? Math.round(s.score * 100) : null;
                return `<div class="source-card">
                  ${pct != null ? `<span class="score">${pct}%</span>` : ""}
                  <div class="file">${escapeHtml(s.file_name || "")}</div>
                  <div class="snippet">${escapeHtml(s.snippet || "")}</div>
                </div>`;
              })
              .join("");
          }
        } else if (event === "thinking") {
          state.pendingThinking += data.content || "";
          schedulePaint();
        } else if (event === "delta") {
          state.pendingDelta += data.content || "";
          schedulePaint();
        } else if (event === "error") {
          showToast(data.message || "问答失败", "error");
        }
        // done 在循环外处理
      }
    );
    // sseFetch 结束即 done（或 error 后结束）
    await finalizeAsk(question, sources);
  } catch (err) {
    showToast(err.message || "请求失败", "error");
    const sb = document.getElementById("stream-block");
    if (sb) sb.remove();
  } finally {
    state.streaming = false;
    if (btn) btn.disabled = false;
    if (state.raf) {
      cancelAnimationFrame(state.raf);
      state.raf = 0;
    }
    try {
      await loadSessions();
    } catch {
      /* ignore */
    }
  }
}

async function finalizeAsk(question, sources) {
  // 用最新会话消息刷新（服务端已落库）
  if (state.sessionId) {
    try {
      const data = await apiFetch(`/api/chat/sessions/${state.sessionId}/messages`);
      state.messages = (data.items || []).map((m) => ({
        question: m.question,
        answer: m.answer,
        sources: m.sources || [],
      }));
    } catch {
      // 回退：本地拼一条
      state.messages.push({
        question,
        answer: state.pendingDelta,
        sources,
      });
    }
  } else {
    state.messages.push({ question, answer: state.pendingDelta, sources });
  }
  state.pendingThinking = "";
  state.pendingDelta = "";
  renderMessages();
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
