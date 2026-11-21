/** 管理端用户占位（M3 #8 实现）。 */

export async function renderAdminUsers(container) {
  container.innerHTML = `
    <div class="page-missing">
      <h2>用户管理</h2>
      <p class="muted">M3 #8 实现：CRUD、角色、重置密码。</p>
      <a href="#/admin">返回看板</a>
    </div>
  `;
}
