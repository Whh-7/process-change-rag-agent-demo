#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""命令行版流程配置变更助手。"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_router import AgentRouter  # noqa: E402


def print_result(result: dict) -> None:
    """打印 AgentRouter 返回结果。"""
    print("\nintent:")
    print(result.get("intent", ""))
    print("\ntools_used:")
    tools = result.get("tools_used", [])
    print(", ".join(tools) if tools else "无")
    print("\nllm_used:")
    print(result.get("llm_used", False))
    fallback_reason = result.get("fallback_reason", "")
    if fallback_reason:
        print("\nfallback_reason:")
        print(fallback_reason)
    print("\nanswer:")
    print(result.get("answer", ""))
    print("\nsources:")
    sources = result.get("sources", [])
    if sources:
        for source in sources:
            if isinstance(source, dict):
                print(
                    f"- {source.get('source_file', '')} | "
                    f"{source.get('source_type', '')} | "
                    f"{source.get('evidence_strength', '')} | "
                    f"{source.get('score', '')}"
                )
            else:
                print(f"- {source}")
    else:
        print("无")


def run_once(query: str) -> None:
    """单次问题模式。"""
    router = AgentRouter(ROOT_DIR)
    print_result(router.route(query))


def run_interactive() -> None:
    """交互模式。"""
    router = AgentRouter(ROOT_DIR)
    print("流程配置变更助手已启动。输入 exit 退出。")
    while True:
        try:
            query = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break
        if query.lower() in {"exit", "quit", "q"}:
            print("已退出。")
            break
        if not query:
            continue
        print_result(router.route(query))


def main() -> None:
    """命令行入口。"""
    if len(sys.argv) > 1:
        run_once(" ".join(sys.argv[1:]).strip())
    else:
        run_interactive()


if __name__ == "__main__":
    main()
