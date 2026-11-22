# rag_enterprise_assistant 开发计划

> 执行入口：仓库根 `CLAUDE.md`；设计基准：`docs/architecture.md`；本文回答**做什么、按什么顺序、何时提交推送**。
> 流程：**远端建仓（需求方）→ 本地关联 → M1…M4 逐 feature commit → 每个 Gate 全绿后打 tag 并推送一次**。
> 顺序固定 M1 → M2 → M3 → M4；**上一里程碑 Gate 未过不得进入下一里程碑**；任一 Gate 失败先修复。

---

## 0. Git 工作流（需求方已定，不得更改）

### 0.1 远端与本地关联（开工第一步）

远端空仓库由**需求方**在 GitHub 预先创建（public，不初始化 README），仓库名 **`rag_enterprise_assistant`**。执行终端拿到 URL 后：

```bash
# 本地目录已由需求方放入：CLAUDE.md、docs/、seed_docs/（三个子文件夹共 12 份）
git init -b main
git remote add origin <需求方提供的 URL>
git config user.name <...> && git config user.email <...>   # 若全局未配置；不要伪造身份，缺就问
uv sync && uv run python --version                          # 确认 3.12，生成 uv.lock
find seed_docs -type f | wc -l                              # 必须 = 12
```

拿不到 URL → **停下询问**，不要自行建仓。

### 0.2 提交与推送规则

- **commit 粒度 = 下文每条 feature 条目**（一条 feature 一个 commit；确需拆分/合并时保持语义不变并在报告说明）
- message 格式：`feat: 中文描述`（前缀按 feat/fix/test/docs/ci/chore），**每条末尾加**：
  ```
  Co-Authored-By: Claude Code <noreply@anthropic.com>
  ```
- 每个 commit 前：`uv run ruff check .` 0 error + 相关 `uv run pytest` 通过
- **每个 Gate 全绿 → 打 annotated tag → 一次性 push（全部 commit + tag）**：

  | Gate | tag | push 命令 |
  |---|---|---|
  | Gate-M1 | `m1` | `git push -u origin main m1`（首次，带 -u） |
  | Gate-M2 | `m2` | `git push origin main m2` |
  | Gate-M3 | `m3` | `git push origin main m3` |
  | Gate-M4 | `m4` | `git push origin main m4` |

- Gate 失败 → 修复并 commit → 重跑 Gate → 全绿前**不打 tag 不 push**；Gate 之外不 push；禁止 force push
- 永不提交：`.env`、`uploads/`、`chroma_data/`、`.venv/`、`__pycache__/`

### 0.3 提交历史预期形态

```
* chore: 初始化仓库（uv 工程骨架与项目文档）      ← m1 之前
* feat: ...
* ...（M1 共 8 条）
* tag: m1                                          ← Gate-M1 全绿后推送
* feat: ...（M2 共 9 条）
* tag: m2
* ...（M3 共 9 条）
* tag: m3
* ...（M4 共 5 条）
* tag: m4
```

---

## M1 — 后端骨架（认证 + CRUD + 权限 + 迁移 + 种子）

**目标**：可运行的 FastAPI 骨架，认证与全部 CRUD 接口带权限，数据库迁移 + 种子数据就位。

### Feature commits

1. **`chore: 初始化仓库（uv 工程骨架与项目文档）`**
   - `.python-version`(3.12)、`pyproject.toml`（`[project]` name=`rag_enterprise_assistant`，requires-python=`>=3.11,<3.13`；deps：fastapi、uvicorn、sqlalchemy、psycopg2-binary、alembic、pydantic-settings、pyjwt、bcrypt、python-multipart、pypdf、python-docx、chromadb、ollama、openai、httpx；`[dependency-groups]` dev：pytest、ruff；ruff 行宽 100；pytest 指向 `tests/`）、`.gitignore`（勿忽略 uv.lock）、`LICENSE`(MIT)、`uv.lock`
   - 本条 commit 时 CLAUDE.md 与 docs/ 已在工作区，一并提交

2. **`feat: FastAPI 应用工厂、配置管理与健康检查`**
   - `app/core/config.py`（Pydantic Settings，SECRET_KEY 固定开发默认值；Ollama 调优默认值 `OLLAMA_THINK=true`、`OLLAMA_NUM_CTX=8192`，见 architecture §4）、`app/db.py`、`app/main.py`（create_app 工厂、`GET /health`、`/docs`）

3. **`feat: PostgreSQL compose 服务与测试库初始化`**
   - `docker-compose.yml`（仅 db：postgres:16、5432、volume、healthcheck、挂载 `docker/initdb/init.sql`）、`docker/initdb/init.sql`（建 `rag_enterprise_test`）

4. **`feat: SQLAlchemy 数据模型与 Alembic 初始迁移`**
   - `app/models/`（users、knowledge_bases、kb_members、documents、chat_sessions、chat_messages，字段见 architecture §5）
   - `alembic.ini` + `alembic/` 首次迁移；本机 `uv run alembic upgrade head` 通过

5. **`feat: bcrypt 密码与 JWT 认证依赖`**
   - `app/core/security.py`：bcrypt(12)、JWT 签发/校验、`login_required`/`admin_required`；**login_required 内校验 user.status，禁用即 401**

6. **`feat: 登录与用户管理接口`**
   - `app/api/routes/auth.py`（POST `/api/auth/login`、GET `/api/auth/me`；status=0 拒绝登录）
   - `app/api/routes/users.py`（admin：分页列表/创建/改密/禁用）
   - 对应 `app/schemas/`

7. **`feat: 知识库 CRUD 与成员授权接口`**
   - `app/api/routes/knowledge_bases.py`：GET 列表（admin 全部 / user 仅成员）、POST/PUT/DELETE（admin；**删除实现 DB 级级联：documents 记录、uploads 物理文件、sessions、messages；Chroma 清理留接口 try/except 容忍 collection 不存在，M2 接通**）、members 子路由（GET/POST/DELETE）

8. **`feat: 文档上传、列表与删除（暂不向量化）`**
   - `app/api/routes/documents.py`：multipart 上传（类型白名单 txt/pdf/md/docx、50MB 限制、uuid stored_name 落盘）、列表（含 status 供轮询）、GET/DELETE；**M1 阶段 status 恒为 pending，不接向量化**

9. **`feat: 管理端统计接口`**
   - `app/api/routes/stats.py`：GET `/api/stats/dashboard` → `{users,kbs,documents,messages, trend:[{date,count}]}` 近 7 天（admin）

10. **`feat: 种子脚本（双账号、按文件夹三库、12 份文档）`**
    - `scripts/seed.py`（幂等：同 kb 同 filename 跳过）：`admin/admin123`、`user/user123`；**按 `seed_docs/` 一级子文件夹各建一个知识库**（文件夹名 = 库名：公司规章制度 / 技术开发规范 / 产品使用指南），各库只导入本文件夹文档；两用户均入全部库成员；12 份文档入库（M1 状态 pending）
    - 本地直跑若 `.env` 指向 `host.docker.internal`，需覆盖 `OLLAMA_BASE_URL=http://localhost:11434`；清库可用 `scripts/wipe_documents.py`（删文档记录 + uploads + Chroma）

11. **`test: 认证、权限矩阵与文档接口测试`**
    - `tests/conftest.py`（测试库 fixture：alembic upgrade head；应用工厂）、`test_auth.py`（登录/过期/错误密码/**禁用用户 401**）、`test_knowledge_base.py`（**权限矩阵**：非成员 403/404、admin 全过、授权后可见）、`test_documents.py`（上传/类型/超限/删除）、`test_stats.py`

### Gate-M1

```bash
uv sync && uv run ruff check .                # 0 error
docker compose up -d db && uv run alembic upgrade head
uv run python scripts/seed.py                 # 3 个知识库 × 各 4 份 = 12
uv run uvicorn app.main:app --reload          # 另开终端
curl -s localhost:8000/health                 # {"status":"ok"}
curl -s -X POST localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}'   # 返回 token
# 用 token 调 GET /api/knowledge-bases、POST 上传一个文档 → 200/201
uv run pytest -q                              # 全部通过
find seed_docs -type f | wc -l                # = 12
```

**Git 动作**：全绿 → `git tag -a m1 -m "Gate-M1 通过：认证+CRUD+权限+迁移+种子"` → `git push -u origin main m1`

---

## M2 — RAG 管线（异步入库 + 阈值检索 + SSE + 会话 + 评估）

**目标**：文档异步向量化、带阈值的向量检索、SSE 流式问答、多会话、评估脚本。

### Feature commits

1. **`feat: 文档解析器与递归分块器（含四格式测试）`**
   - `services/parser.py`（txt/md/pdf/docx；空内容抛业务异常）、`services/chunker.py`（`\n\n`→`\n`→`。`→滑窗，500/50，产出 chunk_index）
   - `tests/test_parser.py`：四格式各 ≥1 例，**fixture 用 seed_docs/ 真实 pdf/docx**；断言非空、关键标题命中

2. **`feat: LLM Provider 抽象与双实现`**
   - `services/llm/base.py`（Protocol：embed / chat_stream——后者逐 token yield **`("thinking"|"delta", text)`** 元组）、`ollama_provider.py`（转发 `message.thinking`，`think`/`num_ctx` 读配置）、`openai_compat_provider.py`（转发 `reasoning_content`）、工厂（按 LLM_PROVIDER）；RAG 提示词（仅依据资料/无依据如实/中文/简洁）

3. **`feat: Chroma 向量服务（cosine 空间与阈值检索）`**
   - `services/vector.py`：**建 collection 必须 `metadata={"hnsw:space":"cosine"}`**（正确性要求）；`add_chunks`（id=`doc_{id}_chunk_{i}`，metadata 含 file_name/chunk_index）、`delete_doc`、`delete_collection`、`search`（relevance=1-distance，低于阈值丢弃）

4. **`feat: 异步入库编排与死状态清理`**
   - `services/ingest.py`（BackgroundTasks；pending→processing→completed|failed；Ollama 不可达给「无法连接 Ollama」；异常写 error_msg）
   - documents 上传改为：落盘→建 pending→立即返回→后台处理
   - `app/main.py` lifespan：**startup 把遗留 pending/processing 置 failed**（"服务重启导致任务中断，请重新上传"）
   - KB 删除的 Chroma 级联在本条接通（M1 留的 try/except 调 `delete_collection`）
   - `scripts/seed.py` 增强：对 pending 种子触发入库、completed 跳过（幂等）

5. **`feat: SSE 流式问答接口`**
   - `POST /api/chat/ask`：权限校验→带阈值检索→先推 `sources`→`chat_stream` 逐 token 推 `thinking`×N（启用思考时）与 `delta`×N→落库→`done`；**禁止整段生成切片伪装**；thinking 仅流式展示不落库；零命中 `sources:[]`+兜底文案；异常 `error` 事件；无权限 JSON 401/403（不进 SSE）

6. **`feat: 多会话管理与对话历史接口`**
   - sessions：GET/POST（`?kb_id=`）、PATCH 重命名、DELETE 级联消息；messages GET 升序；无 session_id 自动建会话（title=问题前 20 字）；`GET /chat/history` 分页 + admin 按 user_id 过滤

7. **`test: SSE 事件顺序、RAG mock 与级联删除测试`**
   - `tests/test_chat.py`：MockProvider 固定输出（含 thinking 产出）；断言事件顺序 sources→thinking→delta→done、逐段到达、零命中兜底、非成员 403、消息落库、会话级联删除

8. **`feat: RAG 检索评估脚本`**
   - `scripts/eval_rag.py`：**15 条 golden 问答对**（按 seed_docs 12 份三主题域出题：问题+期望命中文件名）；指标 Hit@1、Hit@4、MRR、平均检索延迟；产出 `eval_report.md`（本地连 Ollama，不进 CI）

9. **`docs: 提交 RAG 评估报告`**
   - 本地跑通 `uv run python scripts/eval_rag.py`，把生成的 `eval_report.md` 提交入库（**Hit@4 ≥ 0.8 不达标就调题/查检索，不得放水**）

### Gate-M2

```bash
uv run ruff check . && uv run pytest -q       # 全绿（含 test_parser）
uv run uvicorn app.main:app --reload
# 1) 重跑 uv run python scripts/seed.py（把 pending 种子向量化；本地需 OLLAMA_BASE_URL=http://localhost:11434）
#    或 admin 上传 → 立即 pending；轮询 GET /api/documents/{id} 直到 completed（记录耗时）
# 2) user 账号 SSE 问答：
#    curl -N -X POST localhost:8000/api/chat/ask -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
#      -d '{"question":"员工请假需要提前几天申请？","kb_id":1}'
#    确认：sources→thinking×N（启用思考时）→delta×N→done；delta/thinking 逐段到达（非一次性）；sources 含真实文件名与 score
# 3) 问知识库里没有的问题 → sources 空 + 兜底文案
# 4) 非成员访问 → 403/404
# 5) uv run python scripts/eval_rag.py → eval_report.md，Hit@4 ≥ 0.8
```

**Git 动作**：全绿 → `git tag -a m2 -m "Gate-M2 通过：RAG管线+SSE+会话+评估"` → `git push origin main m2`

---

## M3 — 前端（纯静态 hash SPA）

**目标**：完整可用的前端：登录、流式对话+引用卡片、历史、管理端四页；截图就位。

### Feature commits

1. **`feat: 单页骨架、hash 路由与主题样式`**
   - `static/index.html`、`js/router.js`（`#/login|#/chat|#/history|#/admin|#/admin/kb|#/admin/docs|#/admin/users`；未登录跳 login；非 admin 访问 admin 弹回 `#/chat`；切换 document.title）、`js/app.js`、`css/style.css`（CSS 变量主题、组件类、≥900px 双栏/以下单栏）

2. **`feat: fetch 封装与 SSE 流解析器`**
   - `js/api.js`：自动带 token、**读流前先检查状态码**（非 200 解析 JSON 错误并 toast）、401 跳登录、统一 toast；SSE 解析器（fetch+ReadableStream 解析 `event:`/`data:` 帧）

3. **`feat: 登录页`**
   - `js/pages/login.js`：登录表单 → 存 token → 跳转

4. **`feat: 对话页（会话栏、流式渲染与引用卡片）`**
   - `js/pages/chat.js`（可拆 components/）：左：会话列表/新建/重命名/删除/切换；中：提问→**引用卡片**（文件名、snippet、score 百分比）→**思考框**（限高 180px、内部滚动、details 折叠、贴底跟随，与回答气泡分离）→ delta 打字机追加（**rAF 批量刷新**，避免逐 token 强制布局掉帧；思考阶段显示「正在思考…」占位）→done 刷新会话；顶：kb 选择器（仅有权限的）；零命中兜底正常展示

5. **`feat: 对话历史页`**
   - `js/pages/history.js`：分页；admin 多用户过滤下拉

6. **`feat: 管理端看板与 SVG 七日趋势图`**
   - `js/pages/admin.js`：4 统计卡片 + **手写 SVG 柱状图**（近 7 天问答趋势，含坐标轴与悬停 title；无图表库）

7. **`feat: 管理端知识库与成员管理页`**
   - `js/pages/admin_kb.js`：KB CRUD（删除二次确认并提示级联范围）+ 成员勾选授权弹窗（授权/移除后 user 端列表即时变化）

8. **`feat: 管理端文档与用户管理页`**
   - `js/pages/admin_docs.js`：按 kb 上传、列表、**pending/processing 每 2s 轮询**、failed 显示 error_msg 可重传、删除
   - `js/pages/admin_users.js`：用户 CRUD、角色修改、重置密码

9. **`feat: FastAPI 挂载静态资源`**
   - `app/main.py`：`GET /` 返回 index.html、静态 no-cache；`/docs` 仍可用

10. **`docs: 录入四张验收截图`**
    - `docs/screenshots/`：① 登录 ② 对话流+引用卡片+思考框 ③ 管理看板 SVG ④ 文档状态轮询（Gate-M3 走查时同步截图）

### Gate-M3（浏览器人工走查，逐条记录）

```bash
uv run ruff check . && uv run pytest -q       # 仍全绿
uv run uvicorn app.main:app --reload
# http://localhost:8000/ 人工走查：
# [ ] 登录 admin → 看板数字与近7天柱状图正确渲染（SVG，无图表库）
# [ ] 上传文档 → 列表状态从 pending 变 completed
# [ ] user 登录 → 看不到管理菜单；提问出现流式打字机 + 引用卡片
# [ ] 思考过程独立成框（限高 180px、内部滚动、可折叠），与正式回答分开展示
# [ ] 新建/重命名/删除会话，刷新后状态保持
# [ ] admin 授权/移除成员后，user 端知识库列表即时变化
# [ ] user 直接改 URL 访问 #/admin/* → 被弹回 #/chat
# [ ] 401（删 token）后任意操作 → 跳回登录页
# [ ] 截图 4 张已存入 docs/screenshots/
```

**Git 动作**：全绿 → `git tag -a m3 -m "Gate-M3 通过：纯静态前端全功能"` → `git push origin main m3`

---

## M4 — 工程化（Docker + CI + README + 收尾）

**目标**：一键部署、CI 就绪、README 门面完整、总验收通过、交付 GitHub。

### Feature commits

1. **`feat: Docker 镜像与完整 compose 编排`**
   - `Dockerfile`（python:3.12-slim + uv：先拷 pyproject/uv.lock → `uv sync --frozen --no-dev` 层缓存，再拷源码；非 root；uvicorn 8000）
   - `docker-compose.yml` 完整版：+api（build、depends_on db healthy、挂 chroma_data/uploads volume、`.env` 注入、`extra_hosts: host.docker.internal:host-gateway`）
   - `.env.example` 按 architecture §4 全量注释（`OLLAMA_BASE_URL=http://host.docker.internal:11434`）

2. **`ci: GitHub Actions（ruff + pytest + postgres service）`**
   - `.github/workflows/ci.yml`：push/PR → `astral-sh/setup-uv` → `uv sync --frozen` → `uv run ruff check .` → `uv run pytest`（postgres:16 service + init 建测试库）；不依赖 Ollama（RAG 全 mock）

3. **`docs: README（架构图、双启动路径、配置表、截图、评估摘要）`**
   - 中文门面：简介 + **mermaid 架构图**（浏览器→FastAPI→PG/Chroma/Ollama）+ 功能特性（含 4 项增强，插 **4 张真实截图**）+ 快速开始两条路径（uv 本地 / Docker 一键）+ 配置表 + 双模 LLM 切换说明（OpenAI 兼容真实示例）+ `eval_report.md` 结果摘要 + 技术栈/目录/`/docs` 入口/License

4. **`docs: 补齐交付文档与截图终稿`**
   - 按 §1 总验收清单逐项复核的收尾修正（`.env.example` 复核、`.gitignore` 复核、截图替换为最终版等；无修正则本条并入上一条）

5. **`fix: Gate-M4 修复项`（如有）**
   - Gate-M4 暴露的问题逐项修复；没有则跳过本条

### Gate-M4

```bash
uv run ruff check . && uv run pytest -q
docker compose down -v && docker compose up --build -d
curl -s localhost:8000/health                    # ok
curl -s localhost:8000/                          # index.html
curl -s localhost:8000/docs                      # Swagger 200
# 容器内完成：seed → 上传 → 流式问答全链路（Ollama 在宿主机）
git log --oneline                                # 中文、按里程碑分批
git status                                       # 干净，无 .env/uploads/chroma_data/.venv
docker compose down
```

**Git 动作**：全绿 → `git tag -a m4 -m "Gate-M4 通过：Docker+CI+README，交付"` → `git push origin main m4`

---

## 1. 交付前总验收（全部勾选才算完成）

- [ ] 四个 Gate 全过；**远端可见 4 个 tag（m1–m4）与分批中文 commit**
- [ ] `uv run ruff check .` 0 error；`uv run pytest` 全绿（含 test_parser 四格式）；GitHub Actions 可跑通
- [ ] 全新 clone 按 README 快速开始 30 分钟跑通问答链路（uv 与 Docker 两条路径验证；`uv.lock` 在库）
- [ ] bcrypt 密码；无 MD5；`.env` 与真实 API key 未入库
- [ ] 权限矩阵自动化测试；非成员被后端拒绝（非前端隐藏）；禁用用户 401 有测试
- [ ] SSE 真流式逐 token；thinking 与回答分事件传输（思考不落库）；引用卡片有 score 与 snippet；score 来自 cosine 换算
- [ ] 入库全异步、失败可见 error_msg；重启无 processing 死状态
- [ ] KB 删除级联完整（记录/文件/向量/会话）
- [ ] 看板 SVG 无第三方图表库；前端零 npm、零 CDN
- [ ] `seed_docs/` 12 份四格式齐全；`eval_report.md` 在库且 **Hit@4 ≥ 0.8**
- [ ] README 含 mermaid 架构图、双模 LLM 说明、两条启动路径、**4 张真实截图**
- [ ] 已推送 GitHub，commit 中文、按里程碑分批

## 2. 阻塞与风险（与 CLAUDE.md 一致）

| 情形 | 处置 |
|---|---|
| 远端 URL 缺失 / seed_docs ≠ 12 / 环境不满足 | 停下询问，不绕过 |
| Gate 失败 | 修复 → commit → 重跑，全绿前不 push |
| Ollama 未启动/模型缺 | 报错提示 `ollama pull ...`，不静默降级、不换模型 |
| Hit@4 < 0.8 | 调 golden 题或查检索实现，不得放水 |
| 如需切换云端模型 | 默认本地 Ollama 即可完整运行；openai_compat 填任意 OpenAI 兼容端点的 base_url/key/model 即可（示例：OpenAI 官方 + `gpt-4o-mini`） |
| 文档未覆盖的取舍 | 最小范围实现 + 报告说明，不扩大范围 |
