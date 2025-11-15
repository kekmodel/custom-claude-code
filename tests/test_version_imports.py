"""
Test all 4 versions with Anthropic API
"""

import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("Testing Custom Claude Code - All Versions")
print("=" * 60)

# Test 1: v1 - OpenAI API with Anthropic
print("\n1️⃣  Testing v1 (OpenAI API + Anthropic)")
print("-" * 60)
try:
    from custom_claude_code.v1_openai.main import client
    print(f"✅ v1 import successful")
    print(f"   API Key: {os.getenv('OPENAI_API_KEY')[:20]}...")
    print(f"   Base URL: {os.getenv('OPENAI_BASE_URL')}")
    print(f"   Client: {client}")
except Exception as e:
    print(f"❌ v1 import failed: {e}")

# Test 2: v2 - LangGraph
print("\n2️⃣  Testing v2 (LangGraph)")
print("-" * 60)
try:
    from custom_claude_code.v2_langgraph.main import main as v2_main
    print(f"✅ v2 import successful")
except Exception as e:
    print(f"❌ v2 import failed: {e}")

# Test 3: v3 - OpenAI Agents SDK
print("\n3️⃣  Testing v3 (OpenAI Agents SDK)")
print("-" * 60)
try:
    from custom_claude_code.v3_openai_agents.main import main as v3_main
    print(f"✅ v3 import successful")
except Exception as e:
    print(f"❌ v3 import failed: {e}")

# Test 4: v4 - Claude Agent SDK
print("\n4️⃣  Testing v4 (Claude Agent SDK)")
print("-" * 60)
try:
    from custom_claude_code.v4_claude_agent.main import main as v4_main
    print(f"✅ v4 import successful")
    print(f"   API Key: {os.getenv('ANTHROPIC_API_KEY')[:20]}...")
except Exception as e:
    print(f"❌ v4 import failed: {e}")

print("\n" + "=" * 60)
print("Import tests complete!")
print("=" * 60)
