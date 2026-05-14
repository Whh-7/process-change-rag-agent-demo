#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""可选 LLM 客户端。

默认适配 OpenAI-compatible Chat Completions。未配置 API key 或关闭开关时，
调用方会自动回退到规则模板。
"""

from __future__ import annotations

import os
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:  # noqa: BLE001
    load_dotenv = None


PLACEHOLDER_KEY = "your_api_key_here"


def _load_env() -> None:
    """读取 .env；缺少 python-dotenv 时不影响规则模板运行。"""
    if load_dotenv is not None:
        load_dotenv()


def _as_bool(value: str | None) -> bool:
    """解析环境变量布尔值。"""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def get_llm_config() -> dict[str, Any]:
    """返回 LLM 配置，不暴露 API key 内容。"""
    _load_env()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    return {
        "enable": _as_bool(os.getenv("LLM_ENABLE", "false")),
        "provider": os.getenv("LLM_PROVIDER", "openai_compatible").strip() or "openai_compatible",
        "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com").strip() or "https://api.deepseek.com",
        "model": os.getenv("LLM_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash",
        "has_api_key": bool(api_key and api_key != PLACEHOLDER_KEY),
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2") or 0.2),
        "max_tokens": int(float(os.getenv("LLM_MAX_TOKENS", "1200") or 1200)),
    }


def is_llm_enabled() -> bool:
    """只有显式开启且检测到非占位 API key 时才调用 LLM。"""
    config = get_llm_config()
    return bool(config["enable"] and config["has_api_key"])


def call_chat_completion(
    messages: list[dict[str, str]],
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str | None:
    """调用 OpenAI-compatible Chat Completions；失败时返回 None。"""
    config = get_llm_config()
    if not is_llm_enabled():
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("LLM_API_KEY", "").strip(), base_url=config["base_url"])
        response = client.chat.completions.create(
            model=config["model"],
            messages=messages,
            temperature=config["temperature"] if temperature is None else temperature,
            max_tokens=config["max_tokens"] if max_tokens is None else max_tokens,
        )
        content = response.choices[0].message.content if response.choices else ""
        return content.strip() if content else None
    except Exception:  # noqa: BLE001
        return None


def _disabled_reason() -> str:
    """给调用方返回简短 fallback 原因，不包含敏感信息。"""
    config = get_llm_config()
    if not config["enable"]:
        return "LLM_ENABLE=false，使用规则模板。"
    if not config["has_api_key"]:
        return "未检测到有效 LLM_API_KEY，使用规则模板。"
    return "LLM 调用失败，已回退到规则模板。"


def _format_context(context: str | list[Any]) -> str:
    """将 context 转成清晰文本。"""
    if isinstance(context, str):
        return context
    lines: list[str] = []
    for index, item in enumerate(context, start=1):
        if isinstance(item, dict):
            lines.append(f"[{index}]")
            for key, value in item.items():
                lines.append(f"{key}: {value}")
        else:
            lines.append(f"[{index}] {item}")
        lines.append("")
    return "\n".join(lines).strip()


def generate_with_context(
    system_prompt: str,
    user_prompt: str,
    context: str | list[Any],
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> tuple[str | None, str | None]:
    """基于给定 context 生成回答；不可用时返回 fallback 原因。"""
    if not is_llm_enabled():
        return None, _disabled_reason()
    context_text = _format_context(context)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"用户问题：\n{user_prompt}\n\n可用 context：\n{context_text}"},
    ]
    text = call_chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
    if not text:
        return None, _disabled_reason()
    return text, None


def generate_rag_answer(user_query: str, retrieved_docs: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """使用 RAG 检索结果生成自然中文回答。"""
    context = []
    for item in retrieved_docs[:5]:
        context.append(
            {
                "source_file": item.get("source_file", ""),
                "source_type": item.get("source_type", ""),
                "evidence_strength": item.get("evidence_strength", ""),
                "score": item.get("score", ""),
                "text": item.get("text", ""),
            }
        )
    system_prompt = """你是流程配置变更助手。
只能基于给定 context 回答。
不得编造资料中没有的信息。
如果资料中没有明确依据，必须说“资料中未检索到明确依据”。
回答必须包含：
1. 结论
2. 解释
3. 适用条件
4. 需要人工复核的情况
5. 参考来源文件名"""
    return generate_with_context(system_prompt, user_query, context, temperature=0.2, max_tokens=1200)


def generate_review_report_llm(
    summary_stats: dict[str, Any],
    key_items: list[dict[str, Any]],
) -> tuple[str | None, str | None]:
    """基于结构化统计和重点清单生成复核报告。"""
    system_prompt = """你是流程配置变更复核助手。
你只能基于给定统计和重点清单生成报告。
不得编造数据。
不得夸大风险。
必须区分“配置影响等级”和“复核优先级”。
必须强调“配置影响等级高不等于不可采纳”。
对缺少强依据、存在弱线索、存在冲突的项目提出重点复核建议。
输出中文 Markdown 报告。"""
    context = {"summary_stats": summary_stats, "key_items": key_items}
    return generate_with_context(system_prompt, "生成一份流程配置变更复核建议报告", [context], temperature=0.2, max_tokens=1200)
