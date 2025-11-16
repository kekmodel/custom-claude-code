"""
@tool 데코레이터가 하는 모든 작업 확인하기
"""

from langchain_core.tools import tool
from pprint import pprint
import json


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 기본 @tool 사용
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool
def search_database(query: str, limit: int = 10) -> str:
    """Search the customer database for records matching the query.

    This tool searches through customer records and returns matching results.
    Use this when you need to find customer information.

    Args:
        query: Search terms to look for in customer records
        limit: Maximum number of results to return (default: 10)

    Returns:
        String containing search results
    """
    return f"Found {limit} results for '{query}'"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Google-style docstring 파싱 활성화
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(parse_docstring=True)
def calculate_tax(amount: float, rate: float) -> float:
    """Calculate tax amount based on given rate.

    Args:
        amount: The base amount to calculate tax on
        rate: Tax rate as a decimal (e.g., 0.1 for 10%)

    Returns:
        Calculated tax amount
    """
    return amount * rate


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 분석: @tool이 하는 모든 작업
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def analyze_tool(tool_obj):
    """도구 객체 분석"""
    print("=" * 80)
    print(f"📦 Tool: {tool_obj.name}")
    print("=" * 80)

    print("\n1️⃣ 기본 속성:")
    print(f"   - name: {tool_obj.name}")
    print(f"   - description: {tool_obj.description[:100]}..." if len(tool_obj.description) > 100 else f"   - description: {tool_obj.description}")
    print(f"   - return_direct: {tool_obj.return_direct}")

    print("\n2️⃣ 함수 정보:")
    print(f"   - func: {tool_obj.func}")
    print(f"   - coroutine: {tool_obj.coroutine}")

    print("\n3️⃣ Args Schema (Pydantic 모델):")
    if tool_obj.args_schema:
        print(f"   - Class: {tool_obj.args_schema}")
        print(f"   - Fields:")
        for field_name, field_info in tool_obj.args_schema.model_fields.items():
            print(f"     • {field_name}")
            print(f"       - type: {field_info.annotation}")
            print(f"       - required: {field_info.is_required()}")
            print(f"       - default: {field_info.default}")
            if field_info.description:
                print(f"       - description: {field_info.description}")

    print("\n4️⃣ JSON Schema (LLM에게 전달되는 스키마):")
    schema = tool_obj.args_schema.model_json_schema() if tool_obj.args_schema else {}
    print(json.dumps(schema, indent=2))

    print("\n5️⃣ Tool Call Schema (LLM function calling 형식):")
    tool_call_schema = {
        "name": tool_obj.name,
        "description": tool_obj.description,
        "parameters": schema
    }
    print(json.dumps(tool_call_schema, indent=2))

    print("\n6️⃣ 실행 테스트:")
    if tool_obj.name == "search_database":
        result = tool_obj.invoke({"query": "john", "limit": 5})
        print(f"   Result: {result}")
    elif tool_obj.name == "calculate_tax":
        result = tool_obj.invoke({"amount": 100.0, "rate": 0.1})
        print(f"   Result: {result}")

    print("\n")


if __name__ == "__main__":
    print("\n" + "🔍 @tool 데코레이터가 하는 모든 작업 분석\n".center(80, "="))

    analyze_tool(search_database)
    analyze_tool(calculate_tax)

    print("\n" + "📌 요약: @tool 데코레이터가 하는 작업들".center(80, "="))
    print("""
1. ✅ 함수를 StructuredTool 객체로 변환
   - BaseTool을 상속받은 객체 생성
   - 함수 자체를 .func 속성에 저장

2. ✅ 메타데이터 추출
   - name: 함수 이름 사용 (또는 커스텀 name 지정)
   - description: Docstring의 첫 부분 사용
   - return_direct: False (기본값)

3. ✅ 타입 힌트 → Pydantic 모델 변환 (infer_schema=True일 때)
   - 함수 시그니처에서 타입 힌트 추출
   - 동적으로 Pydantic BaseModel 생성
   - args_schema 속성에 저장

4. ✅ Docstring 파싱 (parse_docstring=True일 때)
   - Google-style docstring의 Args: 섹션 파싱
   - 각 파라미터의 description을 Pydantic 필드에 추가
   - 잘못된 docstring이면 ValueError 발생 (error_on_invalid_docstring=True)

5. ✅ JSON Schema 생성
   - Pydantic 모델 → JSON Schema 변환
   - LLM function calling 형식으로 변환
   - {"name": ..., "description": ..., "parameters": {...}}

6. ✅ 실행 인터페이스 제공
   - invoke(args_dict): 동기 실행
   - ainvoke(args_dict): 비동기 실행
   - __call__(args_dict): 직접 호출

7. ✅ 에러 처리
   - 파라미터 검증 (Pydantic 자동 검증)
   - handle_tool_error: 에러 핸들링 옵션
   - handle_validation_error: 검증 에러 핸들링

8. ✅ 콜백 지원
   - callbacks: 실행 전후 콜백
   - verbose: 디버깅 정보 출력
   - metadata: 메타데이터 태깅
""")
