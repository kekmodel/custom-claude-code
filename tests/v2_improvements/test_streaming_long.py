"""
긴 텍스트 스트리밍 테스트

"..." 없이 실시간으로 나와야 함 (배칭 최적화 적용)
"""

import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from custom_claude_code.v2_langgraph.main import process_graph_stream

load_dotenv()


async def test_long_streaming():
    """긴 응답 스트리밍 테스트"""
    print("\n" + "=" * 80)
    print("긴 텍스트 스트리밍 테스트 (배칭 최적화)")
    print("=" * 80)

    messages = []
    working_dir = os.getcwd()

    # 긴 응답을 유도하는 질문
    print("\n📝 요청: Python의 데코레이터에 대해 자세히 설명해줘 (예제 포함)")
    messages.append(
        HumanMessage(
            content="Python의 데코레이터에 대해 자세히 설명해줘. "
            "기본 개념, 사용법, 실용적인 예제 3가지를 포함해서 길게 작성해줘."
        )
    )

    await process_graph_stream(messages, working_dir)

    print("\n✅ 완료")
    print("\n💡 확인 사항:")
    print("  - 텍스트가 '...' 없이 부드럽게 스트리밍되었는가?")
    print("  - 긴 텍스트에서도 끊김 없이 실시간으로 표시되었는가?")


if __name__ == "__main__":
    asyncio.run(test_long_streaming())
