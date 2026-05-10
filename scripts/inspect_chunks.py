#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查 chunks_preview.csv 的切分效果。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
PREVIEW_PATH = ROOT_DIR / "outputs" / "chunks_preview.csv"


def main() -> None:
    """打印每种 source_type 的前 3 条 chunk。"""
    if not PREVIEW_PATH.exists():
        print(f"未找到 {PREVIEW_PATH}，请先运行 python scripts/build_knowledge_base.py")
        return

    df = pd.read_csv(PREVIEW_PATH, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    if df.empty:
        print("chunks_preview.csv 为空")
        return

    for source_type, group in df.groupby("source_type"):
        print("=" * 80)
        print(f"source_type: {source_type}")
        for _, row in group.head(3).iterrows():
            print("-" * 80)
            print(f"chunk_id: {row.get('chunk_id', '')}")
            print(f"source_file: {row.get('source_file', '')}")
            print(f"evidence_strength: {row.get('evidence_strength', '')}")
            print(f"text_preview: {row.get('text_preview', '')}")


if __name__ == "__main__":
    main()
