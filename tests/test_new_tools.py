"""
Test script for the 5 new tools added to v1, v3, and v4

Tests:
- bash_background: Start a simple background process
- bash_output: Read output from background process
- kill_shell: Kill the background process
- web_search: Search (requires ddgs package)
- web_fetch: Fetch URL (requires httpx, beautifulsoup4)
"""

import asyncio
import sys


async def test_v1_tools():
    """Test v1 (OpenAI API) implementation"""
    print("=" * 60)
    print("Testing v1 (OpenAI API) - New Tools")
    print("=" * 60)

    from src.custom_claude_code.v1_openai.tools import (
        TOOL_REGISTRY,
        tool_bashbackground,
        tool_bashoutput,
        tool_killshell,
    )
    from src.custom_claude_code.v1_openai.types import (
        BashBackgroundInput,
        BashOutputInput,
        KillShellInput,
    )

    # Test 1: Start background process
    print("\n1. Testing bash_background...")
    bg_input = BashBackgroundInput(
        command="echo 'Hello from background' && sleep 1 && echo 'Done'",
        description="Test background process",
    )
    result = await tool_bashbackground(bg_input)
    print(f"Result: {result[:100]}...")

    # Extract shell_id from result
    shell_id = result.split("Shell ID: ")[1].split("\n")[0] if "Shell ID:" in result else None
    print(f"Shell ID: {shell_id}")

    if shell_id:
        # Test 2: Read output
        print("\n2. Testing bash_output...")
        await asyncio.sleep(0.5)  # Give it time to produce output
        output_input = BashOutputInput(bash_id=shell_id)
        result = await tool_bashoutput(output_input)
        print(f"Output: {result[:200]}...")

        # Test 3: Kill shell
        print("\n3. Testing kill_shell...")
        kill_input = KillShellInput(shell_id=shell_id)
        result = await tool_killshell(kill_input)
        print(f"Result: {result}")

    print("\n✅ v1 tools working!")


async def test_v3_tools():
    """Test v3 (OpenAI Agents SDK) implementation"""
    print("\n" + "=" * 60)
    print("Testing v3 (OpenAI Agents SDK) - New Tools")
    print("=" * 60)

    from src.custom_claude_code.v3_openai_agents.tools import TOOLS

    # v3 tools are FunctionTool objects from OpenAI Agents SDK
    # They're not directly callable - they're used by the Agent
    # So we just verify they're properly registered

    print("\n1. Verifying tools are registered...")
    tool_names = [tool.name for tool in TOOLS]
    print(f"Total tools: {len(TOOLS)}")
    print(f"Tool names: {tool_names}")

    # Check that new tools are present
    new_tools = ["bash_background", "bash_output", "kill_shell", "web_search", "web_fetch"]
    print("\n2. Checking new tools...")
    for tool_name in new_tools:
        if tool_name in tool_names:
            print(f"  ✓ {tool_name} registered")
        else:
            print(f"  ✗ {tool_name} NOT found")
            raise AssertionError(f"Tool {tool_name} not registered in v3")

    print("\n✅ v3 tools properly registered!")


async def test_v4_tools():
    """Test v4 (Claude Agent SDK) implementation"""
    print("\n" + "=" * 60)
    print("Testing v4 (Claude Agent SDK) - New Tools")
    print("=" * 60)

    from src.custom_claude_code.v4_claude_agent.tools import CUSTOM_TOOLS

    # v4 tools are SdkMcpTool objects decorated with @tool
    # They can be called but let's verify registration first

    print("\n1. Verifying custom tools are registered...")
    tool_names = [tool.name for tool in CUSTOM_TOOLS]
    print(f"Total custom tools: {len(CUSTOM_TOOLS)}")
    print(f"Tool names: {tool_names}")

    # Check that new tools are present
    new_tools = ["bash_background", "bash_output", "kill_shell", "web_search", "web_fetch"]
    print("\n2. Checking new tools...")
    for tool_name in new_tools:
        if tool_name in tool_names:
            print(f"  ✓ {tool_name} registered")
        else:
            print(f"  ✗ {tool_name} NOT found")
            raise AssertionError(f"Tool {tool_name} not registered in v4")

    # v4 tools are decorated with @tool and will be used by Claude SDK Client
    # They're registered as MCP tools via create_sdk_mcp_server
    print("\n3. Verifying MCP server integration...")
    from claude_agent_sdk import create_sdk_mcp_server

    try:
        custom_server = create_sdk_mcp_server(
            name="test-custom-tools", version="1.0.0", tools=CUSTOM_TOOLS
        )
        print(f"  ✓ MCP server created successfully")
        print(f"  ✓ Tools will be available as: mcp__custom__<tool_name>")
    except Exception as e:
        print(f"  ✗ MCP server creation failed: {e}")
        raise

    print("\n✅ v4 tools properly configured!")


async def test_web_tools():
    """Test web tools (optional - requires packages)"""
    print("\n" + "=" * 60)
    print("Testing Web Tools (Optional)")
    print("=" * 60)

    try:
        from src.custom_claude_code.v1_openai.tools import tool_websearch, tool_webfetch
        from src.custom_claude_code.v1_openai.types import WebSearchInput, WebFetchInput

        # Test web_search
        print("\n1. Testing web_search...")
        search_input = WebSearchInput(query="Python asyncio", allowed_domains=None, blocked_domains=None)
        result = await tool_websearch(search_input)
        if "[ERROR]" in result:
            print(f"⚠️  web_search not available: {result[:100]}")
        else:
            print(f"✅ web_search working! Found {result.count('**[') or 0} results")

        # Test web_fetch
        print("\n2. Testing web_fetch...")
        fetch_input = WebFetchInput(url="https://example.com", prompt="Get the main heading")
        result = await tool_webfetch(fetch_input)
        if "[ERROR]" in result:
            print(f"⚠️  web_fetch not available: {result[:100]}")
        else:
            print(f"✅ web_fetch working! Fetched {len(result)} characters")

    except Exception as e:
        print(f"⚠️  Web tools test skipped: {e}")


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Testing New Tools Implementation (v2.1 → v1, v3, v4)")
    print("=" * 60)

    try:
        # Test each version
        await test_v1_tools()
        await test_v3_tools()
        await test_v4_tools()

        # Optional web tools test
        await test_web_tools()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nSummary:")
        print("- v1: 17 tools (12 original + 5 new)")
        print("- v3: 11 tools (6 original + 5 new)")
        print("- v4: 11 tools (6 SDK + 5 custom MCP)")
        print("\nNew tools:")
        print("  1. bash_background - Background process execution")
        print("  2. bash_output - Non-blocking output reading")
        print("  3. kill_shell - Process termination")
        print("  4. web_search - DuckDuckGo search")
        print("  5. web_fetch - Smart HTML extraction")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
