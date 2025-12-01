"""
v2.3: DeepAgents 타입 정의

DeepAgents는 자체 상태 관리를 하므로 별도 AgentState가 필요 없지만,
커스텀 미들웨어에서 사용할 타입들을 정의합니다.
"""

from typing import TypedDict, Optional, Literal


class TodoItem(TypedDict):
    """할 일 항목"""
    content: str
    status: Literal["pending", "in_progress", "completed"]
    activeForm: str


class SubagentConfig(TypedDict):
    """Subagent 설정"""
    name: str
    description: str
    system_prompt: str
    tools: list
    model: Optional[str]
