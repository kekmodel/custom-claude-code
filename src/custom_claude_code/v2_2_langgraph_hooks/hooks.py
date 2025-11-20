"""
Hook System for v2.2

Hook System은 Claude Code의 핵심 확장 메커니즘입니다.
다양한 이벤트에 대해 콜백을 등록하여 동작을 커스터마이징할 수 있습니다.

지원하는 Hook Events:
- PreToolUse: 도구 실행 전 호출
- PostToolUse: 도구 실행 후 호출
- UserPromptSubmit: 사용자 프롬프트 제출 시 호출
- PreCompact: 메시지 압축 전 호출
- Stop: 실행 중지 시 호출
- SubagentStop: Subagent 중지 시 호출
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Literal, Optional
import re

# Hook Event 타입
HookEvent = Literal[
    "PreToolUse",      # 도구 실행 전
    "PostToolUse",     # 도구 실행 후
    "UserPromptSubmit", # 사용자 프롬프트 제출 시
    "PreCompact",      # 메시지 압축 전
    "Stop",            # 실행 중지 시
    "SubagentStop"     # Subagent 중지 시
]

# Hook Callback 타입
HookCallback = Callable[
    [dict[str, Any], Optional[str], "HookContext"],
    Awaitable[dict[str, Any]]
]


@dataclass
class HookContext:
    """Hook 실행 컨텍스트"""
    session_id: str = ""
    turn_count: int = 0
    user_id: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class HookMatcher:
    """
    Hook Matcher: 특정 도구나 패턴에만 hook을 적용

    Args:
        matcher: 도구 이름 또는 정규식 패턴 (예: "Bash", "Write|Edit")
                None이면 모든 도구에 적용
        hooks: 실행할 콜백 함수 리스트
    """
    matcher: Optional[str] = None
    hooks: list[HookCallback] = field(default_factory=list)

    def matches(self, tool_name: str) -> bool:
        """도구 이름이 matcher와 일치하는지 확인"""
        if self.matcher is None:
            return True  # 모든 도구 매치

        try:
            pattern = re.compile(self.matcher)
            return bool(pattern.match(tool_name))
        except re.error:
            # 정규식 오류 시 exact match
            return self.matcher == tool_name


class HookSystem:
    """
    Hook System: 이벤트 기반 확장 시스템

    Example:
        # Hook 등록
        async def my_validator(input_data, tool_use_id, context):
            if input_data['tool_name'] == 'Bash':
                command = input_data['tool_input'].get('command', '')
                if 'rm -rf /' in command:
                    return {
                        'decision': 'block',
                        'systemMessage': 'Dangerous command detected'
                    }
            return {}

        hook_system = HookSystem()
        hook_system.register('PreToolUse', HookMatcher(
            matcher='Bash',
            hooks=[my_validator]
        ))

        # Hook 실행
        result = await hook_system.trigger(
            'PreToolUse',
            {'tool_name': 'Bash', 'tool_input': {'command': 'rm -rf /'}},
            tool_use_id='abc123',
            context=HookContext(session_id='session_1', turn_count=5)
        )

        if result.get('decision') == 'block':
            print('Tool execution blocked!')
    """

    def __init__(self):
        """Initialize Hook System"""
        self.hooks: dict[HookEvent, list[HookMatcher]] = {
            "PreToolUse": [],
            "PostToolUse": [],
            "UserPromptSubmit": [],
            "PreCompact": [],
            "Stop": [],
            "SubagentStop": [],
        }

    def register(self, event: HookEvent, matcher: HookMatcher) -> None:
        """
        Hook 등록

        Args:
            event: Hook event 이름
            matcher: HookMatcher 객체
        """
        if event in self.hooks:
            self.hooks[event].append(matcher)
        else:
            raise ValueError(f"Unknown hook event: {event}")

    def register_callback(
        self,
        event: HookEvent,
        callback: HookCallback,
        matcher: Optional[str] = None
    ) -> None:
        """
        Hook 콜백 직접 등록 (편의 메서드)

        Args:
            event: Hook event 이름
            callback: 콜백 함수
            matcher: 도구 이름 패턴 (None이면 모든 도구)
        """
        self.register(event, HookMatcher(matcher=matcher, hooks=[callback]))

    async def trigger(
        self,
        event: HookEvent,
        input_data: dict[str, Any],
        tool_use_id: Optional[str] = None,
        context: Optional[HookContext] = None
    ) -> dict[str, Any]:
        """
        Hook 실행

        Args:
            event: Hook event 이름
            input_data: Hook에 전달할 데이터
            tool_use_id: 도구 사용 ID (선택적)
            context: Hook 컨텍스트 (선택적)

        Returns:
            dict: Hook 실행 결과
                - decision: "block" | "allow" | "ask" (선택적)
                - systemMessage: 시스템 메시지 (선택적)
                - hookSpecificOutput: Hook별 특수 출력 (선택적)
                - updatedInput: 수정된 입력 데이터 (선택적)
        """
        if context is None:
            context = HookContext()

        tool_name = input_data.get('tool_name', '')

        # 등록된 모든 matchers를 순회
        for matcher in self.hooks.get(event, []):
            # Matcher가 도구 이름과 일치하는지 확인
            if not matcher.matches(tool_name):
                continue

            # Matcher의 모든 콜백 실행
            for callback in matcher.hooks:
                try:
                    result = await callback(input_data, tool_use_id, context)

                    # block 결정이 있으면 즉시 반환
                    if result.get('decision') == 'block':
                        return result

                    # ask 결정 (사용자 승인 요청)
                    if result.get('decision') == 'ask':
                        return result

                    # 입력 데이터 업데이트 (다음 hook으로 전달)
                    if 'updatedInput' in result:
                        input_data.update(result['updatedInput'])

                    # Hook별 특수 출력 처리
                    if 'hookSpecificOutput' in result:
                        # 특수 출력을 input_data에 병합
                        hook_output = result['hookSpecificOutput']
                        if isinstance(hook_output, dict):
                            input_data.setdefault('_hook_outputs', []).append(hook_output)

                except Exception as e:
                    # Hook 실행 중 오류 발생 시 로깅하고 계속 진행
                    print(f"[Hook Error] {event} hook failed: {type(e).__name__}: {str(e)}")
                    continue

        return {}  # 모든 hook 통과

    def has_hooks(self, event: HookEvent) -> bool:
        """특정 이벤트에 등록된 hook이 있는지 확인"""
        return len(self.hooks.get(event, [])) > 0


# 전역 Hook System 인스턴스 (싱글톤 패턴)
_global_hook_system: Optional[HookSystem] = None


def get_hook_system() -> HookSystem:
    """전역 Hook System 인스턴스 반환"""
    global _global_hook_system
    if _global_hook_system is None:
        _global_hook_system = HookSystem()
    return _global_hook_system


def reset_hook_system() -> None:
    """전역 Hook System 초기화 (테스트용)"""
    global _global_hook_system
    _global_hook_system = None


# 편의 함수들
async def trigger_hook(
    event: HookEvent,
    input_data: dict[str, Any],
    tool_use_id: Optional[str] = None,
    context: Optional[HookContext] = None
) -> dict[str, Any]:
    """전역 Hook System으로 hook 실행 (편의 함수)"""
    hook_system = get_hook_system()
    return await hook_system.trigger(event, input_data, tool_use_id, context)


def register_hook(
    event: HookEvent,
    callback: HookCallback,
    matcher: Optional[str] = None
) -> None:
    """전역 Hook System에 hook 등록 (편의 함수)"""
    hook_system = get_hook_system()
    hook_system.register_callback(event, callback, matcher)
