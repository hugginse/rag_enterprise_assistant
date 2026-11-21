/** 对话页：会话栏 + KB 选择 + 流式问答（引用卡片 / 思考框 / rAF 打字机）。 */

import { apiFetch, sseFetch, showToast } from "../api.js";
import { navigate } from "../router.js";

const state = {
  kbs: [],
  kbId: null,
  sessions: [],
  sessionId: null,
  messages: [],
  streaming: false,
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
              <select id="kb-select" title="选择知识库"></select>
              <button class="btn btn-sm btn-primary" id="btn-new-session" type="button">＋ 新会话</button>
            </div>
            <div class="session-list" id="session-list"></div>
          </section>
          <section class="chat-main">
            <div class="chat-messages" id="chat-messages">
              <div class="empty">选择或新建会话，开始提问吧 👋</div>
            </div>
            <form class="chat-input" id="chat-form">
              <textarea id="chat-question" rows="2"
                        placeholder="输入问题，Enter 发送，Shift+Enter 换行" required></textarea>
              <button class="btn btn-primary" id="btn-send" type="submit">发送</button>
            </form>
          </section>
        </div>
      </div>
    </div>
  `;

  const $ = (sel) => container.querySelector(sel);

  const user = JSON.parse(localStorage.getItem("user") || "null");
  const label = $("#user-label");
  if (label && user) label.textContent = `${user.nickname || user.username}（${user.role}）`;
  const navAdmin = $("#nav-admin");
  if (navAdmin && user && user.role === "admin") navAdmin.hidden = false;

  $("#btn-logout").addEventListener("click", () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("login");
  });

  $("#btn-new-session").addEventListener("click", async () => {
    if (!state.kbId) {
      showToast("请先选择知识库", "error");
      return;
    }
    try {
      const s = await apiFetch("/api/chat/sessions", {
        method: "POST",
        body: { kb_id: Number(state.kbId), title: "新会话" },
      });
      state.sessionId = s.id;
      state.messages = [];
      await loadSessions();
      renderMessages();
      $("#chat-question").focus();
    } catch (e) {
      showToast(e.message, "error");
    }
  });

  /* ---------- 知识库 ---------- */
  async function loadKbs() {
    const data = await apiFetch("/api/knowledge-bases");
    state.kbs = data.items || [];
    const sel = $("#kb-select");
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
    await loadSessions();
  }

  $("#kb-select").addEventListener("change", async (e) => {
    state.kbId = Number(e.target.value);
    state.sessionId = null;
    state.messages = [];
    renderMessages();
    await loadSessions();
  });

  /* ---------- 会话 ---------- */
  async function loadSessions() {
    const q = state.kbId ? `?kb_id=${state.kbId}` : "";
    const data = await apiFetch(`/api/chat/sessions${q}`);
    state.sessions = data.items || [];
    renderSessionList();
  }

  function renderSessionList() {
    const box = $("#session-list");
    if (state.sessions.length === 0) {
      box.innerHTML = `<div class="empty">暂无会话</div>`;
      return;
    }
    box.innerHTML = state.sessions
      .map(
        (s) => `
      <div class="session-item ${s.id === state.sessionId ? "active" : ""}" data-id="${s.id}">
        <span class="s-title" title="${escapeHtml(s.title)}">${escapeHtml(s.title)}</span>
        <span class="s-actions">
          <button type="button" class="icon-btn" data-act="rename" title="重命名">✎</button>
          <button type="button" class="icon-btn" data-act="del" title="删除">✕</button>
        </span>
      </div>`
      )
      .join("");

    box.querySelectorAll(".session-item").forEach((item) => {
      const id = Number(item.dataset.id);
      item.querySelector(".s-title").addEventListener("click", () => openSession(id));
      item.querySelector('[data-act="rename"]').addEventListener("click", async (e) => {
        e.stopPropagation();
        const cur = state.sessions.find((s) => s.id === id);
        const title = window.prompt("重命名会话", cur ? cur.title : "");
        if (!title || !title.trim()) return;
        try {
          await apiFetch(`/api/chat/sessions/${id}`, {
            method: "PATCH",
            body: { title: title.trim().slice(0, 64) },
          });
          await loadSessions();
          showToast("已重命名", "success");
        } catch (err) {
          showToast(err.message, "error");
        }
      });
      item.querySelector('[data-act="del"]').addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!window.confirm("删除该会话？消息记录将一并删除。")) return;
        try {
          await apiFetch(`/api/chat/sessions/${id}`, { method: "DELETE" });
          if (state.sessionId === id) {
            state.sessionId = null;
            state.messages = [];
            renderMessages();
          }
          await loadSessions();
          showToast("已删除", "success");
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  }

  async function openSession(id) {
    state.sessionId = id;
    renderSessionList();
    try {
      const data = await apiFetch(`/api/chat/sessions/${id}/messages`);
      state.messages = (data.items || []).map((m) => ({
        question: m.question,
        answer: m.answer,
        sources: m.sources || [],
        thinking: null, // 思考不落库，仅会话内保留
      }));
    } catch (err) {
      showToast(err.message, "error");
      state.messages = [];
    }
    renderMessages(true);
  }

  /* ---------- 消息渲染 ---------- */
  function renderMessages(scroll = false) {
    const box = $("#chat-messages");
    if (state.messages.length === 0 && !state.streaming) {
      box.innerHTML = `<div class="empty">选择或新建会话，开始提问吧 👋</div>`;
      return;
    }
    box.innerHTML = state.messages
      .map(
        (m) => `
      <div class="msg-pair">
        <div class="msg-user">${escapeHtml(m.question)}</div>
        <div class="msg-assistant">
          ${renderSources(m.sources)}
          <div class="msg-answer">
            ${m.thinking ? renderThinking(m.thinking) : ""}
            <div class="answer-text">${formatAnswer(m.answer)}</div>
          </div>
        </div>
      </div>`
      )
      .join("");
    if (scroll) box.scrollTop = box.scrollHeight;
  }

  function renderThinking(text) {
    return `
      <details class="thinking-box" open>
        <summary>🧠 思考过程</summary>
        <div class="thinking-body">${escapeHtml(text)}</div>
      </details>`;
  }

  function renderSources(sources) {
    if (!sources || sources.length === 0) return "";
    return `
      <div class="sources">
        <div class="sources-title">📎 引用来源（${sources.length}）</div>
        <div class="source-cards">
          ${sources
            .map(
              (s) => `
            <details class="source-card">
              <summary>
                <span class="source-file">${escapeHtml(s.file_name || "未知文件")}</span>
                <span class="source-score">${((s.score || 0) * 100).toFixed(1)}%</span>
              </summary>
              <div class="source-snippet">${escapeHtml(s.snippet || "")}</div>
            </details>`
            )
            .join("")}
        </div>
      </div>`;
  }

  /* ---------- 提问（SSE） ---------- */
  $("#chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (state.streaming) return;
    const input = $("#chat-question");
    const question = input.value.trim();
    if (!question) return;
    if (!state.kbId) {
      showToast("请先选择知识库", "error");
      return;
    }

    // 无会话则自动建
    if (!state.sessionId) {
      try {
        const s = await apiFetch("/api/chat/sessions", {
          method: "POST",
          body: { kb_id: Number(state.kbId), title: question.slice(0, 20) },
        });
        state.sessionId = s.id;
        await loadSessions();
      } catch (err) {
        showToast(err.message, "error");
        return;
      }
    }

    state.streaming = true;
    const btn = $("#btn-send");
    btn.disabled = true;
    btn.textContent = "思考中…";
    input.value = "";

    const box = $("#chat-messages");
    if (box.querySelector(".empty")) box.innerHTML = "";
    const pair = document.createElement("div");
    pair.className = "msg-pair streaming";
    pair.innerHTML = `
      <div class="msg-user">${escapeHtml(question)}</div>
      <div class="msg-assistant">
        <div class="sources-slot" id="live-sources" hidden></div>
        <div class="msg-answer">
          <details class="thinking-box" id="live-thinking" open hidden>
            <summary>🧠 思考过程</summary>
            <div class="thinking-body" id="live-thinking-body"></div>
          </details>
          <div class="answer-text" id="live-answer"><span class="thinking-placeholder">正在思考…</span><span class="cursor">▍</span></div>
        </div>
      </div>`;
    box.appendChild(pair);
    box.scrollTop = box.scrollHeight;

    const liveSources = pair.querySelector("#live-sources");
    const liveThinking = pair.querySelector("#live-thinking");
    const liveThinkingBody = pair.querySelector("#live-thinking-body");
    const liveAnswer = pair.querySelector("#live-answer");
    let fullAnswer = "";
    let fullThinking = "";
    let sources = [];
    let gotDone = false;

    const stickToBottom = (el) =>
      el.scrollHeight - el.scrollTop - el.clientHeight < 48;

    let rafPending = false;
    const flushAnswer = () => {
      rafPending = false;
      if (fullThinking) {
        liveThinking.hidden = false;
        const stick = stickToBottom(liveThinkingBody);
        liveThinkingBody.textContent = fullThinking;
        if (stick) liveThinkingBody.scrollTop = liveThinkingBody.scrollHeight;
      }
      liveAnswer.innerHTML = fullAnswer
        ? formatAnswer(fullAnswer) + `<span class="cursor">▍</span>`
        : `<span class="thinking-placeholder">正在思考…</span><span class="cursor">▍</span>`;
      box.scrollTop = box.scrollHeight;
    };
    const scheduleFlush = () => {
      if (!rafPending) {
        rafPending = true;
        requestAnimationFrame(flushAnswer);
      }
    };

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
            if (sources.length) {
              liveSources.hidden = false;
              liveSources.innerHTML = renderSources(sources);
            } else {
              liveSources.hidden = true;
              liveSources.innerHTML = "";
            }
          } else if (event === "thinking") {
            fullThinking += data.content || "";
            scheduleFlush();
          } else if (event === "delta") {
            fullAnswer += data.content || "";
            scheduleFlush();
          } else if (event === "error") {
            showToast(data.message || "问答服务异常", "error");
            liveAnswer.innerHTML = `<span class="error-text">${escapeHtml(
              data.message || "问答服务异常"
            )}</span>`;
          }
        }
      );
      // 流结束（正常 done 或截断）
      gotDone = true;
      state.messages.push({
        question,
        answer: fullAnswer || "（无回答）",
        sources,
        thinking: fullThinking || null,
      });
      pair.classList.remove("streaming");
      pair.innerHTML = `
        <div class="msg-user">${escapeHtml(question)}</div>
        <div class="msg-assistant">
          ${renderSources(sources)}
          <div class="msg-answer">
            ${fullThinking ? renderThinking(fullThinking) : ""}
            <div class="answer-text">${formatAnswer(fullAnswer)}</div>
          </div>
        </div>`;
      box.scrollTop = box.scrollHeight;
      try {
        await loadSessions();
      } catch {
        /* ignore */
      }
    } catch (err) {
      showToast(err.message || "请求失败", "error");
      liveAnswer.innerHTML = `<span class="error-text">${escapeHtml(err.message || "请求失败")}</span>`;
    } finally {
      state.streaming = false;
      btn.disabled = false;
      btn.textContent = "发送";
      if (rafPending) cancelAnimationFrame(rafPending);
      box.scrollTop = box.scrollHeight;
      void gotDone;
    }
  });

  $("#chat-question").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      $("#chat-form").requestSubmit();
    }
  });

  /* ---------- init ---------- */
  try {
    await loadKbs();
    renderMessages();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatAnswer(text) {
  let html = escapeHtml(text);
  // 先抽出代码块，避免误伤其中的方括号
  const codes = [];
  html = html.replace(/```([\s\S]*?)```/g, (_, c) => {
    codes.push(c.trim());
    return `\u0000CODE${codes.length - 1}\u0000`;
  });
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // 依据引用：[文件名.ext] 或 [文件名.ext #3] → 醒目徽章
  html = html.replace(
    /\[([^\[\]]+?\.(?:md|txt|pdf|docx))(?:\s*#\s*(\d+))?\]/gi,
    (_, file, n) =>
      `<span class="cite-ref" title="回答依据来源">📎 ${file}${n ? ` #${n}` : ""}</span>`
  );
  // 「参考资料」「依据」等引导词轻量强调
  html = html.replace(
    /(根据)?(参考资料|依据文件|依据资料)/g,
    '<span class="cite-lead">$2</span>'
  );
  html = html.replace(/\n/g, "<br>");
  html = html.replace(/\u0000CODE(\d+)\u0000/g, (_, i) => `<pre>${codes[Number(i)]}</pre>`);
  return html;
}
