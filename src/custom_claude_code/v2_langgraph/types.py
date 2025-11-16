"""
v2: LangGraph 타입 정의

핵심: 모든 노드가 공유하는 AgentState 구조 정의
messages는 add_messages reducer로 자동 append
"""

from typing import Annotated, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    모든 노드가 공유하는 상태

    messages: Annotated[..., add_messages]로 자동 append (덮어쓰기 ❌)
    기타 필드: 일반 덮어쓰기 방식
    """

    # LangGraph reducer: Annotated[타입, reducer함수]로 병합 방식 지정
    # add_messages = 기존 리스트에 append (덮어쓰기 X)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    """대화 메시지 목록 (add_messages reducer로 자동 append)"""

    working_dir: Optional[str]
    """현재 작업 디렉토리 (system prompt 생성에 사용)"""

    selected_tools: Optional[list[str]]
    """사용 가능한 도구 목록 (None이면 전체 허용)"""

    depth: int
    """Subagent 중첩 깊이 (무한 재귀 방지용, max=5)"""

    todos: Optional[list[dict]]
    """작업 추적 목록 (content, status, activeForm)"""


__all__ = ["AgentState"]
