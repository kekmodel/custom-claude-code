"""
v2.3: DeepAgents 기반 구현

특징:
- create_deep_agent 함수로 에이전트 생성
- Middleware 아키텍처 활용 (TodoListMiddleware, FilesystemMiddleware, SubAgentMiddleware)
- Planning tool, Sub agents, File system access 지원
- 기존 v2.1 도구들을 Custom Middleware로 통합
"""

__all__ = ["main"]


def __getattr__(name: str):
    """Lazy import to avoid circular import issues"""
    if name == "main":
        from .main import main
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
