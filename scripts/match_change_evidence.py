#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""运行变更依据匹配，并输出简单性能日志。"""

from __future__ import annotations

import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from evidence_matcher import run_evidence_matching  # noqa: E402


def main() -> None:
    """命令行入口。"""
    change_report_path = ROOT_DIR / "outputs" / "change_report.csv"
    persist_dir = ROOT_DIR / "outputs" / "chroma_db"
    output_dir = ROOT_DIR / "outputs"

    start_time = time.perf_counter()
    report_df, meta = run_evidence_matching(change_report_path, persist_dir, output_dir)
    end_time = time.perf_counter()
    total_seconds = end_time - start_time
    avg_seconds = total_seconds / len(report_df) if len(report_df) else 0

    print(f"读取 change_report {meta['input_count']} 条")
    print(f"当前 RAG 检索模式：{meta['mode']}")
    print(f"已完成 {len(report_df)} 条证据匹配")
    print(f"强变更依据数量：{meta['strong_count']}")
    print(f"中等变更依据数量：{meta['medium_count']}")
    print(f"弱线索数量：{meta['weak_count']}")
    print(f"仅有配置或规则上下文数量：{meta['context_only_count']}")
    print(f"未找到依据数量：{meta['missing_count']}")
    print(f"weak_clue_flag=True 数量：{meta['weak_clue_flag_count']}")
    print(f"conflict_flag=True 数量：{meta['conflict_count']}")
    print(f"开始时间戳：{start_time:.3f}")
    print(f"结束时间戳：{end_time:.3f}")
    print(f"总耗时：{total_seconds:.3f} 秒")
    print(f"平均每条变更耗时：{avg_seconds:.3f} 秒")
    print("输出文件路径：")
    print(f"- {meta['csv_path']}")
    print(f"- {meta['xlsx_path']}")
    print(f"- {meta['summary_path']}")
    print("")
    print("前 5 条匹配结果预览：")
    if report_df.empty:
        print("无匹配结果")
    else:
        preview_columns = [
            "change_id",
            "change_type",
            "risk_level",
            "evidence_status",
            "conflict_flag",
            "evidence_source_file_1",
            "evidence_source_type_1",
            "evidence_strength_1",
        ]
        print(report_df[preview_columns].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
