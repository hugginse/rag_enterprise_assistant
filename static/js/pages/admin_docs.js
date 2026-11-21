/** 管理端文档占位（M3 #8 实现）。 */

export async function renderAdminDocs(container) {
  container.innerHTML = `
    <div class="page-missing">
      <h2>文档管理</h2>
      <p class="muted">M3 #8 实现：上传、2s 轮询、失败重传。</p>
      <a href="#/admin">返回看板</a>
    </div>
  `;
}
