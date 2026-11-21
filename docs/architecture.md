# rag_enterprise_assistant 架构设计

> 本文是项目的**设计基准**：做什么、做成长什么样以本文为准；执行顺序与提交节奏见 `docs/plan.md`。
> 文档自包含，不依赖任何外部蓝本。

---

## 1. 系统总览

企业级知识库问答系统（RAG）：知识库管理 → 文档异步入库（解析/分块/向量化）→ 带权限的向量检索 → SSE 流式问答 + 引用溯源 → 多会话管理 → 管理端看板。

```mermaid
flowchart LR
    B[浏览器 static/ 纯静态 SPA] -->|HTTP / SSE| F[FastAPI app/]
    F --> PG[(PostgreSQL<br/>业务数据)]
    F --> CH[(Chroma 内嵌<br/>kb_id 独立 collection)]
    F --> O[Ollama 本地<br/>qwen3:4b / qwen3-embedding:4b]
    F -. LLM_PROVIDER=openai_compat .-> API[OpenAI 兼容 API<br/>如 OpenAI 官方]
```

---

## 2. 技术定稿（已确认，不得擅自更改）

| 维度 | 决策 |
|---|---|
| 执行环境 | Windows 11 + Git Bash；Python 固定 3.12；环境管理**只用 uv**（`.python-version` + `uv sync` / `uv run`，`uv.lock` 入库）；禁用 `python3`/裸 `python`/conda |
| 前端 | 纯静态 HTML/JS/CSS，单页 **hash 路由 + ES Modules**，手写 CSS；**无构建、无 CDN、无 npm 依赖** |
| 后端 | **FastAPI** + SQLAlchemy 2.0 + Pydantic + Alembic，Swagger 自动生成（`/docs`） |
| 关系库 | **PostgreSQL 16**（docker-compose 内置；首次启动执行 `docker/initdb/init.sql` 建测试库 `rag_enterprise_test`） |
| 向量库 | **Chroma**（Python 内嵌进程，持久化目录 `chroma_data/`）；每库一个 collection（`kb_{id}`）；**建 collection 必须 `metadata={"hnsw:space":"cosine"}`** |
| LLM 接入 | **双模 Provider 抽象**：默认本地 Ollama；可切任意 OpenAI 兼容 API（示例：OpenAI 官方） |
| 本地模型 | LLM = `qwen3:4b`，嵌入 = `qwen3-embedding:4b`（需求方指定，可 env 覆盖，**不得降级**） |
| 检索 | 向量检索 + 分数阈值过滤 + 可配置 top_k；零命中返回兜底文案 |
| 入库 | **FastAPI BackgroundTasks** 异步；`status` 状态机 + 前端轮询；**startup 清理死状态** |
| 问答 | **SSE 流式**（POST + Fetch ReadableStream 解析）+ 引用溯源卡片 + **思考过程分框展示** |
| 密码 | **bcrypt**（work factor 12；严禁 MD5/SHA1） |
| 权限 | JWT（24h）+ admin/user 双角色 + **知识库成员级授权**（kb_members）；禁用用户存量 token 立即 401 |
| 测试 | pytest（接口/权限/RAG mock/四格式解析）+ 本地 RAG 评估脚本（不进 CI） |
| 部署 | Docker Compose（postgres + api）+ GitHub Actions CI（ruff + pytest + postgres service） |
| 图表 | 管理端看板手写 **SVG/CSS**，不引图表库 |
| 交付 | GitHub 公开仓库 + 4 张真实截图 + 入库的 `eval_report.md` |

### 明确不做（防蔓延）

WebSocket、前端测试框架、前端构建、Kubernetes、多轮上下文改写（每问独立检索）、rerank、BM25 混合检索。

---

## 3. 目录结构

```
rag_enterprise_assistant/
├── CLAUDE.md                   # 执行终端入口
├── docs/
│   ├── plan.md                 # 里程碑 + feature commit 清单 + Gate
│   └── architecture.md         # 本文
├── README.md                   # 中文门面：mermaid 架构图、快速开始、配置表、真实截图
├── LICENSE                     # MIT
├── .gitignore                  # .env / .venv / __pycache__ / uploads/ / chroma_data/ / *.db / .idea
├── .python-version             # 3.12
├── uv.lock                     # 入库
├── .env.example                # 全部环境变量及默认值（含 OpenAI 兼容真实示例）
├── pyproject.toml              # [project] + [dependency-groups] dev + ruff(行宽100) + pytest(tests/)
├── docker-compose.yml          # db + api
├── docker/initdb/init.sql      # 首次启动建测试库
├── Dockerfile                  # python:3.12-slim + uv
├── .github/workflows/ci.yml    # setup-uv → ruff → pytest
├── alembic.ini / alembic/
├── docs/screenshots/           # 4 张真实截图（入库）
├── eval_report.md              # RAG 评估报告（入库）
├── app/
│   ├── main.py                 # create_app 工厂：路由、静态挂载、CORS、lifespan 死状态清理
│   ├── core/
│   │   ├── config.py           # Pydantic Settings
│   │   └── security.py         # bcrypt、JWT、login_required / admin_required
│   ├── db.py                   # engine/session、get_db
│   ├── models/                 # SQLAlchemy 模型
│   ├── schemas/                # Pydantic 请求/响应
│   ├── api/routes/             # auth / users / knowledge_bases / documents / chat / stats
│   └── services/
│       ├── llm/
│       │   ├── base.py         # LLMProvider Protocol
│       │   ├── ollama_provider.py
│       │   └── openai_compat_provider.py
│       ├── vector.py           # Chroma：入库/删除/阈值检索（cosine）
│       ├── parser.py           # txt/md/pdf/docx
│       ├── chunker.py          # 递归分隔符 500/50
│       └── ingest.py           # BackgroundTasks 编排 + 状态机
├── static/                     # 纯静态前端
│   ├── index.html
│   ├── css/style.css
│   └── js/  (api.js, router.js, app.js, pages/*.js, components/*.js)
├── seed_docs/                  # 12 份示例文档（需求方已放入，三个子文件夹）
│   ├── 公司规章制度/            # 4 份
│   ├── 技术开发规范/            # 4 份
│   └── 产品使用指南/            # 4 份
├── scripts/
│   ├── seed.py                 # 幂等种子（admin/user/知识库/12 份文档）
│   └── eval_rag.py             # 15 条 golden 问答对 → eval_report.md
└── tests/
    ├── conftest.py             # app 工厂、测试库 fixture、MockProvider
    ├── test_auth.py            # 含禁用用户 401
    ├── test_knowledge_base.py  # 权限矩阵
    ├── test_documents.py
    ├── test_parser.py          # 四格式，fixture 用 seed_docs 真实文件
    ├── test_chat.py            # SSE 事件顺序 + RAG mock
    └── test_stats.py
```

**关键原则**：`chroma_data/`、`uploads/`、`.env`、`.venv/` 永不入库；`seed_docs/`、`docs/screenshots/`、`eval_report.md`、`uv.lock` 入库。

---

## 4. 配置与环境变量（`app/core/config.py`，`.env.example` 全量列出）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-change-me`（固定开发值） | 随机值会导致重启全员掉线；生产必换 |
| `DATABASE_URL` | `postgresql+psycopg2://rag:rag123@localhost:5432/rag_enterprise` | 测试库为同地址 `rag_enterprise_test` |
| `LLM_PROVIDER` | `ollama` | `ollama` \| `openai_compat` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | compose 内用 `http://host.docker.internal:11434` |
| `OLLAMA_LLM_MODEL` | `qwen3:4b` | |
| `OLLAMA_EMBED_MODEL` | `qwen3-embedding:4b` | |
| `OLLAMA_THINK` | `true` | qwen3 思考模式：true 时思考内容以 SSE `thinking` 事件流式转发（前端分框展示）；false 跳过思考、总耗时更短 |
| `OLLAMA_NUM_CTX` | `8192` | 上下文窗口（嵌入侧固定 4096）。**必须显式限制**：否则 Ollama 按模型声明的 262144 满配预分配 KV cache（约 40GB），挤爆 16GB 显存导致模型 CPU/GPU 混跑（实测 67% CPU、prompt 评估 ~30s）；限 8k 后 KV cache 约 1.3GB，模型 **100% GPU** 驻留 |
| `OPENAI_COMPAT_BASE_URL` | `https://api.openai.com/v1` | LLM_PROVIDER=openai_compat 时使用；可换任意 OpenAI 兼容端点 |
| `OPENAI_COMPAT_API_KEY` | 空 | 同上；**绝不提交真实 key** |
| `OPENAI_COMPAT_MODEL` | `gpt-4o-mini` | 同上；按所选端点填真实模型名 |
| `RETRIEVAL_TOP_K` | `4` | |
| `RETRIEVAL_SCORE_THRESHOLD` | `0.3` | cosine 空间下 relevance = 1 - distance，低于阈值丢弃 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `500` / `50` | |
| `CHROMA_PERSIST_DIR` | `chroma_data` | gitignore |
| `UPLOAD_DIR` | `uploads` | gitignore |
| `UPLOAD_MAX_MB` | `50` | |
| `JWT_EXPIRE_HOURS` | `24` | |

**Provider 抽象**（`services/llm/base.py`）：

```python
class LLMProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def chat_stream(self, system: str, question: str, context: str) -> Iterator[tuple[str, str]]: ...
```

- `chat_stream` 逐 token yield **`("thinking" | "delta", text)`** 元组：`thinking` = 模型思考过程（未启用思考时不产出），`delta` = 正式回答；Ollama 取 `message.thinking`，OpenAI 兼容端点取 `reasoning_content`
- `OllamaProvider`：ollama 官方 SDK（`think` / `options.num_ctx` 读配置）；`OpenAICompatProvider`：openai 官方 SDK（`base_url` 指向任意 OpenAI 兼容端点，示例为 OpenAI 官方）
- 工厂按 `LLM_PROVIDER` 实例化；**测试通过依赖注入替换为 MockProvider**
- RAG 提示词：仅依据参考资料作答、无依据如实说明、中文、简洁专业

---

## 5. 数据模型

| 表 | 关键字段 | 说明 |
|---|---|---|
| `users` | id, username(uniq), password_hash, nickname, role(`admin`/`user`), status(1/0), created_at | bcrypt |
| `knowledge_bases` | id, name, description, created_by→users, status, created_at | |
| `kb_members` | id, kb_id, user_id, created_at；UNIQUE(kb_id,user_id) | 用户可见/可问某 KB ⇔ 是 admin 或在表中 |
| `documents` | id, kb_id, filename, stored_name(uuid), file_type, file_size, status(`pending`/`processing`/`completed`/`failed`), error_msg, chunk_count, created_by, created_at, updated_at | 路径 `uploads/{stored_name}` |
| `chat_sessions` | id, user_id, kb_id, title, created_at, updated_at | title 默认取首问前 20 字 |
| `chat_messages` | id, session_id, user_id, kb_id, question, answer, sources(JSON), created_at | sources 含 file_name/chunk_index/score/snippet |

### 权限规则（必须有测试覆盖）

- `admin`：全部资源；管理成员、上传/删文档、看全部对话历史
- `user`：只能列出/问答「自己是成员」的知识库；只能看自己的会话与消息
- 所有涉及 kb 的读写接口后端强校验，**不能只靠前端隐藏菜单**
- **禁用用户（status=0）**：`login_required` 每次查库校验 status，存量 JWT 立即 401

### 删除级联策略（定稿）

- `DELETE /knowledge-bases/{id}` = **级联物理删除**：documents 记录 → uploads 物理文件 → Chroma `kb_{id}` collection → 该库全部 chat_sessions 与 chat_messages；任一步失败整体回滚
- `DELETE /documents/{id}`：记录 + 物理文件 + Chroma 分块
- `DELETE /users/{id}` = 禁用（status=0），不物理删

### 迁移与测试库

- Alembic 管理全部表；`alembic upgrade head` 是每个相关 Gate 的项
- `docker/initdb/init.sql` 首次启动建 `rag_enterprise_test`；`conftest.py` 在测试库跑 `alembic upgrade head`（顺带验证迁移）

---

## 6. API 设计（前缀 `/api`；除登录外全部 `Authorization: Bearer <token>`）

| 方法 | 路径 | 角色 | 说明 |
|---|---|---|---|
| POST | `/auth/login` | 公开 | `{username,password}` → `{token,user}`；status=0 拒绝 |
| GET | `/auth/me` | 登录 | 当前用户（校验 status） |
| GET/POST | `/users` | admin | 列表(分页)/创建 |
| PUT/DELETE | `/users/{id}` | admin | 修改(含重置密码)/禁用 |
| GET | `/knowledge-bases` | 登录 | admin 全部；user 仅成员可见 |
| POST/PUT | `/knowledge-bases[/{id}]` | admin | CRUD |
| DELETE | `/knowledge-bases/{id}` | admin | 级联物理删除 |
| GET/POST/DELETE | `/knowledge-bases/{id}/members[/{user_id}]` | admin | 成员授权 |
| GET | `/documents?kb_id=` | 按 kb 权限 | 列表（含 status，供轮询） |
| POST | `/documents` | admin | multipart `kb_id`+`file`；立即返回 `status=pending` |
| GET/DELETE | `/documents/{id}` | 按 kb 权限 | 状态查询 / 删除（同步清 Chroma + 文件） |
| POST | `/chat/ask` | 按 kb 权限 | **SSE 流式**，body `{question,kb_id,session_id?}`；无 session_id 自动创建 |
| GET/POST | `/chat/sessions?kb_id=` | 登录 | 会话列表（updated_at 倒序）/ 新建 |
| PATCH/DELETE | `/chat/sessions/{id}` | 归属/admin | 重命名 / 删除（级联删消息） |
| GET | `/chat/sessions/{id}/messages` | 归属/admin | 消息升序 |
| GET | `/chat/history?page=&user_id=` | 登录 | 分页；admin 可看全部并按用户过滤 |
| GET | `/stats/dashboard` | admin | `{users,kbs,documents,messages, trend:[{date,count}]}` 近 7 天 |

### SSE 事件协议（`Content-Type: text/event-stream`）

```
event: sources
data: {"sources":[{"file_name":"员工请假管理办法.md","chunk_index":3,"score":0.67,"snippet":"..."}]}

event: thinking
data: {"content":"首先"}

...（thinking×N，可选，模型启用思考时）

event: delta
data: {"content":"根据"}

...（delta×N）

event: done
data: {"session_id":"...","message_id":123}

event: error
data: {"message":"问答服务异常: ..."}
```

- 顺序固定：`sources` → `thinking`×N（可选） → `delta`×N → `done`；**零命中**：`sources: []` + 兜底文案「未找到相关内容，请换个问法」，不算错误
- `thinking` 为模型思考过程，仅流式展示、**不落库**；正式回答（`delta` 拼接结果）落库于 `chat_messages.answer`
- 回答完成（`done`）后才落库 `chat_messages`
- `EventSource` 不支持 POST → 前端必须 **fetch + ReadableStream** 手动解析（M3 验收项）
- 无权限时不进 SSE，直接 JSON 401/403；前端 api.js **读流前先检查响应状态码**

### 入库状态机

`pending → processing → completed | failed`；失败必写 `error_msg`，前端可见可重传。
**死状态清理**：lifespan startup 时把遗留 `pending`/`processing` 置 `failed`（`error_msg = "服务重启导致任务中断，请重新上传"`）——BackgroundTasks 不持久，不清理会永远转圈。

---

## 7. RAG 管线

1. **parser.py**：txt/md（utf-8）、pdf（pypdf）、docx（python-docx）；解析为空抛业务异常
2. **chunker.py**：递归分隔符（`\n\n` → `\n` → `。` → 字符滑窗），500/50，产出 `chunk_index`
3. **vector.py**（Chroma 封装）：
   - `add_chunks(kb_id, ...)` / `delete_doc(kb_id, doc_id)` / `delete_collection(kb_id)` / `search(kb_id, query, top_k, threshold)`
   - **建 collection 必须 `metadata={"hnsw:space":"cosine"}`**——否则 `1-distance` 阈值语义失效（L2 下可为负、无上界），这是正确性要求
   - 分块 id 约定 `doc_{doc_id}_chunk_{i}`；metadata：doc_id / file_name / chunk_index
4. **ingest.py**：BackgroundTasks 触发；Ollama 不可达给可读错误（「无法连接 Ollama」）；异常写 `error_msg`
5. **chat/ask**：权限校验 → 检索（带阈值）→ 推 `sources` → Provider `chat_stream` 逐 token 推 `thinking`×N（启用思考时）与 `delta`×N → 落库 → 推 `done`；**禁止先整段生成再切片伪装流式**

---

## 8. 前端架构（纯静态 hash SPA）

| 路由 | 页面 | 要点 |
|---|---|---|
| `#/login` | login.js | 登录表单 |
| `#/chat` | chat.js（核心） | 左：会话栏 CRUD/切换；中：提问 → 引用卡片（文件名/snippet/score%）→ **思考框**（限高 180px、内部滚动、details 折叠、流式贴底跟随，与回答气泡分离）→ delta 打字机 → done 刷新会话；顶：kb 选择器（仅有权限的） |
| `#/history` | history.js | 分页历史；admin 多用户过滤下拉 |
| `#/admin` | admin.js | 4 统计卡片 + **手写 SVG 柱状图**（近 7 天，含坐标轴与悬停 title） |
| `#/admin/kb` | admin_kb.js | KB CRUD（删除二次确认提示级联范围）+ 成员勾选弹窗 |
| `#/admin/docs` | admin_docs.js | 上传/列表/**2s 轮询**（pending/processing），failed 显示 error_msg 可重传 |
| `#/admin/users` | admin_users.js | 用户 CRUD、角色、重置密码 |

- `router.js`：手写 hash 路由；未登录跳 login；**非 admin 访问 admin 路由弹回 `#/chat`**；切换更新 `document.title`
- `api.js`：fetch 封装（自动带 token、401 跳登录、统一 toast）+ **SSE 解析器**（解析 `event:`/`data:` 帧）
- 流式渲染：thinking/delta 按 **requestAnimationFrame 批量刷新**（每帧至多一次 innerHTML + 滚动），避免逐 token 强制布局掉帧；思考阶段回答区显示「正在思考…」占位；思考框贴底跟随仅在用户距底 48px 内生效（上滑回看不打断）
- 思考过程**仅流式展示不落库**；本会话内存保留，重开会话仅显示问答与引用
- `style.css`：CSS 变量主题 + 组件类（按钮/输入/表格/弹窗/toast/气泡/引用卡片）；≥900px 双栏，以下单栏
- FastAPI 挂 `static/`：`GET /` 返回 index.html，静态 no-cache；`/docs` 仍可用

---

## 9. 测试与评估

- **conftest.py**：独立测试库 `rag_enterprise_test`（alembic 建表）、应用工厂、MockProvider（固定输出）
- 覆盖：登录/过期/错误密码/禁用 401；**权限矩阵**（非成员 403/404、admin 全通过、授权后可见）；上传/类型/超限/删除；**四格式解析**（fixture 用 seed_docs 真实文件）；**SSE 事件顺序** sources→thinking→delta→done（MockProvider 产出 thinking）、零命中兜底、消息落库、会话级联删除；stats
- CI 不依赖 Ollama（RAG 全 mock）；`scripts/eval_rag.py` 本地跑，**不进 CI**
- **eval**：15 条 golden 问答对（问题 + 期望命中文件，按 seed_docs 12 份三主题域出题）；指标 Hit@1、Hit@4、MRR、平均检索延迟；产出 `eval_report.md` 入库，**Hit@4 ≥ 0.8**

---

## 10. 部署与 CI

- **Dockerfile**：`python:3.12-slim` + uv（`COPY --from=ghcr.io/astral-sh/uv`，先拷 `pyproject.toml`/`uv.lock` → `uv sync --frozen --no-dev` 利用层缓存），非 root，`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **compose**：db（postgres:16 + healthcheck + volume + initdb）+ api（depends_on db healthy，挂 `chroma_data`/`uploads` volume，`.env` 注入，`extra_hosts: host.docker.internal:host-gateway`）；`down` 不删数据，`down -v` 才清
- **CI**（`.github/workflows/ci.yml`）：push/PR → `astral-sh/setup-uv` → `uv sync --frozen` → `uv run ruff check .` → `uv run pytest`（postgres:16 service + init 建测试库）；与本机同一套 uv 写法
