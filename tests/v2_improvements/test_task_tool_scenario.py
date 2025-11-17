"""
task_tool 실제 사용 시나리오 테스트

Explore agent를 사용하여 코드베이스 구조 파악
"""

import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from custom_claude_code.v2_langgraph.main import process_graph_stream

load_dotenv()


async def test_task_tool_scenario():
    """task_tool (Explore agent) 사용 시나리오"""
    print("\n" + "=" * 80)
    print("task_tool (Explore agent) 시나리오 테스트")
    print("=" * 80)

    messages = []
    working_dir = os.getcwd()

    # Explore agent를 호출하는 요청 (LLM이 task_tool을 사용하도록 유도)
    print("\n📝 요청: 코드베이스 구조 분석 (Explore agent 유도)")
    messages.append(HumanMessage(content="코드베이스 구조를 간단히 설명해줘"))

    try:
        await process_graph_stream(messages, working_dir)
        print("\n✅ 성공: task_tool 시나리오 완료")
    except ValueError as e:
        print(f"\n❌ 실패: {e}")
        return False

    print(f"\n최종 메시지 수: {len(messages)}")

    # 연속 AIMessage 체크
    consecutive_found = False
    for i in range(len(messages) - 1):
        from langchain_core.messages import AIMessage

        if isinstance(messages[i], AIMessage) and isinstance(messages[i + 1], AIMessage):
            consecutive_found = True
            print(f"\n⚠️  [{i}]-[{i+1}] 연속 AIMessage 발견!")

    if not consecutive_found:
        print("\n✅ 연속 AIMessage 없음 - 테스트 통과!")
        return True
    else:
        print("\n❌ 연속 AIMessage 존재 - 테스트 실패!")
        return False


if __name__ == "__main__":
    asyncio.run(test_task_tool_scenario())
