"""
Version 1: OpenAI API 직접 사용

Claude Code의 핵심 아키텍처를 OpenAI API로 구현:
- Function calling을 통한 도구 사용
- stop_reason 처리 (tool_calls vs stop)
- 대화 루프 (append-only messages)
- 기본 도구들: Read, Write, Edit, Bash
"""
