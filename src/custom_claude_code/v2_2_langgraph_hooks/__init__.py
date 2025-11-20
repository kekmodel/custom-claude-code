"""
Version 2.2: LangGraph + Hook System 구현

v2.1 기반 + Hook System 추가:
- StateGraph로 대화 플로우 정의
- ToolNode로 도구 실행
- ConditionalEdge로 분기 처리
- Checkpointer로 대화 히스토리 관리

Hook System:
- 6개 Hook Events (PreToolUse, PostToolUse, UserPromptSubmit, PreCompact, Stop, SubagentStop)
- Stateless Agents (Validation Agent, File Extraction Agent)
- Permission System (can_use_tool API)
- Settings Loader (CLAUDE.md 자동 로드)
"""
