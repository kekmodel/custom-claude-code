"""
현재 v2 구현의 tools가 어떤 스키마를 생성하는지 확인
"""

import sys
sys.path.insert(0, '/Users/jd/Documents/workspace/custom-claude-code/src')

from custom_claude_code.v2_langgraph.tools import read_file, write_file
import json


def check_tool_schema(tool):
    print("=" * 80)
    print(f"📦 Tool: {tool.name}")
    print("=" * 80)

    schema = tool.args_schema.model_json_schema() if tool.args_schema else {}

    print("\n1️⃣ 전체 description:")
    print(f"{schema.get('description', 'N/A')[:200]}...")

    print("\n2️⃣ Parameters:")
    for param_name, param_schema in schema.get('properties', {}).items():
        print(f"\n   • {param_name}:")
        print(f"     - type: {param_schema.get('type')}")
        print(f"     - title: {param_schema.get('title')}")
        print(f"     - description: {param_schema.get('description', '❌ NONE')}")  # 여기가 핵심!
        if 'default' in param_schema:
            print(f"     - default: {param_schema.get('default')}")

    print("\n3️⃣ 전체 JSON Schema:")
    print(json.dumps(schema, indent=2, ensure_ascii=False))
    print("\n")


if __name__ == "__main__":
    print("\n🔍 현재 구현의 tools 스키마 확인\n")

    check_tool_schema(read_file)
    check_tool_schema(write_file)

    print("=" * 80)
    print("📌 결론:")
    print("=" * 80)
    print("""
현재 구현 (@tool만 사용, parse_docstring 미지정):
- parse_docstring=False (기본값)
- ✅ Docstring 전체는 tool description으로 사용됨
- ❌ Args 섹션의 각 파라미터 설명은 스키마에 포함되지 않음
- ❌ 각 parameter에 "description" 필드가 없음

개선 방법:
모든 @tool을 @tool(parse_docstring=True)로 변경하면
각 파라미터에 description이 추가됨!
""")
