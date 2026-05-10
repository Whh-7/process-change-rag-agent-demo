#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""流程配置差异分析模块。

对比系统导出的旧版配置表和新版目标配置表，输出结构化变更清单，
用于后续 RAG 证据匹配和人工复核。
"""

from __future__ import annotations

import csv
import html
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd


COMPARE_FIELDS = [
    "business_domain",
    "phase",
    "gate",
    "task_name",
    "task_alias",
    "owner_role",
    "owner_name",
    "responsible_department",
    "collaborate_departments",
    "input_doc",
    "deliverable",
    "approval_role",
    "approval_mode",
    "system_node",
    "trigger_condition",
    "due_rule",
    "is_required",
]

REPORT_FIELDS = [
    "change_id",
    "change_type",
    "match_key",
    "task_id_old",
    "task_id_new",
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

HIGH_RISK_FIELDS = {"owner_name", "responsible_department", "approval_role"}
MEDIUM_RISK_FIELDS = {
    "deliverable",
    "input_doc",
    "system_node",
    "task_alias",
    "due_rule",
    "is_required",
}


def load_config(path: str | Path) -> pd.DataFrame:
    """读取配置 CSV，并兼容 utf-8-sig 编码。"""
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """统一清洗空值和字符串首尾空格，避免误判差异。"""
    normalized = df.copy()
    normalized = normalized.fillna("")
    for column in normalized.columns:
        normalized[column] = normalized[column].astype(str).str.strip()
    return normalized


def build_match_key(df: pd.DataFrame) -> pd.DataFrame:
    """生成匹配键：优先 task_id，否则使用 business_domain + phase + task_name。"""
    result = df.copy()
    required = ["business_domain", "phase", "task_name"]
    for column in ["task_id", *required]:
        if column not in result.columns:
            result[column] = ""

    fallback_key = (
        result["business_domain"].astype(str).str.strip()
        + "|"
        + result["phase"].astype(str).str.strip()
        + "|"
        + result["task_name"].astype(str).str.strip()
    )
    task_id_key = result["task_id"].astype(str).str.strip()
    result["match_key"] = task_id_key.where(task_id_key != "", fallback_key)
    return result


def get_compare_fields(old_df: pd.DataFrame, new_df: pd.DataFrame) -> list[str]:
    """获取实际可比较字段；缺失字段自动跳过并打印提示。"""
    available: list[str] = []
    for field in COMPARE_FIELDS:
        missing = []
        if field not in old_df.columns:
            missing.append("旧配置 old config")
        if field not in new_df.columns:
            missing.append("新配置 new config")
        if missing:
            print(f"跳过缺失字段 / Skip missing field: {field} ({', '.join(missing)})")
            continue
        available.append(field)
    return available


def row_value(row: pd.Series | None, field: str) -> str:
    """安全读取行字段。"""
    if row is None or field not in row.index:
        return ""
    value = row[field]
    return "" if pd.isna(value) else str(value).strip()


def choose_context(old_row: pd.Series | None, new_row: pd.Series | None) -> tuple[str, str, str]:
    """为报告选择业务域、阶段、任务名称上下文，优先使用新版。"""
    business_domain = row_value(new_row, "business_domain") or row_value(old_row, "business_domain")
    phase = row_value(new_row, "phase") or row_value(old_row, "phase")
    task_name = row_value(new_row, "task_name") or row_value(old_row, "task_name")
    return business_domain, phase, task_name


def risk_level(change_type: str, field: str) -> str:
    """根据变更类型和字段判断风险等级。"""
    if change_type in {"新增任务", "删除任务"}:
        return "高"
    if field in HIGH_RISK_FIELDS:
        return "高"
    if field in MEDIUM_RISK_FIELDS:
        return "中"
    return "低"


def build_evidence_query(
    business_domain: str,
    phase: str,
    task_name: str,
    field: str,
    old_value: str,
    new_value: str,
    change_type: str,
) -> str:
    """生成用于 RAG 检索的中文 query。"""
    field_label = {
        "owner_name": "负责人",
        "responsible_department": "责任部门",
        "deliverable": "交付文档",
        "input_doc": "输入文档",
        "approval_role": "审批角色",
        "due_rule": "时间规则",
        "task_name": "任务名称",
        "task_alias": "任务别名",
        "system_node": "系统节点",
    }.get(field, field or change_type)

    values = " ".join(value for value in [old_value, new_value] if value)
    if change_type == "新增任务":
        return f"{business_domain} {phase} {task_name} 新增任务 责任部门 负责人 交付文档 审批角色 变更依据".strip()
    if change_type == "删除任务":
        return f"{business_domain} {phase} {task_name} 删除任务 废止依据 会议纪要".strip()
    return f"{business_domain} {phase} {task_name} {field_label} {values} 变更依据".strip()


def build_review_suggestion(change_type: str, field: str) -> str:
    """根据变更类型和字段生成复核建议。"""
    if change_type == "新增任务":
        return "建议确认责任部门、负责人、交付文档、审批角色是否完整。"
    if change_type == "删除任务":
        return "建议确认该节点是否确实废止，避免误删正式流程配置。"
    if field == "owner_name":
        return "建议核对任命调整通知或会议纪要。"
    if field == "responsible_department":
        return "建议核对部门更新表和会议纪要。"
    if field == "deliverable":
        return "建议核对流程变更会议纪要或部门更新表。"
    return "建议人工复核变更依据。"


def make_change_record(
    change_no: int,
    change_type: str,
    match_key: str,
    old_row: pd.Series | None,
    new_row: pd.Series | None,
    field: str,
    old_value: str,
    new_value: str,
) -> dict[str, str]:
    """组装一条结构化差异记录。"""
    business_domain, phase, task_name = choose_context(old_row, new_row)
    level = risk_level(change_type, field)
    return {
        "change_id": f"CHG{change_no:04d}",
        "change_type": change_type,
        "match_key": match_key,
        "task_id_old": row_value(old_row, "task_id"),
        "task_id_new": row_value(new_row, "task_id"),
        "business_domain": business_domain,
        "phase_old": row_value(old_row, "phase"),
        "phase_new": row_value(new_row, "phase"),
        "task_name_old": row_value(old_row, "task_name"),
        "task_name_new": row_value(new_row, "task_name"),
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "risk_level": level,
        "evidence_query": build_evidence_query(
            business_domain, phase, task_name, field, old_value, new_value, change_type
        ),
        "review_suggestion": build_review_suggestion(change_type, field),
    }


def dataframe_by_key(df: pd.DataFrame) -> dict[str, pd.Series]:
    """按 match_key 构造索引；重复键保留第一条并提示。"""
    records: dict[str, pd.Series] = {}
    duplicated = df[df["match_key"].duplicated(keep=False)]["match_key"].unique().tolist()
    if duplicated:
        preview = "、".join(duplicated[:5])
        print(f"发现重复匹配键 / Duplicate match_key found, keep first: {preview}")
    for _, row in df.iterrows():
        key = row["match_key"]
        if key not in records:
            records[key] = row
    return records


def compare_configs(old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """对比旧版和新版配置，输出差异 DataFrame。"""
    old_df = build_match_key(normalize_dataframe(old_df))
    new_df = build_match_key(normalize_dataframe(new_df))
    compare_fields = get_compare_fields(old_df, new_df)

    old_map = dataframe_by_key(old_df)
    new_map = dataframe_by_key(new_df)
    all_keys = sorted(set(old_map) | set(new_map))

    changes: list[dict[str, str]] = []
    change_no = 1
    for key in all_keys:
        old_row = old_map.get(key)
        new_row = new_map.get(key)
        if old_row is None and new_row is not None:
            changes.append(make_change_record(change_no, "新增任务", key, None, new_row, "", "", "新增任务"))
            change_no += 1
            continue
        if old_row is not None and new_row is None:
            changes.append(make_change_record(change_no, "删除任务", key, old_row, None, "", "删除任务", ""))
            change_no += 1
            continue
        if old_row is None or new_row is None:
            continue

        for field in compare_fields:
            old_value = row_value(old_row, field)
            new_value = row_value(new_row, field)
            if old_value != new_value:
                changes.append(
                    make_change_record(
                        change_no, "字段变更", key, old_row, new_row, field, old_value, new_value
                    )
                )
                change_no += 1

    return pd.DataFrame(changes, columns=REPORT_FIELDS)


def col_name(index: int) -> str:
    """把从 1 开始的列号转换为 Excel 列名。"""
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def write_simple_xlsx(path: Path, rows: Iterable[dict[str, str]], fields: list[str]) -> None:
    """使用标准库写入简单 xlsx，作为 pandas Excel 引擎缺失时的兜底。"""
    table = [fields] + [[str(row.get(field, "")) for field in fields] for row in rows]
    sheet_rows = []
    for r_idx, row in enumerate(table, 1):
        cells = []
        for c_idx, value in enumerate(row, 1):
            ref = f"{col_name(c_idx)}{r_idx}"
            safe_value = html.escape(value, quote=False)
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{safe_value}</t></is></c>')
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    dimension = f"A1:{col_name(len(fields))}{len(table)}"
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension}"/><sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="change_report" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", content_types_xml)
        xlsx.writestr("_rels/.rels", rels_xml)
        xlsx.writestr("xl/workbook.xml", workbook_xml)
        xlsx.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        xlsx.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def save_change_report(report_df: pd.DataFrame, output_dir: str | Path) -> tuple[Path, Path]:
    """保存 change_report.csv 和 change_report.xlsx。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    csv_path = output_path / "change_report.csv"
    xlsx_path = output_path / "change_report.xlsx"

    report_df.to_csv(csv_path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    try:
        report_df.to_excel(xlsx_path, index=False)
    except Exception as exc:
        print(f"pandas 写入 xlsx 失败，使用标准库兜底 / Fallback xlsx writer: {exc}")
        write_simple_xlsx(xlsx_path, report_df.to_dict("records"), REPORT_FIELDS)
    return csv_path, xlsx_path


def value_counts_lines(report_df: pd.DataFrame, column: str) -> list[str]:
    """生成 markdown 统计列表。"""
    if report_df.empty or column not in report_df.columns:
        return ["- 无"]
    counts = report_df[column].replace("", "未填写").value_counts()
    return [f"- {name}: {count}" for name, count in counts.items()]


def write_summary(report_df: pd.DataFrame, output_dir: str | Path) -> Path:
    """写入 change_summary.md。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary_path = output_path / "change_summary.md"

    total = len(report_df)
    added = int((report_df["change_type"] == "新增任务").sum()) if not report_df.empty else 0
    deleted = int((report_df["change_type"] == "删除任务").sum()) if not report_df.empty else 0
    field_changed = int((report_df["change_type"] == "字段变更").sum()) if not report_df.empty else 0

    lines = [
        "# 流程配置差异分析摘要",
        "",
        f"- 总变更数量: {total}",
        f"- 新增任务数量: {added}",
        f"- 删除任务数量: {deleted}",
        f"- 字段变更数量: {field_changed}",
        "",
        "## 风险等级统计",
        "",
        *value_counts_lines(report_df, "risk_level"),
        "",
        "## 按业务域统计",
        "",
        *value_counts_lines(report_df, "business_domain"),
        "",
        "## 按阶段统计",
        "",
        *value_counts_lines(report_df, "phase_new"),
        "",
        "## 按字段统计",
        "",
        *value_counts_lines(report_df, "field"),
        "",
        "## 前 10 条高风险变化示例",
        "",
    ]

    high_risk = report_df[report_df["risk_level"] == "高"].head(10) if not report_df.empty else report_df
    if high_risk.empty:
        lines.append("- 无")
    else:
        for _, row in high_risk.iterrows():
            lines.append(
                f"- {row['change_id']} {row['change_type']} | {row['business_domain']} | "
                f"{row['phase_new'] or row['phase_old']} | {row['task_name_new'] or row['task_name_old']} | "
                f"{row['field'] or '任务'} | {row['old_value']} -> {row['new_value']}"
            )

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def analyze_change(
    old_path: str | Path,
    new_path: str | Path,
    output_dir: str | Path,
) -> tuple[pd.DataFrame, dict[str, Path | int]]:
    """完整执行读取、对比、保存和摘要生成。"""
    old_df = load_config(old_path)
    new_df = load_config(new_path)
    report_df = compare_configs(old_df, new_df)
    csv_path, xlsx_path = save_change_report(report_df, output_dir)
    summary_path = write_summary(report_df, output_dir)
    meta: dict[str, Path | int] = {
        "old_rows": len(old_df),
        "new_rows": len(new_df),
        "changes": len(report_df),
        "csv_path": csv_path,
        "xlsx_path": xlsx_path,
        "summary_path": summary_path,
    }
    return report_df, meta
