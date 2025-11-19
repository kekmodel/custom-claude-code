"""
Quick demo showing the 5 new tools in action

This demonstrates the actual execution of new tools without AI
to verify they work correctly.
"""

import asyncio
import time


async def demo_v1_background_tools():
    """Demo v1 background process tools"""
    print("=" * 70)
    print("DEMO: v1 Background Process Tools")
    print("=" * 70)

    from src.custom_claude_code.v1_openai.tools import (
        tool_bashbackground,
        tool_bashoutput,
        tool_killshell,
    )
    from src.custom_claude_code.v1_openai.types import (
        BashBackgroundInput,
        BashOutputInput,
        KillShellInput,
    )

    print("\n📌 Step 1: Start background process")
    print("   Command: 'for i in 1 2 3; do echo \"Count: $i\"; sleep 1; done'")

    bg_input = BashBackgroundInput(
        command="for i in 1 2 3; do echo 'Count: $i'; sleep 1; done", description="Demo counter"
    )
    result = await tool_bashbackground(bg_input)
    print(f"   Result: {result[:150]}")

    # Extract shell ID
    shell_id = result.split("Shell ID: ")[1].split("\n")[0]
    print(f"   ✅ Process started with ID: {shell_id}")

    print("\n📌 Step 2: Check output (first time)")
    await asyncio.sleep(1.5)
    output_input = BashOutputInput(bash_id=shell_id)
    result = await tool_bashoutput(output_input)
    print(f"   Output:\n   {result.replace(chr(10), chr(10) + '   ')}")

    print("\n📌 Step 3: Check output (second time)")
    await asyncio.sleep(1.5)
    result = await tool_bashoutput(output_input)
    print(f"   Output:\n   {result.replace(chr(10), chr(10) + '   ')}")

    print("\n📌 Step 4: Kill the process")
    kill_input = KillShellInput(shell_id=shell_id)
    result = await tool_killshell(kill_input)
    print(f"   Result: {result}")

    print("\n✅ Background process demo completed!\n")


async def demo_v1_web_tools():
    """Demo v1 web tools"""
    print("=" * 70)
    print("DEMO: v1 Web Tools")
    print("=" * 70)

    from src.custom_claude_code.v1_openai.tools import tool_websearch, tool_webfetch
    from src.custom_claude_code.v1_openai.types import WebSearchInput, WebFetchInput

    print("\n📌 Step 1: Search the web")
    print("   Query: 'Python programming'")

    search_input = WebSearchInput(query="Python programming", allowed_domains=None, blocked_domains=None)
    result = await tool_websearch(search_input)

    if "[ERROR]" in result:
        print(f"   ⚠️  Web search requires 'ddgs' package: uv add ddgs")
        print(f"   Skipping web search demo")
    else:
        # Show first 500 chars
        lines = result.split("\n")
        print(f"   Found {result.count('**[') or 0} results")
        print(f"   First result: {lines[2][:100] if len(lines) > 2 else 'N/A'}...")

    print("\n📌 Step 2: Fetch webpage content")
    print("   URL: https://example.com")

    fetch_input = WebFetchInput(url="https://example.com", prompt="Get the main heading")
    result = await tool_webfetch(fetch_input)

    if "[ERROR]" in result:
        print(f"   ⚠️  Web fetch requires 'httpx' and 'beautifulsoup4'")
        print(f"   Install with: uv add httpx beautifulsoup4")
    else:
        # Extract title
        if "**Title**:" in result:
            title_line = [line for line in result.split("\n") if "**Title**:" in line][0]
            print(f"   Page title: {title_line}")
        print(f"   Content length: {len(result)} characters")
        print(f"   ✅ Content fetched successfully")

    print("\n✅ Web tools demo completed!\n")


async def demo_comparison():
    """Show how the same task looks across all versions"""
    print("=" * 70)
    print("COMPARISON: Same Task Across All Versions")
    print("=" * 70)

    print("\n🎯 Task: Run 'echo Hello && sleep 1' in background, check output, kill\n")

    # V1
    print("📦 v1 (OpenAI API):")
    print("   1. tool_bashbackground(BashBackgroundInput(...))")
    print("   2. tool_bashoutput(BashOutputInput(bash_id=...))")
    print("   3. tool_killshell(KillShellInput(shell_id=...))")

    # V3
    print("\n📦 v3 (OpenAI Agents SDK):")
    print("   1. bash_background(command=..., description=...)")
    print("   2. bash_output(shell_id=...)")
    print("   3. kill_shell(shell_id=...)")

    # V4
    print("\n📦 v4 (Claude Agent SDK):")
    print("   1. bash_background({'command': ..., 'description': ...})")
    print("   2. bash_output({'shell_id': ...})")
    print("   3. kill_shell({'shell_id': ...})")

    print("\n💡 All three versions provide identical functionality!")
    print("   - Different frameworks, same capabilities")
    print("   - v1: Full control, Pydantic types")
    print("   - v3: OpenAI Agents SDK, @function_tool")
    print("   - v4: Claude SDK, @tool + MCP server\n")


async def main():
    """Run all demos"""
    print("\n" + "=" * 70)
    print("NEW TOOLS DEMO - v2.1 Features in v1, v3, v4")
    print("=" * 70)
    print("\nThis demo shows the 5 new tools in action:")
    print("  1. bash_background - Run commands in background")
    print("  2. bash_output - Read output without blocking")
    print("  3. kill_shell - Terminate background processes")
    print("  4. web_search - DuckDuckGo search")
    print("  5. web_fetch - Smart HTML content extraction\n")

    try:
        # Demo background tools
        await demo_v1_background_tools()

        # Demo web tools
        await demo_v1_web_tools()

        # Show comparison
        await demo_comparison()

        print("=" * 70)
        print("✅ DEMO COMPLETED!")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Run automated tests: uv run python test_new_tools.py")
        print("  2. Try manual tests: See MANUAL_TEST_GUIDE.md")
        print("  3. Run actual AI conversations with the new tools")
        print("\nAll implementations (v1, v3, v4) now have the same")
        print("capabilities as v2.1!")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
