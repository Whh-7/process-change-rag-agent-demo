#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Streamlit 页面：流程配置变更 RAG + Agent 助手 Demo。

页面只负责展示和调度已有模块，不改动 data 数据；如启用 LLM，也只用于回答表达和报告润色。
"""

from __future__ import annotations

import subprocess
import sys
import traceback
import gc
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_router import AgentRouter  # noqa: E402
from llm_client import get_llm_config  # noqa: E402
from rag_engine import reset_rag_cache, search_docs  # noqa: E402


STATUS_CHECKS = [
    {
        "module": "基础数据",
        "path": "data/01_system_export_current_config.csv",
        "command": "python scripts/generate_mock_data.py",
    },
    {
        "module": "基础数据",
        "path": "data/03_target_config_v2.csv",
        "command": "python scripts/generate_mock_data.py",
    },
    {
        "module": "差异分析",
        "path": "outputs/change_report.csv",
        "command": "python scripts/run_change_analysis.py",
    },
    {
        "module": "RAG 建库",
        "path": "outputs/chunks_preview.csv",
        "command": "python scripts/build_knowledge_base.py",
    },
    {
        "module": "RAG 建库",
        "path": "outputs/chroma_db",
        "command": "python scripts/build_knowledge_base.py",
    },
    {
        "module": "证据匹配",
        "path": "outputs/change_report_with_evidence.csv",
        "command": "python scripts/match_change_evidence.py",
    },
    {
        "module": "证据匹配",
        "path": "outputs/evidence_summary.md",
        "command": "python scripts/match_change_evidence.py",
    },
]


def load_csv_safe(path: Path) -> pd.DataFrame:
    """安全读取 CSV，缺失或读取失败时返回空 DataFrame 并提示。"""
    if not path.exists():
        st.warning(f"未找到文件：`{path.relative_to(ROOT_DIR)}`")
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False).fillna("")
    except Exception as exc:  # noqa: BLE001
        st.error(f"读取 `{path.relative_to(ROOT_DIR)}` 失败：{exc}")
        return pd.DataFrame()


def read_text_safe(path: Path) -> str:
    """安全读取文本文件。"""
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        st.error(f"读取 `{path.relative_to(ROOT_DIR)}` 失败：{exc}")
        return ""


def parse_eval_summary_meta(path: Path) -> dict[str, str]:
    """从评估 summary 顶部解析 retrieval_mode / generated_at 等信息。"""
    text = read_text_safe(path)
    meta: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("- "):
            continue
        body = line[2:]
        if ":" not in body:
            continue
        key, value = body.split(":", 1)
        key = key.strip()
        if key in {"retrieval_mode", "use_rerank", "generated_at", "python_executable"}:
            meta[key] = value.strip()
    return meta


def run_script(script_relative: str) -> subprocess.CompletedProcess[str] | None:
    """通过当前 Python 解释器运行项目脚本，并捕获输出。"""
    script_path = ROOT_DIR / script_relative
    if not script_path.exists():
        st.error(f"脚本不存在：`{script_relative}`")
        return None
    try:
        return subprocess.run(
            [sys.executable, str(script_path)],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"运行 `{script_relative}` 失败：{exc}")
        return None


def show_script_result(result: subprocess.CompletedProcess[str] | None) -> None:
    """展示脚本运行结果。"""
    if result is None:
        return
    if result.returncode == 0:
        st.success("脚本运行完成。")
    else:
        st.error(f"脚本运行失败，退出码：{result.returncode}")
    if result.stdout:
        with st.expander("stdout", expanded=result.returncode != 0):
            st.code(result.stdout)
    if result.stderr:
        with st.expander("stderr", expanded=True):
            st.code(result.stderr)


def value_counts_frame(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """生成可用于表格和柱状图的统计 DataFrame。"""
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=[column, "数量"])
    counts = df[column].replace("", "未填写").value_counts().reset_index()
    counts.columns = [column, "数量"]
    return counts


def show_count_chart(df: pd.DataFrame, column: str, title: str) -> None:
    """展示字段分布柱状图，缺字段时给出提示。"""
    st.subheader(title)
    counts = value_counts_frame(df, column)
    if counts.empty:
        st.info(f"缺少字段 `{column}`，无法统计。")
        return
    st.bar_chart(counts.set_index(column))


def multiselect_filter(df: pd.DataFrame, column: str, label: str, key_prefix: str) -> list[str]:
    """根据字段生成多选筛选器，缺字段时返回空列表。"""
    if df.empty or column not in df.columns:
        st.caption(f"缺少字段 `{column}`，跳过该筛选。")
        return []
    options = sorted([value for value in df[column].dropna().unique().tolist() if value != ""])
    return st.multiselect(label, options=options, default=[], key=f"{key_prefix}_{column}_filter")


def apply_filters(df: pd.DataFrame, filters: dict[str, list[str]]) -> pd.DataFrame:
    """按多个字段筛选 DataFrame。"""
    filtered = df.copy()
    for column, selected in filters.items():
        if selected and column in filtered.columns:
            filtered = filtered[filtered[column].isin(selected)]
    return filtered


def bool_filter(df: pd.DataFrame, column: str, label: str, key_prefix: str) -> str:
    """生成 True/False/全部 筛选器。"""
    if df.empty or column not in df.columns:
        st.caption(f"缺少字段 `{column}`，跳过该筛选。")
        return "全部"
    return st.selectbox(label, ["全部", "True", "False"], key=f"{key_prefix}_{column}_bool_filter")


def render_tab(tab_name: str, render_func) -> None:
    """为每个 Tab 增加保护，避免单个页面异常拖垮整页。"""
    try:
        render_func()
    except Exception as exc:  # noqa: BLE001
        st.error(f"{tab_name} 加载失败：{exc}")
        with st.expander("查看错误详情"):
            st.code(traceback.format_exc())


def is_chroma_permission_error(result: subprocess.CompletedProcess[str] | None) -> bool:
    """判断脚本输出是否包含 Windows 下 ChromaDB 文件占用错误。"""
    if result is None:
        return False
    text = f"{result.stdout}\n{result.stderr}"
    return "PermissionError" in text and ("WinError 32" in text or "chroma_db" in text)


def normalize_bool_series(series: pd.Series) -> pd.Series:
    """兼容字符串和布尔类型的 True 判断。"""
    return series.astype(str).str.lower().isin(["true", "1", "yes", "是"])


def add_phase_task_columns(df: pd.DataFrame) -> pd.DataFrame:
    """为页面展示补充 phase/task_name 便捷列。"""
    if df.empty:
        return df
    out = df.copy()
    if "phase" not in out.columns:
        phase_new = out["phase_new"] if "phase_new" in out.columns else pd.Series("", index=out.index)
        phase_old = out["phase_old"] if "phase_old" in out.columns else pd.Series("", index=out.index)
        out["phase"] = phase_new.where(phase_new.astype(str) != "", phase_old)
    if "task_name" not in out.columns:
        task_new = out["task_name_new"] if "task_name_new" in out.columns else pd.Series("", index=out.index)
        task_old = out["task_name_old"] if "task_name_old" in out.columns else pd.Series("", index=out.index)
        out["task_name"] = task_new.where(task_new.astype(str) != "", task_old)
    return out


def show_status_tab() -> None:
    """Tab1：展示关键文件和模块状态，并提供脚本运行按钮。"""
    st.header("系统状态")
    with st.expander("LLM 可选生成层状态", expanded=True):
        show_llm_status()
    rows = []
    for item in STATUS_CHECKS:
        path = ROOT_DIR / item["path"]
        rows.append(
            {
                "模块": item["module"],
                "文件": item["path"],
                "状态": "已完成" if path.exists() else "未生成",
                "建议命令": "" if path.exists() else item["command"],
            }
        )
    status_df = pd.DataFrame(rows)
    st.dataframe(status_df, use_container_width=True, hide_index=True)

    missing = status_df[status_df["状态"] == "未生成"]
    if missing.empty:
        st.success("关键输出文件均已生成，可以直接进行问答、检索和报告查看。")
    else:
        st.warning("存在未生成文件，请按建议命令补齐对应步骤。")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("运行差异分析", key="status_tab_run_change_analysis", use_container_width=True):
            with st.spinner("正在运行差异分析..."):
                show_script_result(run_script("scripts/run_change_analysis.py"))
    with col2:
        st.warning("如果当前页面已经使用过 RAG 检索，Windows 下重建 ChromaDB 可能因为文件占用失败。建议关闭页面后在终端运行 `python scripts/build_knowledge_base.py`。")
        if st.button("构建知识库", key="status_tab_build_kb", use_container_width=True):
            with st.spinner("正在构建知识库..."):
                reset_rag_cache()
                gc.collect()
                result = run_script("scripts/build_knowledge_base.py")
                if is_chroma_permission_error(result):
                    st.error("ChromaDB 目录可能正在被当前 Streamlit 进程占用，请关闭页面后在终端运行构建命令。")
                    with st.expander("查看脚本输出"):
                        if result and result.stdout:
                            st.code(result.stdout)
                        if result and result.stderr:
                            st.code(result.stderr)
                else:
                    show_script_result(result)
    with col3:
        if st.button("运行证据匹配", key="status_tab_match_evidence", use_container_width=True):
            with st.spinner("正在运行证据匹配..."):
                show_script_result(run_script("scripts/match_change_evidence.py"))


def show_sources_table(sources: list[dict[str, Any]]) -> None:
    """展示 Agent 或 RAG 返回的来源列表。"""
    if not sources:
        st.info("暂无来源。")
        return
    rows = []
    for source in sources:
        rows.append(
            {
                "source_file": source.get("source_file", ""),
                "source_type": source.get("source_type", ""),
                "evidence_strength": source.get("evidence_strength", ""),
                "score": source.get("score", ""),
                "rerank_score": source.get("rerank_score", ""),
                "rerank_reason": source.get("rerank_reason", ""),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def show_llm_status() -> None:
    """展示 LLM 配置状态，不显示 API key。"""
    config = get_llm_config()
    rows = [
        {"配置项": "LLM_ENABLE", "值": str(config.get("enable", False))},
        {"配置项": "LLM_PROVIDER", "值": str(config.get("provider", ""))},
        {"配置项": "LLM_BASE_URL", "值": str(config.get("base_url", ""))},
        {"配置项": "LLM_MODEL", "值": str(config.get("model", ""))},
        {"配置项": "是否检测到 API key", "值": "是" if config.get("has_api_key") else "否"},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def show_agent_tab() -> None:
    """Tab2：调用轻量 Agent Router 做规则化问答。"""
    st.header("Agent 问答")
    examples = [
        "聊天记录能不能作为正式变更依据？",
        "旧配置表和新版配置表能不能证明变更原因？",
        "新旧配置有哪些变化？",
        "哪些变化缺少强变更依据？",
        "生成一份本次流程配置变更复核建议报告。",
        "新增任务节点需要校验哪些字段？",
    ]
    if "agent_query" not in st.session_state:
        st.session_state.agent_query = examples[0]

    st.caption("推荐问题")
    cols = st.columns(3)
    for index, question in enumerate(examples):
        with cols[index % 3]:
            if st.button(question, key=f"agent_example_{index}", use_container_width=True):
                st.session_state.agent_query = question

    query = st.text_area("请输入问题", key="agent_query", height=90)
    if st.button("提交问题", key="agent_tab_submit", type="primary"):
        if not query.strip():
            st.warning("请输入问题。")
            return
        with st.spinner("Agent 正在路由并生成回答..."):
            try:
                result = AgentRouter(ROOT_DIR).route(query)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Agent 调用失败：{exc}")
                return
        st.markdown("**intent**")
        st.code(str(result.get("intent", "")))
        st.markdown("**tools_used**")
        st.code(", ".join(result.get("tools_used", [])))
        st.markdown("**llm_used**")
        st.code(str(result.get("llm_used", False)))
        fallback_reason = result.get("fallback_reason", "")
        if fallback_reason:
            st.markdown("**fallback_reason**")
            st.info(str(fallback_reason))
        st.markdown("**answer**")
        st.markdown(str(result.get("answer", "")))
        st.markdown("**sources**")
        show_sources_table(result.get("sources", []))


def show_change_report_tab() -> None:
    """Tab3：展示 01 vs 03 差异分析结果。"""
    st.header("变更清单")
    path = ROOT_DIR / "outputs/change_report.csv"
    if not path.exists():
        st.warning("未找到 `outputs/change_report.csv`，请先运行：`python scripts/run_change_analysis.py`")
        return
    df = load_csv_safe(path)
    if df.empty:
        return

    st.metric("总变更数量", len(df))
    cols = st.columns(3)
    with cols[0]:
        show_count_chart(df, "change_type", "按 change_type 统计")
    with cols[1]:
        show_count_chart(df, "risk_level", "按配置影响等级统计")
    with cols[2]:
        show_count_chart(df, "business_domain", "按 business_domain 统计")

    with st.expander("筛选条件", expanded=True):
        fcols = st.columns(4)
        with fcols[0]:
            change_type = multiselect_filter(df, "change_type", "change_type", "change_report_tab_change_type")
        with fcols[1]:
            risk_level = multiselect_filter(df, "risk_level", "配置影响等级", "change_report_tab_risk")
        with fcols[2]:
            business_domain = multiselect_filter(df, "business_domain", "business_domain", "change_report_tab_domain")
        with fcols[3]:
            field = multiselect_filter(df, "field", "field", "change_report_tab_field")

    filtered = apply_filters(
        df,
        {
            "change_type": change_type,
            "risk_level": risk_level,
            "business_domain": business_domain,
            "field": field,
        },
    )
    st.caption(f"当前显示 {len(filtered)} / {len(df)} 条")
    st.dataframe(filtered, use_container_width=True, hide_index=True)


def show_evidence_tab() -> None:
    """Tab4：展示证据匹配结果和筛选表格。"""
    st.header("证据匹配")
    path = ROOT_DIR / "outputs/change_report_with_evidence.csv"
    if not path.exists():
        st.warning("未找到 `outputs/change_report_with_evidence.csv`，请先运行：`python scripts/match_change_evidence.py`")
        return
    df = add_phase_task_columns(load_csv_safe(path))
    if df.empty:
        return
    if "impact_level" not in df.columns and "risk_level" in df.columns:
        df["impact_level"] = df["risk_level"]

    cols = st.columns(4)
    with cols[0]:
        st.metric("总记录数", len(df))
    with cols[1]:
        conflict_count = int(normalize_bool_series(df["conflict_flag"]).sum()) if "conflict_flag" in df.columns else 0
        st.metric("conflict_flag=True", conflict_count)
    with cols[2]:
        weak_count = int(normalize_bool_series(df["weak_clue_flag"]).sum()) if "weak_clue_flag" in df.columns else 0
        st.metric("weak_clue_flag=True", weak_count)
    with cols[3]:
        strong_count = int((df["evidence_status"] == "强变更依据").sum()) if "evidence_status" in df.columns else 0
        st.metric("强变更依据", strong_count)

    c1, c2 = st.columns(2)
    with c1:
        show_count_chart(df, "evidence_status", "evidence_status 分布")
    with c2:
        show_count_chart(df, "review_priority", "review_priority 分布")

    with st.expander("筛选条件", expanded=True):
        fcols = st.columns(6)
        with fcols[0]:
            evidence_status = multiselect_filter(df, "evidence_status", "evidence_status", "evidence_tab_status")
        with fcols[1]:
            review_priority = multiselect_filter(df, "review_priority", "review_priority", "evidence_tab_priority")
        with fcols[2]:
            business_domain = multiselect_filter(df, "business_domain", "business_domain", "evidence_tab_domain")
        with fcols[3]:
            impact_level = multiselect_filter(df, "impact_level", "配置影响等级", "evidence_tab_impact")
        with fcols[4]:
            conflict = bool_filter(df, "conflict_flag", "conflict_flag", "evidence_tab_conflict")
        with fcols[5]:
            weak = bool_filter(df, "weak_clue_flag", "weak_clue_flag", "evidence_tab_weak")

    filtered = apply_filters(
        df,
        {
            "evidence_status": evidence_status,
            "review_priority": review_priority,
            "business_domain": business_domain,
            "impact_level": impact_level,
        },
    )
    if conflict != "全部" and "conflict_flag" in filtered.columns:
        filtered = filtered[normalize_bool_series(filtered["conflict_flag"]) == (conflict == "True")]
    if weak != "全部" and "weak_clue_flag" in filtered.columns:
        filtered = filtered[normalize_bool_series(filtered["weak_clue_flag"]) == (weak == "True")]

    columns = [
        "change_id",
        "change_type",
        "business_domain",
        "phase",
        "task_name",
        "field",
        "old_value",
        "new_value",
        "impact_level",
        "evidence_status",
        "review_priority",
        "decision_suggestion",
        "evidence_source_file_1",
        "evidence_source_type_1",
    ]
    existing = [column for column in columns if column in filtered.columns]
    missing = [column for column in columns if column not in filtered.columns]
    if missing:
        st.caption("以下字段不存在，已跳过：" + "、".join(missing))
    st.caption(f"当前显示 {len(filtered)} / {len(df)} 条")
    st.dataframe(filtered[existing] if existing else filtered, use_container_width=True, hide_index=True)


def show_focus_table(df: pd.DataFrame, title: str, subset: pd.DataFrame) -> None:
    """展示复核报告中的重点清单。"""
    st.subheader(title)
    if subset.empty:
        st.info("暂无记录。")
        return
    columns = [
        "change_id",
        "change_type",
        "business_domain",
        "phase",
        "task_name",
        "field",
        "impact_level",
        "evidence_status",
        "review_priority",
        "decision_suggestion",
    ]
    existing = [column for column in columns if column in subset.columns]
    st.dataframe(subset[existing].head(10), use_container_width=True, hide_index=True)


def show_review_report_tab() -> None:
    """Tab5：展示 evidence_summary.md 和页面级复核摘要。"""
    st.header("复核建议报告")
    if st.button("使用 Agent Router 生成复核报告", key="review_tab_agent_report"):
        with st.spinner("正在生成复核报告..."):
            result = AgentRouter(ROOT_DIR).route("生成一份本次流程配置变更复核建议报告")
        st.markdown("**llm_used**")
        st.code(str(result.get("llm_used", False)))
        fallback_reason = result.get("fallback_reason", "")
        if fallback_reason:
            st.markdown("**fallback_reason**")
            st.info(str(fallback_reason))
        st.markdown(str(result.get("answer", "")))
        st.divider()
    summary_path = ROOT_DIR / "outputs/evidence_summary.md"
    evidence_path = ROOT_DIR / "outputs/change_report_with_evidence.csv"

    summary = read_text_safe(summary_path)
    if summary:
        st.subheader("evidence_summary.md")
        st.markdown(summary)
    else:
        st.warning("未找到 `outputs/evidence_summary.md`，请先运行：`python scripts/match_change_evidence.py`")

    if not evidence_path.exists():
        st.info("未找到证据匹配 CSV，无法生成页面级摘要。")
        return

    df = add_phase_task_columns(load_csv_safe(evidence_path))
    if df.empty:
        return
    if "impact_level" not in df.columns and "risk_level" in df.columns:
        df["impact_level"] = df["risk_level"]

    st.subheader("页面级摘要")
    st.metric("总变更数", len(df))
    cols = st.columns(3)
    with cols[0]:
        show_count_chart(df, "impact_level", "配置影响等级分布")
    with cols[1]:
        show_count_chart(df, "evidence_status", "依据状态分布")
    with cols[2]:
        show_count_chart(df, "review_priority", "复核优先级分布")

    priority = df["review_priority"] if "review_priority" in df.columns else pd.Series("", index=df.index)
    conflict = normalize_bool_series(df["conflict_flag"]) if "conflict_flag" in df.columns else pd.Series(False, index=df.index)
    weak = normalize_bool_series(df["weak_clue_flag"]) if "weak_clue_flag" in df.columns else pd.Series(False, index=df.index)

    show_focus_table(df, "需要重点补证的前 10 条", df[priority == "重点补证"])
    show_focus_table(df, "存在冲突的前 10 条", df[conflict])
    show_focus_table(df, "存在弱线索的前 10 条", df[weak])


def show_rag_test_tab() -> None:
    """Tab6：直接调用 RAG 检索测试。"""
    st.header("RAG 检索测试")
    examples = [
        "聊天记录能不能作为正式变更依据？",
        "新增任务节点需要校验哪些字段？",
        "电控 A样阶段 软件需求冻结 负责人 任命调整依据",
        "SOP阶段有哪些复核要求？",
    ]
    if "rag_query" not in st.session_state:
        st.session_state.rag_query = examples[0]

    cols = st.columns(2)
    for index, question in enumerate(examples):
        with cols[index % 2]:
            if st.button(question, key=f"rag_example_{index}", use_container_width=True):
                st.session_state.rag_query = question

    query = st.text_area("检索 query", key="rag_query", height=80)
    top_k = st.selectbox("top_k", [3, 5, 10], index=1, key="rag_test_tab_top_k")
    use_rerank = st.checkbox("启用 rerank 重排序", value=False, key="rag_test_tab_use_rerank")

    if st.button("开始检索", key="rag_test_tab_submit", type="primary"):
        if not query.strip():
            st.warning("请输入检索 query。")
            return
        with st.spinner("正在检索知识库..."):
            try:
                results = search_docs(
                    query,
                    top_k=int(top_k),
                    persist_dir=ROOT_DIR / "outputs/chroma_db",
                    use_rerank=use_rerank,
                    candidate_k=20,
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"检索失败：{exc}")
                kb_dir = ROOT_DIR / "outputs/chroma_db"
                chunks_file = kb_dir / "chunks.json"
                if kb_dir.exists() and chunks_file.exists():
                    st.info("检测到知识库目录已存在，但检索调用失败。可尝试重启 Streamlit 页面，或在终端重新运行：`python scripts/build_knowledge_base.py`")
                else:
                    st.info("未检测到完整知识库，请先运行：`python scripts/build_knowledge_base.py`")
                with st.expander("查看错误详情"):
                    st.code(traceback.format_exc())
                return
        rows = [
            {
                "rank": item.get("rank", ""),
                "score": item.get("score", ""),
                "source_file": item.get("source_file", ""),
                "source_type": item.get("source_type", ""),
                "evidence_strength": item.get("evidence_strength", ""),
                "rerank_score": item.get("rerank_score", ""),
                "rerank_reason": item.get("rerank_reason", ""),
                "text": item.get("text", ""),
            }
            for item in results
        ]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("未检索到结果。")

    show_rag_eval_section()


def show_rag_eval_section() -> None:
    """明确区分 baseline 与 rerank 的评估展示。"""
    st.divider()
    st.subheader("RAG 评估结果")
    baseline_summary = ROOT_DIR / "outputs/eval/rag_eval_summary.md"
    baseline_results = ROOT_DIR / "outputs/eval/rag_eval_results.csv"
    rerank_summary = ROOT_DIR / "outputs/eval/rag_eval_summary_rerank.md"
    rerank_results = ROOT_DIR / "outputs/eval/rag_eval_results_rerank.csv"

    if baseline_summary.exists() and rerank_summary.exists():
        diff_seconds = abs(baseline_summary.stat().st_mtime - rerank_summary.stat().st_mtime)
        if diff_seconds > 600:
            st.warning("baseline 和 rerank 评估文件可能不是同一轮生成，建议重新运行两条评估命令。")
        baseline_meta = parse_eval_summary_meta(baseline_summary)
        rerank_meta = parse_eval_summary_meta(rerank_summary)
        baseline_mode = baseline_meta.get("retrieval_mode", "未记录")
        rerank_mode = rerank_meta.get("retrieval_mode", "未记录")
        if baseline_mode != rerank_mode:
            st.warning("Baseline 与 Rerank 使用了不同检索模式，指标不可直接比较。")
        if baseline_mode == "keyword_fallback" or rerank_mode == "keyword_fallback":
            st.warning("当前评估不是 vector mode，可能是 sentence_transformers 不可用。")

    with st.expander("Baseline 评估结果：outputs/eval/rag_eval_summary.md", expanded=False):
        if baseline_summary.exists():
            meta = parse_eval_summary_meta(baseline_summary)
            st.caption("摘要文件：outputs/eval/rag_eval_summary.md")
            st.info(f"retrieval_mode: {meta.get('retrieval_mode', '未记录')} | generated_at: {meta.get('generated_at', '未记录')}")
            if meta.get("retrieval_mode") == "keyword_fallback":
                st.warning("当前评估不是 vector mode，可能是 sentence_transformers 不可用。")
            st.markdown(read_text_safe(baseline_summary))
        else:
            st.info("baseline 不存在：请运行 `python scripts/run_rag_evaluation.py`")
        if baseline_results.exists():
            st.caption("明细文件：outputs/eval/rag_eval_results.csv")
            st.dataframe(load_csv_safe(baseline_results), use_container_width=True, hide_index=True)

    with st.expander("Rerank 评估结果：outputs/eval/rag_eval_summary_rerank.md", expanded=False):
        if rerank_summary.exists():
            meta = parse_eval_summary_meta(rerank_summary)
            st.caption("摘要文件：outputs/eval/rag_eval_summary_rerank.md")
            st.info(f"retrieval_mode: {meta.get('retrieval_mode', '未记录')} | generated_at: {meta.get('generated_at', '未记录')}")
            if meta.get("retrieval_mode") == "keyword_fallback":
                st.warning("当前评估不是 vector mode，可能是 sentence_transformers 不可用。")
            st.markdown(read_text_safe(rerank_summary))
        else:
            st.info("rerank 不存在：请运行 `python scripts/run_rag_evaluation.py --rerank`")
        if rerank_results.exists():
            st.caption("明细文件：outputs/eval/rag_eval_results_rerank.csv")
            st.dataframe(load_csv_safe(rerank_results), use_container_width=True, hide_index=True)


def main() -> None:
    """Streamlit 入口。"""
    st.set_page_config(page_title="流程配置变更 RAG + Agent 助手 Demo", layout="wide")
    st.title("流程配置变更 RAG + Agent 助手 Demo")
    st.write("本系统模拟车企项目开发流程配置变更场景，支持多来源资料建库、新旧配置差异分析、变更依据匹配和复核建议生成。")
    with st.expander("LLM 可选生成层状态", expanded=False):
        show_llm_status()

    tabs = st.tabs(["系统状态", "Agent 问答", "变更清单", "证据匹配", "复核建议报告", "RAG 检索测试"])
    with tabs[0]:
        render_tab("系统状态", show_status_tab)
    with tabs[1]:
        render_tab("Agent 问答", show_agent_tab)
    with tabs[2]:
        render_tab("变更清单", show_change_report_tab)
    with tabs[3]:
        render_tab("证据匹配", show_evidence_tab)
    with tabs[4]:
        render_tab("复核建议报告", show_review_report_tab)
    with tabs[5]:
        render_tab("RAG 检索测试", show_rag_test_tab)


if __name__ == "__main__":
    main()
