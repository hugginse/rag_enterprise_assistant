"""文档解析器：txt / md / pdf / docx → 纯文本。"""

from pathlib import Path


class ParseError(Exception):
    """业务异常：解析失败或内容为空。"""


def parse_file(path: str | Path) -> str:
    """按扩展名解析文件为文本；空内容或不支持类型抛 ParseError。"""
    p = Path(path)
    if not p.is_file():
        raise ParseError(f"文件不存在: {p}")

    ext = p.suffix.lower()
    if ext in (".txt", ".md"):
        text = _parse_text(p)
    elif ext == ".pdf":
        text = _parse_pdf(p)
    elif ext == ".docx":
        text = _parse_docx(p)
    else:
        raise ParseError(f"不支持的文件类型: {ext}")

    if not text or not text.strip():
        raise ParseError(f"文件内容为空: {p.name}")
    return text


def _parse_text(path: Path) -> str:
    # 尝试 utf-8，失败回退 gbk（部分 Windows 记事本文本）
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError(f"无法识别文本编码: {path.name}")


def _parse_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _parse_docx(path: Path) -> str:
    from docx import Document as DocxDocument

    doc = DocxDocument(str(path))
    parts = [p.text for p in doc.paragraphs]
    # 表格文本也纳入
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)
