#!/usr/bin/env python3
"""
Unit test for Hook System trigger mechanism
Tests that hooks properly return hookSpecificOutput
"""

import asyncio
from src.custom_claude_code.v2_2_langgraph_hooks.hooks import (
    register_hook,
    trigger_hook,
    HookContext,
    reset_hook_system
)


async def test_hook_specific_output():
    """Test that hookSpecificOutput is properly returned"""
    print("Testing hookSpecificOutput return...")

    # Reset hook system to clean state
    reset_hook_system()

    # Register a test hook
    async def test_hook(input_data, tool_use_id, context):
        return {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStop",
                "additionalContext": "Test context added by hook"
            }
        }

    register_hook("SubagentStop", test_hook)

    # Trigger the hook
    context = HookContext(session_id="test", turn_count=1)
    result = await trigger_hook(
        event="SubagentStop",
        input_data={
            "subagent_type": "Test",
            "result": "Test result",
            "message_count": 5
        },
        tool_use_id=None,
        context=context
    )

    print(f"Hook result: {result}")

    # Verify hookSpecificOutput is in the result
    if "hookSpecificOutput" in result:
        hook_output = result["hookSpecificOutput"]
        if hook_output.get("additionalContext") == "Test context added by hook":
            print("✅ TEST PASSED: hookSpecificOutput properly returned")
            return True
        else:
            print(f"❌ TEST FAILED: Wrong additionalContext: {hook_output.get('additionalContext')}")
            return False
    else:
        print(f"❌ TEST FAILED: hookSpecificOutput not in result. Got: {result}")
        return False


async def test_pretooluse_block():
    """Test that PreToolUse can block execution"""
    print("\nTesting PreToolUse block...")

    reset_hook_system()

    async def blocker_hook(input_data, tool_use_id, context):
        if input_data.get("tool_name") == "run_bash":
            command = input_data.get("tool_input", {}).get("command", "")
            if "rm" in command:
                return {
                    "decision": "block",
                    "systemMessage": "rm commands blocked"
                }
        return {}

    register_hook("PreToolUse", blocker_hook, matcher="run_bash")

    # Trigger with dangerous command
    result = await trigger_hook(
        event="PreToolUse",
        input_data={
            "tool_name": "run_bash",
            "tool_input": {"command": "rm -rf /"},
        },
        tool_use_id="test123",
        context=HookContext()
    )

    if result.get("decision") == "block":
        print("✅ TEST PASSED: PreToolUse successfully blocked execution")
        return True
    else:
        print(f"❌ TEST FAILED: Expected block decision, got: {result}")
        return False


async def test_posttooluse_continue():
    """Test that PostToolUse can stop execution with continue_=False"""
    print("\nTesting PostToolUse continue_=False...")

    reset_hook_system()

    async def stopper_hook(input_data, tool_use_id, context):
        if "CRITICAL" in str(input_data.get("tool_response", "")):
            return {
                "continue_": False,
                "stopReason": "Critical error detected",
                "systemMessage": "Execution stopped"
            }
        return {"continue_": True}

    register_hook("PostToolUse", stopper_hook)

    # Trigger with critical error
    result = await trigger_hook(
        event="PostToolUse",
        input_data={
            "tool_name": "run_bash",
            "tool_input": {"command": "echo test"},
            "tool_response": "CRITICAL ERROR: System failure"
        },
        tool_use_id="test123",
        context=HookContext()
    )

    if result.get("continue_") == False:
        print("✅ TEST PASSED: PostToolUse successfully set continue_=False")
        return True
    else:
        print(f"❌ TEST FAILED: Expected continue_=False, got: {result}")
        return False


async def main():
    print("=" * 60)
    print("Hook System Unit Tests")
    print("=" * 60)

    test1 = await test_hook_specific_output()
    test2 = await test_pretooluse_block()
    test3 = await test_posttooluse_continue()

    print("\n" + "=" * 60)
    if all([test1, test2, test3]):
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return True
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        return False


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
