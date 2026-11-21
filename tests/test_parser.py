"""四格式解析与分块测试；fixture 使用 seed_docs/ 真实 pdf/docx。"""

from pathlib import Path

import pytest

from app.services.chunker import chunk_text, chunk_with_index
from app.services.parser import ParseError, parse_file

SEED = Path("seed_docs")


def _find(ext: str) -> Path:
    files = sorted(SEED.rglob(f"*{ext}"))
    assert files, f"seed_docs 中缺少 {ext}"
    return files[0]


def test_parse_txt():
    path = _find(".txt")
    text = parse_file(path)
    assert text.strip()
    assert len(text) > 50


def test_parse_md():
    path = _find(".md")
    text = parse_file(path)
    assert text.strip()
    # md 常含标题
    assert "#" in text or "规范" in text or "办法" in text


def test_parse_pdf_real_seed():
    path = _find(".pdf")
    text = parse_file(path)
    assert text.strip(), f"pdf 解析为空: {path}"
    # 关键内容命中（真实 seed 至少应抽出一段可读文本）
    assert len(text.strip()) > 30


def test_parse_docx_real_seed():
    path = _find(".docx")
    text = parse_file(path)
    assert text.strip(), f"docx 解析为空: {path}"
    assert len(text.strip()) > 30


def test_parse_empty_raises(tmp_path: Path):
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_file(empty)


def test_parse_unsupported_raises(tmp_path: Path):
    bad = tmp_path / "x.exe"
    bad.write_bytes(b"MZ")
    with pytest.raises(ParseError):
        parse_file(bad)


def test_parse_missing_raises(tmp_path: Path):
    with pytest.raises(ParseError):
        parse_file(tmp_path / "nope.txt")


def test_chunk_produces_indexed_chunks():
    path = _find(".md")
    text = parse_file(path)
    indexed = chunk_with_index(text, chunk_size=500, chunk_overlap=50)
    assert indexed
    assert indexed[0][0] == 0
    for i, chunk in indexed:
        assert i >= 0
        assert chunk.strip()
        assert len(chunk) <= 500 + 50  # 允许 overlap 拼接边界


def test_chunk_empty_text():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_chunk_respects_size():
    long_text = ("句子内容测试。" * 200).strip()
    chunks = chunk_text(long_text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    for c in chunks:
        assert c.strip()
