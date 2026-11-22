"""幂等种子：admin/user 账号、按 seed_docs 子文件夹各建一个知识库并导入对应文档。

用法：uv run python scripts/seed.py
"""

import sys
import uuid
from pathlib import Path

# 保证项目根在 sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Document, KbMember, KnowledgeBase, User  # noqa: E402

SEED_DOCS_DIR = ROOT / "seed_docs"
UPLOAD_DIR = ROOT / "uploads"

ALLOWED_EXT = {".txt", ".md", ".pdf", ".docx"}


def ensure_user(db, username: str, password: str, nickname: str, role: str) -> User:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        user = User(
            username=username,
            password_hash=hash_password(password),
            nickname=nickname,
            role=role,
            status=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[user] 创建 {username}/{password} (role={role}, id={user.id})")
    else:
        # 确保启用且密码/角色符合种子约定（幂等重跑可修复）
        user.status = 1
        user.role = role
        db.commit()
        print(f"[user] 已存在 {username} (id={user.id})，跳过")
    return user


def ensure_kb(db, name: str, creator_id: int, description: str) -> KnowledgeBase:
    kb = db.execute(select(KnowledgeBase).where(KnowledgeBase.name == name)).scalar_one_or_none()
    if kb is None:
        kb = KnowledgeBase(
            name=name,
            description=description,
            created_by=creator_id,
            status=1,
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        print(f"[kb] 创建「{name}」 id={kb.id}")
    else:
        print(f"[kb] 已存在「{name}」 id={kb.id}")
    return kb


def ensure_member(db, kb_id: int, user_id: int) -> None:
    row = db.execute(
        select(KbMember).where(KbMember.kb_id == kb_id, KbMember.user_id == user_id)
    ).scalar_one_or_none()
    if row is None:
        db.add(KbMember(kb_id=kb_id, user_id=user_id))
        db.commit()
        print(f"[member] user {user_id} → kb {kb_id}")
    else:
        print(f"[member] user {user_id} 已在 kb {kb_id}")


def seed_documents(db, kb_id: int, source_dir: Path, creator_id: int) -> None:
    """递归扫描 source_dir/，同 kb 同 filename 跳过；创建 pending 并触发入库。"""
    if not source_dir.is_dir():
        print(f"[docs] 未找到 {source_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(
        p for p in source_dir.rglob("*") if p.is_file() and p.suffix.lower() in ALLOWED_EXT
    )
    print(f"[docs] {source_dir.name}: 扫描到 {len(files)} 份可入库文件")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    skipped = 0

    for path in files:
        filename = path.name
        existing = db.execute(
            select(Document).where(Document.kb_id == kb_id, Document.filename == filename)
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue

        stored_name = f"seed_{kb_id}_{uuid.uuid4().hex}{path.suffix.lower()}"
        stored_path = UPLOAD_DIR / stored_name
        stored_path.write_bytes(path.read_bytes())

        doc = Document(
            kb_id=kb_id,
            filename=filename,
            stored_name=stored_name,
            file_type=path.suffix.lower().lstrip("."),
            file_size=stored_path.stat().st_size,
            status="pending",
            chunk_count=0,
            created_by=creator_id,
        )
        db.add(doc)
        db.commit()
        created += 1
        print(f"[docs] + {path.relative_to(source_dir)} → pending")

    print(f"[docs] 新增 {created}，跳过 {skipped}")

    # 对 pending 触发入库；completed 跳过（幂等）
    from app.services.ingest import ingest_document_by_id

    pending = (
        db.execute(select(Document).where(Document.kb_id == kb_id, Document.status == "pending"))
        .scalars()
        .all()
    )
    for doc in pending:
        print(f"[ingest] {doc.filename} ...")
        ingest_document_by_id(doc.id)
        db.expire_all()
        doc2 = db.get(Document, doc.id)
        print(
            f"[ingest] {doc.filename} → {doc2.status}"
            + (f" ({doc2.error_msg})" if doc2.error_msg else "")
        )
    print(f"[ingest] 处理 {len(pending)} 份 pending")


def discover_kb_dirs() -> list[Path]:
    """seed_docs 下一级子目录即知识库（文件夹名 = 知识库名）。"""
    if not SEED_DOCS_DIR.is_dir():
        print(f"[docs] 未找到 {SEED_DOCS_DIR}", file=sys.stderr)
        sys.exit(1)
    dirs = sorted(p for p in SEED_DOCS_DIR.iterdir() if p.is_dir())
    if not dirs:
        print("[docs] seed_docs 下没有子文件夹，无法按文件夹建库", file=sys.stderr)
        sys.exit(1)
    return dirs


def main() -> None:
    db = SessionLocal()
    try:
        admin = ensure_user(db, "admin", "admin123", "管理员", "admin")
        user = ensure_user(db, "user", "user123", "普通用户", "user")
        kb_dirs = discover_kb_dirs()
        print(f"[seed] 按文件夹建库：{', '.join(d.name for d in kb_dirs)}")
        for source_dir in kb_dirs:
            kb = ensure_kb(
                db,
                name=source_dir.name,
                creator_id=admin.id,
                description=f"种子知识库：{source_dir.name}（对应 seed_docs/{source_dir.name}/）",
            )
            ensure_member(db, kb.id, admin.id)
            ensure_member(db, kb.id, user.id)
            seed_documents(db, kb.id, source_dir, admin.id)
        print("seed 完成")
    finally:
        db.close()


if __name__ == "__main__":
    main()
