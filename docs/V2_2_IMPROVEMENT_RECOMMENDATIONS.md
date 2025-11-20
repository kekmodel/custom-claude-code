# v2.2 개선 권장사항
## SDK 분석 기반 v2.2 Hook System 강화 방안

> **분석 기반**: SDK_IMPLEMENTATION_DEEP_DIVE.md + AGENT_SELF_IMPROVEMENT_VIA_SDK.md
> **목적**: v2.2의 Hook System을 SDK 수준으로 강화

---

## Executive Summary

v2.2는 **Hook System의 기반 구조는 완벽**하지만, **실제 통합이 미완성** 상태입니다.

**현재 상태**:
- ✅ `HookSystem` 클래스 완벽 구현 (hooks.py)
- ✅ `Validation Agent` 구현 (validation_agent.py)
- ✅ `Permission System` 구현 (permission.py)
- ✅ 6개 Hook Events 타입 정의
- ❌ **execute_tools()에서 Hook 호출 안 함** (치명적!)
- ❌ `continue_` 필드 미구현
- ❌ `systemMessage` → LLM 전달 안 됨

**결론**: 구조는 우수하나, **실제 동작 연결이 필요**합니다.

---

## 1. 치명적 누락: Hook 실제 통합

### 1.1 문제점

**현재 graph.py:execute_tools()**:
```python
# v2_2_langgraph_hooks/graph.py:21-88
async def execute_tools(state: AgentState) -> dict:
    """커스텀 도구 실행 노드"""
    # ... (생략)

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        try:
            # ❌ PreToolUse Hook 호출 없음!

            if tool_name == "task_tool":
                result = await execute_subagent(...)
            else:
                result = tool.invoke(tool_args)

            # ❌ PostToolUse Hook 호출 없음!

            tool_messages.append(ToolMessage(...))
        except Exception as e:
            tool_messages.append(ToolMessage(...))

    return {"messages": tool_messages}
```

**문제**:
- Hook System이 구현되어 있지만 **아무도 호출하지 않음**
- Validation Agent가 있지만 **사용되지 않음**
- Permission System이 있지만 **무용지물**

### 1.2 해결 방안

**SDK 패턴 적용**:

```python
# graph.py 개선안
from .hooks import trigger_hook, HookContext

async def execute_tools(state: AgentState) -> dict:
    """Hook System 통합 도구 실행 노드"""
    messages = state["messages"]
    last_message = messages[-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_messages = []
    updated_todos = state.get("todos")

    # Hook Context 생성
    context = HookContext(
        session_id=state.get("session_id", "default"),
        turn_count=len(messages),
    )

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]

        # ✅ PreToolUse Hook 트리거
        pre_hook_result = await trigger_hook(
            event="PreToolUse",
            input_data={
                "tool_name": tool_name,
                "tool_input": tool_args,
            },
            tool_use_id=tool_call_id,
            context=context
        )

        # Hook이 차단하면 실행 안 함
        if pre_hook_result.get("decision") == "block":
            error_msg = pre_hook_result.get("systemMessage", "Tool execution blocked by hook")
            tool_messages.append(
                ToolMessage(content=f"[BLOCKED] {error_msg}", tool_call_id=tool_call_id, name=tool_name)
            )

            # systemMessage를 LLM에게 전달
            if pre_hook_result.get("systemMessage"):
                # 다음 턴에 LLM이 볼 수 있도록 HumanMessage 추가
                from langchain_core.messages import HumanMessage
                tool_messages.append(
                    HumanMessage(content=f"<system-reminder>\n{pre_hook_result['systemMessage']}\n</system-reminder>")
                )

            continue  # 다음 도구로

        # Hook이 입력 수정했으면 반영
        if "updatedInput" in pre_hook_result:
            tool_args.update(pre_hook_result["updatedInput"])

        # 도구 실행
        try:
            if tool_name == "task_tool":
                system_prompt = get_system_prompt(state.get("working_dir"))
                current_depth = state.get("depth", 0)
                result = await execute_subagent(
                    subagent_type=tool_args.get("subagent_type", "general-purpose"),
                    prompt=tool_args.get("prompt", ""),
                    system_prompt=system_prompt,
                    current_depth=current_depth,
                    max_depth=5,
                    model_name=tool_args.get("model", "claude-haiku-4-5"),
                )
            elif tool_name == "todo_write":
                tool = TOOLS_BY_NAME.get(tool_name)
                result = tool.invoke(tool_args)
                updated_todos = tool_args.get("todos", [])
            else:
                tool = TOOLS_BY_NAME.get(tool_name)
                if not tool:
                    result = f"[ERROR] Unknown tool: {tool_name}"
                else:
                    if hasattr(tool, 'coroutine') or tool_name in ['web_search', 'web_fetch']:
                        result = await tool.ainvoke(tool_args)
                    else:
                        result = tool.invoke(tool_args)

            # ✅ PostToolUse Hook 트리거
            post_hook_result = await trigger_hook(
                event="PostToolUse",
                input_data={
                    "tool_name": tool_name,
                    "tool_input": tool_args,
                    "tool_response": result,
                },
                tool_use_id=tool_call_id,
                context=context
            )

            # continue_ 필드 체크 (즉시 중단)
            if not post_hook_result.get("continue_", True):
                stop_reason = post_hook_result.get("stopReason", "Execution halted by hook")
                tool_messages.append(
                    ToolMessage(content=f"[STOPPED] {stop_reason}", tool_call_id=tool_call_id, name=tool_name)
                )

                # systemMessage 전달
                if post_hook_result.get("systemMessage"):
                    from langchain_core.messages import HumanMessage
                    tool_messages.append(
                        HumanMessage(content=f"<system-reminder>\n{post_hook_result['systemMessage']}\n</system-reminder>")
                    )

                # 즉시 반환 (더 이상 도구 실행 안 함)
                return {"messages": tool_messages, "todos": updated_todos}

            # 일반 Tool Result
            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_call_id, name=tool_name)
            )

            # PostToolUse Hook의 additionalContext를 LLM에게 전달
            if post_hook_result.get("hookSpecificOutput", {}).get("additionalContext"):
                from langchain_core.messages import HumanMessage
                additional = post_hook_result["hookSpecificOutput"]["additionalContext"]
                tool_messages.append(
                    HumanMessage(content=f"<system-reminder>\n{additional}\n</system-reminder>")
                )

        except Exception as e:
            tool_messages.append(
                ToolMessage(
                    content=f"[ERROR] {type(e).__name__}: {str(e)}",
                    tool_call_id=tool_call_id,
                    name=tool_name
                )
            )

    result_dict = {"messages": tool_messages}
    if updated_todos is not None:
        result_dict["todos"] = updated_todos

    return result_dict
```

**개선 효과**:
- ✅ PreToolUse Hook으로 사전 차단 가능
- ✅ PostToolUse Hook으로 즉시 중단 가능 (`continue_=False`)
- ✅ systemMessage가 LLM에게 전달됨
- ✅ additionalContext가 LLM에게 전달됨
- ✅ Validation Agent 활용 가능
- ✅ Permission System 활용 가능

---

## 2. continue_ 필드 구현

### 2.1 문제점

**현재 hooks.py:trigger()**:
```python
# hooks.py:146-209
async def trigger(self, event, input_data, tool_use_id, context):
    # ...
    for callback in matcher.hooks:
        result = await callback(input_data, tool_use_id, context)

        # ✅ decision: "block" 처리
        if result.get('decision') == 'block':
            return result

        # ✅ decision: "ask" 처리
        if result.get('decision') == 'ask':
            return result

        # ❌ continue_ 필드 처리 없음!

        # ...

    return {}
```

**문제**: SDK의 `continue_: False`로 즉시 중단하는 기능이 없음

### 2.2 해결 방안

**hooks.py 개선**:

```python
# hooks.py:trigger() 메서드 업데이트
async def trigger(
    self,
    event: HookEvent,
    input_data: dict[str, Any],
    tool_use_id: Optional[str] = None,
    context: Optional[HookContext] = None
) -> dict[str, Any]:
    """
    Hook 실행

    Returns:
        dict: Hook 실행 결과
            - decision: "block" | "allow" | "ask" (선택적)
            - continue_: bool (선택적, PostToolUse에서 사용)
            - stopReason: str (선택적, continue_=False일 때)
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

                # ✅ continue_=False 즉시 반환 (최우선!)
                if 'continue_' in result and not result['continue_']:
                    return result

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
                    hook_output = result['hookSpecificOutput']
                    if isinstance(hook_output, dict):
                        input_data.setdefault('_hook_outputs', []).append(hook_output)

            except Exception as e:
                # Hook 실행 중 오류 발생 시 로깅하고 계속 진행
                print(f"[Hook Error] {event} hook failed: {type(e).__name__}: {str(e)}")
                continue

    return {}  # 모든 hook 통과
```

**사용 예시**:

```python
# PostToolUse Hook으로 Critical 에러 즉시 중단
async def critical_error_stopper(input_data, tool_use_id, context):
    """Critical 에러 감지 시 즉시 중단"""
    tool_response = input_data.get("tool_response", "")

    critical_patterns = ["FATAL", "OutOfMemoryError", "ENOSPC"]

    for pattern in critical_patterns:
        if pattern in str(tool_response):
            logger.error(f"🛑 Critical error: {pattern}")
            return {
                "continue_": False,  # ← 즉시 중단!
                "stopReason": f"Critical error detected: {pattern}",
                "systemMessage": f"🚨 Execution halted - critical error: {pattern}",
            }

    return {"continue_": True}  # 계속 진행

# Hook 등록
from .hooks import register_hook
register_hook("PostToolUse", critical_error_stopper)
```

---

## 3. UserPromptSubmit Hook 통합

### 3.1 문제점

**현재 main.py**:
```python
# main.py에서 사용자 입력 처리
user_input = input("User: ")
state["messages"].append(HumanMessage(content=user_input))
# ❌ UserPromptSubmit Hook 호출 안 함!
```

### 3.2 해결 방안

**main.py 개선**:

```python
# main.py
from .hooks import trigger_hook, HookContext

async def process_user_input(user_input: str, state: AgentState) -> str:
    """사용자 입력 처리 (Hook 통합)"""

    # UserPromptSubmit Hook 트리거
    context = HookContext(
        session_id=state.get("session_id", "default"),
        turn_count=len(state["messages"]),
    )

    hook_result = await trigger_hook(
        event="UserPromptSubmit",
        input_data={"user_input": user_input},
        context=context
    )

    # additionalContext를 user_input에 추가
    final_input = user_input
    if hook_result.get("hookSpecificOutput", {}).get("additionalContext"):
        additional = hook_result["hookSpecificOutput"]["additionalContext"]
        final_input = f"{user_input}\n\n<system-reminder>\n{additional}\n</system-reminder>"

    return final_input

# 사용
user_input = input("User: ")
processed_input = await process_user_input(user_input, state)
state["messages"].append(HumanMessage(content=processed_input))
```

**활용 예시**:

```python
# 프로젝트 컨텍스트 자동 주입 Hook
async def project_context_injector(input_data, tool_use_id, context):
    """UserPromptSubmit: 프로젝트 정보 자동 주입"""
    from .settings import load_project_settings
    from pathlib import Path

    # CLAUDE.md 및 프로젝트 설정 로드
    settings = load_project_settings(cwd=Path.cwd())
    claude_md = settings.get("claude_md")

    if claude_md:
        return {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"""
Project Instructions (CLAUDE.md):
{claude_md}

IMPORTANT: Follow these project-specific instructions when responding.
                """,
            }
        }

    return {}

# Hook 등록
register_hook("UserPromptSubmit", project_context_injector)
```

---

## 4. SubagentStop Hook 통합

### 4.1 문제점

**현재 nodes.py:execute_subagent()**:
```python
# nodes.py:64-158
async def execute_subagent(...) -> str:
    # ...
    final_state = await subagent_graph.ainvoke(...)

    if final_state["messages"]:
        last_msg = final_state["messages"][-1]
        if isinstance(last_msg, AIMessage):
            return last_msg.content or "(no response)"

    # ❌ SubagentStop Hook 호출 안 함!
    return "(no response)"
```

### 4.2 해결 방안

**nodes.py 개선**:

```python
# nodes.py
async def execute_subagent(
    subagent_type: str,
    prompt: str,
    system_prompt: str,
    current_depth: int = 0,
    max_depth: int = 5,
    model_name: str = "claude-haiku-4-5",
) -> str:
    """독립 StateGraph로 Subagent 실행"""
    from langchain_core.runnables import RunnableConfig
    from .hooks import trigger_hook, HookContext

    if current_depth >= max_depth:
        return f"[ERROR] Max subagent depth ({max_depth}) exceeded"

    # ... (도구 제한, 그래프 생성 코드는 동일)

    try:
        final_state = await subagent_graph.ainvoke(initial_state, config=RunnableConfig(callbacks=[]))

        # Subagent 결과 추출
        result_content = "(no response)"
        if final_state["messages"]:
            last_msg = final_state["messages"][-1]
            if isinstance(last_msg, AIMessage):
                result_content = last_msg.content or "(no response)"

        # ✅ SubagentStop Hook 트리거
        context = HookContext(
            turn_count=len(final_state["messages"]),
            extra={"subagent_type": subagent_type, "depth": current_depth + 1}
        )

        hook_result = await trigger_hook(
            event="SubagentStop",
            input_data={
                "subagent_type": subagent_type,
                "prompt": prompt,
                "result": result_content,
                "message_count": len(final_state["messages"]),
            },
            context=context
        )

        # Hook이 결과를 수정했으면 반영
        if hook_result.get("modifiedResult"):
            result_content = hook_result["modifiedResult"]

        # additionalContext를 결과에 추가
        if hook_result.get("hookSpecificOutput", {}).get("additionalContext"):
            additional = hook_result["hookSpecificOutput"]["additionalContext"]
            result_content = f"{result_content}\n\n<hook-note>\n{additional}\n</hook-note>"

        return result_content

    except Exception as e:
        return f"[ERROR] Subagent failed: {type(e).__name__}: {str(e)}"
```

**활용 예시**:

```python
# Subagent 결과 요약 Hook
async def subagent_result_summarizer(input_data, tool_use_id, context):
    """SubagentStop: Subagent 결과 요약 추가"""
    subagent_type = input_data.get("subagent_type")
    message_count = input_data.get("message_count", 0)

    return {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStop",
            "additionalContext": f"""
Subagent Execution Summary:
- Type: {subagent_type}
- Messages: {message_count}
- Status: Completed successfully
            """,
        }
    }

register_hook("SubagentStop", subagent_result_summarizer)
```

---

## 5. Agent Definition 패턴 도입

### 5.1 문제점

**현재 방식** (코드로 하드코딩):
```python
# nodes.py:94-101
if subagent_type == "Explore":
    explore_tools = {"read_file", "grep_code", "glob_files", "web_search", "web_fetch"}
    allowed_tools = [t for t in allowed_tools if t.name in explore_tools]
elif subagent_type == "Plan":
    plan_tools = {"read_file", "grep_code", "glob_files", "web_search", "web_fetch"}
    allowed_tools = [t for t in allowed_tools if t.name in plan_tools]
```

**문제**:
- 새 Subagent 추가 시 코드 수정 필요
- 재사용 불가능 (프로젝트 간 공유 어려움)

### 5.2 해결 방안

**SDK 패턴 적용 - AgentDefinition**:

```python
# types.py에 추가
from typing import TypedDict, Optional

class AgentDefinition(TypedDict):
    """Subagent 정의 (SDK 패턴)"""
    description: str  # Main Agent에게 보이는 설명
    prompt: str       # Subagent의 system prompt 추가 내용
    tools: list[str]  # 허용된 도구 목록
    model: Optional[str]  # "sonnet", "haiku", "opus" 또는 None
```

**config.py 개선**:

```python
# config.py
from .types import AgentDefinition

# Subagent 정의 (설정으로 분리!)
AGENT_DEFINITIONS: dict[str, AgentDefinition] = {
    "Explore": {
        "description": "Searches and explores the codebase for files, patterns, and information",
        "prompt": """You are a file search specialist.
Your strengths:
- Rapidly finding files using glob patterns
- Searching code and text with powerful regex patterns
- Reading and analyzing file contents

CRITICAL: This is a READ-ONLY exploration task. You MUST NOT create, write, or modify any files.
        """,
        "tools": ["read_file", "grep_code", "glob_files", "web_search", "web_fetch"],
        "model": "haiku",  # 빠른 검색용
    },

    "Plan": {
        "description": "Plans implementation steps for complex tasks without executing them",
        "prompt": """You are a planning specialist.
Analyze the requirements and create a detailed implementation plan.

IMPORTANT: You are in planning mode only. Do NOT execute any changes.
Use ExitPlanMode tool when you've completed the plan.
        """,
        "tools": ["read_file", "grep_code", "glob_files", "web_search", "web_fetch"],
        "model": "sonnet",  # 더 나은 계획 수립용
    },

    "code-reviewer": {
        "description": "Reviews code for best practices, bugs, and security issues",
        "prompt": """You are a code review expert.
Analyze code for:
1. Security vulnerabilities (SQL injection, XSS, etc.)
2. Performance issues
3. Best practice violations
4. Potential bugs

Provide constructive, actionable feedback.
        """,
        "tools": ["read_file", "grep_code", "glob_files"],
        "model": "sonnet",
    },

    "doc-writer": {
        "description": "Writes comprehensive technical documentation",
        "prompt": """You are a technical documentation expert.
Write clear, comprehensive documentation with:
- Clear explanations
- Code examples
- Usage patterns
- Common pitfalls
        """,
        "tools": ["read_file", "write_file", "edit_file", "grep_code"],
        "model": "sonnet",
    },
}
```

**nodes.py 개선**:

```python
# nodes.py
from .config import AGENT_DEFINITIONS

async def execute_subagent(
    subagent_type: str,
    prompt: str,
    system_prompt: str,
    current_depth: int = 0,
    max_depth: int = 5,
    model_name: str = "claude-haiku-4-5",
) -> str:
    """독립 StateGraph로 Subagent 실행 (AgentDefinition 기반)"""
    from langchain_core.runnables import RunnableConfig

    if current_depth >= max_depth:
        return f"[ERROR] Max subagent depth ({max_depth}) exceeded"

    # ✅ AgentDefinition에서 설정 로드
    agent_def = AGENT_DEFINITIONS.get(subagent_type)

    if not agent_def:
        # Unknown subagent type → general-purpose로 fallback
        agent_def = {
            "description": "General-purpose agent",
            "prompt": "",
            "tools": [t.name for t in TOOLS if t.name not in {"task_tool", "todo_write"}],
            "model": None,
        }

    # 모델 결정
    if agent_def["model"]:
        # AgentDefinition에 모델 지정되어 있으면 사용
        model_alias = agent_def["model"]
        if model_alias in MODEL_ALIASES:
            provider, full_model_name = MODEL_ALIASES[model_alias]
        else:
            provider = "anthropic"
            full_model_name = model_alias
    else:
        # 없으면 기본 모델
        provider = "anthropic"
        full_model_name = model_name

    # 도구 제한 (AgentDefinition에서 가져옴)
    allowed_tool_names = set(agent_def["tools"])
    allowed_tools = [t for t in TOOLS if t.name in allowed_tool_names]

    # System prompt 구성
    base_prompt = system_prompt
    additional_prompt = agent_def["prompt"]

    if additional_prompt:
        subagent_system_prompt = f"{base_prompt}\n\n{additional_prompt}"
    else:
        subagent_system_prompt = base_prompt

    # ... (나머지는 동일)
```

**장점**:
- ✅ 새 Subagent 추가 시 config.py만 수정
- ✅ 재사용 가능 (AGENT_DEFINITIONS를 파일로 저장 가능)
- ✅ Main Agent가 description을 보고 적절한 Subagent 선택
- ✅ 모델별 최적화 (Explore=haiku, Plan=sonnet)

---

## 6. Retry 패턴 구현

### 6.1 문제점

현재 v2.2는 **도구 실패 시 LLM이 판단**해야 합니다. SDK처럼 **자동 재시도 힌트**가 없습니다.

### 6.2 해결 방안

**PostToolUse Hook으로 재시도 힌트**:

```python
# hooks_examples.py (새 파일)
async def retry_hint_hook(input_data, tool_use_id, context):
    """PostToolUse: 재시도 가능한 에러 감지 및 힌트"""
    tool_response = input_data.get("tool_response", "")

    # 재시도 가능한 에러 패턴
    retryable_patterns = {
        "ETIMEDOUT": "Network timeout - try again after a brief wait",
        "ECONNREFUSED": "Connection refused - service may be starting, retry in a few seconds",
        "EBUSY": "Resource busy - wait and retry",
        "429": "Rate limit exceeded - wait 5 seconds and retry",
        "503": "Service unavailable - temporary issue, retry shortly",
    }

    response_str = str(tool_response)

    for pattern, hint in retryable_patterns.items():
        if pattern in response_str:
            return {
                "continue_": True,
                "systemMessage": f"💡 {hint}",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": f"""
This is a temporary/retryable error: {pattern}

Recommendation: {hint}

You can retry the same command after addressing the issue.
Consider implementing exponential backoff if retrying multiple times.
                    """,
                }
            }

    return {}

# 등록
from .hooks import register_hook
register_hook("PostToolUse", retry_hint_hook)
```

**State 기반 재시도 제한**:

```python
# types.py에 추가
class AgentState(TypedDict):
    # ... 기존 필드
    retry_counts: Optional[dict[str, int]]  # tool_call_id → retry count
```

```python
# graph.py에서 재시도 제한
async def execute_tools(state: AgentState) -> dict:
    # ...
    retry_counts = state.get("retry_counts", {})
    max_retries = 3

    for tool_call in last_message.tool_calls:
        tool_call_id = tool_call["id"]

        # 재시도 횟수 확인
        current_retries = retry_counts.get(tool_call_id, 0)

        if current_retries >= max_retries:
            tool_messages.append(
                ToolMessage(
                    content=f"[ERROR] Max retries ({max_retries}) exceeded for this tool call",
                    tool_call_id=tool_call_id,
                    name=tool_name
                )
            )
            continue

        # 도구 실행
        # ...

        # 실패 시 재시도 카운터 증가
        if "[ERROR]" in str(result) or "error" in str(result).lower():
            retry_counts[tool_call_id] = current_retries + 1
        else:
            # 성공 시 카운터 리셋
            retry_counts.pop(tool_call_id, None)

    return {
        "messages": tool_messages,
        "retry_counts": retry_counts,
    }
```

---

## 7. 실전 예제: 완전한 통합

### 7.1 CI/CD Bot (SDK 패턴 완전 적용)

```python
# examples/cicd_bot_v2_2.py
"""
v2.2 기반 Self-Correcting CI/CD Bot

SDK 패턴 적용:
1. PreToolUse Hook - 빌드 명령어 검증
2. PostToolUse Hook - 빌드 결과 분석 및 재시도 제어
3. continue_ 필드 - Critical 에러 즉시 중단
4. AgentDefinition - code-reviewer Subagent
5. Retry 패턴 - 최대 3회 재시도
"""

import asyncio
from pathlib import Path
from langchain_core.messages import HumanMessage

# v2.2 imports
from custom_claude_code.v2_2_langgraph_hooks.graph import graph
from custom_claude_code.v2_2_langgraph_hooks.hooks import register_hook
from custom_claude_code.v2_2_langgraph_hooks.config import AGENT_DEFINITIONS
from custom_claude_code.v2_2_langgraph_hooks.types import AgentState

# Global state (실전에서는 Redis 등 사용)
retry_counts = {}

# Hook 1: Build 명령어 검증
async def build_validator_hook(input_data, tool_use_id, context):
    """PreToolUse: 빌드 명령어만 허용"""
    tool_name = input_data.get("tool_name")

    if tool_name != "bash_command":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")

    # 허용된 빌드 명령어
    allowed_commands = [
        "npm run build",
        "npm test",
        "npm run lint",
        "git status",
        "git diff",
    ]

    if not any(cmd in command for cmd in allowed_commands):
        return {
            "decision": "block",
            "systemMessage": "🚫 Only build and test commands are allowed in CI/CD mode",
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Only build/test commands allowed in CI/CD mode",
            }
        }

    return {}

# Hook 2: Build 결과 분석 및 재시도 제어
async def build_result_analyzer(input_data, tool_use_id, context):
    """PostToolUse: 빌드 결과 분석 및 재시도 제어"""
    global retry_counts

    tool_name = input_data.get("tool_name")

    if tool_name != "bash_command":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")

    # Build 명령어가 아니면 통과
    if "npm run build" not in command and "npm test" not in command:
        return {}

    tool_response = str(input_data.get("tool_response", ""))

    # Critical 에러 체크
    critical_patterns = ["FATAL", "OutOfMemoryError", "ENOSPC"]
    for pattern in critical_patterns:
        if pattern in tool_response:
            return {
                "continue_": False,  # 즉시 중단!
                "stopReason": f"Critical CI/CD error: {pattern}",
                "systemMessage": f"🚨 Build halted - critical error: {pattern}",
            }

    # Build 성공
    if "error" not in tool_response.lower():
        # 재시도 카운터 리셋
        if tool_use_id in retry_counts:
            del retry_counts[tool_use_id]

        return {
            "systemMessage": "✅ Build/test succeeded!",
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "Build successful. Ready for deployment.",
            }
        }

    # Build 실패 - 재시도 제어
    retry_count = retry_counts.get(tool_use_id, 0)
    max_retries = 3

    if retry_count >= max_retries:
        return {
            "continue_": False,  # 최대 재시도 초과 - 중단
            "stopReason": f"Build failed after {max_retries} attempts",
            "systemMessage": f"❌ Build failed after {max_retries} retries - manual intervention needed",
        }

    # 재시도 카운터 증가
    retry_counts[tool_use_id] = retry_count + 1

    # 에러 분석
    error_lines = [line for line in tool_response.split('\n') if 'error' in line.lower()]
    error_count = len(error_lines)

    return {
        "continue_": True,
        "systemMessage": f"⚠️ Build failed with {error_count} errors (attempt {retry_count + 1}/{max_retries})",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"""
Build failed. This is attempt {retry_count + 1} of {max_retries}.

Error summary:
{chr(10).join(error_lines[:5])}

Please:
1. Read the error messages carefully
2. Identify the root cause
3. Fix the issues one at a time
4. Re-run the build to verify

Remaining attempts: {max_retries - retry_count - 1}
            """,
        }
    }

# Hook 등록
register_hook("PreToolUse", build_validator_hook, matcher="bash_command")
register_hook("PostToolUse", build_result_analyzer, matcher="bash_command")

# AgentDefinition에 code-reviewer 추가 (이미 config.py에 있다고 가정)

async def run_cicd_bot():
    """CI/CD Bot 실행"""

    initial_state: AgentState = {
        "messages": [
            HumanMessage(content="""
Run the build and fix any errors that occur.
Keep trying until the build succeeds or you reach the retry limit (3 attempts).

Use the code-reviewer agent if you need help analyzing errors.
            """)
        ],
        "working_dir": str(Path.cwd()),
        "selected_tools": None,
        "depth": 0,
        "todos": None,
        "retry_counts": {},
    }

    print("🤖 CI/CD Bot started\n")

    # Graph 실행
    final_state = await graph.ainvoke(initial_state)

    print("\n" + "="*60)
    print("CI/CD Workflow Complete")
    print("="*60)
    print(f"Total messages: {len(final_state['messages'])}")
    print(f"Retry attempts: {sum(retry_counts.values())}")

if __name__ == "__main__":
    asyncio.run(run_cicd_bot())
```

---

## 8. 우선순위 및 로드맵

### 8.1 Critical (즉시 구현 필요)

**우선순위 1**: Hook 실제 통합 (execute_tools 수정)
- 예상 시간: 2-3시간
- 영향도: ⭐⭐⭐⭐⭐
- 이유: 현재 Hook System이 동작하지 않음

**우선순위 2**: continue_ 필드 구현
- 예상 시간: 1시간
- 영향도: ⭐⭐⭐⭐⭐
- 이유: SDK의 핵심 기능, 즉시 중단 불가능

**우선순위 3**: systemMessage LLM 전달
- 예상 시간: 1시간
- 영향도: ⭐⭐⭐⭐
- 이유: Hook의 피드백이 LLM에게 전달되지 않음

### 8.2 Important (단기 구현 권장)

**우선순위 4**: UserPromptSubmit Hook 통합
- 예상 시간: 2시간
- 영향도: ⭐⭐⭐⭐
- 이유: 프로젝트 컨텍스트 자동 주입 가능

**우선순위 5**: SubagentStop Hook 통합
- 예상 시간: 1시간
- 영향도: ⭐⭐⭐
- 이유: Subagent 결과 후처리 가능

**우선순위 6**: AgentDefinition 패턴 도입
- 예상 시간: 3-4시간
- 영향도: ⭐⭐⭐⭐
- 이유: 코드 재사용성 및 확장성 향상

### 8.3 Nice to Have (장기 검토)

**우선순위 7**: Retry 패턴 구현
- 예상 시간: 2-3시간
- 영향도: ⭐⭐⭐
- 이유: 더 나은 UX, 하지만 LLM이 이미 재시도 가능

**우선순위 8**: In-Process MCP 구현
- 예상 시간: 1주일
- 영향도: ⭐⭐⭐
- 이유: 성능 향상, 하지만 현재 도구 시스템도 충분

---

## 9. 결론

### 9.1 v2.2의 현재 위치

```
┌────────────────────────────────────────────────────┐
│ v2.2 Hook System 완성도                             │
├────────────────────────────────────────────────────┤
│ 구조 설계: ████████████████████████ 95%            │
│ 실제 통합: ████                     20%            │
│ 문서화:   ██████████████████        80%            │
│ 테스트:   ████                      20%            │
├────────────────────────────────────────────────────┤
│ 전체:     ████████████              50%            │
└────────────────────────────────────────────────────┘
```

**강점**:
- ✅ Hook System 기반 구조가 SDK 수준으로 우수
- ✅ Validation Agent, Permission System 등 고급 기능 구현
- ✅ LangGraph 통합으로 워크플로우 명확

**약점**:
- ❌ Hook이 실제로 호출되지 않음 (execute_tools 미통합)
- ❌ continue_ 필드 미구현
- ❌ systemMessage가 LLM에게 전달 안 됨

### 9.2 SDK vs v2.2 비교

| 기능 | SDK | v2.2 현재 | v2.2 개선 후 |
|-----|-----|----------|------------|
| Hook System | ✅ | ⚠️ (구조만) | ✅ |
| PreToolUse | ✅ | ⚠️ (미통합) | ✅ |
| PostToolUse | ✅ | ⚠️ (미통합) | ✅ |
| continue_ | ✅ | ❌ | ✅ |
| systemMessage→LLM | ✅ | ❌ | ✅ |
| AgentDefinition | ✅ | ❌ | ✅ |
| UserPromptSubmit | ✅ | ⚠️ (미통합) | ✅ |
| SubagentStop | ✅ | ❌ | ✅ |
| In-Process MCP | ✅ | ❌ | ⚠️ (선택) |

### 9.3 최종 권장사항

**단기 (1주일 내)**:
1. ✅ execute_tools()에 Hook 통합
2. ✅ continue_ 필드 구현
3. ✅ systemMessage LLM 전달

**중기 (2주일 내)**:
4. ✅ UserPromptSubmit Hook 통합
5. ✅ SubagentStop Hook 통합
6. ✅ AgentDefinition 패턴 도입

**장기 (선택)**:
7. ⚠️ Retry 패턴 구현
8. ⚠️ In-Process MCP 구현

**구현하면**:
- ✅ v2.2가 SDK 수준의 Hook System 제공
- ✅ Production-ready Self-Correcting Agent 구축 가능
- ✅ 연구용 + 실전용 모두 커버

---

**작성자**: Claude (Sonnet 4.5)
**분석 기반**: SDK_IMPLEMENTATION_DEEP_DIVE.md + AGENT_SELF_IMPROVEMENT_VIA_SDK.md + v2.2 코드 검토
**목적**: v2.2를 SDK 수준으로 강화하기 위한 실행 가능한 로드맵
**문서 버전**: 1.0 (2025-11-20)
