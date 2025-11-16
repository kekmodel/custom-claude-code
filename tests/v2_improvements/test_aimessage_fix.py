"""
AIMessage 중복 문제 수정 검증 테스트

이 테스트는 다음을 확인합니다:
1. 그래프가 1회만 실행되는지 (ainvoke 재실행 방지)
2. 메시지 구조가 올바른지 (연속 AIMessage 방지)
3. Subagent 이벤트가 올바르게 필터링되는지
"""

import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from custom_claude_code.v2_langgraph.graph import graph

load_dotenv()


async def test_message_structure():
    """메시지 구조 검증: User/Assistant 교대 패턴 확인"""
    print("\n" + "=" * 80)
    print("테스트 1: 메시지 구조 검증")
    print("=" * 80)

    messages = [
        HumanMessage(content="파일 목록을 조회하고, 그 중 하나를 읽어줘"),
    ]

    config = {"recursion_limit": 50}
    invocation_count = 0

    # Graph invoke 호출 횟수 추적
    original_ainvoke = graph.ainvoke

    async def counted_ainvoke(*args, **kwargs):
        nonlocal invocation_count
        invocation_count += 1
        print(f"  [DEBUG] ainvoke 호출 #{invocation_count}")
        return await original_ainvoke(*args, **kwargs)

    graph.ainvoke = counted_ainvoke

    try:
        print("\n🚀 그래프 실행 중...")
        result = await graph.ainvoke(
            {"messages": messages, "working_dir": os.getcwd(), "depth": 0, "todos": None}, config=config
        )

        final_messages = result["messages"]

        print(f"\n📊 결과:")
        print(f"  - 총 메시지 수: {len(final_messages)}")
        print(f"  - ainvoke 호출 횟수: {invocation_count}")

        # 메시지 구조 출력
        print(f"\n📝 메시지 구조:")
        for i, msg in enumerate(final_messages):
            msg_type = type(msg).__name__
            has_tools = "(with tool_calls)" if isinstance(msg, AIMessage) and msg.tool_calls else ""
            print(f"  [{i}] {msg_type} {has_tools}")

        # 검증 1: 연속된 AIMessage 확인
        print(f"\n✅ 검증 1: 연속된 AIMessage 확인")
        consecutive_ai = False
        for i in range(len(final_messages) - 1):
            if isinstance(final_messages[i], AIMessage) and isinstance(final_messages[i + 1], AIMessage):
                print(f"  ❌ FAIL: Index {i}와 {i+1}이 모두 AIMessage!")
                consecutive_ai = True

        if not consecutive_ai:
            print(f"  ✅ PASS: 연속된 AIMessage 없음")

        # 검증 2: tool_calls 후 ToolMessage 확인
        print(f"\n✅ 검증 2: tool_calls 후 ToolMessage 확인")
        tool_call_check = True
        for i in range(len(final_messages) - 1):
            if isinstance(final_messages[i], AIMessage) and final_messages[i].tool_calls:
                next_msg = final_messages[i + 1]
                if not isinstance(next_msg, ToolMessage):
                    print(f"  ❌ FAIL: Index {i} AIMessage with tool_calls 후 {type(next_msg).__name__}!")
                    tool_call_check = False

        if tool_call_check:
            print(f"  ✅ PASS: 모든 tool_calls 후 ToolMessage 존재")

        # 검증 3: ainvoke 호출 횟수
        print(f"\n✅ 검증 3: 그래프 실행 횟수")
        if invocation_count == 1:
            print(f"  ✅ PASS: ainvoke 1회만 호출됨 (이중 실행 없음)")
        else:
            print(f"  ❌ FAIL: ainvoke {invocation_count}회 호출됨 (예상: 1회)")

        return not consecutive_ai and tool_call_check and invocation_count == 1

    finally:
        graph.ainvoke = original_ainvoke


async def test_subagent_execution():
    """Subagent 실행 시 메시지 중복 방지 확인"""
    print("\n" + "=" * 80)
    print("테스트 2: Subagent 실행 (task_tool 사용)")
    print("=" * 80)

    messages = [
        HumanMessage(content="코드베이스에서 main.py 파일을 찾아서 첫 10줄을 읽어줘"),
    ]

    config = {"recursion_limit": 50}

    print("\n🚀 그래프 실행 중 (task_tool 사용 예상)...")
    result = await graph.ainvoke(
        {"messages": messages, "working_dir": os.getcwd(), "depth": 0, "todos": None}, config=config
    )

    final_messages = result["messages"]

    print(f"\n📊 결과:")
    print(f"  - 총 메시지 수: {len(final_messages)}")

    # 메시지 구조 출력
    print(f"\n📝 메시지 구조:")
    for i, msg in enumerate(final_messages):
        msg_type = type(msg).__name__
        has_tools = "(with tool_calls)" if isinstance(msg, AIMessage) and msg.tool_calls else ""
        if isinstance(msg, AIMessage) and msg.tool_calls:
            tool_names = [tc.get("name") for tc in msg.tool_calls]
            has_tools += f" {tool_names}"
        print(f"  [{i}] {msg_type} {has_tools}")

    # 검증: task_tool 사용 후에도 연속 AIMessage 없는지
    print(f"\n✅ 검증: task_tool 사용 후 메시지 구조")
    consecutive_ai = False
    for i in range(len(final_messages) - 1):
        if isinstance(final_messages[i], AIMessage) and isinstance(final_messages[i + 1], AIMessage):
            print(f"  ❌ FAIL: Index {i}와 {i+1}이 모두 AIMessage!")
            consecutive_ai = True

    if not consecutive_ai:
        print(f"  ✅ PASS: task_tool 사용 후에도 연속 AIMessage 없음")

    return not consecutive_ai


async def test_astream_events_state_capture():
    """astream_events에서 최종 state 추출 확인"""
    print("\n" + "=" * 80)
    print("테스트 3: astream_events 최종 state 캡처")
    print("=" * 80)

    from custom_claude_code.v2_langgraph.main import EventHandler

    messages = [HumanMessage(content="현재 디렉토리 경로를 알려줘")]
    config = {"recursion_limit": 50}

    handler = EventHandler(initial_messages=messages)
    print("\n🚀 astream_events 실행 중...")

    async for event in graph.astream_events(
        {"messages": messages, "working_dir": os.getcwd(), "depth": 0, "todos": None},
        config=config,
        version="v2",
    ):
        kind = event.get("event")

        if kind == "on_chain_start":
            handler.handle_chain_start(event)
        elif kind == "on_chat_model_stream":
            handler.handle_chat_model_stream(event)
        elif kind == "on_chat_model_end":
            handler.handle_chat_model_end(event)
        elif kind == "on_chain_end":
            handler.handle_chain_end(event)

    final_messages = handler.get_final_messages()

    print(f"\n📊 결과:")
    if final_messages:
        print(f"  ✅ 최종 messages 캡처 성공")
        print(f"  - Messages: {len(final_messages)}개")
        print(f"\n📝 메시지 구조:")
        for i, msg in enumerate(final_messages):
            msg_type = type(msg).__name__
            print(f"  [{i}] {msg_type}")

        consecutive_ai = False
        for i in range(len(final_messages) - 1):
            if isinstance(final_messages[i], AIMessage) and isinstance(final_messages[i + 1], AIMessage):
                consecutive_ai = True

        if not consecutive_ai:
            print(f"\n  ✅ PASS: astream_events에서 누적한 messages도 올바른 메시지 구조")
            return True
        else:
            print(f"\n  ❌ FAIL: astream_events에서 누적한 messages에 연속 AIMessage 존재")
            return False
    else:
        print(f"  ❌ FAIL: 최종 messages 캡처 실패")
        return False


async def main():
    """전체 테스트 실행"""
    print("\n" + "=" * 80)
    print("AIMessage 중복 문제 수정 검증 테스트")
    print("=" * 80)

    results = []

    try:
        # 테스트 1: 기본 메시지 구조
        result1 = await test_message_structure()
        results.append(("메시지 구조 검증", result1))
    except Exception as e:
        print(f"\n❌ 테스트 1 실패: {e}")
        import traceback

        traceback.print_exc()
        results.append(("메시지 구조 검증", False))

    try:
        # 테스트 2: Subagent 실행
        result2 = await test_subagent_execution()
        results.append(("Subagent 실행", result2))
    except Exception as e:
        print(f"\n❌ 테스트 2 실패: {e}")
        import traceback

        traceback.print_exc()
        results.append(("Subagent 실행", False))

    try:
        # 테스트 3: astream_events state 캡처
        result3 = await test_astream_events_state_capture()
        results.append(("astream_events state 캡처", result3))
    except Exception as e:
        print(f"\n❌ 테스트 3 실패: {e}")
        import traceback

        traceback.print_exc()
        results.append(("astream_events state 캡처", False))

    # 최종 결과
    print("\n" + "=" * 80)
    print("테스트 결과 요약")
    print("=" * 80)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(result for _, result in results)
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 모든 테스트 통과!")
    else:
        print("❌ 일부 테스트 실패")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
