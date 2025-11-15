"""
v2: LangGraph StateGraph 구성

Claude Code의 핵심 워크플로우를 StateGraph로 구현:
1. START → agent
2. agent → conditional_edge → tools or END
3. tools → agent (루프)
"""

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .nodes import call_agent, execute_subagent, get_system_prompt, should_continue
from .tools import TOOLS, TOOLS_BY_NAME
from .types import AgentState

# ============================================================================
# Custom Tool Execution Node (Subagent 지원)
# ============================================================================


async def execute_tools(state: AgentState) -> dict:
    """
    커스텀 도구 실행 노드

    task_tool 호출은 execute_subagent()로 라우팅하고,
    나머지 도구는 정상 실행

    Args:
        state: 현재 AgentState

    Returns:
        ToolMessage 결과들
    """
    messages = state["messages"]
    last_message = messages[-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_messages = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]

        try:
            # Task tool은 특별 처리 (Subagent 실행!)
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
            else:
                # 일반 도구는 정상 실행
                tool = TOOLS_BY_NAME.get(tool_name)
                if not tool:
                    result = f"[ERROR] Unknown tool: {tool_name}"
                else:
                    result = tool.invoke(tool_args)

            tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call_id))

        except Exception as e:
            tool_messages.append(
                ToolMessage(content=f"[ERROR] {type(e).__name__}: {str(e)}", tool_call_id=tool_call_id)
            )

    return {"messages": tool_messages}


# ============================================================================
# StateGraph 구성
# ============================================================================


def create_graph(use_memory: bool = False):
    """
    LangGraph StateGraph 생성

    Args:
        use_memory: 메모리 사용 여부 (checkpointer)

    Returns:
        Compiled graph
    """
    # StateGraph 생성
    builder = StateGraph(AgentState)

    # 노드 추가
    builder.add_node("agent", call_agent)
    builder.add_node("tools", execute_tools)  # 커스텀 도구 노드 (Subagent 지원!)

    # 엣지 추가
    builder.add_edge(START, "agent")  # START → agent

    # 조건부 엣지: agent → tools or END
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",  # tool_calls 있으면 tools로
            END: END,  # 없으면 종료
        },
    )

    builder.add_edge("tools", "agent")  # tools → agent (루프)

    # Compile
    if use_memory:
        memory = MemorySaver()
        graph = builder.compile(checkpointer=memory)
    else:
        graph = builder.compile()

    return graph


# ============================================================================
# 기본 그래프 인스턴스
# ============================================================================

# 메모리 없는 기본 그래프
graph = create_graph(use_memory=False)

# 메모리 사용 그래프
graph_with_memory = create_graph(use_memory=True)
