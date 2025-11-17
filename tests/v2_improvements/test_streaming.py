"""
텍스트 스트리밍 테스트

"..." 없이 실시간으로 나와야 함
"""

import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from custom_claude_code.v2_langgraph.main import process_graph_stream

load_dotenv()


async def test_streaming():
    """간단한 질문으로 스트리밍 테스트"""
    print("\n" + "=" * 80)
    print("텍스트 스트리밍 테스트")
    print("=" * 80)

    messages = []
    working_dir = os.getcwd()

    print("\n📝 요청: 간단한 Python 함수 작성 (스트리밍 확인)")
    messages.append(HumanMessage(content="Hello! 간단하게 인사해줘"))

    await process_graph_stream(messages, working_dir)

    print("\n✅ 완료")


if __name__ == "__main__":
    asyncio.run(test_streaming())
