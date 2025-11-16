"""
AIMessage 중복 디버깅 테스트

디버그 로그로 정확한 원인 파악
"""

import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from src.custom_claude_code.v2_langgraph.main import process_graph_stream

load_dotenv()


async def test_duplicate_detection():
    """중복 발생 시나리오 재현"""
    print("\n" + "=" * 80)
    print("AIMessage 중복 디버깅 테스트")
    print("=" * 80)

    messages = []
    working_dir = os.getcwd()

    # 도구를 여러 번 호출하는 작업 (중복 발생 가능성 높음)
    print("\n📝 요청: 여러 파일 읽기 작업")
    messages.append(HumanMessage(content="v2_langgraph 폴더의 models.py, config.py, nodes.py 파일을 읽어줘"))

    try:
        await process_graph_stream(messages, working_dir)
        print("\n✅ 성공: 중복 없이 완료")
    except ValueError as e:
        print(f"\n❌ 중복 감지됨!")
        print(str(e))

    print("\n최종 메시지 수:", len(messages))


if __name__ == "__main__":
    asyncio.run(test_duplicate_detection())
