"""
Permission System (can_use_tool API)

High-level API for tool permission control.
Hook System의 고수준 추상화입니다.
"""

from typing import Any, Callable, Awaitable, Optional, Literal
from .hooks import HookCallback, HookContext

# Permission 결정 타입
PermissionDecision = Literal["allow", "deny", "ask"]

# can_use_tool 콜백 타입
CanUseTool = Callable[
    [str, dict[str, Any], dict[str, Any]],
    Awaitable[dict[str, Any]]
]


async def can_use_tool_to_hook(
    can_use_tool_callback: CanUseTool,
    input_data: dict[str, Any],
    tool_use_id: Optional[str],
    context: HookContext
) -> dict[str, Any]:
    """
    can_use_tool 콜백을 Hook System으로 변환

    Args:
        can_use_tool_callback: can_use_tool 콜백 함수
        input_data: Hook input data
        tool_use_id: Tool use ID
        context: Hook context

    Returns:
        dict: Hook result
    """
    tool_name = input_data.get('tool_name', '')
    tool_input = input_data.get('tool_input', {})

    # Context 변환
    permission_context = {
        'session_id': context.session_id,
        'turn_count': context.turn_count,
        'tool_use_id': tool_use_id,
        **context.extra
    }

    # can_use_tool 콜백 실행
    result = await can_use_tool_callback(tool_name, tool_input, permission_context)

    behavior = result.get('behavior', 'allow')

    if behavior == 'deny':
        return {
            'decision': 'block',
            'systemMessage': result.get('message', 'Permission denied'),
            'hookSpecificOutput': {
                'hookEventName': 'PreToolUse',
                'permissionDecision': 'deny',
                'permissionDecisionReason': result.get('message', 'Permission denied')
            }
        }
    elif behavior == 'ask':
        return {
            'decision': 'ask',
            'systemMessage': result.get('message', 'Approval required'),
            'hookSpecificOutput': {
                'hookEventName': 'PreToolUse',
                'permissionDecision': 'ask',
                'permissionDecisionReason': result.get('message', 'Approval required')
            }
        }

    # allow
    hook_result = {}

    # 입력 수정
    if 'updatedInput' in result:
        hook_result['updatedInput'] = result['updatedInput']

    return hook_result


def create_permission_hook(can_use_tool_callback: CanUseTool) -> HookCallback:
    """
    can_use_tool 콜백을 PreToolUse Hook으로 변환

    Args:
        can_use_tool_callback: can_use_tool 콜백 함수

    Returns:
        HookCallback: PreToolUse Hook 콜백

    Example:
        async def my_permission_handler(tool_name, input_data, context):
            # Block system directory writes
            if tool_name == "Write" and input_data.get("file_path", "").startswith("/system/"):
                return {
                    "behavior": "deny",
                    "message": "System directory write not allowed"
                }

            # Redirect config files to sandbox
            if tool_name in ["Write", "Edit"] and "config" in input_data.get("file_path", ""):
                safe_path = f"./sandbox/{input_data['file_path']}"
                return {
                    "behavior": "allow",
                    "updatedInput": {**input_data, "file_path": safe_path}
                }

            return {"behavior": "allow"}

        from .hooks import register_hook
        from .permission import create_permission_hook

        permission_hook = create_permission_hook(my_permission_handler)
        register_hook('PreToolUse', permission_hook)
    """
    async def hook_wrapper(
        input_data: dict[str, Any],
        tool_use_id: Optional[str],
        context: HookContext
    ) -> dict[str, Any]:
        return await can_use_tool_to_hook(
            can_use_tool_callback,
            input_data,
            tool_use_id,
            context
        )

    return hook_wrapper
