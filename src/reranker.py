#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""轻量规则 reranker。

不依赖大模型或大型 cross-encoder，只基于原始检索分、关键词重合、
来源类型、证据强度和业务字段命中做重排序。
"""

from __future__ import annotations

import json
import re
from typing import Any


BUSINESS_DOMAINS = ["电机", "电控", "电源", "整机", "热管理", "传动系统", "车载软件"]
PHASES = ["立项阶段", "准备阶段", "策划阶段", "A样阶段", "B1样阶段", "B2样阶段", "C样阶段", "D样阶段", "SOP阶段"]
FIELD_WORDS = [
    "负责人",
    "责任人",
    "责任部门",
    "交付文档",
    "交付物",
    "审批角色",
    "时间规则",
    "任务名称",
    "新增任务",
    "复核",
]


def tokenize(text: str) -> list[str]:
    """轻量分词：英文数字按词，中文按字符和二字片段。"""
    lowered = str(text or "").lower()
    words = re.findall(r"[a-z0-9_]+", lowered)
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
    bigrams = [a + b for a, b in zip(chinese_chars, chinese_chars[1:])]
    return words + chinese_chars + bigrams


def metadata_text(metadata: Any) -> str:
    """将 metadata 转成可匹配文本。"""
    if not metadata:
        return ""
    if isinstance(metadata, dict):
        return " ".join(str(value) for value in metadata.values())
    try:
        return json.dumps(metadata, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        return str(metadata)


def normalize_scores(results: list[dict[str, Any]]) -> list[float]:
    """对原始 score 做 min-max 归一化。"""
    scores = []
    for item in results:
        try:
            scores.append(float(item.get("score", 0) or 0))
        except (TypeError, ValueError):
            scores.append(0.0)
    if not scores:
        return []
    min_score = min(scores)
    max_score = max(scores)
    if max_score == min_score:
        return [1.0 for _ in scores]
    return [(score - min_score) / (max_score - min_score) for score in scores]


def keyword_overlap_score(query: str, item: dict[str, Any]) -> float:
    """计算 query 与文本/metadata 的关键词重合度。"""
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 0.0
    doc_text = f"{item.get('text', '')} {metadata_text(item.get('metadata', {}))}"
    doc_tokens = set(tokenize(doc_text))
    if not doc_tokens:
        return 0.0
    return len(query_tokens & doc_tokens) / len(query_tokens)


def source_type_bonus(query: str, item: dict[str, Any]) -> tuple[float, str]:
    """根据问题意图给来源类型加分。"""
    source_type = str(item.get("source_type", ""))
    rule_keywords = ["规则", "要求", "校验", "复核", "应该如何", "能不能", "是否可以", "正式依据", "作为正式依据", "上下文"]
    chat_keywords = ["聊天记录", "口头通知", "聊天", "口头"]
    chat_content_keywords = ["内容是什么", "说了什么", "怎么说", "提到什么"]
    is_chat_content_query = any(keyword in query for keyword in chat_keywords) and any(keyword in query for keyword in chat_content_keywords)
    is_formal_evidence_query = any(keyword in query for keyword in chat_keywords) and any(keyword in query for keyword in ["正式依据", "能不能作为", "作为正式依据", "是否可以"])
    is_rule_query = any(keyword in query for keyword in rule_keywords) and not is_chat_content_query
    is_specific_rule_query = ("SOP" in query and "复核" in query) or ("新增任务节点" in query and "校验" in query) or ("只有配置上下文" in query and "复核" in query)

    if source_type == "rule_manual":
        if is_specific_rule_query:
            return 3.0, "SOP/新增节点/配置上下文复核类问题，rule_manual 强加分"
        if is_formal_evidence_query:
            return 2.8, "正式依据判定问题，rule_manual 优先"
        if is_rule_query:
            return 2.2, "规则类问题，rule_manual 加分"

    if is_specific_rule_query and source_type == "meeting_minutes":
        return 5.0, "SOP复核类问题，meeting_minutes 辅助强加分"

    if is_specific_rule_query and source_type in {"old_config", "target_config", "chat_message"}:
        return -2.0, "规则复核类问题，配置上下文/弱线索降权"

    if is_rule_query and source_type == "meeting_minutes":
        return 2.0, "规则类问题，meeting_minutes 辅助加分"

    if is_rule_query and source_type in {"old_config", "target_config"}:
        return -1.2, "规则类问题，配置上下文降权"

    if is_formal_evidence_query:
        if source_type == "meeting_minutes":
            return 1.4, "正式依据判定问题，meeting_minutes 次优先"
        if source_type == "chat_message":
            return 0.6, "正式依据判定问题，chat_message 仅作线索"

    if is_chat_content_query and source_type == "chat_message":
        return 1.4, "查询聊天具体内容，chat_message 加分"

    rules = [
        (["规则", "能不能", "依据要求", "校验", "怎么判断"], ["rule_manual"], "规则问题命中规则手册"),
        (["任命", "负责人", "责任人"], ["appointment_notice"], "负责人/任命问题命中任命通知"),
        (["会议", "纪要", "评审"], ["meeting_minutes"], "会议问题命中会议纪要"),
        (["聊天", "口头"], ["chat_message"], "聊天/口头问题命中聊天记录"),
        (["旧配置", "新版配置", "配置表"], ["old_config", "target_config"], "配置表问题命中配置上下文"),
    ]
    for keywords, source_types, reason in rules:
        if any(keyword in query for keyword in keywords) and source_type in source_types:
            return 1.0, reason
    return 0.0, ""


def evidence_strength_bonus(item: dict[str, Any]) -> tuple[float, str]:
    """strong > medium > weak。"""
    strength = str(item.get("evidence_strength", ""))
    mapping = {"strong": (1.0, "强证据加分"), "medium": (0.7, "中等证据加分"), "weak": (0.35, "弱线索低加分")}
    return mapping.get(strength, (0.0, ""))


def phase_business_field_bonus(query: str, item: dict[str, Any]) -> tuple[float, str]:
    """业务域、阶段、字段名同时出现在 query 和文档时加分。"""
    doc_text = f"{item.get('text', '')} {metadata_text(item.get('metadata', {}))}"
    candidates = BUSINESS_DOMAINS + PHASES + FIELD_WORDS
    matched = [word for word in candidates if word in query and word in doc_text]
    if not matched:
        return 0.0, ""
    return min(1.0, len(matched) / 3.0), "字段命中：" + "、".join(matched[:5])


def rerank_results(
    query: str,
    results: list[dict[str, Any]],
    top_k: int = 5,
    strategy: str = "hybrid_rule",
) -> list[dict[str, Any]]:
    """对 search_docs 候选结果重排序。"""
    if strategy != "hybrid_rule" or not results:
        return results[:top_k]

    normalized_scores = normalize_scores(results)
    reranked: list[dict[str, Any]] = []
    for index, item in enumerate(results):
        vector_score_norm = normalized_scores[index] if index < len(normalized_scores) else 0.0
        keyword_score = keyword_overlap_score(query, item)
        source_bonus, source_reason = source_type_bonus(query, item)
        strength_bonus, strength_reason = evidence_strength_bonus(item)
        field_bonus, field_reason = phase_business_field_bonus(query, item)
        rerank_score = (
            0.55 * vector_score_norm
            + 0.20 * keyword_score
            + 0.10 * source_bonus
            + 0.10 * strength_bonus
            + 0.05 * field_bonus
        )
        new_item = dict(item)
        reasons = [
            f"vector={vector_score_norm:.3f}",
            f"keyword={keyword_score:.3f}",
        ]
        reasons.extend(reason for reason in [source_reason, strength_reason, field_reason] if reason)
        new_item["rerank_score"] = round(rerank_score, 6)
        new_item["rerank_reason"] = "；".join(reasons)
        reranked.append(new_item)

    reranked.sort(key=lambda row: float(row.get("rerank_score", 0)), reverse=True)
    for rank, item in enumerate(reranked[:top_k], start=1):
        item["rank"] = rank
    return reranked[:top_k]
