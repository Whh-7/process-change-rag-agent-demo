#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""构建离线知识库。"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag_engine import build_knowledge_base  # noqa: E402


def write_build_summary(stats: dict, output_path: Path) -> None:
    """写入知识库构建摘要。"""
    lines = [
        "# RAG 知识库构建摘要",
        "",
        f"- 检索模式: {stats.get('mode', '')}",
        f"- 读取文件数: {stats.get('loaded_file_count', 0)}",
        f"- 跳过重复 xlsx 数: {stats.get('skipped_duplicate_xlsx_count', 0)}",
        f"- 生成 chunk 数: {stats.get('chunk_count', 0)}",
        f"- 向量库保存路径: {stats.get('persist_dir', '')}",
        "",
        "## 已读取文件",
        "",
    ]
    for file_name in stats.get("loaded_files", []):
        lines.append(f"- {file_name}")

    lines.extend(["", "## 跳过的重复 xlsx", ""])
    skipped = stats.get("skipped_duplicate_xlsx", [])
    if skipped:
        lines.extend(f"- {file_name}" for file_name in skipped)
    else:
        lines.append("- 无")

    lines.extend(["", "## source_type 统计", ""])
    for name, count in stats.get("source_type_counts", {}).items():
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## evidence_strength 统计", ""])
    for name, count in stats.get("evidence_strength_counts", {}).items():
        lines.append(f"- {name}: {count}")

    if stats.get("vector_error"):
        lines.extend(["", "## 向量模式降级原因", "", str(stats["vector_error"])])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """命令行入口。"""
    data_dir = ROOT_DIR / "data"
    persist_dir = ROOT_DIR / "outputs" / "chroma_db"
    stats = build_knowledge_base(data_dir=data_dir, persist_dir=persist_dir, rebuild=True)
    summary_path = ROOT_DIR / "outputs" / "kb_build_summary.md"
    write_build_summary(stats, summary_path)

    print("知识库构建完成")
    print(f"读取文件数：{stats.get('loaded_file_count', 0)}")
    print(f"跳过重复 xlsx 数：{stats.get('skipped_duplicate_xlsx_count', 0)}")
    print(f"生成 chunk 数：{stats.get('chunk_count', 0)}")
    print("source_type 统计：")
    for name, count in stats.get("source_type_counts", {}).items():
        print(f"- {name}: {count}")
    print("evidence_strength 统计：")
    for name, count in stats.get("evidence_strength_counts", {}).items():
        print(f"- {name}: {count}")
    print(f"向量库保存路径：{persist_dir}")
    print(f"构建摘要：{summary_path}")
    print(f"chunk 预览：{ROOT_DIR / 'outputs' / 'chunks_preview.csv'}")


if __name__ == "__main__":
    main()
