"""
Subagent 실행 엔진

Claude Code의 핵심 메커니즘:
- Task tool을 통해 Subagent 실행
- 독립적인 대화 컨텍스트
- 같은 시스템 프롬프트 + 도구 (캐시 공유!)
- 무한 중첩 가능 (DAG 제약)
"""

import json
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from .tools import TOOLS, execute_tool
from .types import SubagentType, TaskInput

# ============================================================================
# Model Mapping
# ============================================================================

MODEL_MAP = {
    "sonnet": "claude-sonnet-4-5",  # Claude Sonnet 4.5
    "opus": "claude-opus-4",  # Claude Opus 4
    "haiku": "claude-haiku-4-5",  # Claude Haiku 4.5
}


# ============================================================================
# Subagent 실행 엔진
# ============================================================================


async def execute_subagent(
    client: AsyncOpenAI, task_input: TaskInput, system_prompt: str, current_depth: int = 0, max_depth: int = 5
) -> str:
    """
    Subagent 실행

    Args:
        client: OpenAI async client
        task_input: Task tool input (Pydantic validated)
        system_prompt: System prompt (같은 프롬프트 사용!)
        current_depth: Current nesting depth
        max_depth: Maximum nesting depth

    Returns:
        Subagent report (str)

    Raises:
        RecursionError: If max depth exceeded
    """
    # 중첩 깊이 제한 (무한 재귀 방지)
    if current_depth >= max_depth:
        raise RecursionError(
            f"Subagent nesting depth exceeded {max_depth}.\n" f"This usually indicates circular Task calls."
        )

    # Model 선택
    model_name = MODEL_MAP.get(task_input.model.value if task_input.model else "haiku", "claude-haiku-4-5")

    # Tools 필터링 (Agent 타입별)
    allowed_tools = _filter_tools_by_agent_type(task_input.subagent_type)

    # Subagent의 독립적인 messages
    subagent_messages: List[Dict[str, Any]] = [
        {"role": "user", "content": task_input.prompt}  # Task의 prompt가 첫 메시지!
    ]

    # Subagent 대화 루프
    turn_count = 0
    max_turns = 50  # 무한 루프 방지

    while turn_count < max_turns:
        turn_count += 1

        try:
            # OpenAI API 호출
            response = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": system_prompt}, *subagent_messages],
                tools=allowed_tools,
                temperature=0.7,
                max_tokens=4096,
            )

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            # Assistant 메시지 추가
            assistant_message = {"role": "assistant", "content": message.content or ""}

            # tool_calls가 있으면 추가
            if message.tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ]

            subagent_messages.append(assistant_message)

            # finish_reason 처리
            if finish_reason == "stop":
                # Subagent 완료!
                final_report = message.content or "(No response)"
                return final_report

            elif finish_reason == "tool_calls":
                # 도구 실행
                tool_results = []

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name

                    try:
                        tool_input = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_input = {}

                    # 특별 처리: Task tool (중첩 Subagent)
                    if tool_name == "Task":
                        try:
                            nested_task_input = TaskInput(**tool_input)

                            # 재귀적으로 Subagent 실행!
                            nested_report = await execute_subagent(
                                client=client,
                                task_input=nested_task_input,
                                system_prompt=system_prompt,
                                current_depth=current_depth + 1,
                                max_depth=max_depth,
                            )

                            tool_results.append(
                                {"role": "tool", "tool_call_id": tool_call.id, "content": nested_report}
                            )
                        except Exception as e:
                            tool_results.append(
                                {"role": "tool", "tool_call_id": tool_call.id, "content": f"Subagent failed: {str(e)}"}
                            )

                    # ExitPlanMode 처리 (Plan Agent 종료)
                    elif tool_name == "ExitPlanMode":
                        try:
                            tool_result = await execute_tool(tool_name, tool_input)
                            # Plan을 반환하고 종료
                            return tool_result.result
                        except Exception as e:
                            return f"Error in ExitPlanMode: {str(e)}"

                    # 일반 도구 실행
                    else:
                        try:
                            tool_result = await execute_tool(tool_name, tool_input)
                            tool_results.append(
                                {"role": "tool", "tool_call_id": tool_call.id, "content": tool_result.result}
                            )
                        except Exception as e:
                            tool_results.append(
                                {"role": "tool", "tool_call_id": tool_call.id, "content": f"Error: {str(e)}"}
                            )

                # 도구 결과 추가
                subagent_messages.extend(tool_results)

                # 다시 요청 (continue)
                continue

            elif finish_reason == "length":
                # 토큰 한계 초과
                return f"[TRUNCATED] Subagent exceeded max tokens.\n\n{message.content or ''}"

            else:
                # 알 수 없는 finish_reason
                return f"[ERROR] Unknown finish_reason: {finish_reason}"

        except Exception as e:
            # API 에러
            return f"[ERROR] Subagent failed: {type(e).__name__}: {str(e)}"

    # Max turns 초과
    return f"[TRUNCATED] Subagent exceeded max turns ({max_turns})."


# ============================================================================
# Tools 필터링 (Agent 타입별)
# ============================================================================


def _filter_tools_by_agent_type(agent_type: SubagentType) -> List[Dict[str, Any]]:
    """
    Agent 타입에 따라 사용 가능한 도구 필터링

    Args:
        agent_type: Subagent type

    Returns:
        Filtered tools list
    """
    if agent_type == SubagentType.statusline_setup:
        # statusline-setup: Read, Edit만 허용
        allowed_names = ["Read", "Edit"]
        return [tool for tool in TOOLS if tool["function"]["name"] in allowed_names]

    # 나머지 Agent: 모든 도구 허용
    return TOOLS


# ============================================================================
# Subagent 정보 추출
# ============================================================================


def get_subagent_info(agent_type: SubagentType) -> Dict[str, Any]:
    """
    Subagent 타입별 정보 반환

    Args:
        agent_type: Subagent type

    Returns:
        Info dict with description, typical_tools, etc.
    """
    info_map = {
        SubagentType.general_purpose: {
            "description": "General-purpose agent for complex multi-step tasks",
            "typical_tools": ["All tools available"],
            "when_to_use": [
                "Complex research tasks",
                "Uncertain searches requiring multiple tries",
                "Multi-step automation",
                "Experimental exploration",
            ],
        },
        SubagentType.explore: {
            "description": "Fast agent for exploring codebases",
            "typical_tools": ["Glob", "Grep", "Read", "Task (nested)"],
            "when_to_use": [
                "Finding files by patterns",
                "Searching code for keywords",
                "Understanding codebase architecture",
                "Dependency tracking",
            ],
            "thoroughness_levels": ["quick", "medium", "very thorough"],
        },
        SubagentType.plan: {
            "description": "Planning agent for implementation steps",
            "typical_tools": ["Read", "Task(Explore)", "ExitPlanMode"],
            "when_to_use": [
                "Complex feature implementation before coding",
                "Large-scale refactoring",
                "Architecture changes",
                "Unclear requirements",
            ],
            "special": "Must use ExitPlanMode to present plan",
        },
        SubagentType.statusline_setup: {
            "description": "Specialized agent for statusline setup",
            "typical_tools": ["Read", "Edit (LIMITED!)"],
            "when_to_use": ["User explicitly requests statusline setup"],
            "limitation": "Only Read and Edit tools available",
        },
    }

    return info_map.get(agent_type, {"description": "Unknown agent type"})
