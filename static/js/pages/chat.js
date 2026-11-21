/** 对话页占位（M3 #4 实现）。 */

export async function renderChat(container) {
  container.innerHTML = `
    <div class="page-missing">
      <h2>对话页</h2>
      <p class="muted">M3 #4 实现：会话栏、流式打字机、引用卡片与思考框。</p>
      <a class="btn" href="#/history">查看历史</a>
    </div>
  `;
}
