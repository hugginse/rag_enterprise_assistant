# CLAUDE.md — rag_enterprise_assistant 执行指引

## 项目定位

企业级知识库问答系统（RAG），个人求职作品，交付物为 **GitHub 公开仓库 `rag_enterprise_assistant`**。
本文件与 `docs/plan.md`、`docs/architecture.md` **自包含**：不需要蓝本源码、不需要其他任何外部材料即可完整开工。

## 文档地图（开工前必读，顺序固定）

1. **`docs/plan.md`** — 四个里程碑、逐条 feature commit 清单、每个 Gate 的验收命令与 git 动作 → 回答「做什么、按什么顺序、何时提交推送」
2. **`docs/architecture.md`** — 架构决策、数据模型、API 与 SSE 协议、权限与级联规则、配置表 → 回答「做成长什么样」

冲突处理：**做什么**以 architecture.md 为准；**顺序 / 提交 / 验收**以 plan.md 为准。

## 环境铁律（Windows 11 / Git Bash）

- 环境管理**只用 uv**：`.python-version` 钉 3.12，`uv sync` 建环境，日常一律 `uv run ...`（如 `uv run pytest`、`uv run uvicorn app.main:app --reload`）
- **禁止**：`python3`（本机是损坏的商店别名）、裸 `python`（3.14，chromadb/psycopg2 无 wheel）、conda 环境
- 依赖增改后必须 `uv sync` 并**提交 `uv.lock`**；`.venv/` 不提交
- Ollama 已装 `qwen3:4b` 与 `qwen3-embedding:4b`（127.0.0.1:11434）；Docker 已装；5432 空闲。**模型是需求方指定，不得降级**
- 本机显卡 **RTX 5060 Ti 16GB**；Ollama **必须限制上下文**（`OLLAMA_NUM_CTX=8192`、嵌入 4096）：否则按模型声明的 262144 满配预分配 KV cache（约 40GB）挤爆显存，模型 CPU/GPU 混跑（实测 67% CPU、prompt 评估 ~30s）；限后 100% GPU 驻留、首 token 秒级
- 所有 Gate 命令均为 Git Bash 形式（见 plan.md 各节）

## Git 工作流（需求方已定，不得更改）

- 分支固定 `main`；**远端空仓库由需求方预先在 GitHub 创建**，开工第一步即 `git remote add origin <URL>`；若拿不到 URL，**停下来询问**，不要自行建仓
- 顺序固定 M1 → M2 → M3 → M4；每个里程碑内按 plan.md 的 feature 清单分批 commit
- commit 规范：中文、conventional 前缀（`feat:` / `fix:` / `test:` / `docs:` / `ci:` / `chore:`），**每条末尾加** `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- 每个 commit 前：`uv run ruff check .` 0 error + 相关 `uv run pytest` 通过
- **每个 Gate 全绿 → 打 annotated tag（`m1`/`m2`/`m3`/`m4`）→ 一次性 push（全部 commit + tag）**；Gate 失败先修复并 commit、重跑 Gate，全绿前不打 tag 不 push；Gate 之外不 push；禁止 force push
- 永不提交：`.env`、`uploads/`、`chroma_data/`、`.venv/`、`__pycache__/`

## 质量红线（细节见 architecture.md）

- 权限一律**后端强校验**（非成员 403/404），不能只靠前端隐藏菜单；禁用用户（status=0）存量 JWT 立即 401
- 密码只用 bcrypt；Chroma collection 必须显式 **cosine 空间**（分数阈值语义依赖它）
- SSE 必须**真流式**（逐 token），禁止整段生成后切片伪装；事件顺序固定 `sources → thinking×N（可选） → delta×N → done`（thinking 与回答分事件、分框展示，思考不落库）
- 文档入库全异步（`pending → processing → completed|failed`），失败写 `error_msg`；应用启动清理遗留死状态
- 前端**零 npm、零 CDN、无构建**；看板图表手写 SVG，不引图表库
- 不做范围外功能：rerank、BM25 混合检索、多轮上下文改写、WebSocket、K8s、前端测试框架

## seed_docs（需求方已手动放入）

- 结构：`seed_docs/公司规章制度/`、`seed_docs/技术开发规范/`、`seed_docs/产品使用指南/`，共 **12 份**、覆盖 **txt/md/pdf/docx** 四格式
- **勿改内容与文件名**；seed 脚本与上传校验逻辑需**递归扫描**该目录
- 开工校验：`find seed_docs -type f | wc -l` 必须 = 12

## 开工检查（首次运行，逐项确认）

1. `uv --version`、`docker compose version`、`ollama --version`；`curl -s http://localhost:11434/api/tags` 含两个 qwen3 模型
2. `find seed_docs -type f | wc -l` = 12；`CLAUDE.md`、`docs/plan.md`、`docs/architecture.md` 在仓库根
3. `git config user.name` / `user.email` 已配置（仓库级即可）；未配置则**询问需求方**，不要伪造身份
4. `uv sync && uv run python --version` 输出 3.12
5. 读完 plan.md 与 architecture.md，从 **M1 feature commit #1** 开始执行

## 阻塞时的处置

- 环境不满足、远端 URL 缺失、seed_docs 数量不对、需求方决策缺失 → **停下报告，不要绕过、不要静默降级**
- 技术方案疑问 → 查 architecture.md；文档未覆盖的取舍 → 按最小范围实现并在报告中说明，不擅自扩大范围
