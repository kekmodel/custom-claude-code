"""
Subagent 메시지 필터링 테스트

task_tool을 사용하는 subagent가 자체 tool call을 할 때
messages 구조가 깨지지 않는지 검증
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def test_subagent_with_tool_calls():
    """
    Subagent가 자체 tool call을 할 때 메시지 구조 테스트

    시나리오:
    1. Main agent가 task_tool 호출 (Explore agent 실행)
    2. Explore agent가 glob_files 호출
    3. Main agent의 messages에 Explore의 AIMessage(tool_calls)가 섞이면 안됨
    """
    print("=" * 60)
    print("Subagent 메시지 필터링 테스트")
    print("=" * 60)

    from langchain_core.messages import HumanMessage
    from custom_claude_code.v2_1_langgraph_improved.graph import graph

    # API 키 확인
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print("❌ API 키가 설정되지 않았습니다.")
        return 1

    print("\n[1] Main agent가 task_tool(Explore)를 호출하는 요청...")
    print("   Explore agent는 내부적으로 glob_files를 사용할 것입니다.\n")

    # 간단한 요청: Explore agent가 파일을 찾도록
    initial_state = {
        "messages": [
            HumanMessage(content="Use the Explore agent to find all Python test files in this directory. Just list them.")
        ],
        "working_dir": os.getcwd(),
        "depth": 0,
        "todos": None,
    }

    try:
        config = {"recursion_limit": 50}
        final_state = await graph.ainvoke(initial_state, config=config)

        messages = final_state["messages"]

        print(f"\n[2] 최종 메시지 구조 검증...")
        print(f"   총 메시지 개수: {len(messages)}\n")

        # 메시지 구조 분석
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__

            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                tool_names = [tc.get('name', 'unknown') for tc in msg.tool_calls]
                print(f"   [{i}] {msg_type} with tool_calls: {tool_names}")
            elif hasattr(msg, 'name'):
                print(f"   [{i}] {msg_type} (tool: {msg.name})")
            else:
                content_preview = msg.content[:50] if hasattr(msg, 'content') else "..."
                print(f"   [{i}] {msg_type}: {content_preview}...")

        # 검증: AIMessage와 ToolMessage가 올바르게 쌍을 이루는지
        print(f"\n[3] 메시지 흐름 검증...")

        ai_with_tools = []
        tool_results = []

        for i, msg in enumerate(messages):
            if type(msg).__name__ == 'AIMessage' and hasattr(msg, 'tool_calls') and msg.tool_calls:
                ai_with_tools.append((i, msg.tool_calls))
            elif type(msg).__name__ == 'ToolMessage':
                tool_results.append((i, msg.tool_call_id))

        print(f"   AIMessage(with tool_calls): {len(ai_with_tools)}개")
        print(f"   ToolMessage(results): {len(tool_results)}개")

        # 각 AIMessage의 tool_call이 다음에 ToolMessage로 응답되는지 확인
        for ai_idx, tool_calls in ai_with_tools:
            tool_call_ids = {tc['id'] for tc in tool_calls}

            # 다음 메시지들에서 ToolMessage 찾기
            found_results = set()
            for tr_idx, tr_id in tool_results:
                if tr_idx > ai_idx and tr_id in tool_call_ids:
                    found_results.add(tr_id)

            if found_results == tool_call_ids:
                print(f"   ✅ 메시지 [{ai_idx}]의 모든 tool_calls에 대한 결과 존재")
            else:
                missing = tool_call_ids - found_results
                print(f"   ❌ 메시지 [{ai_idx}]의 tool_calls 중 결과 없음: {missing}")
                print(f"\n   🔍 이것이 바로 'tool_use without tool_result' 오류의 원인입니다!")
                print(f"   Subagent의 AIMessage가 main graph messages에 잘못 추가되었습니다.\n")
                return 1

        print(f"\n✅ 테스트 통과: 모든 tool_calls에 대한 결과가 존재합니다!")
        print(f"   Subagent 필터링이 올바르게 작동합니다.\n")

        return 0

    except Exception as e:
        print(f"\n❌ 테스트 실패: {type(e).__name__}: {str(e)}\n")

        # 오류가 발생한 경우 메시지 구조 출력
        if "tool_use" in str(e) and "tool_result" in str(e):
            print("   이 오류는 Subagent의 AIMessage가 main graph에 섞였을 때 발생합니다.")
            print("   EventHandler의 필터링 로직을 확인하세요.\n")

        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_subagent_with_tool_calls())
    exit(exit_code)
