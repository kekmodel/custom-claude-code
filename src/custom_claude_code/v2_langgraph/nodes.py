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
from typing import Literal

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END

from .tools import TOOLS
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
    return f"""당신은 LangGraph 기반 Claude 코딩 어시스턴트입니다.
당신은 대화형 CLI 도구로서 사용자의 소프트웨어 엔지니어링 작업을 지원합니다. 아래 지침과 사용 가능한 도구를 활용하여 사용자를 지원하세요.

<env>
Working directory: {working_dir}
Is directory a git repo: {"Yes" if is_git_repo else "No"}
Platform: {platform_name}
OS Version: {os_version}
Today's date: {today}
</env>

# Available Tools

다음 도구에 접근할 수 있습니다:
File Operations:
- read_file, write_file, edit_file

Search and Discovery:
- glob_files: 파일명 패턴으로 파일 찾기
- grep_code: 정규식으로 코드 검색

Execution:
- run_bash: bash 명령어 실행 (터미널 작업 전용)

Task Management:
- todo_write: 작업 목록 생성 및 관리
- exit_plan_mode: 구현 계획 제시 및 계획 단계 종료

Agents:
- task_tool: 전문 subagent 실행 (Explore/Plan/General)

# Tool usage policy

1. Read before Edit: edit_file 전에 **항상** read_file 사용
2. Absolute Paths: **항상** 절대 파일 경로 사용
3. Safety: 위험한 작업은 사용자와 확인
4. Explanations: 작업에 대한 간단한 설명 제공

# Task Management

작업을 관리하고 계획하는 데 todo_write 도구를 사용하세요. 이 도구를 **매우** 자주 사용하여 작업을 추적하고 사용자에게 진행 상황을 가시적으로 보여주세요.

이 도구는 또한 작업을 계획하고 더 큰 복잡한 작업을 더 작은 단계로 나누는 데 **극도로** 유용합니다. 계획 시 이 도구를 사용하지 않으면 중요한 작업을 잊어버릴 수 있으며, 이는 용납될 수 없습니다.

작업을 완료하는 즉시 todo를 완료로 표시하는 것이 중요합니다. 여러 작업을 일괄 처리하여 완료 표시하지 마세요.

Examples:

<example>
user: 빌드를 실행하고 타입 오류를 수정해 주세요
assistant: TodoWrite 도구를 사용하여 다음 항목을 할 일 목록에 작성하겠습니다:
- 빌드 실행
- 모든 타입 오류 수정

이제 Bash를 사용하여 빌드를 실행하겠습니다.

10개의 타입 오류를 발견했습니다. TodoWrite 도구를 사용하여 10개의 항목을 할 일 목록에 작성하겠습니다.

첫 번째 todo를 in_progress로 표시합니다

첫 번째 항목 작업을 시작하겠습니다...

첫 번째 항목이 수정되었으니, 첫 번째 todo를 completed로 표시하고 두 번째 항목으로 넘어가겠습니다...
..
..
</example>

# Tool Usage Policy

한 응답에서 여러 도구를 호출할 수 있습니다. 여러 도구를 호출하려고 하고 도구 간에 종속성이 없는 경우, 모든 독립적인 도구 호출을 병렬로 수행하세요. 효율성을 높이기 위해 가능한 한 병렬 도구 호출을 최대화하세요.

가능한 경우 bash 명령 대신 전문 도구를 사용하세요. 파일 작업의 경우 전용 도구를 사용하세요:
  - cat/head/tail 대신 read_file로 파일 읽기
  - sed/awk 대신 edit_file로 편집
  - cat heredoc이나 echo redirection 대신 write_file로 파일 생성

bash 도구는 셸 실행이 필요한 실제 시스템 명령 및 터미널 작업에만 사용하세요 (git, npm, docker 등).

파일 작업에 bash를 **절대** 사용하지 마세요:
- Incorrect usage:
```
run_bash("cat file.txt")        # Use read_file instead
run_bash("find . -name '*.py'") # Use glob_files instead
run_bash("grep pattern file")   # Use grep_code instead
```

- Correct usage:
```
read_file("file.txt")
glob_files("**/*.py")
grep_code("pattern", path="file")
```

Task Tool for Exploration:
- **매우 중요**: 코드베이스를 탐색하여 컨텍스트를 수집하거나 특정 파일/클래스/함수에 대한 정확한 쿼리가 아닌 질문에 답변할 때, 검색 명령어를 직접 실행하는 대신 subagent_type=Explore와 함께 Task 도구를 사용하는 것이 **중요**합니다.

<example>
user: 클라이언트 오류는 어디서 처리되나요?
assistant: [Glob이나 Grep을 직접 사용하는 대신 subagent_type=Explore와 함께 Task 도구를 사용하여 클라이언트 오류를 처리하는 파일을 찾습니다]
</example>

<example>
user: 코드베이스 구조가 어떻게 되나요?
assistant: [subagent_type=Explore와 함께 Task 도구를 사용합니다]
</example>

# Code References

특정 함수나 코드 조각을 참조할 때 사용자가 소스 코드 위치로 쉽게 이동할 수 있도록 `file_path:line_number` 패턴을 포함하세요.

<example>
user: 클라이언트 오류는 어디서 처리되나요?
assistant: 클라이언트는 src/services/process.ts:712의 `connectToServer` 함수에서 실패로 표시됩니다.
</example>

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
    thinking={"type": "enabled", "budget_tokens": 2048},  # thinking 토큰 예산 (최소 1024)
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


async def call_agent(state: AgentState) -> dict:
    """
    🤖 Agent 노드: LLM을 호출하여 다음 액션 결정

    이 노드는 LangGraph 워크플로우의 핵심입니다.
    사용자 메시지와 도구 결과를 받아 LLM에게 전달하고,
    LLM의 응답(텍스트 또는 도구 호출)을 상태에 추가합니다.

    🔄 실행 흐름:
    1. 현재 상태에서 messages 가져오기
    2. Auto compact: 메시지가 많으면 자동 압축 (30개 이상)
    3. SystemMessage가 없으면 추가 (첫 호출 시)
    4. LLM 호출 (model_with_tools.invoke)
    5. 응답 메시지 반환 → StateGraph가 자동으로 messages에 append

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

    📌 Auto Compact 기능:
    - 토큰 수가 100k 이상이면 자동 압축
    - SystemMessage와 최근 20개 메시지는 유지
    - 중간 메시지는 LLM으로 요약
    - ⚠️ 요약 시 프롬프트 캐싱 무효화 (비용 증가 가능)

    📌 확장 예시:
    ```python
    async def call_agent(state: AgentState) -> dict:
        # 커스텀 로직 추가
        if state.get("debug_mode"):
            print("Debug: calling LLM...")

        messages = state["messages"]

        # Auto compact 적용
        messages = await compact_messages(messages)

        # ...기존 로직...
        response = await model_with_tools.ainvoke(messages)

        # 추가 상태 업데이트
        return {
            "messages": [response],
            "last_call_time": datetime.now()  # 새 필드 추가
        }
    ```
    """
    messages = list(state["messages"])

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 1: SystemMessage 추가 (첫 호출이거나 SystemMessage가 없을 때)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⚠️ 중요: Auto compact 전에 SystemMessage를 보장해야 함!

    if not messages or not isinstance(messages[0], SystemMessage):
        working_dir = state.get("working_dir", os.getcwd())
        system_prompt = get_system_prompt(working_dir)
        # SystemMessage를 맨 앞에 추가
        messages = [SystemMessage(content=system_prompt)] + list(messages)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 2: Auto Compact (메시지가 많으면 자동 압축)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    original_message_count = len(messages)
    messages = await compact_messages(messages)
    was_compressed = len(messages) < original_message_count

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 3: 메시지 구조 검증 (Anthropic API 요구사항)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Anthropic API 요구사항: tool_use 뒤에는 반드시 tool_result가 와야 함
    # 검증 로직 추가
    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            # 다음 메시지가 있는지 확인
            if i + 1 < len(messages):
                next_msg = messages[i + 1]
                # 다음 메시지가 ToolMessage가 아니면 에러!
                if not isinstance(next_msg, ToolMessage):
                    print(f"\n❌ 메시지 구조 오류 발견!")
                    print(f"   Index {i}: AIMessage with tool_calls")
                    print(f"   Tool calls: {[tc.get('name') for tc in msg.tool_calls]}")
                    print(f"   Index {i+1}: {type(next_msg).__name__} (should be ToolMessage!)")
                    print(f"\n전체 메시지 구조:")
                    for idx, m in enumerate(messages):
                        msg_type = type(m).__name__
                        has_tools = "(with tool_calls)" if isinstance(m, AIMessage) and hasattr(m, "tool_calls") and m.tool_calls else ""
                        print(f"   [{idx}] {msg_type} {has_tools}")

                    # 잘못된 메시지 제거 (임시 해결)
                    print(f"\n🔧 임시 수정: tool_calls가 있는 AIMessage를 제거합니다")
                    messages = messages[:i] + messages[i+1:]
                    break

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 4: LLM 호출
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 🤖 LLM 호출! (async로 변경)
    # - messages: 대화 히스토리 전체 (압축된 버전)
    # - 도구 목록은 이미 bind_tools()로 연결됨
    response = await model_with_tools.ainvoke(messages)
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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 4: 메시지 반환 (압축 여부에 따라 다름)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if was_compressed:
        # 압축했으면 state의 메시지를 교체해야 함!
        # 단, SystemMessage는 항상 state에 유지 (중복 방지)
        from langchain_core.messages import RemoveMessage

        # 📚 학습 포인트: LangGraph의 add_messages reducer와 State 교체
        #
        # 문제: add_messages는 기본적으로 append만 함
        # - 로컬 변수 messages를 압축해도 state["messages"]는 그대로
        # - 다음 턴에서 압축 안 된 원본 messages를 다시 가져옴 → 연속 압축 발생!
        #
        # 해결: RemoveMessage로 기존 메시지 삭제 + 압축된 메시지 추가
        # - LangGraph의 add_messages는 RemoveMessage를 지원함
        # - RemoveMessage(id=msg_id)를 반환하면 해당 메시지 삭제
        # - 그 다음 새 메시지들을 추가
        #
        # 주의: SystemMessage 중복 방지!
        # - state에 이미 SystemMessage 존재
        # - 압축된 messages에도 SystemMessage 포함
        # - 두 번 추가하면 "multiple non-consecutive system messages" 에러
        # - 해결: SystemMessage는 삭제도, 추가도 하지 않음 (state에 유지)
        # SystemMessage 제외한 기존 메시지 모두 삭제
        remove_messages = [
            RemoveMessage(id=msg.id)
            for msg in state["messages"]
            if not isinstance(msg, SystemMessage) and hasattr(msg, "id") and msg.id is not None
        ]

        # 압축된 메시지에서도 SystemMessage 제외 (이미 state에 있으므로)
        compressed_without_system = [msg for msg in messages if not isinstance(msg, SystemMessage)]

        # 결과: [RemoveMessage들...] + [압축된 메시지들] + [새 response]
        # → state는 [SystemMessage(기존), 요약, 최근 메시지들, response]로 교체됨
        return {"messages": remove_messages + compressed_without_system + [response]}
    else:
        # 압축 안 했으면 response만 추가 (기본 동작)
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
# Auto Compact: 대화 히스토리 압축
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _count_tokens(messages: list) -> int:
    """
    메시지 목록의 대략적인 토큰 수 계산

    Args:
        messages: 토큰을 계산할 메시지 목록

    Returns:
        대략적인 토큰 수 (문자 수 / 4)

    Note:
        정확한 토큰 계산은 tiktoken 라이브러리가 필요하지만,
        간단한 휴리스틱(문자 수 / 4)으로 충분히 근사할 수 있습니다.

        중요: tool_calls도 포함하여 계산합니다!
    """
    import json

    total_chars = 0

    for msg in messages:
        # Content 계산
        if hasattr(msg, "content") and msg.content:
            total_chars += len(str(msg.content))

        # tool_calls 계산 (AIMessage)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            # tool_calls를 JSON으로 변환하여 문자 수 계산
            tool_calls_str = json.dumps(msg.tool_calls)
            total_chars += len(tool_calls_str)

    return total_chars // 4  # 대략적인 추정: 4 characters ≈ 1 token


def _format_messages_for_summary(messages: list) -> str:
    """
    메시지 목록을 요약용 텍스트로 포맷팅

    Args:
        messages: 포맷팅할 메시지 목록

    Returns:
        요약용 텍스트 문자열

    Note:
        HumanMessage, AIMessage, ToolMessage를 구분하여 포맷팅합니다.
        AIMessage의 tool_calls도 포함하여 도구 호출 정보를 유지합니다.
        맥락 이해를 위해 모든 메시지를 **전체** 포함합니다.
    """
    from langchain_core.messages import HumanMessage, ToolMessage

    formatted = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            formatted.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            # AIMessage는 content 또는 tool_calls를 가질 수 있음
            if msg.content:
                formatted.append(f"Assistant: {msg.content}")  # 전체 포함
            # 도구 호출이 있으면 포함
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_names = [tc.get("name", "unknown") for tc in msg.tool_calls]
                formatted.append(f"Assistant: [도구 호출: {', '.join(tool_names)}]")
        elif isinstance(msg, ToolMessage):
            # ToolMessage의 name 속성 안전하게 접근
            tool_name = getattr(msg, "name", "unknown_tool")
            content = str(msg.content) if msg.content else "(empty)"
            formatted.append(f"Tool({tool_name}): {content}")  # 전체 포함

    return "\n".join(formatted)


async def compact_messages(messages: list, max_tokens: int = 100_000) -> list:  # 프로덕션 기준
    """
    🗜️ 대화 히스토리 자동 압축

    긴 대화에서 토큰 수가 max_tokens를 초과하면,
    오래된 메시지를 LLM으로 요약하여 컨텍스트 창을 관리합니다.

    📌 압축 전략 (Claude Code 방식):
    1. **항상** 유지: SystemMessage (첫 메시지, state에 이미 존재)
    2. **항상** 유지: 마지막 대화 턴 (마지막 HumanMessage부터 끝까지)
       - 사용자의 최신 요청 + AI 응답 + 도구 결과를 완전히 보존
       - 정상 대화에서 HumanMessage는 항상 존재함 (사용자가 먼저 질문)
    3. 요약 대상: 중간의 오래된 메시지들

    Args:
        messages: 압축할 메시지 목록
        max_tokens: 압축 트리거 토큰 임계값 (기본: 100,000)

    Returns:
        압축된 메시지 목록
        - [SystemMessage, HumanMessage(요약), 최근 대화 턴...]

    Example:
        ```python
        # 압축 전: 50개 메시지, 150k tokens
        # [SystemMessage, msg1, msg2, ..., msg48, HumanMessage("최신 요청"), AIMessage]

        messages = await compact_messages(messages)

        # 압축 후: 4개 메시지, 5k tokens
        # [SystemMessage, HumanMessage("요약..."), HumanMessage("최신 요청"), AIMessage]
        ```

    📚 학습 포인트:
        1. **State 교체 메커니즘** (call_agent에서 처리):
           - 압축했으면 RemoveMessage로 기존 메시지 삭제 (SystemMessage 제외)
           - 압축된 메시지로 state 교체
           - 이렇게 해야 다음 턴에서 압축된 state를 유지

        2. **Cooldown 체크**:
           - 두 번째 메시지가 "[이전 대화 요약]"으로 시작하면 방금 압축한 것
           - 무한 루프 방지 (압축 → 다시 압축 → ...)

        3. **HumanMessage로 요약**:
           - SystemMessage 다음 HumanMessage = LLM이 학습한 일반적인 패턴
           - AIMessage로 하면 비정상적인 순서 (SystemMessage → AIMessage)

        4. **단순화된 로직**:
           - HumanMessage는 항상 존재 (사용자가 먼저 질문) → fallback 불필요
           - 마지막 대화 턴 완전 유지 → Orphan ToolMessage 발생 안 함

    Note:
        요약은 Claude Haiku + Extended Thinking으로 생성합니다.
        별도의 LLM 호출이 발생하지만, 긴 대화를 유지하는 것보다 훨씬 저렴합니다.

    Warning:
        요약 시 메시지 구조가 변경되므로 **프롬프트 캐싱이 무효화**됩니다.
        압축 직후 첫 LLM 호출은 전체 프롬프트를 재처리하므로 비용이 증가할 수 있습니다.
    """
    from langchain_core.messages import HumanMessage

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 1: 압축 필요 여부 확인 (SystemMessage 제외하고 토큰 체크)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SystemMessage는 항상 유지되므로 토큰 카운팅에서 제외
    system_msg = messages[0] if isinstance(messages[0], SystemMessage) else None
    actual_start_idx = 1 if system_msg else 0
    actual_messages = messages[actual_start_idx:]

    token_count = _count_tokens(actual_messages)
    if token_count <= max_tokens:
        return messages  # 토큰 수가 적으면 압축 불필요

    # 방금 압축했는지 확인 (무한 루프 방지)
    # 두 번째 메시지가 HumanMessage이고 "[이전 대화 요약]"으로 시작하면 방금 압축한 것
    if len(messages) >= 2:
        second_msg = messages[1]
        if isinstance(second_msg, HumanMessage) and hasattr(second_msg, "content"):
            if isinstance(second_msg.content, str) and second_msg.content.startswith("[이전 대화 요약]"):
                print(f"   ⚠️  방금 압축했으므로 스킵 (무한 루프 방지)\n")
                return messages

    # 압축 시작 로그
    print(f"\n🗜️  Auto-compact 시작: {len(messages)}개 메시지, {token_count:,} tokens → {max_tokens:,} 초과")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 2: 메시지 분리 (유지 vs 요약)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # SystemMessage는 이미 위에서 확인했음 (system_msg, actual_start_idx)
    start_idx = actual_start_idx

    # 최근 대화 턴 유지: 마지막 HumanMessage부터 끝까지
    # (사용자 요청 + 응답 + 도구 결과를 모두 유지)
    # 💡 정상 대화에서 HumanMessage는 항상 존재 (사용자가 먼저 질문)
    recent_start_idx = None
    for i in range(len(messages) - 1, start_idx - 1, -1):
        if isinstance(messages[i], HumanMessage):
            recent_start_idx = i
            break

    # 정상 대화에서는 항상 HumanMessage 존재 (assert로 명시)
    assert recent_start_idx is not None, "정상 대화에서 HumanMessage는 항상 존재합니다 (사용자가 먼저 질문)"

    recent_messages = messages[recent_start_idx:]
    middle_messages = messages[start_idx:recent_start_idx]

    # 요약할 메시지가 없거나 너무 적으면 압축 불필요
    if len(middle_messages) < 5:
        return messages  # 최소 5개 이상일 때만 압축

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 3: LLM으로 중간 메시지 요약
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 요약용 프롬프트
    summary_prompt = f"""다음은 이전 대화 히스토리입니다. 핵심 내용을 간결하게 요약해주세요:

# Summary Guidelines

1. 주요 작업과 결정사항 포함
2. 중요한 기술적 세부사항 유지
3. 파일 경로, 함수명 등 구체적 정보 보존
4. 사용자 요구사항과 결과 명시
5. 3-5문단으로 요약

# Conversation History

{_format_messages_for_summary(middle_messages)}

위 대화를 요약해주세요:"""

    # 요약 LLM 호출 (도구 없이, 빠른 모델 사용)
    # 💡 Extended thinking 활성화: 더 깊이 있는 요약 생성
    summary_llm = ChatAnthropic(
        model="claude-haiku-4-5",  # 빠르고 저렴한 모델
        temperature=1,  # Extended thinking 사용 시 반드시 1이어야 함
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        thinking={"type": "enabled", "budget_tokens": 2048},  # thinking 토큰 예산
    )

    try:
        # 이벤트 억제 (astream_events에서 캡처되지 않도록)
        from langchain_core.runnables import RunnableConfig

        summary_response = await summary_llm.ainvoke(
            [HumanMessage(content=summary_prompt)], config=RunnableConfig(callbacks=[])  # 콜백 비활성화
        )
        summary_content = summary_response.content

        # Thinking이 활성화되면 content가 리스트 형태로 반환됨 (text 블록만 추출)
        if isinstance(summary_content, list):
            text_blocks = [block for block in summary_content if block.get("type") == "text"]
            summary_text = "\n".join(block.get("text", "") for block in text_blocks)
        else:
            summary_text = summary_content

        # 요약 메시지 생성 (HumanMessage 사용)
        # 💡 SystemMessage 다음에 HumanMessage가 오는 게 LLM이 학습한 일반적인 패턴
        # 💡 LLM은 이를 "이전 대화 컨텍스트"로 자연스럽게 이해함
        summary_message = HumanMessage(content=f"[이전 대화 요약]\n\n{summary_text}\n\n[요약 끝 - 최근 대화 계속]")

    except Exception as e:
        # 요약 실패 시 폴백: 단순 메시지
        summary_message = HumanMessage(content=f"[이전 대화 요약 실패: {len(middle_messages)}개 메시지 생략]")
        print(f"\n⚠️  요약 생성 실패: {e}\n")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 4: 압축된 메시지 목록 재구성
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    compressed = []

    # 1. SystemMessage 유지
    if system_msg:
        compressed.append(system_msg)

    # 2. 요약 메시지 추가
    compressed.append(summary_message)

    # 3. 최근 메시지 유지
    # 💡 마지막 HumanMessage부터 끝까지 유지하므로 완전한 대화 턴 보장
    # → Orphan ToolMessage 발생하지 않음!

    # Thinking 없는 AIMessage 수정 (thinking 활성화 시 필수)
    for i, msg in enumerate(recent_messages):
        if isinstance(msg, AIMessage) and hasattr(msg, "content"):
            if isinstance(msg.content, list) and len(msg.content) > 0:
                # 첫 번째 블록이 thinking이 아니면 수정
                first_block_type = msg.content[0].get("type")
                if first_block_type not in ["thinking", "redacted_thinking"]:
                    # Thinking 블록이 없는 AIMessage는 content를 문자열로 변환
                    text_blocks = [block.get("text", "") for block in msg.content if block.get("type") == "text"]
                    if text_blocks:
                        # 새로운 AIMessage 생성 (tool_calls를 생성자에 전달)
                        new_msg = AIMessage(
                            content=" ".join(text_blocks),
                            tool_calls=msg.tool_calls if hasattr(msg, "tool_calls") and msg.tool_calls else None
                        )
                        recent_messages[i] = new_msg

    compressed.extend(recent_messages)

    # 압축 완료 로그
    compressed_actual = compressed[1:] if system_msg else compressed
    compressed_tokens = _count_tokens(compressed_actual)

    print(
        f"✅ 압축 완료: {len(messages)}개 → {len(compressed)}개 메시지, {token_count:,} → {compressed_tokens:,} tokens\n"
    )

    # 압축 후에도 토큰 수가 여전히 많으면 경고
    if compressed_tokens > max_tokens:
        print(f"   ⚠️  경고: 압축 후에도 {compressed_tokens:,} > {max_tokens:,} tokens")
        print(f"   → 최근 대화가 이미 임계값을 초과합니다\n")

    return compressed


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
    subagent_system_prompt = (
        system_prompt
        + f"""

# Subagent Restrictions

당신은 제한된 도구 접근 권한을 가진 subagent입니다. 다음 도구에는 접근할 수 **없습니다**:
- task_tool: 다른 subagent를 실행할 수 없습니다 (무한 재귀 방지)
- todo_write: 작업 추적은 main agent에서만 관리됩니다
- exit_plan_mode: 계획은 main agent에서만 처리됩니다

사용 가능한 도구: {', '.join(t.name for t in allowed_tools)}

제한된 도구의 기능이 필요한 경우, 사용 가능한 도구로 작업을 완료하고 결과를 main agent에게 반환하세요.
"""
    )

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
            thinking={"type": "enabled", "budget_tokens": 2048},
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
        "agent", subagent_should_continue, {"tools": "tools", END: END}  # 도구 호출 → tools 노드  # 종료 → END
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
