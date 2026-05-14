#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""上传文件管理模块。

上传文件只进入 RAG 知识库，不会自动替换 data/ 下主配置表。
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = ROOT_DIR / "uploads"
MANIFEST_PATH = UPLOAD_DIR / "upload_manifest.csv"
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".md", ".txt", ".pdf"}
CONFIG_REQUIRED_FIELDS = ["business_domain", "phase", "task_name"]
CONFIG_RECOMMENDED_FIELDS = ["owner_name", "responsible_department", "deliverable", "approval_role"]


def safe_filename(filename: str) -> str:
    """清理文件名，避免路径穿越和特殊字符。"""
    name = Path(filename).name
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    clean_stem = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", stem).strip("_") or "upload"
    return f"{clean_stem}{suffix}"


def _read_manifest() -> pd.DataFrame:
    """读取 manifest，不存在则返回空表。"""
    if not MANIFEST_PATH.exists():
        return pd.DataFrame(
            columns=[
                "upload_id",
                "original_filename",
                "saved_filename",
                "source_type",
                "description",
                "upload_time",
                "file_ext",
            ]
        )
    return pd.read_csv(MANIFEST_PATH, encoding="utf-8-sig", dtype=str, keep_default_na=False).fillna("")


def save_uploaded_file(uploaded_file: Any, source_type: str, description: str = "") -> dict[str, str]:
    """保存 Streamlit 上传文件，并写入 uploads/upload_manifest.csv。"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_filename = safe_filename(getattr(uploaded_file, "name", "upload"))
    file_ext = Path(original_filename).suffix.lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型：{file_ext}")

    upload_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    saved_filename = f"{timestamp}_{upload_id}_{original_filename}"
    saved_path = UPLOAD_DIR / saved_filename

    data = uploaded_file.getbuffer() if hasattr(uploaded_file, "getbuffer") else uploaded_file.read()
    saved_path.write_bytes(bytes(data))

    manifest = _read_manifest()
    row = {
        "upload_id": upload_id,
        "original_filename": original_filename,
        "saved_filename": saved_filename,
        "source_type": source_type,
        "description": description,
        "upload_time": datetime.now().isoformat(timespec="seconds"),
        "file_ext": file_ext,
    }
    manifest = pd.concat([manifest, pd.DataFrame([row])], ignore_index=True)
    manifest.to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    row["saved_path"] = str(saved_path)
    return row


def list_uploaded_files() -> list[dict[str, str]]:
    """列出上传记录。"""
    return _read_manifest().to_dict(orient="records")


def _read_table_columns(file_path: Path) -> list[str]:
    """读取表格列名，用于配置表字段校验。"""
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(file_path, encoding="utf-8-sig", nrows=5)
        return [str(column).strip() for column in df.columns]
    if suffix == ".xlsx":
        df = pd.read_excel(file_path, nrows=5)
        return [str(column).strip() for column in df.columns]
    return []


def validate_config_schema(file_path: str | Path) -> dict[str, Any]:
    """校验 old_config / target_config 上传文件是否满足基础配置表字段要求。"""
    path = Path(file_path)
    if path.suffix.lower() not in {".csv", ".xlsx"}:
        return {
            "is_valid": False,
            "message": "配置表校验仅支持 csv/xlsx。该文件只能作为普通知识库资料。",
            "missing_required": CONFIG_REQUIRED_FIELDS,
            "missing_recommended": CONFIG_RECOMMENDED_FIELDS,
        }
    try:
        columns = set(_read_table_columns(path))
    except Exception as exc:  # noqa: BLE001
        return {
            "is_valid": False,
            "message": f"读取表头失败：{exc}。该文件只能作为普通知识库资料。",
            "missing_required": CONFIG_REQUIRED_FIELDS,
            "missing_recommended": CONFIG_RECOMMENDED_FIELDS,
        }

    missing_required = [field for field in CONFIG_REQUIRED_FIELDS if field not in columns]
    missing_recommended = [field for field in CONFIG_RECOMMENDED_FIELDS if field not in columns]
    if missing_required:
        message = "缺少必须字段，该文件只能作为普通知识库资料，当前版本不允许它自动参与差异分析。"
        is_valid = False
    else:
        message = "字段满足基础配置表要求，但当前版本暂不自动替换主配置表。"
        is_valid = True
    return {
        "is_valid": is_valid,
        "message": message,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
    }
