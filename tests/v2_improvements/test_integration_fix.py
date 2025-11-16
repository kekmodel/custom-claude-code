"""
통합 테스트: process_graph_stream 함수가 올바르게 동작하는지 확인
"""

import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from custom_claude_code.v2_langgraph.main import process_graph_stream

load_dotenv()


async def test_process_graph_stream():
    """process_graph_stream이 messages를 올바르게 업데이트하는지 확인"""
    print("\n" + "=" * 80)
    print("통합 테스트: process_graph_stream")
    print("=" * 80)

    messages = []
    working_dir = os.getcwd()

    # 첫 번째 대화
    print("\n[대화 1] 파일 목록 조회")
    messages.append(HumanMessage(content="현재 디렉토리의 Python 파일 목록을 보여줘"))
    await process_graph_stream(messages, working_dir)

    print(f"\n📊 대화 1 후 메시지 수: {len(messages)}")
    print("📝 메시지 구조:")
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        has_tools = "(with tool_calls)" if isinstance(msg, AIMessage) and msg.tool_calls else ""
        print(f"  [{i}] {msg_type} {has_tools}")

    # 연속 AIMessage 체크
    consecutive = False
    for i in range(len(messages) - 1):
        if isinstance(messages[i], AIMessage) and isinstance(messages[i + 1], AIMessage):
            print(f"❌ FAIL: Index {i}와 {i+1}이 모두 AIMessage!")
            consecutive = True

    if not consecutive:
        print("✅ 대화 1: 메시지 구조 정상")

    # 두 번째 대화 (누적)
    print("\n[대화 2] 이전 대화 이어서")
    prev_count = len(messages)
    messages.append(HumanMessage(content="그 중에서 test로 시작하는 파일만 보여줘"))
    await process_graph_stream(messages, working_dir)

    print(f"\n📊 대화 2 후 메시지 수: {len(messages)} (이전: {prev_count})")
    print("📝 메시지 구조:")
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        has_tools = "(with tool_calls)" if isinstance(msg, AIMessage) and msg.tool_calls else ""
        print(f"  [{i}] {msg_type} {has_tools}")

    # 연속 AIMessage 체크
    consecutive = False
    for i in range(len(messages) - 1):
        if isinstance(messages[i], AIMessage) and isinstance(messages[i + 1], AIMessage):
            print(f"❌ FAIL: Index {i}와 {i+1}이 모두 AIMessage!")
            consecutive = True

    if not consecutive:
        print("✅ 대화 2: 메시지 구조 정상")

    print("\n" + "=" * 80)
    if not consecutive:
        print("🎉 통합 테스트 성공: process_graph_stream이 메시지를 올바르게 관리함")
    else:
        print("❌ 통합 테스트 실패: 메시지 구조 오류 발생")
    print("=" * 80)

    return not consecutive


async def main():
    try:
        success = await test_process_graph_stream()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 에러: {e}")
        import traceback

        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
