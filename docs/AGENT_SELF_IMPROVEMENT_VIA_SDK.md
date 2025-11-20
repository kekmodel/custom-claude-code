# Agent Self-Improvement via Claude Agent SDK
## SDK Hook System을 활용한 Self-Correction 구현 패턴

> **분석 목적**: AI_AGENT_SELF_IMPROVEMENT_ARCHITECTURE.md + SDK_IMPLEMENTATION_DEEP_DIVE.md 통합
> **핵심 질문**: SDK Hook System이 Agent의 Self-Correction을 어떻게 강화하는가?

---

## Executive Summary

Claude Agent SDK의 **Hook System**은 단순한 이벤트 리스너가 아닙니다. **Self-Improvement Loop에 직접 개입**하는 강력한 메커니즘입니다.

**핵심 발견**:

1. **PreToolUse Hook** = **사전 검증 게이트** (실행 전 차단)
2. **PostToolUse Hook** = **즉시 피드백 루프** (실패 감지 및 수정 지시)
3. **UserPromptSubmit Hook** = **컨텍스트 자동 주입** (LLM의 판단력 향상)
4. **continue_ 필드** = **비상 정지 스위치** (Critical 에러 시 즉시 중단)

**결론**: Hook System을 활용하면 **v1/v2에서 코드로 구현했던 Self-Correction 로직을 애플리케이션 레벨로 이동**할 수 있습니다.

---

## 1. Self-Correction의 3계층

### 1.1 계층 구조

```
┌──────────────────────────────────────────────────────────┐
│ Layer 3: Application-Level (SDK Hooks)                   │
│                                                           │
│ • PreToolUse: 실행 전 검증                                 │
│ • PostToolUse: 실행 후 피드백                              │
│ • UserPromptSubmit: 컨텍스트 주입                          │
│ • continue_: False → 즉시 중단                            │
│                                                           │
│ 역할: 애플리케이션별 정책 적용                               │
└──────────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│ Layer 2: CLI-Level (Agent Loop)                          │
│                                                           │
│ • finish_reason 제어                                      │
│ • Tool Result → LLM 피드백                                │
│ • TodoWrite 목표 추적                                     │
│ • Subagent 격리 실행                                      │
│                                                           │
│ 역할: 표준 Self-Correction 패턴                           │
└──────────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│ Layer 1: LLM-Level (Prompt Engineering)                  │
│                                                           │
│ • "If you notice..., immediately fix it"                 │
│ • "That is unacceptable"                                 │
│ • Example-Driven Learning                                │
│                                                           │
│ 역할: LLM의 자기 수정 의지 부여                             │
└──────────────────────────────────────────────────────────┘
```

### 1.2 계층별 역할

**Layer 1 (LLM Prompt)**: "내가 실수하면 스스로 고쳐야 한다"는 **의지**
**Layer 2 (CLI Loop)**: 실수를 **감지하고 재시도**하는 **메커니즘**
**Layer 3 (SDK Hooks)**: 특정 실수를 **사전 차단**하거나 **강제 수정**하는 **정책**

**핵심**: 3계층이 함께 작동하여 **Multi-Layered Defense**를 구성합니다.

---

## 2. PreToolUse Hook - 사전 검증 게이트

### 2.1 목적

**PreToolUse Hook의 역할**:
- ❌ **사전 차단**: 위험한 도구 실행 방지
- 🔧 **입력 수정**: 안전한 형태로 변환
- ➕ **추가 컨텍스트**: LLM에게 힌트 제공

### 2.2 패턴 1: Bash 명령어 검증

**v1 방식 (코드 내부 구현)**:

```python
# v1_openai/tools.py
async def tool_bash(input_obj: BashInput) -> str:
    """Bash 명령어 실행"""
    command = input_obj.command

    # 하드코딩된 검증
    if "rm -rf /" in command:
        return "Error: Dangerous command blocked"

    # 실행
    result = subprocess.run(command, shell=True, capture_output=True)
    return result.stdout.decode()
```

**문제점**:
- 검증 로직이 도구 내부에 하드코딩
- 애플리케이션별 정책 적용 불가능
- 검증 실패해도 LLM이 이미 "실행하려고 시도"한 후

**SDK Hook 방식 (애플리케이션 레벨)**:

```python
async def bash_validator_hook(input_data, tool_use_id, context):
    """PreToolUse: Bash 명령어 사전 검증"""
    tool_name = input_data["tool_name"]
    tool_input = input_data["tool_input"]

    if tool_name != "Bash":
        return {}  # 다른 도구는 통과

    command = tool_input.get("command", "")

    # 애플리케이션별 정책
    dangerous_patterns = [
        "rm -rf /",
        "mkfs",
        "> /dev/sda",
        "dd if=/dev/zero",
    ]

    for pattern in dangerous_patterns:
        if pattern in command:
            logger.error(f"🚫 Blocked dangerous command: {command}")

            # 실행 차단 + LLM에게 피드백
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",  # ← 차단!
                    "permissionDecisionReason": f"Dangerous pattern: {pattern}",
                },
                "systemMessage": f"❌ Command blocked for safety: contains '{pattern}'",
            }

    return {}  # 안전하면 통과
```

**차이점**:

| 측면 | v1 코드 내부 | SDK Hook |
|-----|------------|----------|
| 정책 위치 | 도구 내부 (하드코딩) | 애플리케이션 (설정) |
| 유연성 | 낮음 (코드 수정 필요) | 높음 (Hook 교체) |
| LLM 피드백 | Tool Result (실행 후) | systemMessage (실행 전) |
| 시점 | 실행 중 감지 | **실행 전 차단** |

### 2.3 패턴 2: 입력 자동 수정

**시나리오**: LLM이 상대 경로를 사용했지만, 절대 경로가 필요한 경우

```python
async def path_normalizer_hook(input_data, tool_use_id, context):
    """PreToolUse: 파일 경로 자동 정규화"""
    tool_name = input_data["tool_name"]
    tool_input = input_data["tool_input"]

    if tool_name not in ["Read", "Write", "Edit"]:
        return {}

    file_path = tool_input.get("file_path", "")

    # 상대 경로 → 절대 경로 변환
    if not os.path.isabs(file_path):
        abs_path = os.path.abspath(file_path)
        logger.info(f"🔧 Normalized path: {file_path} → {abs_path}")

        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {  # ← 입력 수정!
                    "file_path": abs_path,
                    **{k: v for k, v in tool_input.items() if k != "file_path"}
                },
            },
            "systemMessage": f"📁 Using absolute path: {abs_path}",
        }

    return {}
```

**실행 흐름**:

```
1. LLM: "I'll read the config file"
   Tool Call: Read(file_path="./config.json")

2. CLI: PreToolUse 이벤트
   → SDK Hook: path_normalizer_hook()

3. Hook: file_path 변환
   "./config.json" → "/Users/jd/project/config.json"
   → updatedInput 반환

4. CLI: 수정된 입력으로 도구 실행
   → Read(file_path="/Users/jd/project/config.json")

5. Tool Result: "{ ... }"  # 성공!

6. LLM: "I successfully read the config"
```

**핵심**: LLM은 자신의 입력이 수정되었는지 **모름** (투명하게 수정됨)

### 2.4 패턴 3: 컨텍스트 자동 주입

**시나리오**: LLM이 파일을 읽을 때 보안 정보가 있는지 자동 확인

```python
async def security_hint_hook(input_data, tool_use_id, context):
    """PreToolUse: 보안 관련 힌트 자동 주입"""
    tool_name = input_data["tool_name"]
    tool_input = input_data["tool_input"]

    if tool_name != "Read":
        return {}

    file_path = tool_input.get("file_path", "")

    # 민감한 파일 패턴
    sensitive_patterns = [".env", "secret", "password", "key", "token"]

    if any(pattern in file_path.lower() for pattern in sensitive_patterns):
        return {
            "systemMessage": "⚠️ This file may contain sensitive information. "
                           "Do NOT expose secrets in responses.",
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "Remember: Never display API keys, "
                                   "passwords, or tokens in your responses.",
            }
        }

    return {}
```

**효과**:

```
1. LLM: "Let me read the .env file"
   Tool Call: Read(file_path=".env")

2. Hook: 민감한 파일 감지
   → systemMessage 주입

3. LLM sees:
   - systemMessage: "⚠️ This file may contain sensitive information..."
   - additionalContext: "Never display API keys..."

4. LLM: [.env 내용 읽음]
   "I found the configuration file. It contains database credentials "
   "and API keys (which I will not display for security)."
   # ← Hook이 LLM의 행동을 바꿨다!
```

---

## 3. PostToolUse Hook - 즉시 피드백 루프

### 3.1 목적

**PostToolUse Hook의 역할**:
- 🔍 **결과 검증**: 성공/실패 즉시 분석
- 💬 **추가 컨텍스트**: LLM에게 해석 힌트 제공
- 🛑 **즉시 중단**: Critical 에러 시 continue_=False

### 3.2 패턴 1: 에러 감지 및 중단

**v1 방식 (CLI 내부 처리)**:

```python
# v1_openai/main.py
async def execute_single_tool_call(tool_call):
    try:
        result = await execute_tool(tool_name, tool_input)
        return {"role": "tool", "content": result.result}
    except Exception as e:
        # 에러를 Tool Result로 반환 (LLM이 판단)
        return {"role": "tool", "content": f"Error: {e}"}
```

**LLM 판단**:
```
Tool Result: "Error: ECONNREFUSED - Database connection failed"

LLM: "The database connection failed. Let me retry with a different approach..."
# ← LLM이 계속 진행 (무한 재시도 가능)
```

**SDK Hook 방식 (애플리케이션 레벨 중단)**:

```python
async def critical_error_stopper(input_data, tool_use_id, context):
    """PostToolUse: Critical 에러 시 즉시 중단"""
    tool_response = input_data.get("tool_response", "")

    # Critical 에러 패턴
    critical_patterns = [
        "ECONNREFUSED",
        "PermissionError",
        "OutOfMemoryError",
        "FATAL",
    ]

    response_str = str(tool_response)

    for pattern in critical_patterns:
        if pattern in response_str:
            logger.error(f"🛑 Critical error detected: {pattern}")

            return {
                "continue_": False,  # ← 즉시 중단!
                "stopReason": f"Critical error detected: {pattern}",
                "systemMessage": f"🚨 Execution halted due to critical error: {pattern}",
            }

    return {"continue_": True}
```

**실행 흐름**:

```
1. LLM: "Let me connect to the database"
   Tool Call: Bash("psql -h localhost -U admin")

2. Tool Result: "psql: error: ECONNREFUSED - could not connect to server"

3. CLI: PostToolUse 이벤트
   → SDK Hook: critical_error_stopper()

4. Hook: "ECONNREFUSED" 감지
   → return {"continue_": False}  # 즉시 중단!

5. CLI: continue_=False 받음
   → Agent Loop 종료 (finish_reason 무시!)
   → ResultMessage 전송

6. SDK: ResultMessage 받음
   → 사용자에게 "Critical error - execution halted" 보고

# LLM의 다음 응답 없음 (강제 종료)
```

**핵심**: `continue_: False`는 **LLM의 판단을 무시**하고 강제 종료합니다.

### 3.3 패턴 2: 자동 재시도 트리거

**시나리오**: 일시적 에러 시 LLM에게 재시도 힌트 제공

```python
async def retry_hint_hook(input_data, tool_use_id, context):
    """PostToolUse: 재시도 가능한 에러 감지 및 힌트"""
    tool_name = input_data["tool_name"]
    tool_response = input_data.get("tool_response", "")

    # 재시도 가능한 에러 패턴
    retryable_patterns = {
        "ETIMEDOUT": "Network timeout - try again",
        "EBUSY": "Resource busy - wait and retry",
        "429": "Rate limit - wait 5 seconds and retry",
    }

    response_str = str(tool_response)

    for pattern, hint in retryable_patterns.items():
        if pattern in response_str:
            logger.warning(f"⚠️ Retryable error: {pattern}")

            return {
                "continue_": True,  # 계속 진행
                "systemMessage": f"💡 {hint}",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": f"This is a temporary error. {hint}. "
                                       "Consider implementing exponential backoff.",
                }
            }

    return {}
```

**효과**:

```
1. Tool Result: "Error: ETIMEDOUT - request timed out"

2. Hook: ETIMEDOUT 감지
   → systemMessage: "💡 Network timeout - try again"
   → additionalContext: "This is a temporary error. Consider exponential backoff."

3. LLM sees:
   - Tool Result: "Error: ETIMEDOUT..."
   - systemMessage: "💡 Network timeout - try again"
   - additionalContext: "This is a temporary error..."

4. LLM: "I see a network timeout. Let me wait a moment and retry..."
   # ← Hook의 힌트가 LLM의 판단을 개선했다!
```

### 3.4 패턴 3: 결과 변환 및 강화

**시나리오**: 도구 결과가 불완전할 때 자동으로 보완

```python
async def result_enhancer_hook(input_data, tool_use_id, context):
    """PostToolUse: 도구 결과 자동 강화"""
    tool_name = input_data["tool_name"]
    tool_response = input_data.get("tool_response", "")

    if tool_name == "Bash" and "npm run build" in tool_input.get("command", ""):
        # 빌드 결과 분석
        if "error" in tool_response.lower():
            # 에러 개수 세기
            error_count = tool_response.count("error:")

            return {
                "systemMessage": f"⚠️ Build failed with {error_count} errors",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": f"Found {error_count} errors. "
                                       "Read the error messages carefully and fix one at a time.",
                }
            }
        else:
            return {
                "systemMessage": "✅ Build succeeded!",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": "Build completed successfully. "
                                       "You can now proceed to the next step.",
                }
            }

    return {}
```

---

## 4. UserPromptSubmit Hook - 컨텍스트 자동 주입

### 4.1 목적

**UserPromptSubmit Hook의 역할**:
- ➕ **컨텍스트 주입**: 사용자 입력에 자동으로 추가 정보 제공
- 🔧 **입력 전처리**: 사용자 입력 정규화
- 📝 **로깅**: 모든 사용자 요청 기록

### 4.2 패턴 1: 프로젝트 컨텍스트 자동 로드

```python
async def project_context_injector(input_data, tool_use_id, context):
    """UserPromptSubmit: 프로젝트 정보 자동 주입"""

    # 프로젝트 메타데이터 로드
    project_info = await load_project_metadata()

    additional_context = f"""
    Project Context:
    - Name: {project_info['name']}
    - Language: {project_info['language']}
    - Framework: {project_info['framework']}
    - Style Guide: {project_info['style_guide_url']}
    - Testing Framework: {project_info['test_framework']}

    When writing code, follow the project's style guide and use the testing framework.
    """

    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        }
    }
```

**효과**:

```
User: "Add a new API endpoint for user registration"

Hook: project_info 주입
  → additionalContext: "Framework: Express.js, Testing: Jest..."

LLM sees:
  - User: "Add a new API endpoint..."
  - Additional Context: "Framework: Express.js, Testing: Jest..."

LLM: "I'll create an Express.js endpoint with Jest tests, following the project style guide..."
  # ← 프로젝트 컨텍스트가 자동으로 제공됨!
```

### 4.3 패턴 2: 사용자 선호도 자동 적용

```python
async def user_preferences_hook(input_data, tool_use_id, context):
    """UserPromptSubmit: 사용자 선호도 자동 적용"""

    # 사용자 설정 로드
    user_prefs = await load_user_preferences()

    prefs_context = f"""
    User Preferences:
    - Preferred Language: {user_prefs.get('language', 'TypeScript')}
    - Code Style: {user_prefs.get('style', 'functional')}
    - Comment Level: {user_prefs.get('comments', 'detailed')}
    - Testing: {user_prefs.get('testing', 'enabled')}

    Apply these preferences when generating code.
    """

    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": prefs_context,
        }
    }
```

**효과**: 사용자가 매번 "TypeScript로", "함수형으로" 등을 명시하지 않아도 자동 적용

---

## 5. Hook Chaining - 다층 검증

### 5.1 여러 Hook의 조합

```python
options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [
            # Hook 1: 보안 검증
            HookMatcher(matcher="Bash", hooks=[bash_security_validator]),

            # Hook 2: 경로 정규화
            HookMatcher(matcher="Read", hooks=[path_normalizer]),
            HookMatcher(matcher="Write", hooks=[path_normalizer]),

            # Hook 3: 로깅 (모든 도구)
            HookMatcher(matcher=None, hooks=[tool_usage_logger]),
        ],

        "PostToolUse": [
            # Hook 1: Critical 에러 중단
            HookMatcher(matcher=None, hooks=[critical_error_stopper]),

            # Hook 2: 재시도 힌트
            HookMatcher(matcher=None, hooks=[retry_hint_provider]),

            # Hook 3: 결과 강화
            HookMatcher(matcher="Bash", hooks=[build_result_enhancer]),
        ],

        "UserPromptSubmit": [
            # Hook 1: 프로젝트 컨텍스트
            HookMatcher(matcher=None, hooks=[project_context_injector]),

            # Hook 2: 사용자 선호도
            HookMatcher(matcher=None, hooks=[user_preferences_applier]),
        ],
    }
)
```

### 5.2 실행 순서

**PreToolUse Hooks**:
```
1. bash_security_validator (Bash만)
   ↓ (통과)
2. tool_usage_logger (모든 도구)
   ↓ (로그 기록)
3. 도구 실행
```

**PostToolUse Hooks**:
```
1. 도구 실행 완료
   ↓
2. critical_error_stopper (모든 도구)
   ↓ (continue_=True)
3. retry_hint_provider (모든 도구)
   ↓ (힌트 추가)
4. build_result_enhancer (Bash만)
   ↓
5. LLM에게 결과 전달
```

**핵심**: Hook은 **순차적으로 실행**되며, **각 Hook의 결과가 누적**됩니다.

---

## 6. 실전 예제: Self-Correcting CI/CD Bot

### 6.1 시나리오

**요구사항**:
1. 코드 변경 시 자동으로 빌드 및 테스트
2. 빌드 실패 시 자동으로 에러 분석 및 수정
3. 테스트 실패 시 최대 3번 재시도
4. Critical 에러 시 즉시 중단 및 알림

### 6.2 Hook 구현

```python
#!/usr/bin/env python3
"""Self-Correcting CI/CD Bot with SDK Hooks"""

import anyio
import logging
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    AssistantMessage,
    TextBlock,
)

logger = logging.getLogger(__name__)

# Global state (실전에서는 Redis 등 사용)
retry_counts = {}

# Hook 1: Build 명령어 검증
async def build_validator_hook(input_data, tool_use_id, context):
    """PreToolUse: 빌드 명령어만 허용"""
    tool_name = input_data["tool_name"]
    tool_input = input_data["tool_input"]

    if tool_name != "Bash":
        return {}

    command = tool_input.get("command", "")

    # 허용된 빌드 명령어
    allowed_commands = [
        "npm run build",
        "npm test",
        "npm run lint",
        "git status",
        "git diff",
    ]

    if not any(cmd in command for cmd in allowed_commands):
        logger.warning(f"❌ Blocked non-build command: {command}")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Only build/test commands allowed in CI/CD mode",
            },
            "systemMessage": "🚫 Only build and test commands are allowed",
        }

    return {}

# Hook 2: Build 결과 분석 및 재시도 제어
async def build_result_analyzer(input_data, tool_use_id, context):
    """PostToolUse: 빌드 결과 분석 및 재시도 제어"""
    tool_name = input_data["tool_name"]
    tool_input = input_data.get("tool_input", {})
    tool_response = input_data.get("tool_response", "")

    if tool_name != "Bash":
        return {}

    command = tool_input.get("command", "")

    # Build 명령어인지 확인
    if "npm run build" not in command and "npm test" not in command:
        return {}

    response_str = str(tool_response)

    # Critical 에러 체크
    critical_patterns = ["FATAL", "OutOfMemoryError", "ENOSPC"]
    for pattern in critical_patterns:
        if pattern in response_str:
            logger.error(f"🛑 Critical build error: {pattern}")
            return {
                "continue_": False,
                "stopReason": f"Critical CI/CD error: {pattern}",
                "systemMessage": f"🚨 Build halted - critical error: {pattern}",
            }

    # Build 성공
    if "error" not in response_str.lower():
        logger.info("✅ Build/test succeeded")
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
        logger.error(f"❌ Max retries ({max_retries}) exceeded")
        return {
            "continue_": False,
            "stopReason": f"Build failed after {max_retries} attempts",
            "systemMessage": f"❌ Build failed after {max_retries} retries - manual intervention needed",
        }

    # 재시도 카운터 증가
    retry_counts[tool_use_id] = retry_count + 1

    # 에러 분석
    error_lines = [line for line in response_str.split('\n') if 'error' in line.lower()]
    error_count = len(error_lines)

    logger.warning(f"⚠️ Build failed (attempt {retry_count + 1}/{max_retries})")

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

Remember: You have {max_retries - retry_count - 1} attempts remaining.
            """,
        }
    }

# Hook 3: 프로젝트 컨텍스트 자동 주입
async def ci_context_injector(input_data, tool_use_id, context):
    """UserPromptSubmit: CI/CD 컨텍스트 주입"""
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": """
CI/CD Mode Active:
- You are operating in continuous integration mode
- Only build and test commands are allowed
- Build failures will trigger automatic analysis and retry (max 3 attempts)
- Critical errors will halt execution immediately
- Your goal: Fix all build/test errors to achieve a successful build
            """,
        }
    }

# Hook 4: 파일 수정 추적
file_modifications = []

async def track_file_changes(input_data, tool_use_id, context):
    """PostToolUse: 파일 수정 추적"""
    tool_name = input_data["tool_name"]
    tool_input = input_data.get("tool_input", {})

    if tool_name in ["Write", "Edit"]:
        file_path = tool_input.get("file_path", "unknown")
        file_modifications.append({
            "file": file_path,
            "tool": tool_name,
            "timestamp": datetime.now().isoformat(),
        })
        logger.info(f"📝 File modified: {file_path}")

    return {}

# 메인 워크플로우
async def ci_cd_workflow():
    """Self-Correcting CI/CD 워크플로우"""

    options = ClaudeAgentOptions(
        # 도구 제한 (CI/CD에 필요한 것만)
        allowed_tools=["Read", "Edit", "Bash", "Grep", "Glob"],

        # Hooks
        hooks={
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[build_validator_hook]),
            ],
            "PostToolUse": [
                HookMatcher(matcher="Bash", hooks=[build_result_analyzer]),
                HookMatcher(matcher="Write", hooks=[track_file_changes]),
                HookMatcher(matcher="Edit", hooks=[track_file_changes]),
            ],
            "UserPromptSubmit": [
                HookMatcher(matcher=None, hooks=[ci_context_injector]),
            ],
        },

        # 시스템 프롬프트
        system_prompt="""You are a CI/CD automation assistant.
Your goal is to ensure all builds and tests pass.

When you encounter build errors:
1. Read the error messages carefully
2. Identify the root cause
3. Fix the code
4. Re-run the build to verify

You have a maximum of 3 retry attempts per build.
        """,

        # 비용 제한
        max_budget_usd=1.0,
    )

    async with ClaudeSDKClient(options=options) as client:
        print("🤖 CI/CD Bot started\n")

        await client.query("""
Run the build and fix any errors that occur.
Keep trying until the build succeeds or you reach the retry limit.
        """)

        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(f"Bot: {block.text}\n")

            elif isinstance(msg, ResultMessage):
                print("\n" + "="*60)
                print("CI/CD Workflow Complete")
                print("="*60)
                print(f"Total cost: ${msg.total_cost_usd:.4f}")
                print(f"Files modified: {len(file_modifications)}")
                for mod in file_modifications:
                    print(f"  - {mod['file']} ({mod['tool']})")

async def main():
    logging.basicConfig(level=logging.INFO)
    await ci_cd_workflow()

if __name__ == "__main__":
    anyio.run(main)
```

### 6.3 실행 시나리오

**성공 케이스**:

```
1. User: "Run the build and fix any errors"

2. CI Context Hook: CI/CD 모드 설명 주입

3. LLM: "I'll run the build first"
   Tool: Bash("npm run build")

4. Build Validator Hook: 허용된 명령어 → 통과

5. Tool Result: "Error: Type error in src/index.ts:42"

6. Build Result Analyzer Hook:
   - 에러 감지
   - retry_count = 0 (첫 시도)
   - additionalContext: "Build failed. Attempt 1/3. Please fix..."

7. LLM: "I see a type error. Let me read the file"
   Tool: Read("src/index.ts")

8. LLM: "Found the issue at line 42. Let me fix it"
   Tool: Edit("src/index.ts", old="const x: number = 'hello'", new="const x: string = 'hello'")

9. Track File Changes Hook: file_modifications 업데이트

10. LLM: "Let me rebuild to verify"
    Tool: Bash("npm run build")

11. Tool Result: "Build successful"

12. Build Result Analyzer Hook:
    - 성공 감지
    - retry_count 리셋
    - systemMessage: "✅ Build/test succeeded!"

13. LLM: "Build succeeded! All errors fixed."
    finish_reason: "stop"
```

**실패 케이스 (Max Retries)**:

```
1-5. [같음]

6. Build Result Analyzer: retry_count = 0 → 1

7-10. [첫 수정 시도]

11. Tool Result: "Error: Still has type errors"

12. Build Result Analyzer: retry_count = 1 → 2

13-16. [두 번째 수정 시도]

17. Tool Result: "Error: Different error now"

18. Build Result Analyzer: retry_count = 2 → 3

19-22. [세 번째 수정 시도]

23. Tool Result: "Error: Still failing"

24. Build Result Analyzer:
    - retry_count = 3 (max)
    - return {"continue_": False}  # 중단!

25. CLI: Agent Loop 강제 종료

26. User notification: "❌ Build failed after 3 retries - manual intervention needed"
```

**Critical Error 케이스**:

```
1-4. [같음]

5. Tool Result: "FATAL: Out of memory"

6. Build Result Analyzer:
   - "FATAL" 감지
   - return {"continue_": False, "stopReason": "Critical CI/CD error: FATAL"}

7. CLI: 즉시 중단 (retry 무시)

8. User notification: "🚨 Build halted - critical error: FATAL"
```

---

## 7. 핵심 인사이트

### 7.1 Hook의 진정한 가치

**Hook ≠ 단순 이벤트 리스너**
**Hook = Self-Correction Loop의 제어권**

```
Without Hooks (v1/v2):
  LLM → Tool → Result → LLM → Decision
  (LLM이 모든 결정)

With Hooks (SDK):
  LLM → [PreHook] → Tool → [PostHook] → Result → LLM → Decision
         ↑ 차단 가능            ↑ 중단 가능
  (애플리케이션이 개입 가능)
```

### 7.2 3계층 Self-Correction 비교

| 계층 | v1/v2 구현 | SDK Hook 구현 | 장점 |
|-----|----------|--------------|-----|
| **사전 검증** | 도구 내부 if문 | PreToolUse Hook | 정책 외부화 |
| **에러 감지** | Tool Result | PostToolUse Hook | 즉시 개입 |
| **강제 중단** | max_turns 도달 | continue_=False | 정확한 중단 |
| **컨텍스트 주입** | System Prompt | UserPromptSubmit Hook | 동적 변경 |

### 7.3 When to Use Hooks

**Hook을 사용해야 할 때**:
- ✅ 애플리케이션별 보안 정책 (Bash 명령어 제한 등)
- ✅ 특정 에러에 대한 즉시 대응 (Critical 에러 중단)
- ✅ 재시도 로직 구현 (최대 N번 재시도)
- ✅ 도메인별 컨텍스트 주입 (프로젝트 정보 등)
- ✅ 감사(Auditing) 및 로깅

**Hook이 불필요한 경우**:
- ❌ 단순 1회성 질문-응답
- ❌ LLM이 자체적으로 처리 가능한 에러
- ❌ 표준 사용 사례 (빌드 → 수정 → 재빌드)

### 7.4 v2.2 Hooks vs SDK Hooks

**v2.2 Hooks**:
```python
# v2_2_langgraph_hooks/hooks.py
class PreToolUseHook:
    """LangGraph 노드로 구현"""
    async def execute(self, state):
        if state["tool_name"] == "Bash":
            if "rm -rf" in state["tool_input"]["command"]:
                return {"permission": "deny"}
        return {"permission": "allow"}
```

**특징**:
- StateGraph 노드로 통합
- 상태 기반 (state 객체)
- 동기적 실행 (그래프 플로우의 일부)

**SDK Hooks**:
```python
# SDK Hook
async def bash_validator(input_data, tool_use_id, context):
    """독립 함수로 구현"""
    if input_data["tool_name"] == "Bash":
        if "rm -rf" in input_data["tool_input"]["command"]:
            return {
                "hookSpecificOutput": {
                    "permissionDecision": "deny"
                }
            }
    return {}
```

**특징**:
- 독립 함수 (CLI와 분리)
- 입력 기반 (input_data dict)
- 비동기 실행 (Control Protocol)

**비교**:

| 측면 | v2.2 Hooks | SDK Hooks |
|-----|-----------|----------|
| 위치 | 그래프 노드 (내부) | Python 함수 (외부) |
| 실행 | 동기 (그래프) | 비동기 (프로토콜) |
| 상태 | StateGraph state | 입력 데이터만 |
| 재사용 | 그래프별 | 프로젝트 간 |
| 디버깅 | 그래프 시각화 | 일반 함수 |

---

## 8. 결론

### 8.1 Self-Improvement의 완성형

**AI Agent의 Self-Improvement = LLM 능력 + Agent Loop + Hooks**

```
┌─────────────────────────────────────────────────────────┐
│ LLM (Claude Sonnet 4.5)                                 │
│ • 코드 이해 능력                                          │
│ • 에러 분석 능력                                          │
│ • 해결책 생성 능력                                        │
└─────────────────────────────────────────────────────────┘
                         +
┌─────────────────────────────────────────────────────────┐
│ Agent Loop (CLI)                                        │
│ • finish_reason 제어                                     │
│ • Tool Result 피드백                                     │
│ • TodoWrite 목표 추적                                    │
│ • Subagent 격리                                         │
└─────────────────────────────────────────────────────────┘
                         +
┌─────────────────────────────────────────────────────────┐
│ Hooks (SDK)                                             │
│ • PreToolUse: 사전 차단                                  │
│ • PostToolUse: 즉시 중단                                 │
│ • UserPromptSubmit: 컨텍스트 주입                        │
│ • continue_: 강제 제어                                   │
└─────────────────────────────────────────────────────────┘
                         =
┌─────────────────────────────────────────────────────────┐
│ Perfect Self-Correcting Agent                           │
│                                                          │
│ • 지능적 판단 (LLM)                                       │
│ • 자동 재시도 (Loop)                                      │
│ • 정책 준수 (Hooks)                                       │
│ • 안전 보장 (Hooks)                                       │
└─────────────────────────────────────────────────────────┘
```

### 8.2 최종 설계 가이드

**Production Agent를 만들 때**:

1. **v1/v2로 프로토타입** - Agent Loop 이해
2. **SDK로 리팩터링** - 안정성 확보
3. **Hooks 추가** - 도메인별 정책 적용
4. **모니터링 강화** - 모든 Hook에 로깅

**Hook 설계 원칙**:

1. **Single Responsibility** - 하나의 Hook은 하나의 책임
2. **Fail-Safe** - Hook 실패 시에도 Agent는 계속 작동
3. **Observable** - 모든 Hook 결정은 로그로 기록
4. **Testable** - Hook은 독립 함수이므로 단위 테스트 가능

### 8.3 미래 전망

**Hook System의 진화 방향**:

```
Current (2025):
  - 6개 Hook Events
  - Python 함수로 구현
  - 수동 등록

Future (예상):
  - ML-based Hook (Hook 자체가 LLM)
  - Visual Hook Builder (No-Code)
  - Hook Marketplace (재사용 가능한 Hook 공유)
  - Auto-Learning Hooks (실행 패턴 학습)
```

**예시: ML-based Hook (미래)**:

```python
# 미래의 Hook?
@ml_hook("error_classifier")
async def smart_error_handler(input_data, tool_use_id, context):
    """ML 모델이 에러를 분류하고 자동으로 대응"""
    error_response = input_data["tool_response"]

    # ML 모델로 에러 분류
    error_type = await ml_model.classify_error(error_response)

    if error_type == "critical":
        return {"continue_": False}
    elif error_type == "retryable":
        return {"systemMessage": "Retry recommended"}
    elif error_type == "fixable":
        # ML 모델이 수정 힌트 생성
        fix_hint = await ml_model.suggest_fix(error_response)
        return {"additionalContext": fix_hint}
    else:
        return {}
```

---

**작성자**: Claude (Sonnet 4.5)
**분석 대상**: Claude Agent SDK Hooks + Self-Improvement Architecture
**목적**: SDK Hook을 활용한 Production-Ready Self-Correcting Agent 구현 가이드
**문서 버전**: 1.0 (2025-11-20)
