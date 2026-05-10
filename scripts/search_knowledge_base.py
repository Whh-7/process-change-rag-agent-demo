#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检索离线知识库。"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag_engine import load_kb_mode, search_docs  # noqa: E402


def write_results_markdown(query: str, results: list[dict], output_path: Path) -> None:
    """保存检索测试结果。"""
    lines = ["# 检索测试结果", "", f"- Query: {query}", "", "## Results", ""]
    if not results:
        lines.append("未检索到结果。")
    for item in results:
        lines.extend(
            [
                f"### Rank {item['rank']}",
                "",
                f"- Score: {item['score']}",
                f"- Source file: {item['source_file']}",
                f"- Source type: {item['source_type']}",
                f"- Evidence strength: {item['evidence_strength']}",
                "",
                item["text"],
                "",
            ]
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """命令行入口。"""
    if len(sys.argv) < 2:
        print('用法：python scripts/search_knowledge_base.py "电控 A样阶段 软件需求冻结 负责人 任命调整依据"')
        return

    query = " ".join(sys.argv[1:]).strip()
    persist_dir = ROOT_DIR / "outputs" / "chroma_db"
    print(f"知识库记录模式：{load_kb_mode(persist_dir)}")
    results = search_docs(query, top_k=5, persist_dir=persist_dir)

    print(f"Query: {query}")
    if not results:
        print("未检索到结果")
    for item in results:
        preview = item["text"][:300].replace("\n", " ")
        print("-" * 80)
        print(f"rank: {item['rank']}")
        print(f"score: {item['score']}")
        print(f"source_file: {item['source_file']}")
        print(f"source_type: {item['source_type']}")
        print(f"evidence_strength: {item['evidence_strength']}")
        print(f"text: {preview}")

    output_path = ROOT_DIR / "outputs" / "retrieval_test_results.md"
    write_results_markdown(query, results, output_path)
    print("-" * 80)
    print(f"检索结果已写入：{output_path}")


if __name__ == "__main__":
    main()
