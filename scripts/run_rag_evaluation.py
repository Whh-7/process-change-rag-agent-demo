#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""运行 RAG 检索评估。"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag_evaluator import evaluate_eval_set, save_eval_outputs, summarize_results  # noqa: E402


def main() -> None:
    """命令行入口。"""
    eval_path = ROOT_DIR / "eval/rag_eval_set.csv"
    persist_dir = ROOT_DIR / "outputs/chroma_db"
    chunks_json = persist_dir / "chunks.json"
    if not persist_dir.exists() or not chunks_json.exists():
        print("未找到完整知识库，请先运行：python scripts/build_knowledge_base.py")
        return
    if not eval_path.exists():
        print(f"未找到评估集：{eval_path}")
        return

    print(f"读取评估集：{eval_path}")
    print(f"使用知识库：{persist_dir}")
    results_df = evaluate_eval_set(eval_path, top_k_values=[1, 3, 5], persist_dir=persist_dir)
    outputs = save_eval_outputs(results_df, ROOT_DIR / "outputs/eval")
    summary = summarize_results(results_df)

    print("\n" + summary)
    print("\n输出文件：")
    print(f"- {outputs['results']}")
    print(f"- {outputs['failed']}")
    print(f"- {outputs['summary']}")


if __name__ == "__main__":
    main()
