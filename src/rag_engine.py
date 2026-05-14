#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""离线 RAG 建库与检索引擎。

优先使用 sentence-transformers + chromadb；依赖、模型或向量库不可用时自动
fallback 到关键词检索。vector mode 下会缓存 embedding 模型和 ChromaDB
collection，避免每次检索重复加载。
"""

from __future__ import annotations

import json
import math
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from document_loader import DocumentChunk, load_documents, write_chunks_preview
from reranker import rerank_results


DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "process_change_evidence"
OUTPUT_DIR = Path("outputs")
CHUNKS_JSON = "chunks.json"
KB_META_JSON = "kb_meta.json"

_EMBEDDING_MODEL = None
_CHROMA_CLIENT = None
_CHROMA_COLLECTION = None
_CHROMA_PERSIST_DIR: Path | None = None
_VECTOR_UNAVAILABLE_ERROR: str | None = None


def reset_rag_cache() -> None:
    """清空进程内 RAG 缓存，主要用于测试或重建库后重新连接。"""
    global _EMBEDDING_MODEL, _CHROMA_CLIENT, _CHROMA_COLLECTION, _CHROMA_PERSIST_DIR, _VECTOR_UNAVAILABLE_ERROR
    _EMBEDDING_MODEL = None
    _CHROMA_CLIENT = None
    _CHROMA_COLLECTION = None
    _CHROMA_PERSIST_DIR = None
    _VECTOR_UNAVAILABLE_ERROR = None


def get_embedding_model():
    """加载并缓存 SentenceTransformer 模型。"""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        print("首次加载 embedding 模型……")
        from sentence_transformers import SentenceTransformer

        _EMBEDDING_MODEL = SentenceTransformer(DEFAULT_MODEL_NAME)
        print("embedding 模型加载完成")
    else:
        print("复用已加载 embedding 模型")
    return _EMBEDDING_MODEL


def get_chroma_collection(persist_dir: str | Path = "outputs/chroma_db"):
    """连接并缓存 ChromaDB collection。"""
    global _CHROMA_CLIENT, _CHROMA_COLLECTION, _CHROMA_PERSIST_DIR
    persist_path = Path(persist_dir)
    if _CHROMA_COLLECTION is not None and _CHROMA_PERSIST_DIR == persist_path:
        print("复用已连接 ChromaDB collection")
        return _CHROMA_COLLECTION

    import chromadb

    _CHROMA_CLIENT = chromadb.PersistentClient(path=str(persist_path))
    _CHROMA_COLLECTION = _CHROMA_CLIENT.get_collection(COLLECTION_NAME)
    _CHROMA_PERSIST_DIR = persist_path
    print("已连接 ChromaDB collection")
    return _CHROMA_COLLECTION


def metadata_to_chroma(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """把 metadata 转换为 chromadb 可接受的简单类型。"""
    clean: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        elif value is None:
            clean[key] = ""
        else:
            clean[key] = json.dumps(value, ensure_ascii=False)
    return clean


def persist_chunks(chunks: list[DocumentChunk], persist_dir: Path, mode: str, stats: dict[str, Any]) -> None:
    """保存 chunk 原文，供 fallback 检索和人工排查使用。"""
    persist_dir.mkdir(parents=True, exist_ok=True)
    (persist_dir / CHUNKS_JSON).write_text(
        json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    meta = {"mode": mode, **stats}
    (persist_dir / KB_META_JSON).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def load_persisted_chunks(persist_dir: str | Path) -> list[dict[str, Any]]:
    """读取持久化 chunk JSON。"""
    path = Path(persist_dir) / CHUNKS_JSON
    if not path.exists():
        raise FileNotFoundError(f"未找到 chunk 索引，请先运行 build_knowledge_base: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_vector_store(chunks: list[DocumentChunk], persist_dir: Path, model_name: str = DEFAULT_MODEL_NAME) -> None:
    """使用 sentence-transformers + chromadb 构建本地向量库。"""
    import chromadb

    model = get_embedding_model()
    client = chromadb.PersistentClient(path=str(persist_dir))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    batch_size = 64
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [chunk.text for chunk in batch]
        embeddings = model.encode(texts, normalize_embeddings=True).tolist()
        collection.add(
            ids=[chunk.chunk_id for chunk in batch],
            documents=texts,
            metadatas=[metadata_to_chroma(chunk.metadata) for chunk in batch],
            embeddings=embeddings,
        )
    reset_rag_cache()


def count_by_metadata(chunks: list[DocumentChunk], key: str) -> dict[str, int]:
    """按 metadata 字段统计 chunk 数量。"""
    counter = Counter(str(chunk.metadata.get(key, "") or "未填写") for chunk in chunks)
    return dict(sorted(counter.items(), key=lambda item: item[0]))


def build_knowledge_base(
    data_dir: str | Path = "data",
    persist_dir: str | Path = "outputs/chroma_db",
    rebuild: bool = True,
) -> dict[str, Any]:
    """构建知识库，依赖不可用时自动使用关键词 fallback。"""
    persist_path = Path(persist_dir)
    if rebuild and persist_path.exists():
        shutil.rmtree(persist_path)
    persist_path.mkdir(parents=True, exist_ok=True)

    chunks, load_stats = load_documents(data_dir)
    write_chunks_preview(chunks, OUTPUT_DIR / "chunks_preview.csv")

    mode = "keyword_fallback"
    vector_error = ""
    try:
        build_vector_store(chunks, persist_path)
        mode = "vector"
        print("当前使用 vector mode：sentence-transformers + chromadb")
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        vector_error = str(exc)
        print(f"当前使用 keyword fallback mode：向量依赖或模型不可用。原因：{exc}")

    stats: dict[str, Any] = {
        **load_stats,
        "mode": mode,
        "vector_error": vector_error,
        "persist_dir": str(persist_path),
        "source_type_counts": count_by_metadata(chunks, "source_type"),
        "evidence_strength_counts": count_by_metadata(chunks, "evidence_strength"),
    }
    persist_chunks(chunks, persist_path, mode, stats)
    return stats


def load_kb_mode(persist_dir: str | Path) -> str:
    """读取知识库记录的模式。"""
    meta_path = Path(persist_dir) / KB_META_JSON
    if not meta_path.exists():
        return "keyword_fallback"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return str(meta.get("mode", "keyword_fallback"))


def get_runtime_search_mode(persist_dir: str | Path = "outputs/chroma_db") -> str:
    """返回当前进程实际检索模式。"""
    if load_kb_mode(persist_dir) != "vector":
        return "keyword_fallback"
    if _VECTOR_UNAVAILABLE_ERROR:
        return "keyword_fallback"
    return "vector"


def inspect_rag_mode(persist_dir: str | Path = "outputs/chroma_db") -> dict[str, Any]:
    """检查当前环境是否具备 vector mode 条件，不加载 embedding 模型。"""
    persist_path = Path(persist_dir)
    reasons: list[str] = []
    kb_mode = load_kb_mode(persist_path)
    can_import_sentence_transformers = False
    can_import_chromadb = False
    chroma_collection_ok = False

    try:
        import sentence_transformers  # noqa: F401

        can_import_sentence_transformers = True
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"无法 import sentence_transformers: {exc}")

    try:
        import chromadb

        can_import_chromadb = True
        if kb_mode == "vector":
            try:
                client = chromadb.PersistentClient(path=str(persist_path))
                client.get_collection(COLLECTION_NAME)
                chroma_collection_ok = True
            except Exception as exc:  # noqa: BLE001
                reasons.append(f"无法连接 ChromaDB collection: {exc}")
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"无法 import chromadb: {exc}")

    if kb_mode != "vector":
        reasons.append(f"知识库记录模式为 {kb_mode}，不是 vector")

    retrieval_mode = "vector" if kb_mode == "vector" and can_import_sentence_transformers and can_import_chromadb and chroma_collection_ok else "keyword_fallback"
    if _VECTOR_UNAVAILABLE_ERROR:
        retrieval_mode = "keyword_fallback"
        reasons.append(f"当前进程 vector 已不可用: {_VECTOR_UNAVAILABLE_ERROR}")

    return {
        "python_executable": sys.executable,
        "persist_dir": str(persist_path),
        "kb_mode": kb_mode,
        "can_import_sentence_transformers": can_import_sentence_transformers,
        "can_import_chromadb": can_import_chromadb,
        "chroma_collection_ok": chroma_collection_ok,
        "retrieval_mode": retrieval_mode,
        "reasons": reasons,
    }


def normalize_vector_result(result: dict[str, Any]) -> list[list[dict[str, Any]]]:
    """把 ChromaDB query 结果转换为统一结构。"""
    all_rows: list[list[dict[str, Any]]] = []
    documents = result.get("documents", [])
    metadatas = result.get("metadatas", [])
    distances = result.get("distances", [])
    for query_index, docs in enumerate(documents):
        rows: list[dict[str, Any]] = []
        query_metadatas = metadatas[query_index] if query_index < len(metadatas) else []
        query_distances = distances[query_index] if query_index < len(distances) else []
        for idx, text in enumerate(docs):
            metadata = query_metadatas[idx] if idx < len(query_metadatas) else {}
            distance = float(query_distances[idx]) if idx < len(query_distances) else 1.0
            rows.append(
                {
                    "rank": idx + 1,
                    "score": round(1.0 - distance, 6),
                    "text": text,
                    "source_file": metadata.get("source_file", ""),
                    "source_type": metadata.get("source_type", ""),
                    "evidence_strength": metadata.get("evidence_strength", ""),
                    "metadata": metadata,
                }
            )
        all_rows.append(rows)
    return all_rows


def search_vector(query: str, top_k: int, persist_dir: Path) -> list[dict[str, Any]]:
    """使用缓存模型和缓存 collection 做单条向量检索。"""
    model = get_embedding_model()
    collection = get_chroma_collection(persist_dir)
    embedding = model.encode([query], normalize_embeddings=True).tolist()[0]
    result = collection.query(query_embeddings=[embedding], n_results=top_k)
    return normalize_vector_result(result)[0]


def batch_search_vector(queries: list[str], top_k: int, persist_dir: Path) -> list[list[dict[str, Any]]]:
    """使用缓存模型和缓存 collection 做批量向量检索。"""
    if not queries:
        return []
    model = get_embedding_model()
    collection = get_chroma_collection(persist_dir)
    embeddings = model.encode(queries, normalize_embeddings=True).tolist()
    result = collection.query(query_embeddings=embeddings, n_results=top_k)
    return normalize_vector_result(result)


def tokenize(text: str) -> list[str]:
    """简单分词：中文按字符/二字片段，英文数字按词。"""
    text = text.lower()
    words = re.findall(r"[a-z0-9_]+", text)
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    bigrams = [a + b for a, b in zip(chinese_chars, chinese_chars[1:])]
    return words + chinese_chars + bigrams


def keyword_score(query_tokens: Counter[str], doc_tokens: Counter[str]) -> float:
    """计算轻量 TF-IDF 风格关键词重叠分。"""
    if not query_tokens or not doc_tokens:
        return 0.0
    score = 0.0
    for token, q_count in query_tokens.items():
        if token in doc_tokens:
            score += (1.0 + math.log(1 + doc_tokens[token])) * q_count
    length_penalty = math.sqrt(sum(doc_tokens.values())) or 1.0
    return score / length_penalty


def search_keyword(query: str, top_k: int, persist_dir: Path) -> list[dict[str, Any]]:
    """关键词 fallback 检索。"""
    chunks = load_persisted_chunks(persist_dir)
    query_tokens = Counter(tokenize(query))
    scored = []
    for chunk in chunks:
        text = chunk.get("text", "")
        metadata = chunk.get("metadata", {})
        combined = text + " " + " ".join(str(value) for value in metadata.values())
        score = keyword_score(query_tokens, Counter(tokenize(combined)))
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)

    rows: list[dict[str, Any]] = []
    for rank, (score, chunk) in enumerate(scored[:top_k], 1):
        metadata = chunk.get("metadata", {})
        rows.append(
            {
                "rank": rank,
                "score": round(float(score), 6),
                "text": chunk.get("text", ""),
                "source_file": metadata.get("source_file", ""),
                "source_type": metadata.get("source_type", ""),
                "evidence_strength": metadata.get("evidence_strength", ""),
                "metadata": metadata,
            }
        )
    return rows


def batch_search_keyword(queries: list[str], top_k: int, persist_dir: Path) -> list[list[dict[str, Any]]]:
    """批量关键词 fallback 检索。"""
    return [search_keyword(query, top_k, persist_dir) for query in queries]


def search_docs(
    query: str,
    top_k: int = 5,
    persist_dir: str | Path = "outputs/chroma_db",
    use_rerank: bool = False,
    candidate_k: int = 20,
) -> list[dict[str, Any]]:
    """检索知识库，返回标准结果列表。"""
    return batch_search_docs(
        [query],
        top_k=top_k,
        persist_dir=persist_dir,
        use_rerank=use_rerank,
        candidate_k=candidate_k,
    )[0]


def batch_search_docs(
    queries: list[str],
    top_k: int = 5,
    persist_dir: str | Path = "outputs/chroma_db",
    use_rerank: bool = False,
    candidate_k: int = 20,
) -> list[list[dict[str, Any]]]:
    """批量检索知识库，vector mode 下复用同一个模型和 collection。"""
    global _VECTOR_UNAVAILABLE_ERROR
    persist_path = Path(persist_dir)
    search_k = max(top_k, candidate_k) if use_rerank else top_k
    mode = load_kb_mode(persist_path)
    if mode == "vector":
        if _VECTOR_UNAVAILABLE_ERROR:
            print(f"当前使用 keyword fallback mode 检索：vector mode 此进程已不可用。原因：{_VECTOR_UNAVAILABLE_ERROR}")
            rows = batch_search_keyword(queries, search_k, persist_path)
            return apply_rerank_if_needed(queries, rows, top_k, use_rerank)
        try:
            print("当前使用 vector mode 检索")
            rows = batch_search_vector(queries, search_k, persist_path)
            return apply_rerank_if_needed(queries, rows, top_k, use_rerank)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            _VECTOR_UNAVAILABLE_ERROR = str(exc)
            print(f"vector mode 加载或检索失败，自动切换 keyword fallback mode。原因：{exc}")
    else:
        print("当前使用 keyword fallback mode 检索")
    rows = batch_search_keyword(queries, search_k, persist_path)
    return apply_rerank_if_needed(queries, rows, top_k, use_rerank)


def apply_rerank_if_needed(
    queries: list[str],
    rows: list[list[dict[str, Any]]],
    top_k: int,
    use_rerank: bool,
) -> list[list[dict[str, Any]]]:
    """按需执行 rerank；失败时回退原排序。"""
    if not use_rerank:
        return [items[:top_k] for items in rows]
    reranked_rows: list[list[dict[str, Any]]] = []
    for query, items in zip(queries, rows):
        try:
            reranked_rows.append(rerank_results(query, items, top_k=top_k))
        except Exception as exc:  # noqa: BLE001
            print(f"rerank 失败，回退原始排序。原因：{exc}")
            reranked_rows.append(items[:top_k])
    return reranked_rows
