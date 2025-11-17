"""
Agent 스피너 테스트

Agent가 thinking 시작할 때 스피너가 표시되는지 확인
"""

import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from custom_claude_code.v2_langgraph.main import process_graph_stream

load_dotenv()


async def test_agent_spinner():
    """Agent thinking 시 스피너 표시 테스트"""
    print("\n" + "=" * 80)
    print("Agent 스피너 테스트")
    print("=" * 80)

    messages = []
    working_dir = os.getcwd()

    print("\n📝 요청: Python의 리스트 컴프리헨션 설명해줘")
    print("\n💡 확인 사항:")
    print("  - Agent 시작 시 🤔 스피너가 표시되는가?")
    print("  - Thinking이 시작되면 스피너가 Thinking 패널로 전환되는가?")
    print("  - Content가 시작되면 스피너가 Content 패널로 전환되는가?")
    print("")

    messages.append(HumanMessage(content="Python의 리스트 컴프리헨션에 대해 간단히 설명해줘"))

    await process_graph_stream(messages, working_dir)

    print("\n✅ 완료")


if __name__ == "__main__":
    asyncio.run(test_agent_spinner())
