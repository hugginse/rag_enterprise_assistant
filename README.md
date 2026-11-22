# rag_enterprise_assistant

企业级知识库问答系统（RAG）：知识库管理 → 文档异步入库（解析 / 分块 / 向量化）→ 带权限的向量检索 → **SSE 流式问答 + 引用溯源** → 多会话管理 → 管理端看板。前端零 npm / 零 CDN / 无构建。

## 架构

```mermaid
flowchart LR
    B[浏览器 static/ 纯静态 SPA] -->|HTTP / SSE| F[FastAPI app/]
    F --> PG[(PostgreSQL<br/>业务数据)]
    F --> CH[(Chroma 内嵌<br/>kb_id 独立 collection)]
    F --> O[Ollama 本地<br/>qwen3:4b / qwen3-embedding:4b]
    F -. LLM_PROVIDER=openai_compat .-> API[OpenAI 兼容 API<br/>如 OpenAI 官方]
```

## 功能特性

- **双角色权限**：admin / user + 知识库成员级授权；禁用用户存量 JWT 立即 401；后端强校验（非成员 403/404）
- **异步入库**：上传即 `pending`，后台 `processing → completed|failed`，失败可见 `error_msg`，重启清理死状态
- **SSE 真流式**：`sources → thinking×N → delta×N → done`，思考与回答分事件、分框展示（思考不落库）
- **引用溯源**：cosine 向量检索 + 分数阈值，引用卡片含文件名 / snippet / score%，正文依据徽章高亮
- **管理端**：看板（手写 SVG 七日趋势，无图表库）、知识库与成员、文档轮询、用户管理
- **评估**：`scripts/eval_rag.py` 15 条 golden → `eval_report.md`（Hit@4 ≥ 0.8）

### 界面预览

| 登录 | 对话流 + 引用 + 思考框 |
|---|---|
| ![登录](docs/screenshots/01-login.png) | ![对话](docs/screenshots/02-chat-stream.png) |

| 管理看板 SVG | 文档状态轮询 |
|---|---|
| ![看板](docs/screenshots/03-admin-dashboard.png) | ![文档](docs/screenshots/04-docs-status.png) |

## 快速开始

### 路径 A：uv 本地开发

**前置**：Python 3.12（仅用 uv 管理）、Docker（PostgreSQL）、本机 Ollama（`qwen3:4b`、`qwen3-embedding:4b`）

```bash
# 1. 依赖与环境
uv sync
uv run python --version          # 应为 3.12.x

# 2. 数据库
docker compose up -d db
uv run alembic upgrade head

# 3. 种子数据（admin/user、示例库、12 份文档并入库）
cp .env.example .env             # 按需修改；本地默认即可
uv run python scripts/seed.py

# 4. 启动
uv run uvicorn app.main:app --reload
# 打开 http://127.0.0.1:8000/
```

演示账号：`admin/admin123` · `user/user123`

### 路径 B：Docker 一键

**前置**：Docker Compose、宿主机 Ollama 已启动

```bash
cp .env.example .env
# 确认 .env 中：
#   OLLAMA_BASE_URL=http://host.docker.internal:11434
#   DATABASE_URL 可保持默认（compose 会覆盖为 db:5432）

docker compose up --build -d
# API: http://127.0.0.1:8000/

# 种子（在容器或宿主机二选一；宿主机需 DATABASE_URL 指向 localhost:5432）
docker compose exec api uv run python scripts/seed.py
# 或本地：uv run python scripts/seed.py
```

## 配置

完整列表见 [`.env.example`](.env.example)（与 `docs/architecture.md` §4 一致）。常用项：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-change-me` | 生产必换 |
| `DATABASE_URL` | `postgresql+psycopg2://rag:rag123@localhost:5432/rag_enterprise` | compose 内覆盖为 `db:5432` |
| `LLM_PROVIDER` | `ollama` | `ollama` \| `openai_compat` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | compose 内：`http://host.docker.internal:11434` |
| `OLLAMA_THINK` | `true` | 思考内容 SSE `thinking` 事件转发 |
| `OLLAMA_NUM_CTX` | `8192` | **必须限制**，否则 KV cache 挤爆 16GB 显存 |
| `RETRIEVAL_TOP_K` / `RETRIEVAL_SCORE_THRESHOLD` | `4` / `0.3` | cosine relevance = 1 − distance |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `500` / `50` | |
| `UPLOAD_MAX_MB` | `50` | |

### 双模 LLM 切换

默认本地 Ollama，开箱即用。切换任意 OpenAI 兼容端点（示例为 OpenAI 官方）：

```env
LLM_PROVIDER=openai_compat
OPENAI_COMPAT_BASE_URL=https://api.openai.com/v1
OPENAI_COMPAT_API_KEY=sk-...        # 绝不提交真实 key
OPENAI_COMPAT_MODEL=gpt-4o-mini
```

## RAG 评估摘要

`uv run python scripts/eval_rag.py` → [`eval_report.md`](eval_report.md)

| 指标 | 值 |
|---|---|
| Hit@1 | **1.00** |
| Hit@4 | **1.00**（要求 ≥ 0.8） |
| MRR | **1.000** |
| 平均检索延迟 | **43 ms** |

15 条 golden 覆盖 12 份 seed 文档（公司规章制度 / 技术开发规范 / 产品使用指南）。

## 技术栈与目录

| 层 | 技术 |
|---|---|
| 后端 | FastAPI · SQLAlchemy 2 · Alembic · Pydantic |
| 关系库 | PostgreSQL 16（docker compose） |
| 向量库 | Chroma（内嵌，`kb_{id}` collection，**cosine**） |
| LLM | Ollama（qwen3）/ OpenAI 兼容双模 Provider |
| 前端 | 纯静态 hash SPA（手写 CSS / SVG，无 npm） |
| 测试 | pytest（权限矩阵、SSE 顺序、四格式解析、RAG mock） |
| CI | GitHub Actions：ruff + pytest + postgres service |

```
app/            # FastAPI（core / models / api / services）
static/         # 纯静态前端
scripts/        # seed.py · eval_rag.py
tests/          # pytest
docs/           # plan · architecture · screenshots
seed_docs/      # 12 份四格式示例文档
alembic/        # 数据库迁移
```

- API 文档：`http://127.0.0.1:8000/docs`（Swagger）
- 设计与顺序：[`docs/architecture.md`](docs/architecture.md) · [`docs/plan.md`](docs/plan.md)

## License

[MIT](LICENSE)
