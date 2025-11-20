# Hook System과 Permission System 분석

> **핵심 발견**: Validation Agent와 File Extraction Agent는 Claude Code 내부에서 **Hook System**을 활용하여 구현된 것으로 추정됩니다.

---

## 🎣 Hook System 개요

Python Agent SDK 레퍼런스에서 발견한 Hook System:

### Hook Event 타입 (6가지)

```python
HookEvent = Literal[
    "PreToolUse",      # 도구 실행 전
    "PostToolUse",     # 도구 실행 후
    "UserPromptSubmit", # 사용자 프롬프트 제출 시
    "Stop",            # 실행 중지 시
    "SubagentStop",    # Subagent 중지 시
    "PreCompact"       # 메시지 압축 전
]
```

### Hook Callback 구조

```python
async def hook_callback(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext
) -> dict[str, Any]:
    """
    Returns:
        {
            "decision": "block",  # 선택적: 작업 차단
            "systemMessage": "...",  # 선택적: 시스템 메시지 추가
            "hookSpecificOutput": {...}  # Hook별 특수 출력
        }
    """
```

---

## 🔗 Validation Agent ↔ Hook System 연결

### 가설: Validation Agent는 PreToolUse Hook의 구현체

우리가 reference JSON에서 발견한 Validation Agent:

```json
{
  "timestamp": "2025-11-19T18:01:47.608Z",
  "system": [
    {
      "type": "text",
      "text": "You are a Claude agent, built on Anthropic's Claude Agent SDK."
    },
    {
      "type": "text",
      "text": "Your task is to process Bash commands..."
    }
  ],
  "messages": [
    {
      "role": "user",
      "content": [{"type": "text", "text": "<policy_spec>...</policy_spec>\n\nCommand: npm run build"}]
    }
  ],
  "tools": []
}
```

**작동 방식 (추정)**:

```
1. Main Agent: Bash("npm run build") 시도
   ↓
2. Claude Code: PreToolUse hook 트리거
   ↓
3. Hook Handler (내부 구현):
   - 별도 LLM 호출 생성 (Validation Agent)
   - system[1] = "Command prefix detection policy"
   - messages = [{"role": "user", "content": "Command: npm run build"}]
   - tools = []
   ↓
4. Validation Agent 응답: "none"
   ↓
5. Hook Handler:
   - "none"과 allowlist 비교
   - allowlist에 있으면: {"behavior": "allow"}
   - 없으면: {"behavior": "deny", "message": "승인 필요"}
   ↓
6. Main Agent: Hook 결과에 따라 실행 또는 차단
```

### PreToolUse Hook 예시 (사용자 커스터마이징)

```python
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

async def validate_bash_command(input_data, tool_use_id, context):
    """사용자 정의 Bash 검증"""
    if input_data['tool_name'] == 'Bash':
        command = input_data['tool_input'].get('command', '')

        # 위험한 명령어 차단
        if 'rm -rf /' in command:
            return {
                'hookSpecificOutput': {
                    'hookEventName': 'PreToolUse',
                    'permissionDecision': 'deny',
                    'permissionDecisionReason': 'Dangerous command blocked'
                }
            }
    return {}

options = ClaudeAgentOptions(
    hooks={
        'PreToolUse': [
            HookMatcher(matcher='Bash', hooks=[validate_bash_command])
        ]
    }
)
```

**Claude Code 내부 구현 (추정)**:

```python
# Claude Code 내부 코드 (추정)
async def internal_bash_validation_hook(input_data, tool_use_id, context):
    """Claude Code가 내부적으로 사용하는 PreToolUse hook"""
    if input_data['tool_name'] == 'Bash':
        command = input_data['tool_input'].get('command', '')

        # 별도 LLM 호출로 검증 (Validation Agent)
        validation_result = await call_validation_agent(command)

        # Prefix 추출
        prefix = validation_result.strip()

        # Allowlist 확인
        if prefix == "command_injection_detected":
            return {
                'hookSpecificOutput': {
                    'hookEventName': 'PreToolUse',
                    'permissionDecision': 'deny',
                    'permissionDecisionReason': 'Command injection detected'
                }
            }

        # User's allowlist와 비교
        if not is_prefix_allowed(prefix):
            return {
                'hookSpecificOutput': {
                    'hookEventName': 'PreToolUse',
                    'permissionDecision': 'ask',  # 사용자 승인 요청
                    'permissionDecisionReason': f'Command prefix "{prefix}" requires approval'
                }
            }

    return {}  # 허용
```

---

## 🔗 File Extraction Agent ↔ Hook System 연결

### 가설: File Extraction Agent는 PostToolUse Hook의 구현체

우리가 reference JSON에서 발견한 File Extraction Agent:

```json
{
  "timestamp": "2025-11-19T17:57:06.513Z",
  "system": [
    {
      "type": "text",
      "text": "Extract any file paths that this command reads or modifies..."
    }
  ],
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Command: ls -la /path\nOutput: total 752\ndrwxr-xr-x ..."
        }
      ]
    }
  ],
  "tools": []
}
```

**작동 방식 (추정)**:

```
1. Main Agent: Bash("ls -la") 실행 완료
   ↓
2. Tool Result 반환: "total 752\ndrwxr-xr-x ..."
   ↓
3. Claude Code: PostToolUse hook 트리거
   ↓
4. Hook Handler (내부 구현):
   - 별도 LLM 호출 생성 (File Extraction Agent)
   - system[1] = "Extract file paths from command output"
   - messages = [{"role": "user", "content": "Command: ls -la\nOutput: ..."}]
   - tools = []
   - temperature = 1 (창의적 추출)
   ↓
5. File Extraction Agent 응답:
   <is_displaying_contents>false</is_displaying_contents>
   <filepaths></filepaths>
   ↓
6. Hook Handler:
   - 파일 경로 파싱
   - is_displaying_contents=true이면 자동으로 파일 읽기
   - Main Agent의 컨텍스트에 파일 추가
   ↓
7. Main Agent: 추가된 컨텍스트로 계속 진행
```

### PostToolUse Hook 예시 (사용자 커스터마이징)

```python
async def log_tool_results(input_data, tool_use_id, context):
    """도구 실행 결과 로깅"""
    tool_name = input_data.get('tool_name', 'unknown')
    tool_result = input_data.get('tool_result', {})

    print(f"[POST-TOOL] {tool_name} completed")
    print(f"  Output length: {len(str(tool_result))}")

    return {}

options = ClaudeAgentOptions(
    hooks={
        'PostToolUse': [
            HookMatcher(hooks=[log_tool_results])
        ]
    }
)
```

**Claude Code 내부 구현 (추정)**:

```python
# Claude Code 내부 코드 (추정)
async def internal_file_extraction_hook(input_data, tool_use_id, context):
    """Claude Code가 내부적으로 사용하는 PostToolUse hook"""
    tool_name = input_data['tool_name']

    # Bash 명령어 결과에서만 파일 경로 추출
    if tool_name == 'Bash':
        command = input_data['tool_input'].get('command', '')
        output = input_data['tool_result'].get('output', '')

        # 별도 LLM 호출로 파일 경로 추출 (File Extraction Agent)
        extraction_result = await call_file_extraction_agent(command, output)

        # XML 파싱
        is_displaying = parse_bool(extraction_result, 'is_displaying_contents')
        file_paths = parse_list(extraction_result, 'filepaths')

        # 파일 경로가 있고, 컨텐츠를 표시하는 경우
        if is_displaying and file_paths:
            # 자동으로 파일 읽기 (Read 도구 사용)
            for path in file_paths:
                await auto_read_file(path)
                # Main Agent의 컨텍스트에 추가

    return {}
```

---

## 🛡️ Permission System (can_use_tool)

### can_use_tool 콜백

```python
async def custom_permission_handler(
    tool_name: str,
    input_data: dict,
    context: dict
):
    """
    Returns:
        {
            "behavior": "allow" | "deny" | "ask",
            "message": "이유",  # deny 시
            "interrupt": True,  # 중단 신호
            "updatedInput": {...}  # 입력 수정
        }
    """
```

### 사용 예시

```python
async def safe_file_operations(tool_name, input_data, context):
    """파일 작업 안전 제어"""

    # 시스템 디렉토리 쓰기 차단
    if tool_name == "Write" and input_data.get("file_path", "").startswith("/system/"):
        return {
            "behavior": "deny",
            "message": "System directory write not allowed",
            "interrupt": True
        }

    # config 파일은 sandbox로 리다이렉션
    if tool_name in ["Write", "Edit"] and "config" in input_data.get("file_path", ""):
        safe_path = f"./sandbox/{input_data['file_path']}"
        return {
            "behavior": "allow",
            "updatedInput": {**input_data, "file_path": safe_path}
        }

    return {"behavior": "allow"}

options = ClaudeAgentOptions(
    can_use_tool=safe_file_operations
)
```

### Validation Agent와의 관계

**가설**: `can_use_tool`은 Hook System의 상위 추상화

```
1. PreToolUse Hook 트리거
   ↓
2. can_use_tool 콜백 실행 (사용자 정의)
   ↓
3. 내부 validation hooks 실행 (Validation Agent 호출)
   ↓
4. 모든 결과 종합하여 최종 결정
```

즉:
- `can_use_tool`: 사용자가 쉽게 사용할 수 있는 고수준 API
- `PreToolUse` hook: 더 세밀한 제어 (Claude Code 내부에서도 사용)
- Validation Agent: Hook 내부에서 호출되는 별도 LLM (보안 검증)

---

## 📝 System Prompt Preset

### claude_code Preset

```python
options = ClaudeAgentOptions(
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": "추가 지침..."  # 선택적
    }
)
```

**발견**:
- 우리가 본 ~17,000 chars의 system prompt가 바로 이 `claude_code` preset!
- `append`로 추가 지침을 붙일 수 있음

**Preset 내용 (추정)**:
```
system[1] = CLAUDE_CODE_PRESET + (append_text if provided)

CLAUDE_CODE_PRESET:
  • Task Management 지침 (~3,000 tokens)
  • 16개 도구 설명 및 사용법 (~14,000 tokens)
  • Git/PR 워크플로우
  • Code References 포맷
  • Output Style (Explanatory, Concise 등)
  • Professional objectivity
  • Error handling patterns
```

---

## 📂 Setting Sources (CLAUDE.md 로드)

### Setting Source 타입

```python
SettingSource = Literal["user", "project", "local"]
```

| Source    | 위치                         | 용도                    |
|-----------|------------------------------|-----------------------|
| `"user"`  | `~/.claude/settings.json`    | 전역 사용자 설정       |
| `"project"` | `.claude/settings.json`     | 프로젝트 설정 (CLAUDE.md 포함!) |
| `"local"` | `.claude/settings.local.json` | 로컬 설정 (gitignored) |

### CLAUDE.md 로드 방식

**중요 발견**: `setting_sources=["project"]` 사용 시 CLAUDE.md 파일이 자동으로 로드됩니다!

```python
options = ClaudeAgentOptions(
    system_prompt={
        "type": "preset",
        "preset": "claude_code"  # Claude Code system prompt 사용
    },
    setting_sources=["project"],  # CLAUDE.md 로드를 위해 필수!
    allowed_tools=["Read", "Write", "Edit"]
)
```

**작동 방식**:
```
1. setting_sources=["project"] 설정
   ↓
2. Claude Code CLI가 .claude/settings.json 및 CLAUDE.md 읽기
   ↓
3. CLAUDE.md 내용을 system prompt에 추가:
   "<system-reminder>
   As you answer the user's questions, you can use the following context:
   # claudeMd
   Codebase and user instructions are shown below...

   Contents of /path/to/CLAUDE.md:
   [CLAUDE.md의 내용]
   </system-reminder>"
   ↓
4. Main Agent가 CLAUDE.md의 지침을 따라 작업 수행
```

우리가 본 reference JSON 파일에서:
```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "<system-reminder>\nAs you answer the user's questions...\n# claudeMd\n\nContents of /Users/jd/Documents/workspace/claude-code-router/CLAUDE.md:\n\n# CLAUDE.md\n..."
        }
      ]
    }
  ]
}
```

→ 이것이 바로 `setting_sources=["project"]`의 결과!

---

## 🔄 PreCompact Hook (메시지 압축)

### PreCompact Hook

```python
HookEvent = Literal[
    # ...
    "PreCompact"  # 메시지 압축 전 호출
]
```

**용도**:
- v2에서 구현한 `compact_messages()` 로직과 관련
- 메시지 압축 전 커스터마이징 가능
- 예: 특정 메시지 보존, 압축 전 백업 등

**예시**:
```python
async def before_compact(input_data, tool_use_id, context):
    """메시지 압축 전 처리"""
    messages = input_data.get('messages', [])

    # 중요한 메시지 마킹 (압축 시 보존)
    important_keywords = ['error', 'warning', 'critical']
    for msg in messages:
        content = str(msg.get('content', ''))
        if any(keyword in content.lower() for keyword in important_keywords):
            msg['preserve'] = True  # 압축 시 보존 요청

    return {
        'hookSpecificOutput': {
            'hookEventName': 'PreCompact',
            'updatedMessages': messages
        }
    }

options = ClaudeAgentOptions(
    hooks={
        'PreCompact': [
            HookMatcher(hooks=[before_compact])
        ]
    }
)
```

---

## 💡 종합 분석: Claude Code의 Hook 기반 아키텍처

### 전체 흐름

```
┌─────────────────────────────────────────────────────────┐
│                     User Request                        │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  UserPromptSubmit Hook                                  │
│  • CLAUDE.md 컨텍스트 주입                              │
│  • 타임스탬프 추가 등                                   │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│                  Main Agent (LLM)                       │
│  • claude_code preset system prompt                     │
│  • CLAUDE.md 컨텍스트                                   │
│  • 도구 선택 및 실행 계획                               │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  PreToolUse Hook                                        │
│  ├─ can_use_tool 콜백 (사용자 정의)                     │
│  ├─ Validation Agent (내부 구현)                       │
│  │   • Bash 명령어 검증                                │
│  │   • Command injection 탐지                          │
│  └─ Allowlist 확인                                      │
│                                                         │
│  Result: allow | deny | ask                            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│              Tool Execution (허용 시)                    │
│  • Bash, Read, Write, Edit, etc.                       │
│  • Tool Result 반환                                     │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  PostToolUse Hook                                       │
│  ├─ File Extraction Agent (내부 구현)                   │
│  │   • Bash 출력에서 파일 경로 추출                     │
│  │   • is_displaying_contents 판단                     │
│  └─ 자동 파일 읽기 (필요 시)                            │
│                                                         │
│  Result: 추가 컨텍스트 주입                             │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│           Main Agent continues...                       │
│  • 도구 결과 + 추가 컨텍스트로 다음 단계 결정           │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
        (100k 토큰 도달 시)
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  PreCompact Hook                                        │
│  • 메시지 압축 전 커스터마이징                          │
│  • 중요 메시지 보존 등                                  │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│            Message Compaction                           │
│  • Claude Haiku + Extended Thinking                     │
│  • 대화 요약 및 압축                                    │
└─────────────────────────────────────────────────────────┘
```

### 핵심 통찰

1. **Hook System = 확장 포인트**
   - Claude Code의 핵심 동작을 Hook을 통해 확장
   - 사용자 정의 Hook과 내부 Hook이 공존

2. **Validation/File Extraction = 내부 Hook 구현**
   - PreToolUse hook에서 Validation Agent 호출
   - PostToolUse hook에서 File Extraction Agent 호출
   - 별도 LLM 호출로 구현 (Stateless)

3. **Permission System = Hook의 고수준 추상화**
   - `can_use_tool`: 사용자 친화적 API
   - Hook: 더 세밀한 제어
   - 둘 다 사용 가능

4. **System Prompt Preset = 재사용 가능한 프롬프트**
   - `claude_code` preset이 표준 system prompt
   - `append`로 커스터마이징 가능

5. **Setting Sources = 프로젝트 컨텍스트 주입**
   - `setting_sources=["project"]` → CLAUDE.md 자동 로드
   - System prompt에 `<system-reminder>` 형태로 주입

---

## 🚀 v1-v4 구현에 적용하기

### 1. Hook System 구현 (v1 예시)

```python
from typing import Callable, Any, Awaitable
from dataclasses import dataclass

@dataclass
class HookContext:
    session_id: str
    turn_count: int

HookCallback = Callable[[dict[str, Any], str | None, HookContext], Awaitable[dict[str, Any]]]

class HookSystem:
    def __init__(self):
        self.hooks: dict[str, list[HookCallback]] = {
            "PreToolUse": [],
            "PostToolUse": [],
            "UserPromptSubmit": [],
            "PreCompact": [],
        }

    def register(self, event: str, callback: HookCallback):
        """Hook 등록"""
        if event in self.hooks:
            self.hooks[event].append(callback)

    async def trigger(
        self,
        event: str,
        input_data: dict[str, Any],
        tool_use_id: str | None = None,
        context: HookContext | None = None
    ) -> dict[str, Any]:
        """Hook 실행"""
        for callback in self.hooks.get(event, []):
            result = await callback(input_data, tool_use_id, context or HookContext("", 0))

            # deny 결정이 있으면 즉시 반환
            if result.get("decision") == "block":
                return result

            # 입력 데이터 업데이트 (다음 hook으로 전달)
            if "hookSpecificOutput" in result:
                input_data.update(result["hookSpecificOutput"])

        return {}

# 사용
hook_system = HookSystem()

# Validation Hook 등록
async def validation_hook(input_data, tool_use_id, context):
    if input_data['tool_name'] == 'Bash':
        # Validation Agent 호출
        prefix = await call_validation_agent(input_data['tool_input']['command'])

        if prefix == "command_injection_detected":
            return {"decision": "block", "systemMessage": "Dangerous command detected"}

    return {}

hook_system.register("PreToolUse", validation_hook)

# 도구 실행 전
hook_result = await hook_system.trigger(
    "PreToolUse",
    {"tool_name": "Bash", "tool_input": {"command": "npm run build"}},
    context=HookContext(session_id="abc123", turn_count=5)
)

if hook_result.get("decision") == "block":
    print("Tool execution blocked!")
else:
    # 도구 실행
    pass
```

### 2. can_use_tool 구현 (v2 예시)

```python
from typing import Callable, Awaitable

CanUseTool = Callable[[str, dict, dict], Awaitable[dict[str, Any]]]

async def safe_file_operations(tool_name: str, input_data: dict, context: dict):
    """파일 작업 안전 제어"""
    if tool_name == "Write" and input_data.get("file_path", "").startswith("/system/"):
        return {
            "behavior": "deny",
            "message": "System directory write not allowed",
            "interrupt": True
        }

    return {"behavior": "allow"}

# LangGraph에서 사용
async def execute_tool(tool_name: str, tool_input: dict, can_use_tool: CanUseTool | None):
    """도구 실행 (permission 체크 포함)"""

    # can_use_tool 콜백 실행
    if can_use_tool:
        permission = await can_use_tool(tool_name, tool_input, {})

        if permission.get("behavior") == "deny":
            return {
                "error": permission.get("message", "Permission denied"),
                "interrupt": permission.get("interrupt", False)
            }

        # 입력 수정
        if "updatedInput" in permission:
            tool_input = permission["updatedInput"]

    # 도구 실행
    return await TOOL_REGISTRY[tool_name](tool_input)
```

### 3. System Prompt Preset 구현 (v3 예시)

```python
CLAUDE_CODE_PRESET = """You are Claude Code, Anthropic's official CLI for Claude.
You are an interactive CLI tool that helps users with software engineering tasks...

[~17,000 chars of system prompt]
"""

def get_system_prompt(preset: dict | str | None) -> str:
    """System prompt 생성"""
    if isinstance(preset, dict):
        if preset.get("type") == "preset" and preset.get("preset") == "claude_code":
            base_prompt = CLAUDE_CODE_PRESET
            append_text = preset.get("append", "")
            return base_prompt + "\n\n" + append_text if append_text else base_prompt
    elif isinstance(preset, str):
        return preset
    else:
        return "You are a helpful coding assistant."
```

### 4. Setting Sources 구현 (v4 예시)

```python
import os
from pathlib import Path

def load_setting_sources(sources: list[str] | None) -> dict[str, Any]:
    """파일시스템에서 설정 로드"""
    if not sources:
        return {}  # 기본: 아무것도 로드하지 않음

    settings = {}

    if "user" in sources:
        # ~/.claude/settings.json
        user_settings = Path.home() / ".claude" / "settings.json"
        if user_settings.exists():
            settings.update(json.loads(user_settings.read_text()))

    if "project" in sources:
        # .claude/settings.json
        project_settings = Path.cwd() / ".claude" / "settings.json"
        if project_settings.exists():
            settings.update(json.loads(project_settings.read_text()))

        # CLAUDE.md (중요!)
        claude_md = Path.cwd() / "CLAUDE.md"
        if claude_md.exists():
            settings["claude_md_content"] = claude_md.read_text()

    if "local" in sources:
        # .claude/settings.local.json
        local_settings = Path.cwd() / ".claude" / "settings.local.json"
        if local_settings.exists():
            settings.update(json.loads(local_settings.read_text()))

    return settings

def inject_claude_md_context(messages: list, settings: dict) -> list:
    """CLAUDE.md 컨텍스트를 messages에 주입"""
    claude_md = settings.get("claude_md_content")
    if not claude_md:
        return messages

    # system-reminder 형태로 주입
    context_message = {
        "role": "user",
        "content": f"""<system-reminder>
As you answer the user's questions, you can use the following context:
# claudeMd
Codebase and user instructions are shown below. Be sure to adhere to these instructions.

Contents of {Path.cwd()}/CLAUDE.md:

{claude_md}

IMPORTANT: this context may or may not be relevant to your tasks.
</system-reminder>"""
    }

    # 첫 번째 user message 앞에 삽입
    return [context_message] + messages
```

---

## 📝 결론

**핵심 발견 요약**:

1. ✅ **Hook System**: Claude Code의 핵심 확장 메커니즘
2. ✅ **Validation Agent**: PreToolUse hook 내부에서 별도 LLM 호출
3. ✅ **File Extraction Agent**: PostToolUse hook 내부에서 별도 LLM 호출
4. ✅ **Permission System**: can_use_tool = Hook의 고수준 추상화
5. ✅ **System Prompt Preset**: claude_code preset = ~17,000 chars
6. ✅ **Setting Sources**: CLAUDE.md 자동 로드 메커니즘

**교육적 가치**:
- Hook System을 이해하면 Claude Code의 확장 가능성 이해
- Validation/File Extraction Agent가 Hook으로 구현된 방식 이해
- v1-v4에 Hook System을 추가하여 실제 Claude Code 수준으로 확장 가능

**다음 단계**: 이 분석을 바탕으로 v1-v4에 Hook System을 구현하여, 사용자 정의 검증 로직, 파일 추출 로직 등을 추가할 수 있습니다!
