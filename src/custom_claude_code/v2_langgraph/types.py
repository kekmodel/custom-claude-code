"""
v2: LangGraph 타입 정의

🎯 핵심 개념:
LangGraph에서 모든 노드는 "상태(State)"를 주고받습니다.
이 파일은 그 상태의 구조를 정의합니다.

📌 다른 도메인으로 확장할 때:
1. AgentState에 필요한 필드 추가
   예: code_quality: Optional[Dict], test_results: Optional[List]
2. 기본 필드(messages, depth)는 유지 권장
"""

from typing import Annotated, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    🔄 LangGraph의 핵심: 모든 노드가 공유하는 상태

    각 노드는 이 상태를 받아서 처리하고, 업데이트된 상태를 반환합니다.
    StateGraph가 자동으로 상태를 병합(merge)합니다.

    ✨ 특수 기능:
    - messages: Annotated로 add_messages reducer 지정
      → 새 메시지가 자동으로 append됨 (덮어쓰기 ❌)
    - 다른 필드: 일반 덮어쓰기 방식

    📝 사용 예시:
    ```python
    def my_node(state: AgentState) -> AgentState:
        # 상태 읽기
        current_messages = state["messages"]

        # 상태 업데이트 (부분 업데이트 가능)
        return {
            "messages": [new_message],  # ← add_messages가 자동 append
            "depth": state["depth"] + 1  # ← 일반 덮어쓰기
        }
    ```
    """

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 필수 필드: 대화 히스토리
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    messages: Annotated[Sequence[BaseMessage], add_messages]
    """
    💬 대화 메시지 목록 (자동 append!)

    Annotated[..., add_messages]의 의미:
    - 노드에서 {"messages": [new_msg]} 반환하면
    - StateGraph가 자동으로 기존 messages에 append
    - 덮어쓰기가 아닌 누적 방식!

    타입: List[BaseMessage] (HumanMessage, AIMessage, ToolMessage 등)

    📌 확장 팁:
    이 패턴을 그대로 유지하면 LangGraph의 자동 메시지 관리 기능을 활용할 수 있습니다.
    """

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 선택 필드: 컨텍스트 정보
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    working_dir: Optional[str]
    """
    📂 현재 작업 디렉토리

    용도: System prompt 생성 시 환경 정보 제공

    📌 확장 팁:
    도메인별로 필요한 컨텍스트를 추가할 수 있습니다:
    - 코드 에디터: current_file, cursor_position
    - 데이터 분석: dataset_path, column_names
    - 고객 지원: user_id, ticket_history
    """

    selected_tools: Optional[list[str]]
    """
    🔧 현재 턴에서 사용 가능한 도구 목록

    용도: 동적 도구 선택 (선택적 기능)
    - None이면 모든 도구 사용 가능
    - 리스트가 있으면 해당 도구만 제한적으로 사용

    📌 확장 팁:
    특정 상황에서 도구를 제한하고 싶을 때 유용:
    - 초보자 모드: 안전한 도구만 허용
    - 읽기 전용 모드: read_file, grep만 허용
    """

    depth: int
    """
    🔢 Subagent 중첩 깊이 (재귀 방지용)

    용도: Task 도구로 Subagent를 호출할 때 무한 재귀 방지
    - depth=0: Main agent
    - depth=1: 1단계 Subagent
    - depth=5: 최대 깊이 (보통 여기서 중단)

    중요: nodes.py의 execute_subagent()에서 depth를 체크하여
          max_depth를 초과하면 RecursionError 발생

    📌 확장 팁:
    복잡한 중첩 작업이 필요하면 max_depth를 조정할 수 있지만,
    무한 루프 위험이 있으니 주의!
    """

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📌 확장 예시: 도메인별 필드 추가
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 코드 품질 분석 도메인이라면:
    # code_quality: Optional[Dict[str, Any]]
    # """코드 품질 점수 및 이슈 목록"""

    # test_results: Optional[List[TestResult]]
    # """테스트 실행 결과"""

    # coverage: Optional[float]
    # """코드 커버리지 퍼센트"""

    # 데이터 분석 도메인이라면:
    # dataframe: Optional[pd.DataFrame]
    # """현재 분석 중인 데이터프레임"""

    # plot_config: Optional[Dict]
    # """시각화 설정"""


# Export for convenience
__all__ = ["AgentState"]
