#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查证据匹配质量。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT_DIR / "outputs" / "change_report_with_evidence.csv"


def safe(row: pd.Series, field: str) -> str:
    """安全读取字段。"""
    value = row.get(field, "")
    if pd.isna(value):
        return ""
    return str(value).strip()


def print_distribution(df: pd.DataFrame, field: str) -> None:
    """打印字段分布。"""
    print(f"\n{field} 分布：")
    if field not in df.columns:
        print(f"- 字段不存在：{field}")
        return
    for name, count in df[field].fillna("").replace("", "未填写").value_counts().items():
        print(f"- {name}: {count}")


def source_type_distribution(df: pd.DataFrame) -> None:
    """统计 evidence_source_type_1~3 命中分布。"""
    values: list[str] = []
    for idx in range(1, 4):
        field = f"evidence_source_type_{idx}"
        if field in df.columns:
            values.extend([item for item in df[field].fillna("").astype(str).str.strip().tolist() if item])
    print("\nsource_type 命中分布：")
    if not values:
        print("- 无")
        return
    for name, count in pd.Series(values).value_counts().items():
        print(f"- {name}: {count}")


def phase_and_task(row: pd.Series) -> tuple[str, str]:
    """取新版优先的阶段和任务名称。"""
    phase = safe(row, "phase_new") or safe(row, "phase_old")
    task = safe(row, "task_name_new") or safe(row, "task_name_old")
    return phase, task


def print_record(row: pd.Series) -> None:
    """打印一条完整证据链。"""
    phase, task = phase_and_task(row)
    print("-" * 80)
    print(f"change_id: {safe(row, 'change_id')}")
    print(f"change_type: {safe(row, 'change_type')}")
    print(f"business_domain: {safe(row, 'business_domain')}")
    print(f"phase: {phase}")
    print(f"task_name: {task}")
    print(f"field: {safe(row, 'field')}")
    print(f"old_value: {safe(row, 'old_value')}")
    print(f"new_value: {safe(row, 'new_value')}")
    print(f"evidence_status: {safe(row, 'evidence_status')}")
    print(f"final_review_suggestion: {safe(row, 'final_review_suggestion')}")
    for idx in range(1, 4):
        text = safe(row, f"evidence_text_{idx}")[:200]
        print(f"evidence_source_file_{idx}: {safe(row, f'evidence_source_file_{idx}')}")
        print(f"evidence_source_type_{idx}: {safe(row, f'evidence_source_type_{idx}')}")
        print(f"evidence_text_{idx}: {text}")


def main() -> None:
    """命令行入口。"""
    if not REPORT_PATH.exists():
        print(f"未找到 {REPORT_PATH}，请先运行 python scripts/match_change_evidence.py")
        return
    df = pd.read_csv(REPORT_PATH, encoding="utf-8-sig", dtype=str, keep_default_na=False).fillna("")

    print(f"读取证据匹配报告：{len(df)} 条")
    print_distribution(df, "evidence_status")
    source_type_distribution(df)

    print("\n前 10 条高风险且非强变更依据的记录：")
    if {"risk_level", "evidence_status"}.issubset(df.columns):
        subset = df[(df["risk_level"] == "高") & (df["evidence_status"] != "强变更依据")].head(10)
    else:
        subset = pd.DataFrame()
    if subset.empty:
        print("- 无")
    else:
        for _, row in subset.iterrows():
            phase, task = phase_and_task(row)
            print(f"- {safe(row, 'change_id')} | {safe(row, 'business_domain')} | {phase} | {task} | {safe(row, 'field')} | {safe(row, 'evidence_status')}")

    print("\n随机 5 条完整证据链：")
    sample_size = min(5, len(df))
    if sample_size == 0:
        print("- 无")
        return
    for _, row in df.sample(n=sample_size, random_state=42).iterrows():
        print_record(row)


if __name__ == "__main__":
    main()
