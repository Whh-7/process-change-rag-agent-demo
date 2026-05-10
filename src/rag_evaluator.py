#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""轻量 RAG 检索评估工具。

只评估 retrieval，不调用大模型，也不做生成质量判断。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_engine import search_docs  # noqa: E402


REQUIRED_COLUMNS = [
    "case_id",
    "query",
    "query_type",
    "expected_source_files",
    "expected_source_types",
    "expected_keywords",
    "expected_evidence_strength",
    "note",
]


def split_expected(value: Any) -> list[str]:
    """将分号分隔的期望字段转成列表。"""
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    return [item.strip() for item in text.split(";") if item.strip()]


def load_eval_set(path: str | Path) -> pd.DataFrame:
    """读取评估集，并检查必需字段。"""
    eval_path = Path(path)
    if not eval_path.exists():
        raise FileNotFoundError(f"未找到评估集文件: {eval_path}")
    df = pd.read_csv(eval_path, encoding="utf-8-sig", dtype=str, keep_default_na=False).fillna("")
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"评估集缺少必需字段: {', '.join(missing)}")
    return df


def normalize_source_file(value: Any) -> str:
    """统一 source_file 为文件名，兼容绝对路径和相对路径。"""
    text = str(value or "").replace("\\", "/")
    return Path(text).name


def contains_any_keyword(results: list[dict[str, Any]], expected_keywords: list[str]) -> bool:
    """判断 top-k 文本中是否包含任一期望关键词。"""
    if not expected_keywords:
        return True
    combined = "\n".join(str(item.get("text", "")) for item in results)
    return any(keyword in combined for keyword in expected_keywords)


def first_match_rank(
    results: list[dict[str, Any]],
    expected_source_files: list[str],
    expected_source_types: list[str],
) -> tuple[int, str, str]:
    """按 source_file 或 source_type 找到首次命中的 rank。"""
    expected_files = {normalize_source_file(item) for item in expected_source_files}
    expected_types = set(expected_source_types)
    for index, item in enumerate(results, start=1):
        source_file = normalize_source_file(item.get("source_file", ""))
        source_type = str(item.get("source_type", ""))
        file_hit = bool(expected_files and source_file in expected_files)
        type_hit = bool(expected_types and source_type in expected_types)
        if file_hit or type_hit:
            return index, source_file, source_type
    return 0, "", ""


def evaluate_results(
    case: dict[str, Any],
    results: list[dict[str, Any]],
    top_k: int,
    error_message: str = "",
) -> dict[str, Any]:
    """对单条 query 的检索结果计算指标。"""
    top_results = results[:top_k]
    expected_files = split_expected(case.get("expected_source_files", ""))
    expected_types = split_expected(case.get("expected_source_types", ""))
    expected_keywords = split_expected(case.get("expected_keywords", ""))
    expected_strength = str(case.get("expected_evidence_strength", "") or "any").strip()

    result_files = {normalize_source_file(item.get("source_file", "")) for item in top_results}
    result_types = {str(item.get("source_type", "")) for item in top_results}
    result_strengths = {str(item.get("evidence_strength", "")) for item in top_results}

    expected_file_set = {normalize_source_file(item) for item in expected_files}
    hit_source_file = int(bool(expected_file_set and result_files.intersection(expected_file_set)))
    hit_source_type = int(bool(expected_types and result_types.intersection(expected_types)))
    hit_keyword = int(contains_any_keyword(top_results, expected_keywords))
    if expected_strength == "any" or not expected_strength:
        hit_evidence_strength = 1
    else:
        hit_evidence_strength = int(expected_strength in result_strengths)

    matched_rank, matched_source_file, matched_source_type = first_match_rank(top_results, expected_files, expected_types)
    mrr = round(1.0 / matched_rank, 6) if matched_rank else 0.0
    overall_pass = int(bool(hit_source_file or (hit_source_type and hit_keyword)))

    top1 = top_results[0] if top_results else {}
    return {
        "case_id": case.get("case_id", ""),
        "query": case.get("query", ""),
        "query_type": case.get("query_type", ""),
        "top_k": top_k,
        "hit_source_file": hit_source_file,
        "hit_source_type": hit_source_type,
        "hit_keyword": hit_keyword,
        "hit_evidence_strength": hit_evidence_strength,
        "mrr": mrr,
        "overall_pass": overall_pass,
        "top1_source_file": normalize_source_file(top1.get("source_file", "")),
        "top1_source_type": top1.get("source_type", ""),
        "top1_score": top1.get("score", ""),
        "top1_text_preview": str(top1.get("text", ""))[:180].replace("\n", " "),
        "matched_rank": matched_rank,
        "matched_source_file": matched_source_file,
        "matched_source_type": matched_source_type,
        "error_message": error_message,
    }


def evaluate_query(
    query: str,
    expected_source_files: str,
    expected_source_types: str,
    expected_keywords: str,
    expected_evidence_strength: str,
    top_k: int,
    persist_dir: str | Path = "outputs/chroma_db",
) -> dict[str, Any]:
    """评估单个 query，检索失败时返回失败记录而不中断。"""
    case = {
        "case_id": "",
        "query": query,
        "query_type": "",
        "expected_source_files": expected_source_files,
        "expected_source_types": expected_source_types,
        "expected_keywords": expected_keywords,
        "expected_evidence_strength": expected_evidence_strength,
    }
    try:
        results = search_docs(query, top_k=top_k, persist_dir=persist_dir)
        return evaluate_results(case, results, top_k)
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001
        return evaluate_results(case, [], top_k, error_message=str(exc))


def evaluate_eval_set(
    eval_path: str | Path,
    top_k_values: list[int] | None = None,
    persist_dir: str | Path = "outputs/chroma_db",
) -> pd.DataFrame:
    """批量评估整个评估集。"""
    top_k_values = top_k_values or [1, 3, 5]
    df = load_eval_set(eval_path)
    max_k = max(top_k_values)
    rows: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        case = row.to_dict()
        query = str(case.get("query", ""))
        error_message = ""
        try:
            results = search_docs(query, top_k=max_k, persist_dir=persist_dir)
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # noqa: BLE001
            results = []
            error_message = str(exc)
        for top_k in top_k_values:
            rows.append(evaluate_results(case, results, top_k, error_message=error_message))

    return pd.DataFrame(rows)


def rate(series: pd.Series) -> float:
    """计算 0/1 指标均值。"""
    if series.empty:
        return 0.0
    return round(float(series.mean()), 4)


def summarize_results(results_df: pd.DataFrame) -> str:
    """生成 Markdown 格式评估摘要。"""
    if results_df.empty:
        return "# RAG 评估摘要\n\n未生成评估结果。"

    total_cases = results_df["case_id"].nunique()
    top_values = sorted(results_df["top_k"].unique().tolist())
    lines = [
        "# RAG 评估摘要",
        "",
        f"- 评估样本总数: {total_cases}",
        "",
        "## 总体指标",
        "",
        "| top_k | source_file hit rate | source_type hit rate | keyword hit rate | evidence_strength hit rate | 平均 MRR | overall_pass 通过率 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for top_k in top_values:
        subset = results_df[results_df["top_k"] == top_k]
        lines.append(
            f"| top{top_k} | {rate(subset['hit_source_file'])} | {rate(subset['hit_source_type'])} | "
            f"{rate(subset['hit_keyword'])} | {rate(subset['hit_evidence_strength'])} | "
            f"{round(float(subset['mrr'].mean()), 4)} | {rate(subset['overall_pass'])} |"
        )

    top_eval = results_df[results_df["top_k"] == max(top_values)]
    lines.extend(["", "## 按 query_type 分组的通过率", ""])
    grouped = top_eval.groupby("query_type")["overall_pass"].mean().reset_index()
    for _, row in grouped.iterrows():
        lines.append(f"- {row['query_type']}: {round(float(row['overall_pass']), 4)}")

    failed = top_eval[top_eval["overall_pass"] == 0].head(10)
    lines.extend(["", "## 失败样本 Top 10", ""])
    if failed.empty:
        lines.append("- 无")
    else:
        for _, row in failed.iterrows():
            lines.append(
                f"- {row['case_id']} | {row['query_type']} | {row['query']} | "
                f"top1={row['top1_source_file']} / {row['top1_source_type']} | error={row['error_message']}"
            )

    pass_rate = rate(top_eval["overall_pass"])
    lines.extend(
        [
            "",
            "## 简短分析",
            "",
            f"- 本次评估只衡量检索结果是否命中期望来源、来源类型、关键词和证据强度，不评估大模型生成质量。",
            f"- top{max(top_values)} overall_pass 通过率为 {pass_rate}，可用于观察知识库 chunk 切分和 query 表达是否适配。",
            "- 如果 source_type 命中较高但 source_file 命中较低，说明检索方向基本正确，但具体文件召回还需要优化 query 或 chunk。",
            "- 如果 keyword hit 较低，优先检查 chunk 文本是否包含期望字段，或评估样本关键词是否过窄。",
        ]
    )
    return "\n".join(lines)


def save_eval_outputs(results_df: pd.DataFrame, output_dir: str | Path = "outputs/eval") -> dict[str, Path]:
    """保存评估结果、失败样本和摘要。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    results_path = output_path / "rag_eval_results.csv"
    failed_path = output_path / "rag_eval_failed_cases.csv"
    summary_path = output_path / "rag_eval_summary.md"

    results_df.to_csv(results_path, index=False, encoding="utf-8-sig")
    if results_df.empty:
        failed_df = results_df
    else:
        max_k = results_df["top_k"].max()
        failed_df = results_df[(results_df["top_k"] == max_k) & (results_df["overall_pass"] == 0)]
    failed_df.to_csv(failed_path, index=False, encoding="utf-8-sig")
    summary_path.write_text(summarize_results(results_df), encoding="utf-8")

    return {"results": results_path, "failed": failed_path, "summary": summary_path}
