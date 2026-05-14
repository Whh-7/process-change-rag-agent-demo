#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""运行 RAG 检索评估，支持 baseline 和 rerank 两种模式。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag_engine import get_runtime_search_mode, inspect_rag_mode  # noqa: E402
from rag_evaluator import compare_with_baseline, evaluate_eval_set, save_eval_outputs, summarize_results  # noqa: E402


def parse_top_k_values(text: str) -> list[int]:
    """解析 --top-k-values 1,3,5。"""
    values = []
    for part in str(text).split(","):
        part = part.strip()
        if part:
            values.append(int(part))
    return values or [1, 3, 5]


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="运行 RAG 检索评估")
    parser.add_argument("--rerank", action="store_true", help="启用轻量规则 rerank")
    parser.add_argument("--top-k-values", default="1,3,5", help="逗号分隔，例如 1,3,5")
    parser.add_argument("--candidate-k", type=int, default=20, help="rerank 候选集大小")
    parser.add_argument("--strict-vector", action="store_true", help="要求必须使用 vector mode，否则停止评估")
    return parser.parse_args()


def main() -> None:
    """命令行入口。"""
    args = parse_args()
    eval_path = ROOT_DIR / "eval/rag_eval_set.csv"
    persist_dir = ROOT_DIR / "outputs/chroma_db"
    chunks_json = persist_dir / "chunks.json"
    if not persist_dir.exists() or not chunks_json.exists():
        print("未找到完整知识库，请先运行：python scripts/build_knowledge_base.py")
        return
    if not eval_path.exists():
        print(f"未找到评估集：{eval_path}")
        return

    mode_info = inspect_rag_mode(persist_dir)
    if args.strict_vector and mode_info["retrieval_mode"] != "vector":
        print("strict-vector 已启用，但当前无法使用 vector mode，评估已停止。")
        print("原因：")
        for reason in mode_info["reasons"]:
            print(f"- {reason}")
        print("请运行：python scripts/check_rag_mode.py")
        sys.exit(1)

    top_k_values = parse_top_k_values(args.top_k_values)
    mode = "rerank" if args.rerank else "baseline"
    suffix = "_rerank" if args.rerank else ""
    print(f"读取评估集：{eval_path}")
    print(f"使用知识库：{persist_dir}")
    print(f"评估模式：{mode}")
    print(f"top_k_values：{top_k_values}")

    results_df = evaluate_eval_set(
        eval_path,
        top_k_values=top_k_values,
        persist_dir=persist_dir,
        use_rerank=args.rerank,
        candidate_k=args.candidate_k,
    )
    retrieval_mode = get_runtime_search_mode(persist_dir)
    generated_at = datetime.now().isoformat(timespec="seconds")
    results_df["retrieval_mode"] = retrieval_mode
    results_df["use_rerank"] = bool(args.rerank)
    summary = summarize_results(
        results_df,
        retrieval_mode=retrieval_mode,
        use_rerank=bool(args.rerank),
        generated_at=generated_at,
        python_executable=sys.executable,
    )
    if args.rerank:
        baseline_path = ROOT_DIR / "outputs/eval/rag_eval_results.csv"
        if baseline_path.exists():
            baseline_df = pd.read_csv(baseline_path, encoding="utf-8-sig")
            summary = summary + "\n" + compare_with_baseline(baseline_df, results_df)
        else:
            summary = summary + "\n\n## Baseline vs Rerank 对比\n\n未找到 baseline 结果，请先运行 `python scripts/run_rag_evaluation.py`。"

    outputs = save_eval_outputs(results_df, ROOT_DIR / "outputs/eval", suffix=suffix, summary_text=summary)

    print("\n" + summary)
    print("\n输出文件：")
    print(f"- {outputs['results']}")
    print(f"- {outputs['failed']}")
    print(f"- {outputs['summary']}")


if __name__ == "__main__":
    main()
