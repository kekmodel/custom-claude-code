#!/usr/bin/env python3
"""
v2.2 Hook System 테스트

이 파일은 v2.2의 Hook System이 제대로 통합되었는지 테스트합니다.

테스트 항목:
1. PreToolUse Hook - Bash 명령어 차단
2. PostToolUse Hook - continue_=False로 즉시 중단
3. UserPromptSubmit Hook - additionalContext 주입
4. SubagentStop Hook - Subagent 결과 후처리
"""

import asyncio
from langchain_core.messages import HumanMessage

from src.custom_claude_code.v2_2_langgraph_hooks.graph import graph
from src.custom_claude_code.v2_2_langgraph_hooks.hooks import register_hook
from src.custom_claude_code.v2_2_langgraph_hooks.types import AgentState


# Test 1: PreToolUse Hook - Bash 명령어 차단
async def bash_blocker_hook(input_data, tool_use_id, context):
    """PreToolUse: rm 명령어 차단"""
    tool_name = input_data.get("tool_name")

    if tool_name == "run_bash":  # Fixed: bash_command → run_bash
        command = input_data.get("tool_input", {}).get("command", "")

        # rm 명령어 차단
        if "rm" in command.lower():
            print(f"[Hook] 🚫 Blocked dangerous command: {command}")
            return {
                "decision": "block",
                "systemMessage": "🚫 'rm' commands are not allowed for safety",
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "rm command blocked for safety",
                }
            }

    return {}


# Test 2: PostToolUse Hook - Critical 에러 시 중단
async def critical_error_stopper(input_data, tool_use_id, context):
    """PostToolUse: CRITICAL 에러 감지 시 즉시 중단"""
    tool_response = str(input_data.get("tool_response", ""))

    if "CRITICAL" in tool_response.upper():
        print(f"[Hook] 🛑 Critical error detected - stopping execution")
        return {
            "continue_": False,  # 즉시 중단!
            "stopReason": "Critical error detected",
            "systemMessage": "🚨 Execution stopped due to critical error",
        }

    return {"continue_": True}


# Test 3: UserPromptSubmit Hook - 컨텍스트 주입
async def context_injector_hook(input_data, tool_use_id, context):
    """UserPromptSubmit: 추가 컨텍스트 자동 주입"""
    print(f"[Hook] 💡 Injecting additional context to user input")
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": """
Testing Mode Active:
- This is a test of the Hook System
- Hooks are working correctly
- All systems operational
            """,
        }
    }


# Test 4: SubagentStop Hook - Subagent 결과 요약
async def subagent_summarizer_hook(input_data, tool_use_id, context):
    """SubagentStop: Subagent 결과 요약 추가"""
    subagent_type = input_data.get("subagent_type")
    message_count = input_data.get("message_count", 0)

    print(f"[Hook] 📊 Subagent completed: {subagent_type} ({message_count} messages)")

    return {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStop",
            "additionalContext": f"""
<Subagent Execution Summary>
- Type: {subagent_type}
- Messages: {message_count}
- Status: ✅ Completed successfully
            """,
        }
    }


async def test_pretooluse_hook():
    """Test 1: PreToolUse Hook - Bash 차단"""
    print("\n" + "="*60)
    print("Test 1: PreToolUse Hook - Bash 명령어 차단")
    print("="*60)

    # Hook 등록
    register_hook("PreToolUse", bash_blocker_hook, matcher="run_bash")  # Fixed: bash_command → run_bash

    # 위험한 명령어 시도
    initial_state: AgentState = {
        "messages": [
            HumanMessage(content="Run the command: rm -rf /tmp/test")
        ],
        "working_dir": "/tmp",
        "selected_tools": None,
        "depth": 0,
        "todos": None,
    }

    try:
        # Graph 실행
        final_state = await graph.ainvoke(initial_state)

        # 결과 확인
        print("\nFinal messages:")
        for msg in final_state["messages"]:
            print(f"  - {msg.__class__.__name__}: {msg.content[:100]}...")

        # BLOCKED 메시지가 있는지 확인
        has_blocked = any("[BLOCKED]" in str(msg.content) for msg in final_state["messages"])
        if has_blocked:
            print("\n✅ Test 1 PASSED: Command was blocked by Hook")
        else:
            print("\n❌ Test 1 FAILED: Command was not blocked")

    except Exception as e:
        print(f"\n❌ Test 1 ERROR: {e}")


async def test_posttooluse_hook():
    """Test 2: PostToolUse Hook - continue_=False"""
    print("\n" + "="*60)
    print("Test 2: PostToolUse Hook - Critical 에러 중단")
    print("="*60)

    # Hook 등록
    register_hook("PostToolUse", critical_error_stopper)

    # Critical 에러를 발생시키는 명령어
    initial_state: AgentState = {
        "messages": [
            HumanMessage(content="Run: echo 'CRITICAL ERROR: System failure'")
        ],
        "working_dir": "/tmp",
        "selected_tools": None,
        "depth": 0,
        "todos": None,
    }

    try:
        final_state = await graph.ainvoke(initial_state)

        print("\nFinal messages:")
        for msg in final_state["messages"]:
            print(f"  - {msg.__class__.__name__}: {msg.content[:100]}...")

        # STOPPED 메시지가 있는지 확인
        has_stopped = any("[STOPPED]" in str(msg.content) for msg in final_state["messages"])
        if has_stopped:
            print("\n✅ Test 2 PASSED: Execution was stopped by Hook")
        else:
            print("\n❌ Test 2 FAILED: Execution was not stopped")

    except Exception as e:
        print(f"\n❌ Test 2 ERROR: {e}")


async def test_userpromptsubmit_hook():
    """Test 3: UserPromptSubmit Hook - 컨텍스트 주입"""
    print("\n" + "="*60)
    print("Test 3: UserPromptSubmit Hook - 컨텍스트 주입")
    print("="*60)

    # Hook 등록
    register_hook("UserPromptSubmit", context_injector_hook)

    # Hook은 main.py의 run_conversation_loop()에서 트리거되므로
    # 여기서는 Hook이 등록되었음을 확인만
    print("✅ Hook registered successfully")
    print("Note: UserPromptSubmit Hook is triggered in main.py interactive loop")


async def test_subagentstop_hook():
    """Test 4: SubagentStop Hook - Subagent 결과 요약"""
    print("\n" + "="*60)
    print("Test 4: SubagentStop Hook - Subagent 결과 후처리")
    print("="*60)

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

    try:
        final_state = await graph.ainvoke(initial_state)

        print("\nFinal messages:")
        for i, msg in enumerate(final_state["messages"][-3:]):  # 마지막 3개만
            print(f"  [{i}] {msg.__class__.__name__}: {msg.content[:150]}...")

        # Debug: ToolMessage 전체 내용 확인
        print("\n[DEBUG] Checking all ToolMessages:")
        for msg in final_state["messages"]:
            if msg.__class__.__name__ == "ToolMessage":
                print(f"  ToolMessage (name={getattr(msg, 'name', 'N/A')}): {msg.content[:300]}...")
                if "<hook-note>" in str(msg.content):
                    print("    ✅ Contains <hook-note>!")

        # Subagent Summary가 있는지 확인 (hook-note 태그로 추가됨)
        has_summary = any("<hook-note>" in str(msg.content) for msg in final_state["messages"])
        if has_summary:
            print("\n✅ Test 4 PASSED: Subagent summary was added by Hook")
        else:
            print("\n❌ Test 4 FAILED: Subagent summary not found")

    except Exception as e:
        print(f"\n❌ Test 4 ERROR: {e}")


async def main():
    """모든 테스트 실행"""
    print("\n🧪 v2.2 Hook System Integration Test")
    print("="*60)

    # Test 1: PreToolUse Hook
    await test_pretooluse_hook()

    # Test 2: PostToolUse Hook (continue_)
    await test_posttooluse_hook()

    # Test 3: UserPromptSubmit Hook
    await test_userpromptsubmit_hook()

    # Test 4: SubagentStop Hook
    await test_subagentstop_hook()

    print("\n" + "="*60)
    print("✅ All Hook System tests completed")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
