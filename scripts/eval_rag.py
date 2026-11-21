"""RAG 检索评估：15 条 golden 问答对 → Hit@1 / Hit@4 / MRR / 平均延迟。

用法：uv run python scripts/eval_rag.py
产出：仓库根 eval_report.md（本地连 Ollama，不进 CI）
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.services.llm import create_provider  # noqa: E402
from app.services.vector import search  # noqa: E402

# 15 条 golden：按 seed_docs 三主题域出题；expected 为期望命中的文件名（列表内任一命中即算 Hit）
GOLDEN: list[dict] = [
    # 公司规章制度（4 docs）
    {"q": "员工请假需要提前几天申请？", "expected": ["员工请假管理办法.md"]},
    {"q": "年休假满10年不满20年可以休几天？", "expected": ["员工请假管理办法.md"]},
    {"q": "员工迟到早退如何处理？", "expected": ["公司考勤管理制度.txt"]},
    {"q": "公司考勤打卡时间是什么时候？", "expected": ["公司考勤管理制度.txt"]},
    {"q": "试用期员工的薪酬结构是怎样的？", "expected": ["公司薪酬福利制度.pdf"]},
    {"q": "年终奖一般什么时候发放？", "expected": ["公司薪酬福利制度.pdf"]},
    {"q": "员工有哪些禁止的行为？", "expected": ["员工行为规范手册.docx"]},
    # 产品使用指南（4 docs）
    {"q": "如何在OA系统提交请假申请？", "expected": ["企业OA系统使用手册.txt"]},
    {"q": "OA系统密码忘记了怎么办？", "expected": ["企业OA系统使用手册.txt"]},
    {"q": "企业邮箱如何配置客户端？", "expected": ["企业邮箱配置说明.pdf"]},
    {"q": "新员工入职需要办理哪些手续？", "expected": ["新员工入职指南.docx"]},
    {"q": "项目管理平台如何创建任务？", "expected": ["项目管理平台操作指南.md"]},
    # 技术开发规范（4 docs）
    {"q": "API接口返回错误码的规范格式是什么？", "expected": ["API接口设计规范.md"]},
    {"q": "Git提交信息应该怎样书写？", "expected": ["Git版本管理规范.docx"]},
    {"q": "Python代码的命名规范有哪些要求？", "expected": ["Python开发编码规范.txt"]},
]


def evaluate() -> dict:
    provider = create_provider()
    kb_id = _kb_id()
    rows: list[dict] = []
    hit1 = hit4 = mrr_sum = 0
    total_latency = 0.0

    for i, g in enumerate(GOLDEN, 1):
        t0 = time.perf_counter()
        emb = provider.embed([g["q"]])[0]
        # 检索 top10 便于算 Hit@k / MRR（接口默认 top_k=4，评估放宽）
        hits = search(
            kb_id,
            query_embedding=emb,
            top_k=10,
            threshold=0.0,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        total_latency += elapsed

        ranked = [h["file_name"] for h in hits]
        expected = set(g["expected"])
        # 去重排名
        seen: list[str] = []
        for name in ranked:
            if name not in seen:
                seen.append(name)

        top1 = 1 if seen and seen[0] in expected else 0
        top4 = 1 if any(n in expected for n in seen[:4]) else 0
        rr = 0.0
        for rank, name in enumerate(seen, 1):
            if name in expected:
                rr = 1.0 / rank
                break

        hit1 += top1
        hit4 += top4
        mrr_sum += rr
        rows.append(
            {
                "i": i,
                "q": g["q"],
                "expected": list(expected),
                "top": seen[:4],
                "hit1": top1,
                "hit4": top4,
                "rr": rr,
                "latency_ms": elapsed,
            }
        )
        print(f"[{i:02d}] hit@1={top1} hit@4={top4} rr={rr:.2f} {elapsed:.0f}ms | {g['q'][:24]}")

    n = len(GOLDEN)
    return {
        "n": n,
        "hit_at_1": hit1 / n,
        "hit_at_4": hit4 / n,
        "mrr": mrr_sum / n,
        "avg_latency_ms": total_latency / n,
        "rows": rows,
    }


def _kb_id() -> int:
    """取第一个有文档的知识库（评估用 admin 权限无关的向量库）。"""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Document, KnowledgeBase

    db = SessionLocal()
    try:
        row = db.execute(
            select(Document.kb_id).where(Document.status == "completed").limit(1)
        ).first()
        if row:
            return int(row[0])
        kb = db.execute(select(KnowledgeBase.id).limit(1)).first()
        if kb:
            return int(kb[0])
        raise SystemExit("没有可用知识库/文档，请先 seed 并完成入库")
    finally:
        db.close()


def render_report(result: dict) -> str:
    lines = [
        "# RAG 检索评估报告",
        "",
        f"> 生成脚本：`scripts/eval_rag.py`；模型：LLM=`{settings.ollama_llm_model}`，"
        f"Embed=`{settings.ollama_embed_model}`；KB id=`{_kb_id()}`",
        f"> 样本数：**{result['n']}**；阈值评估时 `threshold=0.0`（不过滤），top_k=10",
        "",
        "## 指标总览",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        f"| Hit@1 | **{result['hit_at_1']:.2f}** |",
        f"| Hit@4 | **{result['hit_at_4']:.2f}** |",
        f"| MRR | **{result['mrr']:.3f}** |",
        f"| 平均检索延迟 | **{result['avg_latency_ms']:.0f} ms** |",
        "",
        "## 逐条结果",
        "",
        "| # | 问题 | 期望文件 | Top4 命中 | Hit@1 | Hit@4 | RR | 延迟(ms) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in result["rows"]:
        exp = "、".join(r["expected"])
        top = "、".join(r["top"]) if r["top"] else "（空）"
        lines.append(
            f"| {r['i']} | {r['q']} | {exp} | {top} | {r['hit1']} | {r['hit4']} "
            f"| {r['rr']:.2f} | {r['latency_ms']:.0f} |"
        )
    ok = result["hit_at_4"] >= 0.8
    verdict = "✅ 达标" if ok else "❌ 未达标（需调题/查检索，不得放水）"
    lines += [
        "",
        "## 达标判定",
        "",
        f"- Hit@4 ≥ 0.8：{verdict}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    print(f"kb_id={_kb_id()} samples={len(GOLDEN)}")
    result = evaluate()
    report = render_report(result)
    out = ROOT / "eval_report.md"
    out.write_text(report, encoding="utf-8")
    print(
        f"\nHit@1={result['hit_at_1']:.2f} Hit@4={result['hit_at_4']:.2f} "
        f"MRR={result['mrr']:.3f} avg={result['avg_latency_ms']:.0f}ms"
    )
    print(f"written: {out}")
    if result["hit_at_4"] < 0.8:
        print("WARNING: Hit@4 < 0.8", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
