#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""运行 01 vs 03 流程配置差异分析。"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from change_analyzer import analyze_change  # noqa: E402


def main() -> None:
    """命令行入口。"""
    old_path = ROOT_DIR / "data" / "01_system_export_current_config.csv"
    new_path = ROOT_DIR / "data" / "03_target_config_v2.csv"
    output_dir = ROOT_DIR / "outputs"

    report_df, meta = analyze_change(old_path, new_path, output_dir)

    print(f"读取到旧配置 {meta['old_rows']} 行")
    print(f"读取到新配置 {meta['new_rows']} 行")
    print(f"识别到 {meta['changes']} 条差异")
    print("输出文件路径：")
    print(f"- {meta['csv_path']}")
    print(f"- {meta['xlsx_path']}")
    print(f"- {meta['summary_path']}")
    print("")
    print("前 10 条差异预览：")
    if report_df.empty:
        print("无差异")
    else:
        preview_columns = [
            "change_id",
            "change_type",
            "business_domain",
            "phase_new",
            "task_name_new",
            "field",
            "old_value",
            "new_value",
            "risk_level",
        ]
        print(report_df[preview_columns].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
