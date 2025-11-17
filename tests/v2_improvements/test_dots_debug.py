"""
"..." 문제 디버깅 테스트

DEBUG 모드로 정확한 병목 찾기
"""

import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from custom_claude_code.v2_langgraph.main import process_graph_stream

load_dotenv()

# DEBUG 모드 강제 활성화
os.environ["V2_DEBUG"] = "true"


async def test_dots_issue():
    """긴 응답에서 ... 문제 재현 및 디버깅"""
    print("\n" + "=" * 80)
    print("'...' 문제 디버깅 (DEBUG 모드)")
    print("=" * 80)

    messages = []
    working_dir = os.getcwd()

    print("\n📝 요청: v1과 v2 구현 비교 설명 (긴 응답 유도)")
    print("\n💡 DEBUG 로그로 확인할 사항:")
    print("  - 청크 크기 (얼마나 큰 청크가 오는가?)")
    print("  - 청크 도착 간격 (얼마나 자주 오는가?)")
    print("  - 패널 업데이트 시간 (Markdown 파싱 + 렌더링 시간)")
    print("  - 배칭이 제대로 작동하는가?")
    print("")

    messages.append(
        HumanMessage(
            content="v1 OpenAI 구현과 v2 LangGraph 구현의 차이점을 "
            "코드 예제와 함께 자세히 설명해줘. "
            "메시지 관리, 도구 루프, 복잡도 비교 등을 포함해서."
        )
    )

    await process_graph_stream(messages, working_dir)

    print("\n✅ 완료")
    print("\n📊 분석:")
    print("  - 패널 업데이트가 50ms 이상 걸린 경우를 확인하세요")
    print("  - 청크 크기가 불규칙한지 확인하세요")
    print("  - 총 콘텐츠 길이가 길어질수록 업데이트 시간이 증가하는지 확인하세요")


if __name__ == "__main__":
    asyncio.run(test_dots_issue())
