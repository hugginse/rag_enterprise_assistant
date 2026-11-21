"""Chroma 向量服务：入库 / 删除 / 阈值检索（cosine 空间）。"""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from app.core.config import settings

# 正确性要求：建 collection 必须显式 cosine，relevance = 1 - distance 语义才成立
COSINE_METADATA = {"hnsw:space": "cosine"}


def _client() -> chromadb.ClientAPI:
    path = Path(settings.chroma_persist_dir)
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def get_or_create_collection(kb_id: int) -> Collection:
    name = f"kb_{kb_id}"
    return _client().get_or_create_collection(name=name, metadata=COSINE_METADATA)


def add_chunks(
    kb_id: int,
    doc_id: int,
    file_name: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """写入分块；id 约定 doc_{doc_id}_chunk_{i}。"""
    assert len(chunks) == len(embeddings)
    if not chunks:
        return
    collection = get_or_create_collection(kb_id)
    ids = [f"doc_{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {"doc_id": doc_id, "file_name": file_name, "chunk_index": i} for i in range(len(chunks))
    ]
    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def delete_doc(kb_id: int, doc_id: int) -> None:
    """删除某文档全部分块；collection 不存在时容忍。"""
    try:
        collection = _client().get_collection(f"kb_{kb_id}")
    except Exception:
        return
    collection.delete(filter={"doc_id": doc_id})


def delete_collection(kb_id: int) -> None:
    """删除整个 kb collection；不存在时容忍。"""
    try:
        _client().delete_collection(f"kb_{kb_id}")
    except Exception:
        pass


def search(
    kb_id: int,
    query_embedding: list[float],
    top_k: int | None = None,
    threshold: float | None = None,
) -> list[dict[str, Any]]:
    """阈值检索；relevance = 1 - distance，低于阈值丢弃。

    返回 [{file_name, chunk_index, score, snippet}, ...]，score 为 relevance。
    """
    k = top_k if top_k is not None else settings.retrieval_top_k
    thr = threshold if threshold is not None else settings.retrieval_score_threshold
    try:
        collection = _client().get_collection(f"kb_{kb_id}")
    except Exception:
        return []

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]

    hits: list[dict[str, Any]] = []
    for doc, meta, dist in zip(docs, metas, dists, strict=False):
        score = 1.0 - float(dist)
        if score < thr:
            continue
        snippet = (doc or "")[:200]
        hits.append(
            {
                "file_name": (meta or {}).get("file_name", ""),
                "chunk_index": int((meta or {}).get("chunk_index", -1)),
                "score": round(score, 4),
                "snippet": snippet,
            }
        )
    return hits
