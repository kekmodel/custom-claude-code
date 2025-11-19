"""
Web search 도구 테스트
"""

import asyncio
from custom_claude_code.v2_1_langgraph_improved.tools import web_search


async def main():
    print("Web search 테스트...")

    try:
        result = await web_search.ainvoke({"query": "Python programming", "max_results": 2})

        if "python" in result.lower() or "search" in result.lower():
            print("✅ web_search 작동!")
            print(f"\n결과 미리보기:\n{result[:300]}...")
        else:
            print(f"❌ web_search 결과 이상:\n{result}")

    except Exception as e:
        print(f"❌ 오류 발생: {type(e).__name__}: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
