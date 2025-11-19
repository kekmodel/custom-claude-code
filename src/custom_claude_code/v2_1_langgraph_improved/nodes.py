"""
v2.1: LangGraph Nodes (Improved)

개선 사항:
- compact_messages() 제거 (불필요한 압축 로직)
- call_agent() 단순화 (복잡한 RemoveMessage 로직 제거)
- 더 간결하고 명확한 코드
"""

import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .config import V2Config
from .models import MODEL_ALIASES, get_model
from .prompts import get_subagent_system_prompt, get_system_prompt
from .tools import TOOLS
from .types import AgentState

load_dotenv()

# 중앙 설정에서 모델 가져오기
model = get_model(**V2Config.get_model_config())
model_with_tools = model.bind_tools(TOOLS)


async def call_agent(state: AgentState) -> dict:
    """
    LLM 호출 노드 (단순화)

    흐름: SystemMessage 보장 → LLM 호출 → AIMessage 반환
    Returns: {"messages": [AIMessage(...)]}
    """
    messages = list(state["messages"])

    # SystemMessage 보장
    if not messages or not isinstance(messages[0], SystemMessage):
        working_dir = state.get("working_dir", os.getcwd())
        system_prompt = get_system_prompt(working_dir)
        messages = [SystemMessage(content=system_prompt)] + list(messages)

    # LLM 호출 (LangGraph의 add_messages reducer가 자동으로 중복 처리)
    response = await model_with_tools.ainvoke(messages)

    return {"messages": [response]}


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """조건부 라우팅: tool_calls 있으면 "tools", 없으면 END"""
    messages = state["messages"]
    last_message = messages[-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return END


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
    공통 제외: task_tool, todo_write
    """
    from langchain_core.runnables import RunnableConfig

    if current_depth >= max_depth:
        return f"[ERROR] Max subagent depth ({max_depth}) exceeded"

    # 모델 이름 처리 (별칭 지원)
    if model_name in MODEL_ALIASES:
        provider, full_model_name = MODEL_ALIASES[model_name]
    else:
        provider = "anthropic"
        full_model_name = model_name

    # 도구 제한 (역할별 명확한 원칙)
    excluded_tools = {"task_tool", "todo_write"}  # 모든 subagent 공통 제외
    allowed_tools = [t for t in TOOLS if t.name not in excluded_tools]

    if subagent_type == "Explore":
        # 순수 정보 수집: 읽기 + 검색만, 수정/실행 금지
        explore_tools = {"read_file", "grep_code", "glob_files", "web_search", "web_fetch"}
        allowed_tools = [t for t in allowed_tools if t.name in explore_tools]
    elif subagent_type == "Plan":
        # 계획 수립: 정보 수집 + 웹 연구, 실행 금지
        plan_tools = {"read_file", "grep_code", "glob_files", "web_search", "web_fetch"}
        allowed_tools = [t for t in allowed_tools if t.name in plan_tools]

    subagent_system_prompt = get_subagent_system_prompt(system_prompt, subagent_type, allowed_tools)

    def subagent_call_agent(state: AgentState) -> dict:
        """Subagent LLM 호출"""
        msgs = state["messages"]

        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=subagent_system_prompt)] + list(msgs)

        # Subagent용 모델 생성
        llm = get_model(provider=provider, model_name=full_model_name)
        llm_with_tools = llm.bind_tools(allowed_tools)
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def subagent_should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        msgs = state["messages"]
        last_msg = msgs[-1]

        if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
            return "tools"

        return END

    # 독립 StateGraph 생성
    builder = StateGraph(AgentState)
    builder.add_node("agent", subagent_call_agent)
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
        # callbacks=[] 로 subagent 이벤트가 main graph로 전파되는 것 방지
        final_state = await subagent_graph.ainvoke(initial_state, config=RunnableConfig(callbacks=[]))

        if final_state["messages"]:
            last_msg = final_state["messages"][-1]
            if isinstance(last_msg, AIMessage):
                return last_msg.content or "(no response)"

        return "(no response)"

    except Exception as e:
        return f"[ERROR] Subagent failed: {type(e).__name__}: {str(e)}"
