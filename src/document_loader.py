#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""多格式资料加载与 chunk 切分。

本模块只读取原始证据资料，负责把 CSV、XLSX、Markdown、PDF 转换为统一
chunk 结构，供离线 RAG 检索模块建库使用。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import pandas as pd


MAX_CHARS = 800
SPLIT_CHARS = 600
OVERLAP_CHARS = 80


@dataclass
class DocumentChunk:
    """统一 chunk 数据结构。"""

    chunk_id: str
    text: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """转换为可 JSON 序列化的 dict。"""
        return asdict(self)


SOURCE_RULES = {
    "01_system_export_current_config": ("old_config", "strong"),
    "02_department_update_feishu": ("department_update", "medium"),
    "03_target_config_v2": ("target_config", "strong"),
    "04_appointment_adjustment_notice": ("appointment_notice", "strong"),
    "05_process_change_meeting_minutes": ("meeting_minutes", "strong"),
    "06_chat_change_messages": ("chat_message", "weak"),
    "07_process_rule_manual": ("rule_manual", "strong"),
}


def normalize_text(value: Any) -> str:
    """统一处理空值和首尾空格。"""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """清洗表格中的空值和字符串空格。"""
    result = df.fillna("").copy()
    for column in result.columns:
        result[column] = result[column].map(normalize_text)
    return result


def get_source_info(path: Path) -> tuple[str, str]:
    """根据文件名判断 source_type 和 evidence_strength。"""
    stem = path.stem
    for prefix, source_info in SOURCE_RULES.items():
        if stem.startswith(prefix):
            return source_info
    if path.suffix.lower() == ".pdf":
        return "pdf_document", "medium"
    return "document", "medium"


def safe_get(row: pd.Series, field: str) -> str:
    """安全读取表格行字段，字段不存在时返回空字符串。"""
    if field not in row.index:
        return ""
    return normalize_text(row[field])


def warn_missing_fields(source_file: str, columns: set[str], expected_fields: list[str]) -> None:
    """提示缺失字段，但不中断处理。"""
    missing = [field for field in expected_fields if field not in columns]
    if missing:
        print(f"字段缺失，已跳过 / Missing fields skipped: {source_file}: {', '.join(missing)}")


def table_row_to_text(row: pd.Series, source_type: str) -> str:
    """把表格一行转换为自然语言证据文本。"""
    if source_type == "old_config":
        return (
            f"【系统导出旧版配置】业务域：{safe_get(row, 'business_domain')}；"
            f"阶段：{safe_get(row, 'phase')}；任务：{safe_get(row, 'task_name')}；"
            f"责任部门：{safe_get(row, 'responsible_department')}；"
            f"负责人：{safe_get(row, 'owner_name')}；"
            f"交付文档：《{safe_get(row, 'deliverable')}》；"
            f"审批角色：{safe_get(row, 'approval_role')}；"
            f"版本：{safe_get(row, 'version')}；生效日期：{safe_get(row, 'effective_date')}。"
        )
    if source_type == "target_config":
        return (
            f"【新版目标配置】业务域：{safe_get(row, 'business_domain')}；"
            f"阶段：{safe_get(row, 'phase')}；任务：{safe_get(row, 'task_name')}；"
            f"责任部门：{safe_get(row, 'responsible_department')}；"
            f"负责人：{safe_get(row, 'owner_name')}；"
            f"交付文档：《{safe_get(row, 'deliverable')}》；"
            f"审批角色：{safe_get(row, 'approval_role')}；"
            f"版本：{safe_get(row, 'version')}；生效日期：{safe_get(row, 'effective_date')}。"
        )
    if source_type == "department_update":
        return (
            f"【部门在线更新表】提交部门：{safe_get(row, 'submit_department')}；"
            f"业务域：{safe_get(row, 'business_domain')}；"
            f"关联阶段：{safe_get(row, 'related_phase')}；"
            f"关联任务：{safe_get(row, 'related_task')}；"
            f"变更类型：{safe_get(row, 'update_type')}；"
            f"原配置：{safe_get(row, 'old_config') or '无'}；"
            f"建议调整：{safe_get(row, 'new_config')}；"
            f"原因：{safe_get(row, 'reason')}；状态：{safe_get(row, 'status')}；"
            f"证据线索：{safe_get(row, 'evidence_hint')}；备注：{safe_get(row, 'remark')}。"
        )
    values = [f"{column}：{safe_get(row, column)}" for column in row.index if safe_get(row, column)]
    return f"【表格资料】{source_type}；" + "；".join(values)


def table_metadata(row: pd.Series, path: Path, source_type: str, evidence_strength: str, row_index: int) -> dict[str, Any]:
    """生成表格 chunk metadata。"""
    metadata: dict[str, Any] = {
        "source_file": path.name,
        "source_type": source_type,
        "evidence_strength": evidence_strength,
        "row_index": row_index,
    }
    if source_type in {"old_config", "target_config"}:
        fields = [
            "business_domain",
            "phase",
            "task_name",
            "task_id",
            "responsible_department",
            "owner_name",
        ]
    elif source_type == "department_update":
        fields = [
            "submit_department",
            "business_domain",
            "related_phase",
            "related_task",
            "update_type",
            "status",
        ]
    else:
        fields = list(row.index)
    for field in fields:
        metadata[field] = safe_get(row, field)
    return metadata


def load_table_file(path: Path, chunk_prefix: str) -> list[DocumentChunk]:
    """加载 CSV 或 XLSX，每一行转换为一个 chunk。"""
    source_type, evidence_strength = get_source_info(path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    else:
        try:
            df = pd.read_excel(path, dtype=str, keep_default_na=False)
        except Exception as exc:
            print(f"跳过 xlsx，读取失败 / Skip xlsx read failed: {path.name}: {exc}")
            return []
    df = normalize_dataframe(df)

    expected = []
    if source_type in {"old_config", "target_config"}:
        expected = ["business_domain", "phase", "task_name", "task_id", "responsible_department", "owner_name"]
    elif source_type == "department_update":
        expected = ["submit_department", "business_domain", "related_phase", "related_task", "update_type", "status"]
    warn_missing_fields(path.name, set(df.columns), expected)

    chunks: list[DocumentChunk] = []
    for idx, row in df.iterrows():
        row_index = int(idx) + 1
        text = table_row_to_text(row, source_type)
        metadata = table_metadata(row, path, source_type, evidence_strength, row_index)
        chunks.append(DocumentChunk(f"{chunk_prefix}-{row_index:05d}", text, metadata))
    return chunks


def is_table_separator(line: str) -> bool:
    """判断 markdown 表格分隔行。"""
    stripped = line.strip()
    return bool(stripped.startswith("|") and set(stripped.replace("|", "").replace(" ", "")) <= {"-", ":"})


def split_long_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """长文本按固定长度切分，并保留少量 overlap。"""
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    parts = []
    start = 0
    while start < len(text):
        end = min(start + SPLIT_CHARS, len(text))
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(0, end - OVERLAP_CHARS)
    return [part for part in parts if part]


def split_markdown_blocks(markdown: str) -> list[str]:
    """按标题、段落和表格行切分 markdown。"""
    lines = markdown.splitlines()
    blocks: list[str] = []
    current_title = ""
    paragraph: list[str] = []
    table_header = ""

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(item.strip() for item in paragraph if item.strip())
            if current_title:
                text = f"{current_title}\n{text}"
            blocks.extend(split_long_text(text))
            paragraph = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            table_header = ""
            continue
        if stripped.startswith("#"):
            flush_paragraph()
            current_title = stripped.lstrip("#").strip()
            continue
        if stripped.startswith("|"):
            flush_paragraph()
            if is_table_separator(stripped):
                continue
            if not table_header:
                table_header = stripped
                blocks.extend(split_long_text(f"{current_title}\n{stripped}" if current_title else stripped))
            else:
                row_text = f"{current_title}\n{table_header}\n{stripped}" if current_title else f"{table_header}\n{stripped}"
                blocks.extend(split_long_text(row_text))
            continue
        paragraph.append(stripped)

    flush_paragraph()
    return blocks


def extract_simple_metadata(text: str) -> dict[str, str]:
    """从文本中尽量抽取常见字段，抽不到则返回空字段。"""
    metadata: dict[str, str] = {}
    patterns = {
        "business_domain": r"(?:业务域|业务域/产品域)[：:]\s*([^；|\n]+)",
        "phase": r"(?:阶段|关联阶段)[：:]\s*([^；|\n]+)",
        "task_name": r"(?:任务名称|任务|关联任务)[：:]\s*([^；|\n]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            metadata[key] = match.group(1).strip()
    return metadata


def load_markdown_file(path: Path, chunk_prefix: str) -> list[DocumentChunk]:
    """加载 markdown 并切分为 chunk。"""
    source_type, evidence_strength = get_source_info(path)
    content = path.read_text(encoding="utf-8")
    blocks = split_markdown_blocks(content)
    chunks: list[DocumentChunk] = []
    for idx, block in enumerate(blocks, 1):
        metadata: dict[str, Any] = {
            "source_file": path.name,
            "source_type": source_type,
            "evidence_strength": evidence_strength,
            "section_index": idx,
        }
        metadata.update(extract_simple_metadata(block))
        chunks.append(DocumentChunk(f"{chunk_prefix}-{idx:05d}", block, metadata))
    return chunks


def load_pdf_file(path: Path, chunk_prefix: str) -> list[DocumentChunk]:
    """尝试加载 PDF；依赖缺失或读取失败时提示并跳过。"""
    try:
        from pypdf import PdfReader
    except Exception:
        print(f"跳过 PDF，未安装 pypdf / Skip PDF because pypdf is not installed: {path.name}")
        return []

    try:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as exc:
        print(f"跳过 PDF，读取失败 / Skip PDF read failed: {path.name}: {exc}")
        return []

    if not text:
        print(f"跳过 PDF，无可提取文本 / Skip empty PDF text: {path.name}")
        return []

    source_type, evidence_strength = get_source_info(path)
    chunks: list[DocumentChunk] = []
    for idx, block in enumerate(split_long_text(text), 1):
        metadata = {
            "source_file": path.name,
            "source_type": source_type,
            "evidence_strength": evidence_strength,
            "section_index": idx,
        }
        chunks.append(DocumentChunk(f"{chunk_prefix}-{idx:05d}", block, metadata))
    return chunks


def select_source_files(data_dir: str | Path) -> tuple[list[Path], list[Path]]:
    """选择要加载的源文件，默认 CSV 优先并跳过同名 XLSX。"""
    data_path = Path(data_dir)
    files = sorted(path for path in data_path.iterdir() if path.is_file())
    csv_stems = {path.stem for path in files if path.suffix.lower() == ".csv"}
    selected: list[Path] = []
    skipped_xlsx: list[Path] = []
    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".xlsx" and path.stem in csv_stems:
            skipped_xlsx.append(path)
            continue
        if suffix in {".csv", ".xlsx", ".md", ".pdf"}:
            selected.append(path)
    return selected, skipped_xlsx


def load_documents(data_dir: str | Path = "data") -> tuple[list[DocumentChunk], dict[str, Any]]:
    """读取 data 目录下所有支持格式文件，并返回 chunk 与统计信息。"""
    selected_files, skipped_xlsx = select_source_files(data_dir)
    chunks: list[DocumentChunk] = []
    loaded_files: list[str] = []

    for file_no, path in enumerate(selected_files, 1):
        prefix = f"DOC{file_no:03d}"
        suffix = path.suffix.lower()
        file_chunks: list[DocumentChunk]
        if suffix in {".csv", ".xlsx"}:
            file_chunks = load_table_file(path, prefix)
        elif suffix == ".md":
            file_chunks = load_markdown_file(path, prefix)
        elif suffix == ".pdf":
            file_chunks = load_pdf_file(path, prefix)
        else:
            file_chunks = []

        if file_chunks:
            loaded_files.append(path.name)
            chunks.extend(file_chunks)

    stats = {
        "loaded_files": loaded_files,
        "loaded_file_count": len(loaded_files),
        "skipped_duplicate_xlsx": [path.name for path in skipped_xlsx],
        "skipped_duplicate_xlsx_count": len(skipped_xlsx),
        "chunk_count": len(chunks),
    }
    return chunks, stats


def write_chunks_preview(chunks: list[DocumentChunk], output_path: str | Path) -> Path:
    """输出便于人工检查的 chunks_preview.csv。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for chunk in chunks:
        rows.append(
            {
                "chunk_id": chunk.chunk_id,
                "source_file": chunk.metadata.get("source_file", ""),
                "source_type": chunk.metadata.get("source_type", ""),
                "evidence_strength": chunk.metadata.get("evidence_strength", ""),
                "text_preview": chunk.text[:220].replace("\n", " "),
                "metadata_json": json.dumps(chunk.metadata, ensure_ascii=False),
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path
