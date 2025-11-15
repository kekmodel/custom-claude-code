"""
v2: LangGraph Nodes - 핵심 로직

🎯 핵심 개념:
LangGraph에서 "노드(Node)"는 상태를 받아서 처리하고 새 상태를 반환하는 함수입니다.
이 파일은 v2의 핵심 노드 함수들을 정의합니다.

📌 주요 노드:
1. call_agent() - LLM 호출 노드
2. should_continue() - 조건부 라우팅 (도구 실행 vs 종료)
3. execute_subagent() - Subagent 실행 (재귀적 StateGraph 생성!)

🔄 워크플로우:
START → agent → should_continue → [tools → agent] or [END]
                                    └─ 반복 ─┘

📌 확장 팁:
- 새 노드 추가: def my_node(state: AgentState) -> dict 패턴
- 조건 분기: Literal["option1", "option2"] 반환 타입
- Subagent 타입: execute_subagent의 if문에 추가
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# System Prompt 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def get_system_prompt(working_dir: str = None) -> str:
    """
    🤖 LLM에게 전달할 시스템 프롬프트 생성

    역할:
    - LLM의 정체성 정의 ("You are a coding assistant")
    - 환경 정보 제공 (작업 디렉토리, OS 등)
    - 사용 가능한 도구 목록
    - 행동 가이드라인

    Args:
        working_dir: 작업 디렉토리 (None이면 현재 디렉토리)

    Returns:
        시스템 프롬프트 문자열

    📌 확장 팁:
    도메인에 맞게 프롬프트를 수정할 수 있습니다:
    - 데이터 분석: "You are a data scientist..."
    - 고객 지원: "You are a helpful customer service agent..."
    - 코드 리뷰: "You are an expert code reviewer..."
    """
    if working_dir is None:
        working_dir = os.getcwd()

    # 환경 정보 수집
    is_git_repo = os.path.exists(os.path.join(working_dir, ".git"))
    platform_name = platform_module.system().lower()
    os_version = platform_module.platform()
    today = datetime.now().strftime("%Y-%m-%d")

    # 프롬프트 생성
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM 초기화
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 💡 LangChain의 ChatOpenAI를 사용하지만 Anthropic Claude를 호출
# (OpenAI 호환 API 덕분에 가능)
model = ChatOpenAI(
    model="claude-haiku-4-5",
    temperature=0.7,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    openai_api_base=os.getenv("OPENAI_BASE_URL")  # Anthropic API URL
)

# 도구와 함께 바인딩 (중요! 이래야 LLM이 도구를 호출할 수 있음)
model_with_tools = model.bind_tools(TOOLS)
"""
📌 bind_tools()의 역할:
- TOOLS 리스트의 각 도구를 OpenAI function calling 스키마로 변환
- LLM 호출 시 도구 목록을 함께 전달
- LLM이 응답에 tool_calls를 포함할 수 있게 함

📌 확장 팁:
다른 LLM 사용:
- OpenAI: ChatOpenAI(model="gpt-4")
- Anthropic 직접: ChatAnthropic(model="claude-3-5-sonnet-20241022")
- 로컬: ChatOllama(model="llama2")
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 노드 1: Agent (LLM 호출)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def call_agent(state: AgentState) -> dict:
    """
    🤖 Agent 노드: LLM을 호출하여 다음 액션 결정

    이 노드는 LangGraph 워크플로우의 핵심입니다.
    사용자 메시지와 도구 결과를 받아 LLM에게 전달하고,
    LLM의 응답(텍스트 또는 도구 호출)을 상태에 추가합니다.

    🔄 실행 흐름:
    1. 현재 상태에서 messages 가져오기
    2. SystemMessage가 없으면 추가 (첫 호출 시)
    3. LLM 호출 (model_with_tools.invoke)
    4. 응답 메시지 반환 → StateGraph가 자동으로 messages에 append

    Args:
        state: 현재 AgentState (messages, working_dir 등)

    Returns:
        부분 상태 업데이트 딕셔너리
        - {"messages": [AIMessage(...)]}
        - StateGraph가 이를 기존 state와 병합

    📌 중요:
    - 반환값은 전체 상태가 아닌 "업데이트할 부분"만!
    - messages는 Annotated[..., add_messages]이므로 자동 append됨
    - 다른 필드는 덮어쓰기 방식

    📌 확장 예시:
    ```python
    def call_agent(state: AgentState) -> dict:
        # 커스텀 로직 추가
        if state.get("debug_mode"):
            print("Debug: calling LLM...")

        messages = state["messages"]
        # ...기존 로직...
        response = model_with_tools.invoke(messages)

        # 추가 상태 업데이트
        return {
            "messages": [response],
            "last_call_time": datetime.now()  # 새 필드 추가
        }
    ```
    """
    messages = state["messages"]

    # 시스템 프롬프트 추가 (첫 호출이거나 SystemMessage가 없을 때)
    if not messages or not isinstance(messages[0], SystemMessage):
        working_dir = state.get("working_dir", os.getcwd())
        system_prompt = get_system_prompt(working_dir)
        # SystemMessage를 맨 앞에 추가
        messages = [SystemMessage(content=system_prompt)] + list(messages)

    # 🤖 LLM 호출!
    # - messages: 대화 히스토리 전체
    # - 도구 목록은 이미 bind_tools()로 연결됨
    response = model_with_tools.invoke(messages)
    """
    response의 구조:
    - AIMessage 객체
    - content: LLM의 텍스트 응답
    - tool_calls: 도구 호출 목록 (있으면)
      [
          {
              "name": "read_file",
              "args": {"file_path": "/path/to/file"},
              "id": "call_123"
          }
      ]
    """

    # 메시지 반환 (StateGraph가 자동으로 messages 배열에 추가)
    return {"messages": [response]}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 조건부 엣지: 다음 노드 결정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """
    🔀 조건부 라우팅: 다음에 어디로 갈지 결정

    LangGraph의 conditional_edges에서 사용하는 함수입니다.
    마지막 LLM 응답을 보고 "도구 실행" 또는 "종료"를 결정합니다.

    🔄 판단 로직:
    - 마지막 메시지가 AIMessage이고
    - tool_calls가 있으면 → "tools" (도구 노드로)
    - 그렇지 않으면 → END (종료)

    Args:
        state: 현재 AgentState

    Returns:
        "tools" 또는 END (LangGraph 특수 상수)

    📌 확장 예시:
    ```python
    def should_continue(state: AgentState) -> Literal["tools", "verify", "__end__"]:
        '''더 복잡한 라우팅'''
        last_msg = state["messages"][-1]

        # 도구 호출이 있으면 도구 노드로
        if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
            return "tools"

        # 코드가 작성되었으면 검증 노드로
        if state.get("code_written"):
            return "verify"

        # 그 외는 종료
        return END
    ```

    📌 그래프 구성 시:
    ```python
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",      # "tools" 반환 시 tools 노드로
            "verify": "verify",    # "verify" 반환 시 verify 노드로
            END: END               # END 반환 시 종료
        }
    )
    ```
    """
    messages = state["messages"]
    last_message = messages[-1]

    # AIMessage이고 tool_calls가 있는지 체크
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        # 도구 실행 필요!
        return "tools"

    # 도구 호출이 없으면 종료 (사용자에게 최종 응답)
    return END


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Subagent 실행 (Claude Code의 핵심 패턴!)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def execute_subagent(
    subagent_type: str,
    prompt: str,
    system_prompt: str,
    current_depth: int = 0,
    max_depth: int = 5,
    model_name: str = "claude-haiku-4-5",
) -> str:
    """
    🎯 Subagent 실행: 독립적인 StateGraph를 재귀적으로 생성!

    이것이 v2 LangGraph의 가장 강력한 기능입니다.
    Main agent 내부에서 완전히 독립적인 Subagent를 실행할 수 있습니다.
    각 Subagent는 자신만의 StateGraph를 가지며, 독립적으로 실행됩니다.

    🔄 실행 흐름:
    1. Depth 제한 확인 (무한 재귀 방지)
    2. Subagent 타입에 맞는 도구 필터링
    3. 새로운 StateGraph 생성 (Subagent용)
    4. Subagent graph 실행
    5. 최종 응답 추출하여 반환

    Args:
        subagent_type: Subagent 타입 ("explore", "plan", "general", "statusline-setup")
        prompt: Subagent에게 전달할 작업 설명
        system_prompt: Subagent용 시스템 프롬프트
        current_depth: 현재 중첩 깊이 (0이 Main agent)
        max_depth: 최대 허용 깊이 (기본 5)
        model_name: 사용할 LLM 모델

    Returns:
        Subagent의 최종 응답 문자열

    📌 Subagent 타입별 도구 제한:
    - "statusline-setup": read_file, edit_file만
    - 나머지: 모든 도구 사용 가능

    📌 확장 예시: 새 Subagent 타입 추가
    ```python
    # 도구 필터링 부분에 추가
    if subagent_type == "statusline-setup":
        allowed_tools = [t for t in TOOLS if t.name in ["read_file", "edit_file"]]
    elif subagent_type == "code-reviewer":
        # 코드 리뷰 전용: 읽기와 분석 도구만
        allowed_tools = [t for t in TOOLS if t.name in ["read_file", "grep_code", "glob_files"]]
    elif subagent_type == "test-runner":
        # 테스트 실행 전용
        allowed_tools = [t for t in TOOLS if t.name in ["run_bash", "read_file"]]
    else:
        allowed_tools = TOOLS
    ```

    📌 중요 개념: 재귀적 StateGraph
    Subagent는 Main agent와 동일한 구조의 StateGraph를 가집니다:
    - agent 노드: LLM 호출
    - tools 노드: 도구 실행
    - conditional_edges: 도구 실행 vs 종료 판단

    이 패턴 덕분에 Subagent가 자신의 도구를 사용하고,
    필요하면 또 다른 Subagent를 호출할 수 있습니다 (depth 제한 내에서).
    """
    from langchain_core.messages import HumanMessage
    from langgraph.graph import START, StateGraph
    from langgraph.prebuilt import ToolNode

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 1: Depth 제한 확인 (무한 재귀 방지)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if current_depth >= max_depth:
        return f"[ERROR] Max subagent depth ({max_depth}) exceeded"

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 2: 도구 필터링 (Subagent 타입별)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if subagent_type == "statusline-setup":
        # statusline 설정 전용: 읽기/쓰기만 허용
        allowed_tools = [t for t in TOOLS if t.name in ["read_file", "edit_file"]]
    else:
        # 나머지 타입: 모든 도구 허용
        # "explore": 탐색 전용 (파일 찾기, 검색)
        # "plan": 계획 수립 (분석, 읽기)
        # "general": 일반 작업 (모든 도구)
        allowed_tools = TOOLS

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 3: Subagent용 StateGraph 생성
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def subagent_call_agent(state: AgentState) -> dict:
        """
        Subagent의 agent 노드

        Main agent의 call_agent()와 동일한 패턴이지만,
        독립적인 메시지 히스토리를 가집니다.
        """
        msgs = state["messages"]

        # SystemMessage 추가 (Subagent용 system prompt)
        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=system_prompt)] + list(msgs)

        # Subagent용 LLM 생성 (별도 인스턴스)
        llm = ChatOpenAI(model=model_name, temperature=0.7)
        llm_with_tools = llm.bind_tools(allowed_tools)  # 필터링된 도구만!

        # LLM 호출
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def subagent_should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        """
        Subagent의 조건부 엣지

        Main agent의 should_continue()와 동일한 로직.
        도구 호출이 있으면 tools 노드로, 없으면 종료.
        """
        msgs = state["messages"]
        last_msg = msgs[-1]

        if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
            # 🔄 재귀 호출 감지 가능 (Task tool 체크)
            # 여기서 Task tool 호출을 막으려면:
            # if any(call["name"] == "task_tool" for call in last_msg.tool_calls):
            #     return END  # Task 재호출 방지
            return "tools"

        return END

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 4: Subagent graph 구성 (Main agent와 동일한 구조!)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    builder = StateGraph(AgentState)

    # 노드 추가
    builder.add_node("agent", subagent_call_agent)
    builder.add_node("tools", ToolNode(allowed_tools))  # 필터링된 도구로 ToolNode 생성

    # 엣지 추가
    builder.add_edge(START, "agent")  # 시작 → agent
    builder.add_conditional_edges(
        "agent",
        subagent_should_continue,
        {
            "tools": "tools",  # 도구 호출 → tools 노드
            END: END           # 종료 → END
        }
    )
    builder.add_edge("tools", "agent")  # tools → agent (루프)

    # Graph 컴파일
    subagent_graph = builder.compile()
    """
    컴파일된 graph는 완전히 독립적입니다:
    - 자신만의 상태(messages)
    - 자신만의 노드(agent, tools)
    - 자신만의 실행 루프

    Main agent가 여러 Subagent를 동시에 실행할 수도 있습니다!
    """

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 5: Subagent 실행
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 초기 상태 생성 (Subagent 시작 시)
    initial_state = {
        "messages": [HumanMessage(content=prompt)],  # Subagent에게 전달할 작업
        "working_dir": os.getcwd(),
        "selected_tools": None,
        "depth": current_depth + 1,  # Depth 증가!
    }

    try:
        # 🚀 Subagent graph 실행! (비동기)
        final_state = await subagent_graph.ainvoke(initial_state)
        """
        ainvoke()는 graph를 완전히 실행하고 최종 상태를 반환:
        - START → agent → tools → agent → ... → END
        - 모든 메시지가 final_state["messages"]에 누적됨
        """

        # 최종 응답 추출
        if final_state["messages"]:
            last_msg = final_state["messages"][-1]
            if isinstance(last_msg, AIMessage):
                # AIMessage의 content가 Subagent의 최종 리포트
                return last_msg.content or "(no response)"

        return "(no response)"

    except Exception as e:
        # 에러 발생 시 Main agent에게 에러 메시지 반환
        return f"[ERROR] Subagent failed: {type(e).__name__}: {str(e)}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📌 확장 가이드: 커스텀 노드 추가하기
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 예시 1: 코드 검증 노드
# def verify_code(state: AgentState) -> dict:
#     """코드 품질을 검증하는 노드"""
#     # 상태에서 마지막 작성된 코드 가져오기
#     # (추가 필드 필요: last_written_file)
#
#     # 검증 로직 실행 (예: pylint, mypy)
#     # ...
#
#     # 결과를 상태에 추가
#     return {
#         "code_quality": {"score": 8.5, "issues": [...]},
#         "messages": [AIMessage(content="Code verified!")]
#     }

# 예시 2: 사용자 확인 노드
# def ask_user_confirmation(state: AgentState) -> dict:
#     """위험한 작업 전에 사용자 확인"""
#     last_msg = state["messages"][-1]
#
#     # 위험한 작업 감지 (예: run_bash with rm)
#     if "rm -rf" in str(last_msg.tool_calls):
#         # 사용자 입력 받기
#         response = input("Dangerous operation detected. Continue? (y/n): ")
#         if response.lower() != 'y':
#             return {"messages": [AIMessage(content="Operation cancelled")]}
#
#     return {}  # 상태 변경 없음

# 예시 3: 조건부 라우팅 with 3개 옵션
# def complex_router(state: AgentState) -> Literal["verify", "retry", "__end__"]:
#     """복잡한 조건부 라우팅"""
#     code_quality = state.get("code_quality")
#
#     if code_quality and code_quality["score"] < 7:
#         return "retry"  # 코드 재작성
#     elif code_quality:
#         return "verify"  # 추가 검증
#     else:
#         return END  # 종료
