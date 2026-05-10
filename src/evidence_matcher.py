#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""变更依据匹配模块。

读取 change_report.csv，对每条变更使用 evidence_query 检索原始知识库资料，
并按“配置上下文、具体变更依据、弱线索、规则依据”重新判断证据质量。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pandas as pd

from rag_engine import batch_search_docs, get_runtime_search_mode


REQUIRED_CHANGE_FIELDS = [
    "change_id",
    "change_type",
    "business_domain",
    "phase_old",
    "phase_new",
    "task_name_old",
    "task_name_new",
    "field",
    "old_value",
    "new_value",
    "risk_level",
    "evidence_query",
    "review_suggestion",
]

CONFIG_CONTEXT_TYPES = {"old_config", "target_config"}
STRONG_CHANGE_TYPES = {"appointment_notice", "meeting_minutes"}
MEDIUM_CHANGE_TYPES = {"department_update"}
WEAK_CLUE_TYPES = {"chat_message"}
RULE_EVIDENCE_TYPES = {"rule_manual"}

STATUS_STRONG = "强变更依据"
STATUS_MEDIUM = "中等变更依据"
STATUS_WEAK = "弱线索，需人工复核"
STATUS_CONTEXT_ONLY = "仅有配置或规则上下文，缺少变更依据"
STATUS_MISSING = "未找到依据"

CONFLICT_KEYWORDS = [
    "待确认",
    "可能",
    "先别改",
    "会议未确认",
    "不确定",
    "只是听说",
    "没有正式依据",
    "需人工复核",
    "冲突",
    "先不要",
    "未确认",
]


def normalize_value(value: Any) -> str:
    """统一处理空值和首尾空格。"""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def load_change_report(path: str | Path) -> pd.DataFrame:
    """读取 change_report，并对缺失字段使用空字符串兜底。"""
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False).fillna("")
    for column in df.columns:
        df[column] = df[column].map(normalize_value)
    for field in REQUIRED_CHANGE_FIELDS:
        if field not in df.columns:
            print(f"字段缺失，使用空字符串兜底 / Missing field fallback: {field}")
            df[field] = ""
    return df


def build_query_for_change(row: pd.Series) -> str:
    """优先使用 evidence_query；为空时按变更字段自动拼接 query。"""
    evidence_query = normalize_value(row.get("evidence_query", ""))
    if evidence_query:
        return evidence_query

    phase = normalize_value(row.get("phase_new", "")) or normalize_value(row.get("phase_old", ""))
    task_name = normalize_value(row.get("task_name_new", "")) or normalize_value(row.get("task_name_old", ""))
    parts = [
        normalize_value(row.get("business_domain", "")),
        phase,
        task_name,
        normalize_value(row.get("field", "")),
        normalize_value(row.get("old_value", "")),
        normalize_value(row.get("new_value", "")),
        "变更依据",
    ]
    return " ".join(part for part in parts if part)


def source_types_from_results(results: list[dict[str, Any]]) -> set[str]:
    """提取检索结果中的 source_type 集合。"""
    return {normalize_value(item.get("source_type", "")) for item in results if normalize_value(item.get("source_type", ""))}


def files_for_types(results: list[dict[str, Any]], source_types: set[str]) -> str:
    """提取指定 source_type 命中的文件名，去重后用顿号连接。"""
    files = []
    for item in results:
        source_type = normalize_value(item.get("source_type", ""))
        source_file = normalize_value(item.get("source_file", ""))
        if source_type in source_types and source_file and source_file not in files:
            files.append(source_file)
    return "、".join(files)


def categorize_evidence(results: list[dict[str, Any]]) -> dict[str, Any]:
    """按业务语义重新分类证据来源。"""
    source_types = source_types_from_results(results)
    has_config_context = bool(source_types & CONFIG_CONTEXT_TYPES)
    has_strong_change_evidence = bool(source_types & STRONG_CHANGE_TYPES)
    has_medium_change_evidence = bool(source_types & MEDIUM_CHANGE_TYPES)
    has_weak_clue = bool(source_types & WEAK_CLUE_TYPES)
    has_rule_evidence = bool(source_types & RULE_EVIDENCE_TYPES)

    if not results:
        evidence_status = STATUS_MISSING
        primary_category = "none"
    elif has_strong_change_evidence:
        evidence_status = STATUS_STRONG
        primary_category = "strong_change_evidence"
    elif has_medium_change_evidence:
        evidence_status = STATUS_MEDIUM
        primary_category = "medium_change_evidence"
    elif has_weak_clue and not (has_config_context or has_rule_evidence):
        evidence_status = STATUS_WEAK
        primary_category = "weak_clue"
    elif has_config_context or has_rule_evidence:
        evidence_status = STATUS_CONTEXT_ONLY
        primary_category = "config_or_rule_context"
    else:
        evidence_status = STATUS_MISSING
        primary_category = "none"

    return {
        "evidence_status": evidence_status,
        "primary_evidence_category": primary_category,
        "has_config_context": str(has_config_context),
        "has_strong_change_evidence": str(has_strong_change_evidence),
        "has_medium_change_evidence": str(has_medium_change_evidence),
        "has_weak_clue": str(has_weak_clue),
        "has_rule_evidence": str(has_rule_evidence),
        "weak_clue_flag": str(has_weak_clue),
        "config_context_files": files_for_types(results, CONFIG_CONTEXT_TYPES),
        "change_evidence_files": files_for_types(results, STRONG_CHANGE_TYPES | MEDIUM_CHANGE_TYPES),
        "rule_evidence_files": files_for_types(results, RULE_EVIDENCE_TYPES),
    }


def detect_conflict(results: list[dict[str, Any]]) -> bool:
    """检测检索结果中是否存在冲突或待确认表述。"""
    combined_text = "\n".join(str(item.get("text", "")) for item in results)
    return any(keyword in combined_text for keyword in CONFLICT_KEYWORDS)


def enhance_review_suggestion(evidence_status: str, weak_clue_flag: bool, conflict_flag: bool) -> str:
    """使用规则模板生成最终复核建议。"""
    if evidence_status == STATUS_STRONG:
        suggestion = "已检索到正式变更依据，建议业务人员复核后纳入变更清单。"
    elif evidence_status == STATUS_MEDIUM:
        suggestion = "当前主要依据来自部门在线更新表，建议补充正式会议纪要或任命通知后再确认。"
    elif evidence_status == STATUS_WEAK:
        suggestion = "当前仅检索到聊天或口头通知类弱线索，不能直接作为正式变更依据，需人工确认。"
    elif evidence_status == STATUS_CONTEXT_ONLY:
        suggestion = "当前仅能确认新旧配置存在差异，但未检索到明确变更原因或正式依据，建议补充任命通知、会议纪要或部门确认材料。"
    else:
        suggestion = "未检索到明确依据，建议退回业务部门补充说明。"

    if weak_clue_flag:
        suggestion += "同时检索到聊天记录线索，建议核对其是否已被正式会议纪要或通知确认。"
    if conflict_flag:
        suggestion += "检索结果存在冲突或待确认表述，请重点人工复核。"
    return suggestion


def build_review_priority(evidence_status: str, risk_level: str, conflict_flag: bool) -> str:
    """根据证据状态、配置影响等级和冲突标记生成复核优先级。"""
    if conflict_flag:
        return "重点复核"
    if evidence_status == STATUS_STRONG:
        return "常规复核" if risk_level == "高" else "可快速复核"
    if evidence_status == STATUS_MEDIUM:
        return "补充确认"
    if evidence_status == STATUS_WEAK:
        return "重点复核"
    if evidence_status == STATUS_CONTEXT_ONLY:
        return "重点补证"
    if evidence_status == STATUS_MISSING:
        return "暂缓纳入"
    return "补充确认"


def build_decision_suggestion(evidence_status: str, conflict_flag: bool) -> str:
    """根据证据状态生成业务处理建议。"""
    if evidence_status == STATUS_STRONG:
        suggestion = "已有正式依据支撑，可进入候选变更清单，业务人员进行常规复核。"
    elif evidence_status == STATUS_MEDIUM:
        suggestion = "已有部门更新来源，但建议补充会议纪要、任命通知或部门确认材料后再纳入正式变更。"
    elif evidence_status == STATUS_WEAK:
        suggestion = "当前仅有聊天或口头通知线索，不建议直接纳入正式变更，需等待正式材料确认。"
    elif evidence_status == STATUS_CONTEXT_ONLY:
        suggestion = "当前只能确认新旧配置存在差异，但缺少明确变更原因，建议补充变更申请或会议纪要。"
    else:
        suggestion = "未检索到明确依据，建议暂缓纳入并退回补充说明。"
    if conflict_flag:
        suggestion += "检索结果存在冲突或待确认表述，请优先人工复核。"
    return suggestion


def truncate_text(text: str, max_chars: int = 500) -> str:
    """限制证据文本长度，避免 CSV 过长，同时保留原始 evidence_text 字段含义。"""
    text = normalize_value(text).replace("\r", " ").replace("\n", " ")
    return text if len(text) <= max_chars else text[:max_chars] + "..."


def evidence_columns(results: list[dict[str, Any]]) -> dict[str, str]:
    """提取前 3 条主要证据到扁平字段。"""
    output: dict[str, str] = {}
    for idx in range(1, 4):
        item = results[idx - 1] if idx <= len(results) else {}
        output[f"evidence_source_file_{idx}"] = normalize_value(item.get("source_file", ""))
        output[f"evidence_source_type_{idx}"] = normalize_value(item.get("source_type", ""))
        output[f"evidence_strength_{idx}"] = normalize_value(item.get("evidence_strength", ""))
        output[f"evidence_score_{idx}"] = normalize_value(item.get("score", ""))
        output[f"evidence_text_{idx}"] = truncate_text(item.get("text", ""))
    return output


def match_evidence_for_change(row: pd.Series, results: list[dict[str, Any]]) -> dict[str, str]:
    """根据已检索结果生成单条变更的证据匹配字段。"""
    category = categorize_evidence(results)
    conflict_flag = detect_conflict(results)
    weak_clue_flag = category["weak_clue_flag"] == "True"
    risk_level = normalize_value(row.get("risk_level", ""))
    evidence_status = category["evidence_status"]
    matched = {
        **category,
        "conflict_flag": str(conflict_flag),
        "final_review_suggestion": enhance_review_suggestion(evidence_status, weak_clue_flag, conflict_flag),
        "impact_level": risk_level,
        "review_priority": build_review_priority(evidence_status, risk_level, conflict_flag),
        "decision_suggestion": build_decision_suggestion(evidence_status, conflict_flag),
    }
    matched.update(evidence_columns(results))
    return matched


def match_change_report(
    change_report_path: str | Path = "outputs/change_report.csv",
    persist_dir: str | Path = "outputs/chroma_db",
    top_k: int = 5,
) -> pd.DataFrame:
    """对完整 change_report 执行批量证据匹配。"""
    report_df = load_change_report(change_report_path)
    queries = [build_query_for_change(row) for _, row in report_df.iterrows()]
    try:
        batch_results = batch_search_docs(queries, top_k=top_k, persist_dir=persist_dir)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"批量检索失败，所有记录按未找到依据处理 / Batch search failed: {exc}")
        batch_results = [[] for _ in queries]

    rows: list[dict[str, str]] = []
    for idx, (_, row) in enumerate(report_df.iterrows()):
        base = {column: normalize_value(row.get(column, "")) for column in report_df.columns}
        base.update(match_evidence_for_change(row, batch_results[idx] if idx < len(batch_results) else []))
        rows.append(base)
    return pd.DataFrame(rows)


def save_evidence_report(report_df: pd.DataFrame, output_dir: str | Path = "outputs") -> tuple[Path, Path]:
    """保存带证据的 CSV 和 XLSX 报告。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    csv_path = output_path / "change_report_with_evidence.csv"
    xlsx_path = output_path / "change_report_with_evidence.xlsx"
    report_df.to_csv(csv_path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    try:
        report_df.to_excel(xlsx_path, index=False)
    except Exception as exc:
        print(f"xlsx 写入失败，仅保留 CSV / xlsx write failed: {exc}")
    return csv_path, xlsx_path


def status_count(report_df: pd.DataFrame, status: str) -> int:
    """统计某类证据状态数量。"""
    if "evidence_status" not in report_df.columns:
        return 0
    return int((report_df["evidence_status"] == status).sum())


def grouped_status_markdown(report_df: pd.DataFrame, group_field: str) -> list[str]:
    """生成按某字段统计 evidence_status 的 markdown 表。"""
    statuses = [STATUS_STRONG, STATUS_MEDIUM, STATUS_WEAK, STATUS_CONTEXT_ONLY, STATUS_MISSING]
    lines = [
        "| 分组 | 强变更依据 | 中等变更依据 | 弱线索，需人工复核 | 仅有配置或规则上下文 | 未找到依据 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    if report_df.empty or group_field not in report_df.columns:
        return lines
    for name, group in report_df.groupby(group_field, dropna=False):
        counts = [status_count(group, status) for status in statuses]
        lines.append(f"| {name or '未填写'} | {counts[0]} | {counts[1]} | {counts[2]} | {counts[3]} | {counts[4]} |")
    return lines


def row_label(row: pd.Series) -> str:
    """生成摘要中的变更标签。"""
    phase = normalize_value(row.get("phase_new", "")) or normalize_value(row.get("phase_old", ""))
    task = normalize_value(row.get("task_name_new", "")) or normalize_value(row.get("task_name_old", ""))
    return (
        f"{row.get('change_id', '')} | {row.get('risk_level', '')} | {row.get('change_type', '')} | "
        f"{row.get('business_domain', '')} | {phase} | {task} | {row.get('field', '')}"
    )


def write_evidence_summary(report_df: pd.DataFrame, output_dir: str | Path = "outputs") -> Path:
    """写入 evidence_summary.md。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary_path = output_path / "evidence_summary.md"

    weak_clue_count = int((report_df.get("weak_clue_flag", "") == "True").sum()) if not report_df.empty else 0
    conflict_count = int((report_df.get("conflict_flag", "") == "True").sum()) if not report_df.empty else 0
    high_without_strong = report_df[
        (report_df.get("risk_level", "") == "高") & (report_df.get("evidence_status", "") != STATUS_STRONG)
    ].head(10)
    context_only = report_df[report_df.get("evidence_status", "") == STATUS_CONTEXT_ONLY].head(10)
    weak_rows = report_df[report_df.get("weak_clue_flag", "") == "True"].head(10)

    lines = [
        "# 变更依据匹配摘要",
        "",
        f"- 总变更数量: {len(report_df)}",
        f"- 强变更依据数量: {status_count(report_df, STATUS_STRONG)}",
        f"- 中等变更依据数量: {status_count(report_df, STATUS_MEDIUM)}",
        f"- 弱线索数量: {status_count(report_df, STATUS_WEAK)}",
        f"- 仅有配置或规则上下文数量: {status_count(report_df, STATUS_CONTEXT_ONLY)}",
        f"- 未找到依据数量: {status_count(report_df, STATUS_MISSING)}",
        f"- weak_clue_flag=True 数量: {weak_clue_count}",
        f"- conflict_flag=True 数量: {conflict_count}",
        "",
        "## 按 risk_level 统计 evidence_status",
        "",
        *grouped_status_markdown(report_df, "risk_level"),
        "",
        "## 按 change_type 统计 evidence_status",
        "",
        *grouped_status_markdown(report_df, "change_type"),
        "",
        "## 前 10 条高风险但缺少强变更依据的变更",
        "",
    ]
    lines.extend(["- 无"] if high_without_strong.empty else [f"- {row_label(row)} | {row.get('evidence_status', '')}" for _, row in high_without_strong.iterrows()])
    lines.extend(["", "## 前 10 条仅有配置或规则上下文的变更", ""])
    lines.extend(["- 无"] if context_only.empty else [f"- {row_label(row)} | {row.get('config_context_files', '')} | {row.get('rule_evidence_files', '')}" for _, row in context_only.iterrows()])
    lines.extend(["", "## 前 10 条存在弱线索的变更", ""])
    lines.extend(["- 无"] if weak_rows.empty else [f"- {row_label(row)} | {row.get('evidence_status', '')}" for _, row in weak_rows.iterrows()])
    lines.extend(["", "## 示例展示 3 条完整证据链", ""])

    for _, row in report_df.head(3).iterrows():
        lines.extend(
            [
                f"### {row.get('change_id', '')}",
                "",
                f"- 变更: {row_label(row)}",
                f"- evidence_status: {row.get('evidence_status', '')}",
                f"- primary_evidence_category: {row.get('primary_evidence_category', '')}",
                f"- final_review_suggestion: {row.get('final_review_suggestion', '')}",
                f"- 证据1: {row.get('evidence_source_file_1', '')} / {row.get('evidence_source_type_1', '')} / {row.get('evidence_strength_1', '')} / score={row.get('evidence_score_1', '')}",
                f"- 文本1: {row.get('evidence_text_1', '')}",
                f"- 证据2: {row.get('evidence_source_file_2', '')} / {row.get('evidence_source_type_2', '')} / {row.get('evidence_strength_2', '')} / score={row.get('evidence_score_2', '')}",
                f"- 文本2: {row.get('evidence_text_2', '')}",
                f"- 证据3: {row.get('evidence_source_file_3', '')} / {row.get('evidence_source_type_3', '')} / {row.get('evidence_strength_3', '')} / score={row.get('evidence_score_3', '')}",
                f"- 文本3: {row.get('evidence_text_3', '')}",
                "",
            ]
        )

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def run_evidence_matching(
    change_report_path: str | Path = "outputs/change_report.csv",
    persist_dir: str | Path = "outputs/chroma_db",
    output_dir: str | Path = "outputs",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """执行完整证据匹配流程。"""
    report_df = match_change_report(change_report_path, persist_dir=persist_dir, top_k=5)
    mode = get_runtime_search_mode(persist_dir)
    csv_path, xlsx_path = save_evidence_report(report_df, output_dir)
    summary_path = write_evidence_summary(report_df, output_dir)
    meta = {
        "input_count": len(report_df),
        "mode": mode,
        "strong_count": status_count(report_df, STATUS_STRONG),
        "medium_count": status_count(report_df, STATUS_MEDIUM),
        "weak_count": status_count(report_df, STATUS_WEAK),
        "context_only_count": status_count(report_df, STATUS_CONTEXT_ONLY),
        "missing_count": status_count(report_df, STATUS_MISSING),
        "weak_clue_flag_count": int((report_df.get("weak_clue_flag", "") == "True").sum()) if not report_df.empty else 0,
        "conflict_count": int((report_df.get("conflict_flag", "") == "True").sum()) if not report_df.empty else 0,
        "csv_path": csv_path,
        "xlsx_path": xlsx_path,
        "summary_path": summary_path,
    }
    return report_df, meta
