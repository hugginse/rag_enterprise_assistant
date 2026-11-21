"""递归分隔符分块：\\n\\n → \\n → 。 → 字符滑窗，500/50。"""

from app.core.config import settings

SEPARATORS = ("\n\n", "\n", "。")


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """递归切分为重叠块；保证非空、产出顺序稳定。"""
    size = chunk_size if chunk_size is not None else settings.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
    if size <= 0:
        raise ValueError("chunk_size 必须为正")
    if overlap < 0 or overlap >= size:
        raise ValueError("chunk_overlap 必须在 [0, chunk_size) 内")

    cleaned = (text or "").strip()
    if not cleaned:
        return []

    pieces = _split_recursive(cleaned, list(SEPARATORS), size)
    # 合并过小碎片
    merged = _merge_small(pieces, size)
    # 滑窗保证 overlap
    chunks = _apply_overlap(merged, size, overlap)
    return [c for c in chunks if c.strip()]


def chunk_with_index(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[tuple[int, str]]:
    """返回 [(chunk_index, chunk), ...]。"""
    return list(enumerate(chunk_text(text, chunk_size, chunk_overlap)))


def _split_recursive(text: str, separators: list[str], size: int) -> list[str]:
    if len(text) <= size:
        return [text] if text.strip() else []
    if not separators:
        return _sliding_window(text, size)

    sep = separators[0]
    rest = separators[1:]
    if sep not in text:
        return _split_recursive(text, rest, size)

    parts = text.split(sep)
    results: list[str] = []
    buf = ""
    for part in parts:
        candidate = f"{buf}{sep}{part}" if buf else part
        if len(candidate) <= size:
            buf = candidate
        else:
            if buf.strip():
                results.extend(_split_recursive(buf, rest, size))
            if len(part) > size:
                if buf.strip():
                    buf = ""
                results.extend(_split_recursive(part, rest, size))
            else:
                buf = part
    if buf.strip():
        # 尾部与上一块尝试合并
        if results and len(results[-1]) + len(sep) + len(buf) <= size:
            results[-1] = f"{results[-1]}{sep}{buf}"
        else:
            results.extend(_split_recursive(buf, rest, size))
    return results


def _sliding_window(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text] if text.strip() else []
    step = max(size // 2, 1)
    out = []
    i = 0
    while i < len(text):
        out.append(text[i : i + size])
        if i + size >= len(text):
            break
        i += step
    return out


def _merge_small(pieces: list[str], size: int) -> list[str]:
    merged: list[str] = []
    buf = ""
    for p in pieces:
        if not p.strip():
            continue
        candidate = f"{buf}{p}" if buf else p
        # 直接拼接可能丢分隔符语义，仅当都短时合并
        if len(candidate) <= size:
            buf = candidate
        else:
            if buf:
                merged.append(buf)
            buf = p if len(p) <= size else p[:size]
    if buf:
        merged.append(buf)
    return merged


def _apply_overlap(pieces: list[str], size: int, overlap: int) -> list[str]:
    if overlap <= 0 or len(pieces) <= 1:
        return pieces
    out: list[str] = []
    for i, piece in enumerate(pieces):
        if i == 0:
            out.append(piece)
            continue
        prev = pieces[i - 1]
        prev_tail = prev[-overlap:] if overlap < len(prev) else prev
        combined = prev_tail + piece
        if len(combined) <= size:
            out.append(combined)
        else:
            out.append(piece)
    return out
