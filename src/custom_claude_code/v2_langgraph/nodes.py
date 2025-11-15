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

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END

from .tools import TOOLS, TOOLS_BY_NAME
from .types import AgentState

# .env 파일 로드 (모델 초기화 전에 필요)
load_dotenv()

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

<env>
Working directory: {working_dir}
Is directory a git repo: {"Yes" if is_git_repo else "No"}
Platform: {platform_name}
OS Version: {os_version}
Today's date: {today}
</env>

# Tools

다음 도구에 접근할 수 있습니다:
- read_file: 줄 번호와 함께 파일 읽기
- write_file: 파일 생성 또는 덮어쓰기
- edit_file: 정확한 문자열 치환으로 파일 편집
- glob_files: glob 패턴으로 파일 찾기 (예: "**/*.ts")
- grep_code: 정규식으로 코드 검색
- run_bash: bash 명령어 실행
- todo_write: 진행 상황 추적을 위한 작업 목록 생성 및 관리
- exit_plan_mode: 구현 계획 제시 및 계획 단계 종료
- task_tool: 복잡한 작업을 위한 전문 subagent 실행

# Task Management

작업을 관리하고 계획하는 데 todo_write 도구를 사용하세요. 이 도구를 **매우** 자주 사용하여 작업을 추적하고 사용자에게 진행 상황을 가시적으로 보여주세요.

이 도구는 또한 작업을 계획하고 더 큰 복잡한 작업을 더 작은 단계로 나누는 데 **극도로** 유용합니다. 계획 시 이 도구를 사용하지 않으면 중요한 작업을 잊어버릴 수 있으며, 이는 용납될 수 없습니다.

작업을 완료하는 즉시 todo를 완료로 표시하는 것이 중요합니다. 여러 작업을 일괄 처리하여 완료 표시하지 마세요.

Examples:

<example>
user: 빌드를 실행하고 타입 오류를 수정해 주세요
assistant: TodoWrite 도구를 사용하여 다음 항목을 할 일 목록에 작성하겠습니다:
- 빌드 실행
- 타입 오류 수정

이제 Bash를 사용하여 빌드를 실행하겠습니다.

10개의 타입 오류를 발견했습니다. TodoWrite 도구를 사용하여 10개의 항목을 할 일 목록에 작성하겠습니다.

첫 번째 todo를 in_progress로 표시합니다

첫 번째 항목 작업을 시작하겠습니다...

첫 번째 항목이 수정되었으니, 첫 번째 todo를 completed로 표시하고 두 번째 항목으로 넘어가겠습니다...
..
..
</example>

# Tool usage policy

- 파일 검색 시 컨텍스트 사용을 줄이기 위해 Task 도구 사용을 선호하세요.
- 작업이 agent 설명과 일치하는 경우 전문 agent와 함께 Task 도구를 적극적으로 사용해야 합니다.
- 한 응답에서 여러 도구를 호출할 수 있습니다. 여러 도구를 호출하려고 하고 도구 간에 종속성이 없는 경우, 모든 독립적인 도구 호출을 병렬로 수행하세요. 효율성을 높이기 위해 가능한 한 병렬 도구 호출을 최대화하세요. 그러나 일부 도구 호출이 종속 값을 알려주기 위해 이전 호출에 의존하는 경우, 이러한 도구를 병렬로 호출하지 **말고** 순차적으로 호출하세요.
- 가능한 경우 bash 명령어 대신 전문 도구를 사용하세요. 파일 작업의 경우 전용 도구를 사용하세요: cat/head/tail 대신 read_file로 파일 읽기, sed/awk 대신 edit_file로 편집, cat heredoc이나 echo redirection 대신 write_file로 파일 생성.
- **매우 중요**: 코드베이스를 탐색하여 컨텍스트를 수집하거나 특정 파일/클래스/함수에 대한 정확한 쿼리가 아닌 질문에 답변할 때, 검색 명령어를 직접 실행하는 대신 subagent_type=Explore와 함께 Task 도구를 사용하는 것이 **중요**합니다.

<example>
user: 클라이언트 오류는 어디서 처리되나요?
assistant: [Glob이나 Grep을 직접 사용하는 대신 subagent_type=Explore와 함께 Task 도구를 사용하여 클라이언트 오류를 처리하는 파일을 찾습니다]
</example>

# Code References

특정 함수나 코드 조각을 참조할 때 사용자가 소스 코드 위치로 쉽게 이동할 수 있도록 `file_path:line_number` 패턴을 포함하세요.

<example>
user: 클라이언트 오류는 어디서 처리되나요?
assistant: 클라이언트는 src/services/process.ts:712의 `connectToServer` 함수에서 실패로 표시됩니다.
</example>

# Guidelines

1. Read before Edit: edit_file 전에 **항상** read_file 사용
2. Absolute Paths: **항상** 절대 파일 경로 사용
3. Safety: 위험한 작업은 사용자와 확인
4. Explanations: 작업에 대한 간단한 설명 제공

이제 사용자의 요청을 도와주세요."""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM 초기화
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 💡 ChatAnthropic을 직접 사용 (Haiku 4.5 - 빠르고 저렴하며 thinking 지원!)
model = ChatAnthropic(
    model="claude-haiku-4-5",
    temperature=1,  # Extended thinking 사용 시 반드시 1이어야 함
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    # Extended thinking 활성화 (Haiku 4.5부터 지원!)
    thinking={
        "type": "enabled",
        "budget_tokens": 2048  # thinking 토큰 예산 (최소 1024)
    }
)

# 도구와 함께 바인딩 (중요! 이래야 LLM이 도구를 호출할 수 있음)
model_with_tools = model.bind_tools(TOOLS)
"""
📌 Extended Thinking (Haiku 4.5+):
- Haiku 4.5는 extended thinking을 지원하는 첫 번째 Haiku 모델!
- thinking.type: "enabled" - thinking 기능 활성화
- thinking.budget_tokens: thinking에 사용할 최대 토큰 수 (최소 1024)
- ⚠️ 중요: thinking 활성화 시 temperature는 반드시 1이어야 함!
- 코딩과 복잡한 추론 작업에 강력히 권장
- thinking 토큰은 output 요금으로 청구 ($5/1M tokens)

📌 bind_tools()의 역할:
- TOOLS 리스트의 각 도구를 Anthropic tool calling 스키마로 변환
- LLM 호출 시 도구 목록을 함께 전달
- LLM이 응답에 tool_calls를 포함할 수 있게 함

📌 Extended Thinking 지원 모델:
- Claude Haiku 4.5+ (NEW!)
- Claude 3.7 Sonnet
- Claude 4 Sonnet/Opus

📌 확장 팁 - 다른 LLM 사용:
- OpenAI: ChatOpenAI(model="gpt-4")
- Claude 3.5: ChatAnthropic(model="claude-3-5-sonnet-20241022")
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
        subagent_type: Subagent 타입 ("Explore", "Plan", "general-purpose")
        prompt: Subagent에게 전달할 작업 설명
        system_prompt: Subagent용 시스템 프롬프트
        current_depth: 현재 중첩 깊이 (0이 Main agent)
        max_depth: 최대 허용 깊이 (기본 5)
        model_name: 사용할 LLM 모델

    Returns:
        Subagent의 최종 응답 문자열

    📌 Subagent 타입 (Claude Code 원본 설명):

    - "general-purpose": General-purpose agent for researching complex questions,
      searching for code, and executing multi-step tasks. When you are searching
      for a keyword or file and are not confident that you will find the right
      match in the first few tries use this agent to perform the search for you.
      (Tools: *)

    - "Explore": Fast agent specialized for exploring codebases. Use this when
      you need to quickly find files by patterns (eg. "src/components/**/*.tsx"),
      search code for keywords (eg. "API endpoints"), or answer questions about
      the codebase (eg. "how do API endpoints work?"). When calling this agent,
      specify the desired thoroughness level: "quick" for basic searches,
      "medium" for moderate exploration, or "very thorough" for comprehensive
      analysis across multiple locations and naming conventions. (Tools: All tools)

    - "Plan": Fast agent specialized for exploring codebases. Use this when you
      need to quickly find files by patterns (eg. "src/components/**/*.tsx"),
      search code for keywords (eg. "API endpoints"), or answer questions about
      the codebase (eg. "how do API endpoints work?"). When calling this agent,
      specify the desired thoroughness level: "quick" for basic searches,
      "medium" for moderate exploration, or "very thorough" for comprehensive
      analysis across multiple locations and naming conventions. (Tools: All tools)

    📌 공통 도구 제한:
    모든 Subagent는 다음 도구를 사용할 수 없습니다:
    - task_tool (무한 재귀 방지)
    - todo_write (Main agent만 관리)
    - exit_plan_mode (Main agent만 사용)

    📌 확장 예시: 특정 타입에 추가 제한 적용
    ```python
    # 도구 필터링 부분에 추가
    if subagent_type == "Explore":
        # 탐색 전용: 쓰기 도구 제외
        allowed_tools = [t for t in allowed_tools if t.name not in ["write_file", "edit_file"]]
    elif subagent_type == "Plan":
        # 계획 전용: 읽기 도구만
        allowed_tools = [t for t in allowed_tools if t.name in ["read_file", "grep_code", "glob_files"]]
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
    # 모델 이름 변환 (짧은 이름 → 전체 모델 이름)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # task_tool의 model 파라미터는 사용자 편의를 위해 짧은 이름("haiku", "sonnet", "opus")을 받지만,
    # Anthropic API는 전체 모델 ID를 요구하므로 변환이 필요합니다.
    model_map = {
        "haiku": "claude-haiku-4-5",
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-20250514",
    }

    # 짧은 이름이면 변환, 이미 전체 이름이면 그대로 사용
    if model_name in model_map:
        full_model_name = model_map[model_name]
    else:
        full_model_name = model_name

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 2: 도구 필터링 (Subagent 타입별)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Subagent는 특정 도구를 사용할 수 없음 (무한 재귀 방지 및 역할 분리)
    excluded_tools = {"task_tool", "todo_write", "exit_plan_mode"}

    # 모든 Subagent 타입: 제외 도구를 제외한 나머지 허용
    # - "general-purpose": 복잡한 리서치, 코드 검색, 멀티스텝 실행
    # - "Explore": 빠른 코드베이스 탐색 (패턴, 키워드, 질문 답변)
    # - "Plan": 구현 계획 수립
    allowed_tools = [t for t in TOOLS if t.name not in excluded_tools]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 3: Subagent용 system prompt 수정 (제외된 도구 명시)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Subagent용 system prompt: 제외된 도구 명시
    subagent_system_prompt = system_prompt + f"""

# Subagent Restrictions

당신은 제한된 도구 접근 권한을 가진 subagent입니다. 다음 도구에는 접근할 수 **없습니다**:
- task_tool: 다른 subagent를 실행할 수 없습니다 (무한 재귀 방지)
- todo_write: 작업 추적은 main agent에서만 관리됩니다
- exit_plan_mode: 계획은 main agent에서만 처리됩니다

사용 가능한 도구: {', '.join(t.name for t in allowed_tools)}

제한된 도구의 기능이 필요한 경우, 사용 가능한 도구로 작업을 완료하고 결과를 main agent에게 반환하세요.
"""

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 4: Subagent용 StateGraph 생성
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def subagent_call_agent(state: AgentState) -> dict:
        """
        Subagent의 agent 노드

        Main agent의 call_agent()와 동일한 패턴이지만,
        독립적인 메시지 히스토리를 가집니다.
        """
        msgs = state["messages"]

        # SystemMessage 추가 (Subagent용 system prompt - 제외 도구 명시됨)
        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=subagent_system_prompt)] + list(msgs)

        # Subagent용 LLM 생성 (별도 인스턴스)
        # ChatAnthropic 사용 (Main agent와 동일한 모델 패밀리)
        llm = ChatAnthropic(
            model=full_model_name,  # 변환된 전체 모델 이름 사용
            temperature=1,  # thinking 사용 시 1로 고정
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            # Extended thinking 활성화
            thinking={
                "type": "enabled",
                "budget_tokens": 2048
            }
        )
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
    # Step 5: Subagent graph 구성 (Main agent와 동일한 구조!)
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
    # Step 6: Subagent 실행
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 초기 상태 생성 (Subagent 시작 시)
    initial_state = {
        "messages": [HumanMessage(content=prompt)],  # Subagent에게 전달할 작업
        "working_dir": os.getcwd(),
        "selected_tools": None,
        "depth": current_depth + 1,  # Depth 증가!
        "todos": None,  # Subagent도 todos 사용 가능 (하지만 todo_write는 제한됨)
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
