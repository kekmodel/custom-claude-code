#!/usr/bin/env python3
"""Quick test to verify SubagentStop Hook fix"""

import asyncio
from langchain_core.messages import HumanMessage

from src.custom_claude_code.v2_2_langgraph_hooks.graph import graph
from src.custom_claude_code.v2_2_langgraph_hooks.hooks import register_hook
from src.custom_claude_code.v2_2_langgraph_hooks.types import AgentState


async def subagent_summarizer_hook(input_data, tool_use_id, context):
    """SubagentStop: Subagent 결과 요약 추가"""
    subagent_type = input_data.get("subagent_type")
    message_count = input_data.get("message_count", 0)

    print(f"[Hook] 📊 Subagent completed: {subagent_type} ({message_count} messages)")

    return {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStop",
            "additionalContext": f"""<Subagent Execution Summary>
- Type: {subagent_type}
- Messages: {message_count}
- Status: ✅ Completed successfully
            """,
        }
    }


async def main():
    print("Testing SubagentStop Hook fix...")

    # Hook 등록
    register_hook("SubagentStop", subagent_summarizer_hook)

    # Subagent를 사용하는 명령어
    initial_state: AgentState = {
        "messages": [
            HumanMessage(content="Use the Explore agent to find all Python files")
        ],
        "working_dir": ".",
        "selected_tools": None,
        "depth": 0,
        "todos": None,
    }

    final_state = await graph.ainvoke(initial_state)

    # Check for <hook-note> in ToolMessages
    has_hook_note = False
    for msg in final_state["messages"]:
        if msg.__class__.__name__ == "ToolMessage":
            content = str(msg.content)
            if "<hook-note>" in content:
                has_hook_note = True
                print(f"\n✅ FOUND <hook-note> in ToolMessage!")
                # Show the hook-note section
                start = content.find("<hook-note>")
                end = content.find("</hook-note>") + len("</hook-note>")
                print(f"\nHook Note Content:\n{content[start:end]}")
                break

    if not has_hook_note:
        print("\n❌ FAILED: <hook-note> not found")

    return has_hook_note


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
