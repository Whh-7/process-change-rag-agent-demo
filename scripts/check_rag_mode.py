#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查当前 RAG 检索模式。"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag_engine import inspect_rag_mode  # noqa: E402


def main() -> None:
    """命令行入口。"""
    info = inspect_rag_mode(ROOT_DIR / "outputs/chroma_db")
    print(f"当前 Python 路径: {info['python_executable']}")
    print(f"知识库目录: {info['persist_dir']}")
    print(f"知识库记录模式: {info['kb_mode']}")
    print(f"是否可以 import sentence_transformers: {info['can_import_sentence_transformers']}")
    print(f"是否可以 import chromadb: {info['can_import_chromadb']}")
    print(f"ChromaDB collection 是否可连接: {info['chroma_collection_ok']}")
    print(f"当前 search_docs 会使用: {info['retrieval_mode']}")
    if info["retrieval_mode"] != "vector":
        print("无法使用 vector mode 的原因:")
        for reason in info["reasons"]:
            print(f"- {reason}")


if __name__ == "__main__":
    main()
