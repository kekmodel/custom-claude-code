"""
Test ClaudeSDKClient with more tools
"""
import asyncio
from pathlib import Path
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def main():
    print("Testing ClaudeSDKClient with multiple tools...")
    try:
        options = ClaudeAgentOptions(
            model="haiku",
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            system_prompt={"type": "preset", "preset": "claude_code"},
            cwd=Path.cwd(),
            max_turns=50,
            max_thinking_tokens=10000,
            include_partial_messages=True,
        )

        async with ClaudeSDKClient(options=options) as client:
            # First query
            print("\n=== Query 1 ===")
            await client.query("안녕! 어떤 도구들을 사용할 수 있어?")
            async for message in client.receive_response():
                print(f"Message type: {type(message).__name__}")
                if hasattr(message, 'content') and hasattr(message.content, '__len__'):
                    print(f"Content (first 100 chars): {str(message.content)[:100]}...")

            # Second query
            print("\n=== Query 2 ===")
            await client.query("2+2는?")
            async for message in client.receive_response():
                print(f"Message type: {type(message).__name__}")
                if hasattr(message, 'content') and hasattr(message.content, '__len__'):
                    print(f"Content (first 100 chars): {str(message.content)[:100]}...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
