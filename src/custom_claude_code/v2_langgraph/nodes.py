"""
v2: LangGraph Nodes

핵심 노드: call_agent (LLM 호출), should_continue (라우팅), execute_subagent (재귀 실행)
Auto compact: 100k tokens 초과 시 자동 압축
"""

import os
from typing import Literal

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END

from .prompts import (
    get_conversation_summary_prompt,
    get_subagent_system_prompt,
    get_system_prompt,
)
from .tools import TOOLS
from .types import AgentState

load_dotenv()

model = ChatAnthropic(
    model="claude-haiku-4-5",
    temperature=1,
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    thinking={"type": "enabled", "budget_tokens": 2048},
)

model_with_tools = model.bind_tools(TOOLS)


async def call_agent(state: AgentState) -> dict:
    """
    LLM 호출 노드

    흐름: SystemMessage 보장 → Auto compact → LLM 호출 → AIMessage 반환
    Returns: {"messages": [AIMessage(...)]}
    """
    messages = list(state["messages"])

    if not messages or not isinstance(messages[0], SystemMessage):
        working_dir = state.get("working_dir", os.getcwd())
        system_prompt = get_system_prompt(working_dir)
        messages = [SystemMessage(content=system_prompt)] + list(messages)

    original_message_count = len(messages)
    messages = await compact_messages(messages)
    was_compressed = len(messages) < original_message_count

    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            if i + 1 < len(messages):
                next_msg = messages[i + 1]
                if not isinstance(next_msg, ToolMessage):
                    error_msg = [
                        f"\n❌ 메시지 구조 오류!",
                        f"   Index {i}: AIMessage with tool_calls",
                        f"   Tool calls: {[tc.get('name') for tc in msg.tool_calls]}",
                        f"   Index {i+1}: {type(next_msg).__name__} (should be ToolMessage!)",
                        f"\n전체 메시지 구조:",
                    ]
                    for idx, m in enumerate(messages):
                        msg_type = type(m).__name__
                        has_tools = (
                            "(with tool_calls)"
                            if isinstance(m, AIMessage) and hasattr(m, "tool_calls") and m.tool_calls
                            else ""
                        )
                        error_msg.append(f"   [{idx}] {msg_type} {has_tools}")

                    raise ValueError("\n".join(error_msg))

    response = await model_with_tools.ainvoke(messages)

    if was_compressed:
        # RemoveMessage: LangGraph에서 state의 특정 메시지 삭제 (id 기반)
        from langchain_core.messages import RemoveMessage

        remove_messages = [
            RemoveMessage(id=msg.id)
            for msg in state["messages"]
            if not isinstance(msg, SystemMessage) and hasattr(msg, "id") and msg.id is not None
        ]

        compressed_without_system = [msg for msg in messages if not isinstance(msg, SystemMessage)]

        if compressed_without_system and isinstance(compressed_without_system[-1], AIMessage):
            has_tools = (
                hasattr(compressed_without_system[-1], "tool_calls") and compressed_without_system[-1].tool_calls
            )
            print(
                f"\n🔧 중복 방지: 압축된 메시지의 마지막 AIMessage 제거"
                f" (tool_calls={'있음' if has_tools else '없음'})"
            )
            compressed_without_system = compressed_without_system[:-1]

        # State 교체: [RemoveMessage들, 압축된 메시지들, 새 응답]
        # add_messages reducer가 RemoveMessage 먼저 처리 후 나머지 append
        return {"messages": remove_messages + compressed_without_system + [response]}
    else:
        if state["messages"] and isinstance(state["messages"][-1], AIMessage) and isinstance(response, AIMessage):
            print("\n🔧 중복 방지: 이전 AIMessage 교체")
            from langchain_core.messages import RemoveMessage

            last_msg = state["messages"][-1]
            if hasattr(last_msg, "id") and last_msg.id is not None:
                return {"messages": [RemoveMessage(id=last_msg.id), response]}
            else:
                return {"messages": [response]}
        else:
            return {"messages": [response]}


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """조건부 라우팅: tool_calls 있으면 "tools", 없으면 END"""
    messages = state["messages"]
    last_message = messages[-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    # END: LangGraph 내장 상수 (실제 값은 "__end__")
    return END


def _count_tokens(messages: list) -> int:
    """토큰 수 추정 (문자 수 / 4)"""
    import json

    total_chars = 0
    for msg in messages:
        if hasattr(msg, "content") and msg.content:
            total_chars += len(str(msg.content))
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            total_chars += len(json.dumps(msg.tool_calls))
    return total_chars // 4


def _format_messages_for_summary(messages: list) -> str:
    """요약용 텍스트 포맷팅 (User/Assistant/Tool)"""
    from langchain_core.messages import HumanMessage, ToolMessage

    formatted = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            formatted.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            if msg.content:
                formatted.append(f"Assistant: {msg.content}")
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_names = [tc.get("name", "unknown") for tc in msg.tool_calls]
                formatted.append(f"Assistant: [도구 호출: {', '.join(tool_names)}]")
        elif isinstance(msg, ToolMessage):
            tool_name = getattr(msg, "name", "unknown_tool")
            content = str(msg.content) if msg.content else "(empty)"
            formatted.append(f"Tool({tool_name}): {content}")

    return "\n".join(formatted)


async def compact_messages(messages: list, max_tokens: int = 100_000) -> list:
    """
    대화 자동 압축 (max_tokens 초과 시)

    전략: SystemMessage + LLM 요약 + 최근 대화 턴 유지
    Returns: [SystemMessage, HumanMessage(요약), 최근 대화...]
    """
    from langchain_core.messages import HumanMessage

    system_msg = messages[0] if isinstance(messages[0], SystemMessage) else None
    actual_start_idx = 1 if system_msg else 0
    actual_messages = messages[actual_start_idx:]

    token_count = _count_tokens(actual_messages)
    if token_count <= max_tokens:
        return messages

    if len(messages) >= 2:
        second_msg = messages[1]
        if isinstance(second_msg, HumanMessage) and hasattr(second_msg, "content"):
            if isinstance(second_msg.content, str) and second_msg.content.startswith("[이전 대화 요약]"):
                print(f"   ⚠️  방금 압축했으므로 스킵 (무한 루프 방지)\n")
                return messages

    print(f"\n🗜️  Auto-compact 시작: {len(messages)}개 메시지, {token_count:,} tokens → {max_tokens:,} 초과")

    start_idx = actual_start_idx
    recent_start_idx = None
    for i in range(len(messages) - 1, start_idx - 1, -1):
        if isinstance(messages[i], HumanMessage):
            recent_start_idx = i
            break

    assert recent_start_idx is not None, "정상 대화에서 HumanMessage는 항상 존재"

    recent_messages = messages[recent_start_idx:]
    middle_messages = messages[start_idx:recent_start_idx]

    if len(middle_messages) < 5:
        return messages

    formatted_messages = _format_messages_for_summary(middle_messages)
    summary_prompt = get_conversation_summary_prompt(formatted_messages)
    summary_llm = ChatAnthropic(
        model="claude-haiku-4-5",
        temperature=1,
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        thinking={"type": "enabled", "budget_tokens": 2048},
    )

    try:
        from langchain_core.runnables import RunnableConfig

        summary_response = await summary_llm.ainvoke(
            [HumanMessage(content=summary_prompt)], config=RunnableConfig(callbacks=[])
        )
        summary_content = summary_response.content

        if isinstance(summary_content, list):
            text_blocks = [block for block in summary_content if block.get("type") == "text"]
            summary_text = "\n".join(block.get("text", "") for block in text_blocks)
        else:
            summary_text = summary_content

        summary_message = HumanMessage(content=f"[이전 대화 요약]\n\n{summary_text}\n\n[요약 끝 - 최근 대화 계속]")

    except Exception as e:
        summary_message = HumanMessage(content=f"[이전 대화 요약 실패: {len(middle_messages)}개 메시지 생략]")
        print(f"\n⚠️  요약 생성 실패: {e}\n")

    compressed = []
    if system_msg:
        compressed.append(system_msg)

    compressed.append(summary_message)

    for i, msg in enumerate(recent_messages):
        if isinstance(msg, AIMessage) and hasattr(msg, "content"):
            if isinstance(msg.content, list) and len(msg.content) > 0:
                first_block_type = msg.content[0].get("type")
                if first_block_type not in ["thinking", "redacted_thinking"]:
                    text_blocks = [block.get("text", "") for block in msg.content if block.get("type") == "text"]
                    if text_blocks:
                        new_msg = AIMessage(
                            content=" ".join(text_blocks),
                            tool_calls=msg.tool_calls if hasattr(msg, "tool_calls") and msg.tool_calls else None,
                        )
                        recent_messages[i] = new_msg

    compressed.extend(recent_messages)

    compressed_actual = compressed[1:] if system_msg else compressed
    compressed_tokens = _count_tokens(compressed_actual)

    print(
        f"✅ 압축 완료: {len(messages)}개 → {len(compressed)}개 메시지, {token_count:,} → {compressed_tokens:,} tokens\n"
    )

    if compressed_tokens > max_tokens:
        print(f"   ⚠️  경고: 압축 후에도 {compressed_tokens:,} > {max_tokens:,} tokens\n")

    return compressed


async def execute_subagent(
    subagent_type: str,
    prompt: str,
    system_prompt: str,
    current_depth: int = 0,
    max_depth: int = 5,
    model_name: str = "claude-haiku-4-5",
) -> str:
    """
    독립 StateGraph로 Subagent 실행

    도구 제한: Explore (읽기 전용), Plan (읽기만), general (전체)
    공통 제외: task_tool, todo_write, exit_plan_mode
    """
    from langchain_core.messages import HumanMessage
    from langgraph.graph import START, StateGraph
    from langgraph.prebuilt import ToolNode

    if current_depth >= max_depth:
        return f"[ERROR] Max subagent depth ({max_depth}) exceeded"

    model_map = {
        "haiku": "claude-haiku-4-5",
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-20250514",
    }
    full_model_name = model_map.get(model_name, model_name)

    excluded_tools = {"task_tool", "todo_write", "exit_plan_mode"}
    allowed_tools = [t for t in TOOLS if t.name not in excluded_tools]

    if subagent_type == "Explore":
        write_tools = {"write_file", "edit_file"}
        allowed_tools = [t for t in allowed_tools if t.name not in write_tools]
    elif subagent_type == "Plan":
        read_only_tools = {"read_file", "grep_code", "glob_files", "run_bash"}
        allowed_tools = [t for t in allowed_tools if t.name in read_only_tools]

    subagent_system_prompt = get_subagent_system_prompt(system_prompt, subagent_type, allowed_tools)

    def subagent_call_agent(state: AgentState) -> dict:
        msgs = state["messages"]

        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=subagent_system_prompt)] + list(msgs)

        # FIX: 불완전한 도구 호출 제거 (연속 AIMessage 방지)
        if msgs:
            last_msg = msgs[-1]
            if isinstance(last_msg, AIMessage) and hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                print(f"\n⚠️  [Subagent] 불완전한 도구 호출 감지!")
                print(f"   Tool calls: {[tc['name'] for tc in last_msg.tool_calls]}")
                print(f"   → 마지막 AIMessage 제거하여 연속된 AIMessage 방지\n")
                msgs = msgs[:-1]

        llm = ChatAnthropic(
            model=full_model_name,
            temperature=1,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            thinking={"type": "enabled", "budget_tokens": 2048},
        )
        llm_with_tools = llm.bind_tools(allowed_tools)
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def subagent_should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        msgs = state["messages"]
        last_msg = msgs[-1]

        if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
            return "tools"

        return END

    builder = StateGraph(AgentState)
    builder.add_node("agent", subagent_call_agent)
    # ToolNode: LangGraph 기본 도구 실행 노드 (tool_calls → invoke → ToolMessage)
    builder.add_node("tools", ToolNode(allowed_tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", subagent_should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")

    subagent_graph = builder.compile()

    initial_state = {
        "messages": [HumanMessage(content=prompt)],
        "working_dir": os.getcwd(),
        "selected_tools": None,
        "depth": current_depth + 1,
        "todos": None,
    }

    try:
        final_state = await subagent_graph.ainvoke(initial_state)

        if final_state["messages"]:
            last_msg = final_state["messages"][-1]
            if isinstance(last_msg, AIMessage):
                return last_msg.content or "(no response)"

        return "(no response)"

    except Exception as e:
        return f"[ERROR] Subagent failed: {type(e).__name__}: {str(e)}"
