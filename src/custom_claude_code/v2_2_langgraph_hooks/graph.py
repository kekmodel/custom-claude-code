"""
v2.2: LangGraph StateGraph with Hook System

워크플로우: START → agent → should_continue → [tools → agent] or [END]
핵심: StateGraph = 노드(Node) + 엣지(Edge) + 상태(State)

Hook System 통합:
- Tool 실행 전후로 Hook 트리거 가능
- PreToolUse: 도구 검증 및 입력 수정
- PostToolUse: 결과 후처리 및 파일 추출
"""

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import call_agent, execute_subagent, get_system_prompt, should_continue
from .tools import TOOLS_BY_NAME
from .types import AgentState

async def execute_tools(state: AgentState) -> dict:
    """
    커스텀 도구 실행 노드 (LangGraph ToolNode 대체)

    특수 처리: task_tool → Subagent 실행, todo_write → state 업데이트
    일반 도구: TOOLS_BY_NAME에서 invoke()

    Returns: {"messages": [ToolMessage, ...], "todos": [...]}
    """
    messages = state["messages"]
    last_message = messages[-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_messages = []
    updated_todos = state.get("todos")

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]

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

            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_call_id, name=tool_name)
            )

        except Exception as e:
            tool_messages.append(
                ToolMessage(
                    content=f"[ERROR] {type(e).__name__}: {str(e)}", tool_call_id=tool_call_id, name=tool_name
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
