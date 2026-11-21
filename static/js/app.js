/** 应用入口：装配路由页面。 */

import { startRouter } from "./router.js";
import { renderLogin } from "./pages/login.js";
import { renderChat } from "./pages/chat.js";
import { renderHistory } from "./pages/history.js";
import { renderAdmin } from "./pages/admin.js";
import { renderAdminKb } from "./pages/admin_kb.js";
import { renderAdminDocs } from "./pages/admin_docs.js";
import { renderAdminUsers } from "./pages/admin_users.js";
import { showToast } from "./api.js";

const pages = {
  login: renderLogin,
  chat: renderChat,
  history: renderHistory,
  admin: renderAdmin,
  "admin/kb": renderAdminKb,
  "admin/docs": renderAdminDocs,
  "admin/users": renderAdminUsers,
};

// 暴露 toast 供各页使用
window.__toast = showToast;

startRouter(pages);
