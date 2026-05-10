#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""轻量 Agent Router。

根据用户自然语言问题选择已有工具：RAG 检索、差异摘要、证据摘要、
复核报告或项目状态检查。所有回答均由规则模板生成，不调用大模型。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from rag_engine import search_docs


ROOT_DIR = Path(__file__).resolve().parents[1]


class AgentRouter:
    """基于关键词的轻量路由器。"""

    def __init__(self, root_dir: str | Path | None = None) -> None:
        self.root_dir = Path(root_dir) if root_dir else ROOT_DIR

    def route(self, user_query: str) -> dict[str, Any]:
        """判断 intent 并调用对应工具。"""
        query = user_query.strip()
        intent = self.detect_intent(query)
        if intent == "rule_qa":
            result = self.answer_rule_question(query)
            result["intent"] = intent
            return result
        if intent == "status_check":
            answer, sources = self.check_project_status()
            tools = ["check_project_status"]
        elif intent == "diff_summary":
            answer, sources = self.load_change_report_summary()
            tools = ["load_change_report"]
        elif intent == "evidence_summary":
            answer, sources = self.load_evidence_report_summary(query)
            tools = ["load_evidence_report"]
        elif intent == "review_report":
            answer, sources = self.generate_review_report()
            tools = ["generate_review_report"]
        elif intent == "rag_search":
            answer, sources = self.run_rag_search(query)
            tools = ["search_docs"]
        else:
            answer, sources = self.help_message(), []
            tools = []
        return {"intent": intent, "tools_used": tools, "answer": answer, "sources": sources}

    def detect_intent(self, query: str) -> str:
        """根据关键词判断用户意图，规则问答优先于普通检索。"""
        if "哪些变化" in query and any(word in query for word in ["重点补证", "常规复核", "冲突", "弱线索"]):
            return "evidence_summary"
        if self.is_rule_question(query):
            return "rule_qa"

        status_words = ["当前状态", "完成到哪一步", "有哪些文件", "系统状态", "项目状态"]
        review_words = ["复核建议", "总结报告", "生成报告", "风险点", "需要重点关注", "复核报告"]
        evidence_words = ["依据匹配", "证据", "强依据", "弱线索", "缺少依据", "人工复核", "中等依据", "配置上下文", "重点补证", "常规复核", "存在冲突"]
        diff_words = ["有哪些变化", "差异", "变更清单", "新旧配置对比", "变化数量", "新增任务", "字段变更", "高风险"]
        rag_words = ["规则", "依据", "负责人", "交付文档", "聊天记录", "会议纪要", "任命通知", "能不能", "为什么", "校验", "SOP"]

        if any(word in query for word in status_words):
            return "status_check"
        if any(word in query for word in review_words):
            return "review_report"
        if any(word in query for word in evidence_words):
            return "evidence_summary"
        if any(word in query for word in diff_words):
            return "diff_summary"
        if any(word in query for word in rag_words):
            return "rag_search"
        return "help"

    def is_rule_question(self, query: str) -> bool:
        """判断是否为证据规则类问题。"""
        rule_patterns = [
            ("聊天记录" in query and "正式变更依据" in query),
            ("口头通知" in query and "正式依据" in query),
            "弱线索" in query,
            "强依据" in query,
            "强变更依据" in query,
            "中等依据" in query,
            "配置上下文" in query,
            ("规则文档" in query and "依据" in query),
            "能不能作为依据" in query,
            "可以作为正式依据吗" in query,
            ("旧配置表" in query and "变更原因" in query),
            ("新版配置表" in query and "变更原因" in query),
            ("部门在线更新表" in query and "依据" in query),
        ]
        return any(rule_patterns)

    def path(self, relative: str) -> Path:
        """构造项目内路径。"""
        return self.root_dir / relative

    def source_ref(self, source_file: str, source_type: str = "", evidence_strength: str = "", score: Any = "") -> dict[str, Any]:
        """构造统一 sources 条目。"""
        return {
            "source_file": source_file,
            "source_type": source_type,
            "evidence_strength": evidence_strength,
            "score": score,
        }

    def read_csv_safe(self, relative: str) -> pd.DataFrame | None:
        """安全读取 CSV，缺失时返回 None。"""
        path = self.path(relative)
        if not path.exists():
            return None
        return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False).fillna("")

    def missing_file_message(self, relative: str, command: str) -> tuple[str, list[dict[str, Any]]]:
        """生成缺文件提示。"""
        answer = f"未找到 `{relative}`。\n\n请先运行：\n\n```bash\n{command}\n```"
        return answer, []

    def answer_rule_question(self, user_query: str) -> dict[str, Any]:
        """回答证据规则类问题：先给结论，再给检索来源。"""
        query = user_query.strip()
        conclusion = ""
        explanation = ""
        accept_condition = ""
        review_case = ""

        if "聊天记录" in query or "口头通知" in query or "弱线索" in query:
            conclusion = "不能。聊天记录/口头通知不能单独作为正式变更依据，只能作为弱线索。"
            explanation = "聊天记录通常信息不完整，可能存在口语化、冲突或待确认表述，因此不能直接证明某条具体变更已经被正式批准。"
            accept_condition = "如果聊天记录与任命通知、正式会议纪要或部门确认材料一致，可以作为辅助线索。"
            review_case = "如果只有聊天记录，没有强变更依据，则应标记为需人工复核，不能直接纳入正式配置变更。"
        elif "部门在线更新表" in query or "中等依据" in query:
            conclusion = "部门在线更新表属于中等变更依据，不宜单独视为最终正式依据。"
            explanation = "它可以说明某个部门提交了变更申请或建议，但通常还需要会议纪要、任命通知或部门确认材料进一步确认。"
            accept_condition = "当部门更新表状态为已确认或会议确认，并能与正式会议纪要/任命通知相互印证时，可进入候选变更清单。"
            review_case = "如果仅有部门更新表，建议标记为补充确认。"
        elif "旧配置表" in query or "新版配置表" in query or "配置上下文" in query:
            conclusion = "旧配置表和新版配置表属于配置上下文，不能单独证明变更原因。"
            explanation = "它们能说明旧版和新版分别是什么，也能证明差异存在，但不能解释为什么发生该变更。"
            accept_condition = "需要结合任命通知、正式会议纪要或部门确认材料，才能证明具体变更依据。"
            review_case = "如果只命中旧/新配置或规则文档，应标记为仅有配置或规则上下文，缺少变更依据。"
        elif "规则文档" in query:
            conclusion = "规则文档属于规则依据，可以说明怎么判断和怎么复核，但不能证明某条具体变更一定发生。"
            explanation = "规则文档用于解释证据分级、校验字段和人工复核要求。"
            accept_condition = "它可以辅助判断证据是否充分，但仍需具体业务证据支撑变更。"
            review_case = "如果只命中规则文档，应补充任命通知、会议纪要或部门确认材料。"
        else:
            conclusion = "强变更依据包括任命调整通知和正式会议纪要。"
            explanation = "这类资料可以直接说明某条具体变更为什么发生，例如负责人调整、新增任务节点、审批角色调整或时间规则调整。"
            accept_condition = "当检索结果命中任命通知或正式会议纪要，并且内容与变更字段一致，可作为强变更依据。"
            review_case = "如果存在弱线索或冲突表述，即使有强依据，也建议业务人员重点复核。"

        answer, sources = self.run_rag_search(query, include_raw_chunks=False)
        lines = [
            "## 规则问答",
            "",
            f"### 结论\n{conclusion}",
            "",
            f"### 解释\n{explanation}",
            "",
            f"### 可采纳条件\n{accept_condition}",
            "",
            f"### 需人工复核情况\n{review_case}",
            "",
            "### 相关来源",
            answer,
        ]
        return {"tools_used": ["rule_template", "search_docs"], "answer": "\n".join(lines), "sources": sources}

    def count_lines(self, df: pd.DataFrame, column: str, title: str) -> list[str]:
        """生成字段分布统计文本。"""
        lines = [title]
        if column not in df.columns or df.empty:
            lines.append("- 无")
            return lines
        for name, count in df[column].replace("", "未填写").value_counts().items():
            lines.append(f"- {name}: {count}")
        return lines

    def load_change_report_summary(self) -> tuple[str, list[dict[str, Any]]]:
        """读取 change_report.csv 并生成差异摘要。"""
        relative = "outputs/change_report.csv"
        df = self.read_csv_safe(relative)
        if df is None:
            return self.missing_file_message(relative, "python scripts/run_change_analysis.py")

        total = len(df)
        added = int((df.get("change_type", "") == "新增任务").sum()) if "change_type" in df.columns else 0
        deleted = int((df.get("change_type", "") == "删除任务").sum()) if "change_type" in df.columns else 0
        field_changed = int((df.get("change_type", "") == "字段变更").sum()) if "change_type" in df.columns else 0
        high_risk = df[df.get("risk_level", "") == "高"].head(5) if "risk_level" in df.columns else pd.DataFrame()

        lines = [
            "## 新旧配置差异摘要",
            "",
            f"- 总变化数: {total}",
            f"- 新增任务数: {added}",
            f"- 删除任务数: {deleted}",
            f"- 字段变更数: {field_changed}",
            "",
            *self.count_lines(df, "risk_level", "### 配置影响等级统计"),
            "",
            *self.count_lines(df, "business_domain", "### 按 business_domain 统计"),
            "",
            "### 前 5 条配置影响等级为高的变化",
        ]
        if high_risk.empty:
            lines.append("- 无")
        else:
            for _, row in high_risk.iterrows():
                lines.append(f"- {self.change_label(row)} | {row.get('old_value', '')} -> {row.get('new_value', '')}")
        return "\n".join(lines), [self.source_ref(str(self.path(relative)), "change_report", "system_output", "")]

    def load_evidence_report_summary(self, user_query: str = "") -> tuple[str, list[dict[str, Any]]]:
        """读取证据匹配报告并生成摘要。"""
        relative = "outputs/change_report_with_evidence.csv"
        df = self.read_csv_safe(relative)
        if df is None:
            return self.missing_file_message(relative, "python scripts/match_change_evidence.py")

        specific = self.specific_evidence_answer(df, user_query)
        if specific:
            return specific, [self.source_ref(str(self.path(relative)), "evidence_report", "system_output", "")]

        high_without_strong = df[
            (df.get("impact_level", df.get("risk_level", "")) == "高") & (df.get("evidence_status", "") != "强变更依据")
        ].head(5)
        lines = [
            "## 变更依据匹配摘要",
            "",
            *self.count_lines(df, "evidence_status", "### evidence_status 统计"),
            "",
            *self.count_lines(df, "review_priority", "### review_priority 统计"),
            "",
            "### 前 5 条配置影响等级高但缺少强变更依据的变化",
        ]
        if high_without_strong.empty:
            lines.append("- 无")
        else:
            for _, row in high_without_strong.iterrows():
                lines.append(f"- {self.change_label(row)} | {row.get('evidence_status', '')} | {row.get('review_priority', '')}")
        return "\n".join(lines), [self.source_ref(str(self.path(relative)), "evidence_report", "system_output", "")]

    def specific_evidence_answer(self, df: pd.DataFrame, user_query: str) -> str:
        """针对复核优先级类问题返回直接清单。"""
        if not user_query:
            return ""
        if "重点补证" in user_query:
            subset = df[df.get("review_priority", "") == "重点补证"]
            title = "## 需要重点补证的变化"
            empty = "当前没有 review_priority=重点补证 的记录。"
        elif "常规复核" in user_query:
            subset = df[df.get("review_priority", "") == "常规复核"]
            title = "## 可以常规复核的变化"
            empty = "当前没有 review_priority=常规复核 的记录。"
        elif "冲突" in user_query or "弱线索" in user_query:
            subset = df[(df.get("conflict_flag", "") == "True") | (df.get("weak_clue_flag", "") == "True")]
            title = "## 存在冲突或弱线索的变化"
            empty = "当前没有 conflict_flag=True 或 weak_clue_flag=True 的记录。"
        else:
            return ""

        lines = [title, ""]
        if subset.empty:
            lines.append(empty)
        else:
            for _, row in subset.head(12).iterrows():
                lines.append(
                    f"- {self.change_label(row)} | 优先级: {row.get('review_priority', '')} | "
                    f"依据: {row.get('evidence_status', '')} | 建议: {row.get('decision_suggestion', row.get('final_review_suggestion', ''))}"
                )
        return "\n".join(lines)

    def generate_review_report(self) -> tuple[str, list[dict[str, Any]]]:
        """基于 evidence report 生成规则化复核总结。"""
        relative = "outputs/change_report_with_evidence.csv"
        df = self.read_csv_safe(relative)
        if df is None:
            return self.missing_file_message(relative, "python scripts/match_change_evidence.py")

        total = len(df)
        change_type_counts = df.get("change_type", pd.Series(dtype=str)).value_counts()
        impact_counts = df.get("impact_level", df.get("risk_level", pd.Series(dtype=str))).replace("", "未填写").value_counts()
        evidence_counts = df.get("evidence_status", pd.Series(dtype=str)).replace("", "未填写").value_counts()
        priority_counts = df.get("review_priority", pd.Series(dtype=str)).replace("", "未填写").value_counts()

        focus = self.focus_review_rows(df)
        lines = [
            "## 流程配置变更复核建议报告",
            "",
            "### 1. 本次配置变更概览",
            f"- 总变更数: {total}",
            f"- 新增任务数: {int(change_type_counts.get('新增任务', 0))}",
            f"- 字段变更数: {int(change_type_counts.get('字段变更', 0))}",
            "- 配置影响等级分布:",
        ]
        lines.extend([f"  - {name}: {count}" for name, count in impact_counts.items()])
        lines.extend(["", "### 2. 依据状态分布"])
        lines.extend([f"- {name}: {count}" for name, count in evidence_counts.items()])
        lines.extend(["", "### 3. 复核优先级分布"])
        lines.extend([f"- {name}: {count}" for name, count in priority_counts.items()])
        lines.extend(
            [
                "",
                "### 4. 系统建议",
                "配置影响等级高不等于变更不可采纳。如果已有强变更依据且无冲突，可进入常规复核；人工重点应放在缺少强依据、存在弱线索或冲突的变更上。",
                "",
                "### 5. 重点关注清单",
            ]
        )
        if focus.empty:
            lines.append("- 暂无重点关注项。")
        else:
            for _, row in focus.head(12).iterrows():
                lines.append(
                    f"- {self.change_label(row)} | 优先级: {row.get('review_priority', '')} | "
                    f"依据: {row.get('evidence_status', '')} | 建议: {row.get('decision_suggestion', row.get('final_review_suggestion', ''))}"
                )
        lines.extend(
            [
                "",
                "### 6. 后续补充材料建议",
                "- 对“重点补证”“暂缓纳入”的记录，优先补充会议纪要、任命通知或部门确认材料。",
                "- 对存在冲突或弱线索的记录，核对聊天记录是否已被正式会议纪要或通知确认。",
                "- 对“可快速复核”“常规复核”的记录，重点检查字段录入是否与证据文本一致。",
            ]
        )
        return "\n".join(lines), [self.source_ref(str(self.path(relative)), "evidence_report", "system_output", "")]

    def focus_review_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """优先列出需要人工重点关注的记录。"""
        if df.empty:
            return df
        priority = df.get("review_priority", "")
        conflict = df.get("conflict_flag", "")
        weak = df.get("weak_clue_flag", "")
        mask = priority.isin(["重点复核", "重点补证", "暂缓纳入"]) | (conflict == "True") | (weak == "True")
        return df[mask].drop_duplicates("change_id")

    def check_project_status(self) -> tuple[str, list[dict[str, Any]]]:
        """检查关键文件是否存在并输出模块状态。"""
        checks = [
            ("旧版配置数据", "data/01_system_export_current_config.csv"),
            ("新版配置数据", "data/03_target_config_v2.csv"),
            ("差异分析结果", "outputs/change_report.csv"),
            ("chunk 预览", "outputs/chunks_preview.csv"),
            ("Chroma/知识库目录", "outputs/chroma_db"),
            ("证据匹配结果", "outputs/change_report_with_evidence.csv"),
            ("证据摘要", "outputs/evidence_summary.md"),
        ]
        lines = ["## 当前项目状态", ""]
        sources = []
        for name, relative in checks:
            path = self.path(relative)
            status = "已就绪" if path.exists() else "缺失"
            lines.append(f"- {name}: {status} ({relative})")
            if path.exists():
                sources.append(self.source_ref(str(path), "project_file", "system_context", ""))
        lines.extend(
            [
                "",
                "### 建议命令",
                "- 差异分析: `python scripts/run_change_analysis.py`",
                "- RAG 建库: `python scripts/build_knowledge_base.py`",
                "- 证据匹配: `python scripts/match_change_evidence.py`",
                "- 证据检查: `python scripts/inspect_evidence_matches.py`",
            ]
        )
        return "\n".join(lines), sources

    def run_rag_search(self, user_query: str, include_raw_chunks: bool = True) -> tuple[str, list[dict[str, Any]]]:
        """调用 RAG 检索并格式化结果。"""
        try:
            results = search_docs(user_query, top_k=5, persist_dir=self.path("outputs/chroma_db"))
        except Exception as exc:
            return f"检索失败：{exc}\n\n请确认已运行：`python scripts/build_knowledge_base.py`", []

        sources = [self.source_ref(item.get("source_file", ""), item.get("source_type", ""), item.get("evidence_strength", ""), item.get("score", "")) for item in results]
        judgment = self.brief_rag_judgment(user_query, results)
        lines = ["## 基于检索结果的简要判断", judgment, ""]
        if include_raw_chunks:
            lines.append("## 相关依据摘录")
            if not results:
                lines.append("未检索到相关资料。")
            for item in results:
                text = str(item.get("text", ""))[:220].replace("\n", " ")
                lines.append(f"- Rank {item.get('rank', '')} | {item.get('source_file', '')} | {item.get('source_type', '')} | score={item.get('score', '')}: {text}")
        else:
            lines.append("相关来源已列在 sources 中。")
        return "\n".join(lines), sources

    def brief_rag_judgment(self, query: str, results: list[dict[str, Any]]) -> str:
        """为普通 RAG 检索生成模板式简要判断。"""
        top_text = "\n".join(str(item.get("text", "")) for item in results[:3])
        has_rule = any(item.get("source_type") == "rule_manual" for item in results)
        if any(word in query for word in ["能不能", "是否", "可以吗"]) and has_rule:
            if "聊天记录" in query or "口头通知" in query:
                return "不能单独作为正式变更依据。检索到的规则说明显示，聊天记录/口头通知属于弱依据，只能作为待复核线索。"
            if "配置" in query and "变更原因" in query:
                return "不能单独证明变更原因。旧/新配置更适合作为配置上下文，需要结合会议纪要、任命通知或部门确认材料。"
        if "不能单独" in top_text or "弱依据" in top_text:
            return "检索结果提示该问题涉及证据强弱，需要区分正式依据、规则依据和弱线索。"
        return "未形成明确结论，以下为相关检索结果。"

    def change_label(self, row: pd.Series) -> str:
        """格式化一条变更。"""
        phase = row.get("phase_new", "") or row.get("phase_old", "")
        task = row.get("task_name_new", "") or row.get("task_name_old", "")
        return f"{row.get('change_id', '')} | {row.get('business_domain', '')} | {phase} | {task} | {row.get('field', '')}"

    def help_message(self) -> str:
        """输出可用问题示例。"""
        return """我可以回答这些类型的问题：

- 当前系统完成到哪一步了？
- 新旧配置有哪些变化？
- 哪些变更是高风险？
- 这些变更的依据匹配情况怎么样？
- 哪些变化缺少强变更依据？
- 聊天记录能不能作为正式变更依据？
- 新增任务节点需要校验哪些字段？
- 生成一份本次流程配置变更复核建议报告。
- 电控 A样阶段 软件需求冻结 负责人调整依据是什么？
- SOP阶段有哪些复核要求？"""
