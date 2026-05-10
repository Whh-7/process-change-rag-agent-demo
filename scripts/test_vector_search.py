#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""连续检索测试，用于观察 vector mode 模型缓存是否生效。"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag_engine import load_kb_mode, search_docs  # noqa: E402


QUERIES = [
    "聊天记录能不能作为正式变更依据",
    "新增任务节点需要校验哪些字段",
    "电控 A样阶段 软件需求冻结 负责人 任命调整依据",
]


def main() -> None:
    """连续执行 3 个 query，观察模型是否只加载一次。"""
    persist_dir = ROOT_DIR / "outputs" / "chroma_db"
    print(f"知识库记录模式：{load_kb_mode(persist_dir)}")
    print("如果 vector mode 可用，应看到首次加载 embedding 模型一次，后续提示复用。")

    for query in QUERIES:
        print("=" * 80)
        print(f"Query: {query}")
        results = search_docs(query, top_k=3, persist_dir=persist_dir)
        if not results:
            print("未检索到结果")
            continue
        for item in results:
            preview = item["text"][:220].replace("\n", " ")
            print("-" * 80)
            print(f"rank: {item['rank']} | score: {item['score']}")
            print(f"source_file: {item['source_file']}")
            print(f"source_type: {item['source_type']} | evidence_strength: {item['evidence_strength']}")
            print(f"text: {preview}")


if __name__ == "__main__":
    main()
