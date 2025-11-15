"""
v2: LangGraph Nodes

LangGraph 노드 함수 정의:
- call_agent: LLM 호출 (도구와 함께)
- should_continue: 조건부 엣지 함수
"""

import os
import platform as platform_module
from datetime import datetime
from typing import Any, Dict, Literal

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END

from .tools import TOOLS, TOOLS_BY_NAME
from .types import AgentState

# ============================================================================
# System Prompt 생성 (간소화 버전)
# ============================================================================


def get_system_prompt(working_dir: str = None) -> str:
    """
    간소화된 시스템 프롬프트 생성

    LangGraph 버전은 v1보다 간단하게 유지
    (그래프 구조가 워크플로우를 자동화하므로)
    """
    if working_dir is None:
        working_dir = os.getcwd()

    is_git_repo = os.path.exists(os.path.join(working_dir, ".git"))
    platform_name = platform_module.system().lower()
    os_version = platform_module.platform()
    today = datetime.now().strftime("%Y-%m-%d")

    return f"""You are a coding assistant powered by LangGraph.

# Environment

<env>
Working directory: {working_dir}
Is directory a git repo: {"Yes" if is_git_repo else "No"}
Platform: {platform_name}
OS Version: {os_version}
Today's date: {today}
</env>

# Tools

You have access to the following tools:
- **read_file**: Read a file with line numbers
- **write_file**: Create or overwrite a file
- **edit_file**: Edit a file by replacing exact strings
- **glob_files**: Find files by glob pattern (e.g., "**/*.ts")
- **grep_code**: Search code with regex
- **run_bash**: Execute bash commands

# Guidelines

1. **Read before Edit**: Always use read_file before edit_file
2. **Absolute Paths**: Always use absolute file paths
3. **Safety**: Verify dangerous operations with the user
4. **Code References**: Use `file_path:line_number` format when referencing code
5. **Explanations**: Provide brief explanations of your actions

Now, help the user with their request."""


# ============================================================================
# LLM 초기화
# ============================================================================

# Anthropic Claude via OpenAI-compatible API
model = ChatOpenAI(
    model="claude-haiku-4-5",
    temperature=0.7,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    openai_api_base=os.getenv("OPENAI_BASE_URL")
)

# 도구와 함께 바인딩
model_with_tools = model.bind_tools(TOOLS)


# ============================================================================
# Agent 노드
# ============================================================================


def call_agent(state: AgentState) -> dict:
    """
    Agent 노드: LLM 호출

    Args:
        state: 현재 AgentState

    Returns:
        메시지 업데이트 (messages 배열에 추가됨)
    """
    messages = state["messages"]

    # 시스템 프롬프트 추가 (첫 메시지가 아니면 스킵)
    if not messages or not isinstance(messages[0], SystemMessage):
        working_dir = state.get("working_dir", os.getcwd())
        system_prompt = get_system_prompt(working_dir)
        messages = [SystemMessage(content=system_prompt)] + list(messages)

    # LLM 호출
    response = model_with_tools.invoke(messages)

    # 메시지 반환 (LangGraph가 자동으로 messages에 추가)
    return {"messages": [response]}


# ============================================================================
# 조건부 엣지
# ============================================================================


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """
    조건부 엣지: tool_calls 체크

    Args:
        state: 현재 AgentState

    Returns:
        - "tools": 도구 실행 필요
        - END: 완료 (사용자에게 응답)
    """
    messages = state["messages"]
    last_message = messages[-1]

    # AIMessage이고 tool_calls가 있으면 도구 실행
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    # 아니면 종료
    return END


# ============================================================================
# Subagent 실행 (Claude Code의 핵심!)
# ============================================================================


async def execute_subagent(
    subagent_type: str,
    prompt: str,
    system_prompt: str,
    current_depth: int = 0,
    max_depth: int = 5,
    model_name: str = "claude-haiku-4-5",
) -> str:
    """
    Subagent 실행 (LangGraph 버전)

    Args:
        subagent_type: Subagent 타입
        prompt: Subagent에게 전달할 프롬프트
        system_prompt: 시스템 프롬프트
        current_depth: 현재 중첩 깊이
        max_depth: 최대 중첩 깊이
        model_name: 사용할 모델

    Returns:
        Subagent 리포트
    """
    from langchain_core.messages import HumanMessage
    from langgraph.graph import START, StateGraph
    from langgraph.prebuilt import ToolNode

    # Depth 제한
    if current_depth >= max_depth:
        return f"[ERROR] Max subagent depth ({max_depth}) exceeded"

    # 도구 필터링 (statusline-setup만 제한)
    if subagent_type == "statusline-setup":
        allowed_tools = [t for t in TOOLS if t.name in ["read_file", "edit_file"]]
    else:
        allowed_tools = TOOLS

    # Subagent용 새 StateGraph 생성!
    def subagent_call_agent(state: AgentState) -> dict:
        """Subagent의 agent 노드"""
        msgs = state["messages"]
        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=system_prompt)] + list(msgs)

        llm = ChatOpenAI(model=model_name, temperature=0.7)
        llm_with_tools = llm.bind_tools(allowed_tools)
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def subagent_should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        """Subagent의 조건부 엣지"""
        msgs = state["messages"]
        last_msg = msgs[-1]
        if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
            # Task tool 재귀 호출 체크 (여기서는 간단히 처리)
            return "tools"
        return END

    # Subagent graph 구성
    builder = StateGraph(AgentState)
    builder.add_node("agent", subagent_call_agent)
    builder.add_node("tools", ToolNode(allowed_tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", subagent_should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")

    subagent_graph = builder.compile()

    # Subagent 실행!
    initial_state = {
        "messages": [HumanMessage(content=prompt)],
        "working_dir": os.getcwd(),
        "selected_tools": None,
        "depth": current_depth + 1,
    }

    try:
        final_state = await subagent_graph.ainvoke(initial_state)

        # 최종 응답 추출
        if final_state["messages"]:
            last_msg = final_state["messages"][-1]
            if isinstance(last_msg, AIMessage):
                return last_msg.content or "(no response)"

        return "(no response)"

    except Exception as e:
        return f"[ERROR] Subagent failed: {type(e).__name__}: {str(e)}"
