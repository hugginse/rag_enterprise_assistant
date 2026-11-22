"""清空数据库中全部文档：DB 记录 → uploads 物理文件 → Chroma 分块/collection。

用法：uv run python scripts/wipe_documents.py
"""

import sys
from pathlib import Path

# 保证项目根在 sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Document, KnowledgeBase  # noqa: E402
from app.services.vector import delete_collection, delete_doc  # noqa: E402


def main() -> None:
    upload_dir = Path(settings.upload_dir)
    db = SessionLocal()
    try:
        docs = db.execute(select(Document)).scalars().all()
        print(f"[wipe] 文档记录 {len(docs)} 条")

        kb_ids: set[int] = set()
        for doc in docs:
            kb_ids.add(doc.kb_id)
            path = upload_dir / doc.stored_name
            if path.is_file():
                path.unlink()
                print(f"[wipe] 删除文件 {doc.stored_name}")
            try:
                delete_doc(doc.kb_id, doc.id)
            except Exception as exc:  # noqa: BLE001
                print(f"[wipe] chroma delete_doc 失败 doc={doc.id}: {exc}", file=sys.stderr)

        if docs:
            db.execute(delete(Document))
            db.commit()
            print(f"[wipe] 已删除 {len(docs)} 条文档记录")

        # 清掉所有知识库的 collection，避免残留向量
        all_kb_ids = {kb.id for kb in db.execute(select(KnowledgeBase)).scalars()} | kb_ids
        for kb_id in sorted(all_kb_ids):
            try:
                delete_collection(kb_id)
                print(f"[wipe] 删除 collection kb_{kb_id}")
            except Exception as exc:  # noqa: BLE001
                print(f"[wipe] delete_collection kb_{kb_id} 失败: {exc}", file=sys.stderr)

        # 顺带清理 uploads 下无主文件（DB 已无文档）
        if upload_dir.is_dir():
            orphans = [p for p in upload_dir.iterdir() if p.is_file()]
            for p in orphans:
                p.unlink()
            if orphans:
                print(f"[wipe] 清理 uploads 残留 {len(orphans)} 个文件")
    finally:
        db.close()
    print("[wipe] 完成：数据库文档已清空")


if __name__ == "__main__":
    main()
