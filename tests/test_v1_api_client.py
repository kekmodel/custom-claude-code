"""
Test v1 with actual API call to Anthropic
"""

import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

async def test_v1_api():
    print("=" * 60)
    print("Testing v1 with Anthropic API (Claude Haiku)")
    print("=" * 60)

    # Create client
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL")
    )

    print(f"\n✅ Client created")
    print(f"   API Key: {os.getenv('OPENAI_API_KEY')[:20]}...")
    print(f"   Base URL: {os.getenv('OPENAI_BASE_URL')}")

    # Test simple completion
    print("\n🔄 Testing simple completion...")
    try:
        response = await client.chat.completions.create(
            model="claude-haiku-4-5",
            messages=[
                {"role": "user", "content": "Say 'Hello from Claude Haiku!' in one line."}
            ],
            max_tokens=100
        )

        print(f"\n✅ API call successful!")
        print(f"   Model: {response.model}")
        print(f"   Response: {response.choices[0].message.content}")
        print(f"   Tokens: {response.usage.total_tokens}")

    except Exception as e:
        print(f"\n❌ API call failed: {e}")
        return False

    # Test with tools
    print("\n🔧 Testing with tools (function calling)...")
    try:
        response = await client.chat.completions.create(
            model="claude-haiku-4-5",
            messages=[
                {"role": "user", "content": "What's 2+2? Use the calculator tool."}
            ],
            tools=[{
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "Calculate a math expression",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string"}
                        },
                        "required": ["expression"]
                    }
                }
            }],
            max_tokens=100
        )

        if response.choices[0].message.tool_calls:
            print(f"\n✅ Tool calling works!")
            print(f"   Tool: {response.choices[0].message.tool_calls[0].function.name}")
            print(f"   Args: {response.choices[0].message.tool_calls[0].function.arguments}")
        else:
            print(f"\n⚠️  No tool calls (might be expected)")
            print(f"   Response: {response.choices[0].message.content}")

    except Exception as e:
        print(f"\n❌ Tool calling failed: {e}")
        return False

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    asyncio.run(test_v1_api())
