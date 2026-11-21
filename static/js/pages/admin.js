/** 管理看板占位（M3 #6 实现）。 */

export async function renderAdmin(container) {
  container.innerHTML = `
    <div class="page-missing">
      <h2>管理看板</h2>
      <p class="muted">M3 #6 实现：统计卡片 + SVG 七日趋势图。</p>
      <nav class="admin-nav">
        <a href="#/admin/kb">知识库</a>
        <a href="#/admin/docs">文档</a>
        <a href="#/admin/users">用户</a>
      </nav>
    </div>
  `;
}
