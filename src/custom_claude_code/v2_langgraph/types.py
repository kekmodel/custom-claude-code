"""
v2: LangGraph 타입 정의

LangGraph의 MessagesState를 기반으로 확장
- messages: 대화 히스토리 (자동 관리)
- 추가 상태: selected_tools, working_dir 등
"""

from typing import Annotated, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    LangGraph Agent 상태

    LangGraph의 MessagesState 패턴을 따름:
    - messages는 add_messages reducer로 자동 append
    - 다른 필드는 일반 덮어쓰기
    """

    # Messages with automatic append (LangGraph pattern)
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Working directory (for system prompt generation)
    working_dir: Optional[str]

    # Selected tools for current turn (optional, for dynamic tool selection)
    selected_tools: Optional[list[str]]

    # Subagent depth (for nested Task calls)
    depth: int


# Export for convenience
__all__ = ["AgentState"]
