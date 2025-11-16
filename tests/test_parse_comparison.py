"""
parse_docstring=True vs False 비교
"""

from langchain_core.tools import tool
from typing import Optional
import json


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. parse_docstring=False (현재 구현)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool  # parse_docstring 미지정 (기본값: False)
def read_file_v1(file_path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> str:
    """Reads a file from the local filesystem.

    Usage:
    - The file_path parameter must be an absolute path, not a relative path

    Args:
        file_path: The absolute path to the file to read
        offset: The line number to start reading from (1-based index)
        limit: The number of lines to read

    Returns:
        File content with line numbers (cat -n format)
    """
    return f"Reading {file_path}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. parse_docstring=True (개선 버전)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(parse_docstring=True)
def read_file_v2(file_path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> str:
    """Reads a file from the local filesystem.

    Usage:
    - The file_path parameter must be an absolute path, not a relative path

    Args:
        file_path: The absolute path to the file to read
        offset: The line number to start reading from (1-based index)
        limit: The number of lines to read

    Returns:
        File content with line numbers (cat -n format)
    """
    return f"Reading {file_path}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 비교
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def compare_schemas():
    schema_v1 = read_file_v1.args_schema.model_json_schema()
    schema_v2 = read_file_v2.args_schema.model_json_schema()

    print("=" * 80)
    print("❌ parse_docstring=False (현재 구현)")
    print("=" * 80)
    print("\nParameters:")
    for name, schema in schema_v1['properties'].items():
        desc = schema.get('description', '❌ NONE')
        print(f"  {name}: {desc}")

    print("\n\n" + "=" * 80)
    print("✅ parse_docstring=True (개선 버전)")
    print("=" * 80)
    print("\nParameters:")
    for name, schema in schema_v2['properties'].items():
        desc = schema.get('description', '❌ NONE')
        print(f"  {name}: {desc}")

    print("\n\n" + "=" * 80)
    print("📌 차이점 상세 비교")
    print("=" * 80)

    print("\n1️⃣ file_path 파라미터:")
    print(f"\n   V1 (False):")
    print(json.dumps(schema_v1['properties']['file_path'], indent=4))
    print(f"\n   V2 (True):")
    print(json.dumps(schema_v2['properties']['file_path'], indent=4))

    print("\n2️⃣ Tool description (전체 설명):")
    print(f"\n   V1: {schema_v1.get('description', 'N/A')[:80]}...")
    print(f"   V2: {schema_v2.get('description', 'N/A')[:80]}...")
    print("\n   ⚠️  주목: parse_docstring=True일 때는 description이 요약됨!")

    print("\n\n" + "=" * 80)
    print("💡 결론")
    print("=" * 80)
    print("""
parse_docstring=False (현재):
  - Tool 전체 설명: ✅ Docstring 전체 사용
  - 각 파라미터 설명: ❌ 없음
  - LLM이 파라미터 의미를 추론해야 함

parse_docstring=True (권장):
  - Tool 전체 설명: ✅ Docstring 요약 (Args 전까지)
  - 각 파라미터 설명: ✅ Args 섹션에서 추출
  - LLM이 파라미터를 정확히 이해 가능
  - 더 나은 tool calling 정확도!
""")


if __name__ == "__main__":
    compare_schemas()
