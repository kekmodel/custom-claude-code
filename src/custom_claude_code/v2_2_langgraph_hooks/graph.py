"""
v2.2: LangGraph StateGraph with Hook System

워크플로우: START → agent → should_continue → [tools → agent] or [END]
핵심: StateGraph = 노드(Node) + 엣지(Edge) + 상태(State)

Hook System 완전 통합 (execute_tools 노드):
- PreToolUse Hook: 도구 실행 전 검증/차단/입력 수정
  * decision="block" → 도구 실행 차단
  * updatedInput → 입력 파라미터 수정
  * systemMessage → LLM에게 피드백 전달
- PostToolUse Hook: 도구 실행 후 결과 후처리/즉시 중단
  * continue_=False → 즉시 실행 중단
  * additionalContext → LLM에게 추가 정보 전달
  * hookSpecificOutput → Hook별 특수 출력
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .hooks import trigger_hook, HookContext
from .nodes import call_agent, execute_subagent, get_system_prompt, should_continue
from .tools import TOOLS_BY_NAME
from .types import AgentState

async def execute_tools(state: AgentState) -> dict:
    """
    커스텀 도구 실행 노드 (Hook System 통합)

    특수 처리: task_tool → Subagent 실행, todo_write → state 업데이트
    일반 도구: TOOLS_BY_NAME에서 invoke()
    Hook: PreToolUse (실행 전), PostToolUse (실행 후)

    Returns: {"messages": [ToolMessage, ...], "todos": [...]}
    """
    messages = state["messages"]
    last_message = messages[-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_messages = []
    updated_todos = state.get("todos")

    # Hook Context 생성
    context = HookContext(
        session_id=state.get("session_id", "default"),
        turn_count=len(messages),
    )

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]

        # PreToolUse Hook 트리거
        pre_hook_result = await trigger_hook(
            event="PreToolUse",
            input_data={
                "tool_name": tool_name,
                "tool_input": tool_args,
            },
            tool_use_id=tool_call_id,
            context=context
        )

        # Hook이 차단하면 실행 안 함
        if pre_hook_result.get("decision") == "block":
            error_msg = pre_hook_result.get("systemMessage", "Tool execution blocked by hook")
            tool_messages.append(
                ToolMessage(content=f"[BLOCKED] {error_msg}", tool_call_id=tool_call_id, name=tool_name)
            )

            # systemMessage를 LLM에게 전달
            if pre_hook_result.get("systemMessage"):
                tool_messages.append(
                    HumanMessage(content=f"<system-reminder>\n{pre_hook_result['systemMessage']}\n</system-reminder>")
                )

            continue  # 다음 도구로

        # Hook이 입력 수정했으면 반영
        if "updatedInput" in pre_hook_result:
            tool_args.update(pre_hook_result["updatedInput"])

        # 도구 실행
        try:
            if tool_name == "task_tool":
                system_prompt = get_system_prompt(state.get("working_dir"))
                current_depth = state.get("depth", 0)
                result = await execute_subagent(
                    subagent_type=tool_args.get("subagent_type", "general-purpose"),
                    prompt=tool_args.get("prompt", ""),
                    system_prompt=system_prompt,
                    current_depth=current_depth,
                    max_depth=5,
                    model_name=tool_args.get("model", "claude-haiku-4-5"),
                )

            elif tool_name == "todo_write":
                tool = TOOLS_BY_NAME.get(tool_name)
                result = tool.invoke(tool_args)
                updated_todos = tool_args.get("todos", [])

            else:
                tool = TOOLS_BY_NAME.get(tool_name)
                if not tool:
                    result = f"[ERROR] Unknown tool: {tool_name}"
                else:
                    # Async 도구는 ainvoke 사용
                    if hasattr(tool, 'coroutine') or tool_name in ['web_search', 'web_fetch']:
                        result = await tool.ainvoke(tool_args)
                    else:
                        result = tool.invoke(tool_args)

            # PostToolUse Hook 트리거
            post_hook_result = await trigger_hook(
                event="PostToolUse",
                input_data={
                    "tool_name": tool_name,
                    "tool_input": tool_args,
                    "tool_response": result,
                },
                tool_use_id=tool_call_id,
                context=context
            )

            # continue_ 필드 체크 (즉시 중단)
            if not post_hook_result.get("continue_", True):
                stop_reason = post_hook_result.get("stopReason", "Execution halted by hook")
                tool_messages.append(
                    ToolMessage(content=f"[STOPPED] {stop_reason}", tool_call_id=tool_call_id, name=tool_name)
                )

                # systemMessage 전달
                if post_hook_result.get("systemMessage"):
                    tool_messages.append(
                        HumanMessage(content=f"<system-reminder>\n{post_hook_result['systemMessage']}\n</system-reminder>")
                    )

                # 즉시 반환 (더 이상 도구 실행 안 함)
                result_dict = {"messages": tool_messages}
                if updated_todos is not None:
                    result_dict["todos"] = updated_todos
                return result_dict

            # 일반 Tool Result
            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_call_id, name=tool_name)
            )

            # PostToolUse Hook의 additionalContext를 LLM에게 전달
            hook_output = post_hook_result.get("hookSpecificOutput", {})
            if hook_output.get("additionalContext"):
                tool_messages.append(
                    HumanMessage(content=f"<system-reminder>\n{hook_output['additionalContext']}\n</system-reminder>")
                )

        except Exception as e:
            tool_messages.append(
                ToolMessage(
                    content=f"[ERROR] {type(e).__name__}: {str(e)}",
                    tool_call_id=tool_call_id,
                    name=tool_name
                )
            )

    result_dict = {"messages": tool_messages}
    if updated_todos is not None:
        result_dict["todos"] = updated_todos

    return result_dict


def create_graph(use_memory: bool = True):
    """
    StateGraph 생성 및 구성

    구성: 1) StateGraph(AgentState) → 2) 노드 추가 → 3) 엣지 연결 → 4) 컴파일
    흐름: START → agent → should_continue → [tools → agent] or [END]
    """
    builder = StateGraph(AgentState)

    # 노드: 실행 가능한 함수 (state 받아서 dict 반환)
    builder.add_node("agent", call_agent)
    builder.add_node("tools", execute_tools)

    # START, END: LangGraph 내장 특수 노드
    builder.add_edge(START, "agent")

    # 조건부 엣지: 함수 결과(str)를 다음 노드 이름으로 매핑
    # should_continue()가 "tools" 반환 → tools 노드로, END 반환 → 종료
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")

    if use_memory:
        # MemorySaver: 각 노드 실행 후 state 저장 (대화 이력 유지)
        memory = MemorySaver()
        graph = builder.compile(checkpointer=memory)
    else:
        graph = builder.compile()

    return graph


graph = create_graph(use_memory=False)
graph_with_memory = create_graph(use_memory=True)
