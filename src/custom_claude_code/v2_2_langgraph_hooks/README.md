# v2.2: LangGraph + Hook System

> **Version 2.2**: v2.1에 Hook System을 추가한 버전
>
> **핵심 기능**: Claude Code의 Hook System 완전 구현

---

## 🆕 v2.2의 새로운 기능

### Hook System

Claude Code의 핵심 확장 메커니즘인 **Hook System**을 완전히 구현했습니다.

**6가지 Hook Events**:
1. **PreToolUse**: 도구 실행 전 호출 → Validation Agent 구현
2. **PostToolUse**: 도구 실행 후 호출 → File Extraction Agent 구현
3. **UserPromptSubmit**: 사용자 프롬프트 제출 시 호출 → CLAUDE.md 컨텍스트 주입
4. **PreCompact**: 메시지 압축 전 호출 → 압축 전 커스터마이징
5. **Stop**: 실행 중지 시 호출
6. **SubagentStop**: Subagent 중지 시 호출

### Validation Agent

**PreToolUse Hook**으로 구현된 Bash 명령어 보안 검증:
- 별도 LLM 호출로 command injection 탐지
- Command prefix 추출 및 allowlist 확인
- 위험한 명령어 자동 차단 또는 승인 요청

### File Path Extraction Agent

**PostToolUse Hook**으로 구현된 파일 경로 자동 추출:
- Bash 출력에서 파일 경로 자동 감지
- `is_displaying_contents` 판단
- 추출된 파일 정보를 컨텍스트에 추가

### Permission System (can_use_tool)

Hook System의 고수준 추상화:
- 간단한 API로 도구 권한 제어
- 입력 데이터 수정 가능 (예: 경로 리다이렉션)
- deny, allow, ask 결정 지원

### Settings Loader (CLAUDE.md)

Setting Sources를 통한 프로젝트 컨텍스트 로드:
- `setting_sources=["project"]` → CLAUDE.md 자동 로드
- `<system-reminder>` 형태로 주입
- 프로젝트 지침을 Agent가 따르도록 함

---

## 📁 파일 구조

```
v2_2_langgraph_hooks/
├── hooks.py                      # Hook System 핵심
├── validation_agent.py           # Validation Agent (PreToolUse)
├── file_extraction_agent.py      # File Extraction Agent (PostToolUse)
├── permission.py                 # can_use_tool API
├── settings.py                   # CLAUDE.md Loader
├── graph.py                      # LangGraph (v2.1 기반)
├── nodes.py                      # Nodes (Hook 통합)
├── tools.py                      # Tools (v2.1과 동일)
├── prompts.py                    # Prompts (v2.1과 동일)
├── models.py                     # Models (v2.1과 동일)
├── config.py                     # Config (v2.1과 동일)
├── types.py                      # Types (v2.1과 동일)
└── main.py                       # Main entry point
```

---

## 🚀 빠른 시작

### 기본 사용 (v2.1과 동일)

```python
from custom_claude_code.v2_2_langgraph_hooks import main

# v2.1과 동일하게 사용 가능 (Hook System은 선택적)
asyncio.run(main.run_conversation_loop())
```

### Hook System 사용

#### 1. Validation Agent 활성화

```python
from custom_claude_code.v2_2_langgraph_hooks.hooks import register_hook
from custom_claude_code.v2_2_langgraph_hooks.validation_agent import create_bash_validation_hook

# Validation Agent 활성화 (Bash 명령어 보안 검증)
validation_hook = create_bash_validation_hook(
    allowlist=["ls", "cat", "git status", "git diff", "npm test"],
    enable_validation=True  # LLM으로 검증 (False면 간단한 체크만)
)

register_hook('PreToolUse', validation_hook, matcher='Bash')
```

#### 2. File Path Extraction Agent 활성화

```python
from custom_claude_code.v2_2_langgraph_hooks.file_extraction_agent import create_file_extraction_hook

# File Extraction Agent 활성화 (Bash 출력에서 파일 경로 추출)
extraction_hook = create_file_extraction_hook(enable_extraction=True)

register_hook('PostToolUse', extraction_hook, matcher='Bash')
```

#### 3. can_use_tool 사용 (Permission System)

```python
from custom_claude_code.v2_2_langgraph_hooks.permission import create_permission_hook

async def my_permission_handler(tool_name, input_data, context):
    """도구 권한 제어"""

    # 시스템 디렉토리 쓰기 차단
    if tool_name == "Write" and input_data.get("file_path", "").startswith("/system/"):
        return {
            "behavior": "deny",
            "message": "System directory write not allowed"
        }

    # config 파일은 sandbox로 리다이렉션
    if tool_name in ["Write", "Edit"] and "config" in input_data.get("file_path", ""):
        safe_path = f"./sandbox/{input_data['file_path']}"
        return {
            "behavior": "allow",
            "updatedInput": {**input_data, "file_path": safe_path}
        }

    return {"behavior": "allow"}

# Permission Hook 등록
permission_hook = create_permission_hook(my_permission_handler)
register_hook('PreToolUse', permission_hook)
```

#### 4. CLAUDE.md 로드

```python
from custom_claude_code.v2_2_langgraph_hooks.settings import get_claude_md_context
from pathlib import Path

# CLAUDE.md 컨텍스트 가져오기
claude_md_context = get_claude_md_context(cwd=Path.cwd())

# 첫 번째 user message에 주입
if claude_md_context:
    messages = [
        {"role": "user", "content": claude_md_context},
        {"role": "user", "content": "실제 사용자 프롬프트"}
    ]
```

#### 5. 커스텀 Hook 작성

```python
from custom_claude_code.v2_2_langgraph_hooks.hooks import HookContext

async def my_custom_hook(input_data, tool_use_id, context):
    """커스텀 Hook 콜백"""

    tool_name = input_data.get('tool_name', '')
    print(f"[Hook] {tool_name} 실행 중...")

    # 특정 조건에서 차단
    if tool_name == "Bash" and "dangerous" in str(input_data):
        return {
            'decision': 'block',
            'systemMessage': 'Dangerous operation detected'
        }

    return {}  # 허용

# Hook 등록
register_hook('PreToolUse', my_custom_hook, matcher='Bash')
```

---

## 📚 주요 API

### Hook System

```python
from custom_claude_code.v2_2_langgraph_hooks.hooks import (
    get_hook_system,
    register_hook,
    trigger_hook,
    HookContext,
    HookMatcher
)

# 전역 Hook System 가져오기
hook_system = get_hook_system()

# Hook 등록
register_hook(
    'PreToolUse',           # Event 이름
    my_callback,            # 콜백 함수
    matcher='Bash'          # 도구 이름 패턴 (None이면 모든 도구)
)

# Hook 실행
result = await trigger_hook(
    'PreToolUse',
    {'tool_name': 'Bash', 'tool_input': {...}},
    tool_use_id='abc123',
    context=HookContext(session_id='s1', turn_count=5)
)

# 결과 확인
if result.get('decision') == 'block':
    print('Tool execution blocked!')
```

### Validation Agent

```python
from custom_claude_code.v2_2_langgraph_hooks.validation_agent import (
    create_bash_validation_hook,
    call_validation_agent,
    BashValidator,
    DEFAULT_ALLOWLIST
)

# Hook 생성
validation_hook = create_bash_validation_hook(
    allowlist=["ls", "cat", "git status"],  # 허용 목록
    enable_validation=True                  # LLM 검증 사용
)

# 직접 호출 (테스트용)
prefix = await call_validation_agent("npm run build")
print(f"Command prefix: {prefix}")

# Validator 인스턴스 사용
validator = BashValidator(allowlist=DEFAULT_ALLOWLIST)
result = await validator.validate_hook(input_data, tool_use_id, context)
```

### File Extraction Agent

```python
from custom_claude_code.v2_2_langgraph_hooks.file_extraction_agent import (
    create_file_extraction_hook,
    call_file_extraction_agent,
    FilePathExtractor
)

# Hook 생성
extraction_hook = create_file_extraction_hook(
    enable_extraction=True,  # LLM 추출 사용
    auto_read_files=False    # 자동 파일 읽기 (미구현)
)

# 직접 호출
result = await call_file_extraction_agent("cat foo.txt", "file contents...")
print(f"Is displaying contents: {result['is_displaying_contents']}")
print(f"File paths: {result['filepaths']}")
```

### Permission System

```python
from custom_claude_code.v2_2_langgraph_hooks.permission import (
    create_permission_hook,
    CanUseTool
)

async def my_can_use_tool(tool_name, input_data, context):
    if tool_name == "Write":
        return {"behavior": "ask", "message": "Write requires approval"}
    return {"behavior": "allow"}

permission_hook = create_permission_hook(my_can_use_tool)
register_hook('PreToolUse', permission_hook)
```

### Settings Loader

```python
from custom_claude_code.v2_2_langgraph_hooks.settings import (
    SettingsLoader,
    inject_claude_md_context,
    load_project_settings,
    get_claude_md_context
)

# 프로젝트 설정 로드
settings = load_project_settings(cwd=Path.cwd())
print(f"CLAUDE.md: {settings.get('claude_md')}")

# CLAUDE.md 컨텍스트 주입
context = get_claude_md_context(cwd=Path.cwd())
# → "<system-reminder>...</system-reminder>" 형태
```

---

## 🔍 Hook Event별 사용 예시

### PreToolUse: 도구 실행 전 검증

```python
async def pre_tool_validator(input_data, tool_use_id, context):
    tool_name = input_data['tool_name']
    tool_input = input_data['tool_input']

    # 예: Write 도구로 특정 파일 쓰기 차단
    if tool_name == "Write" and "secret" in tool_input.get("file_path", ""):
        return {
            'decision': 'block',
            'systemMessage': 'Cannot write to secret files'
        }

    return {}

register_hook('PreToolUse', pre_tool_validator, matcher='Write')
```

### PostToolUse: 도구 실행 후 처리

```python
async def post_tool_logger(input_data, tool_use_id, context):
    tool_name = input_data['tool_name']
    tool_result = input_data['tool_result']

    # 예: 모든 도구 실행 결과 로깅
    print(f"[PostTool] {tool_name} completed")
    print(f"  Result: {str(tool_result)[:100]}...")

    return {}

register_hook('PostToolUse', post_tool_logger)  # 모든 도구에 적용
```

### UserPromptSubmit: 프롬프트 제출 시 수정

```python
async def prompt_enhancer(input_data, tool_use_id, context):
    original_prompt = input_data.get('prompt', '')

    # 예: 모든 프롬프트에 타임스탬프 추가
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        'updatedInput': {
            'prompt': f"[{timestamp}] {original_prompt}"
        }
    }

register_hook('UserPromptSubmit', prompt_enhancer)
```

### PreCompact: 메시지 압축 전 커스터마이징

```python
async def preserve_important_messages(input_data, tool_use_id, context):
    messages = input_data.get('messages', [])

    # 예: 에러 메시지는 압축에서 보존
    important_keywords = ['error', 'warning', 'critical']
    for msg in messages:
        content = str(msg.get('content', ''))
        if any(keyword in content.lower() for keyword in important_keywords):
            msg['preserve'] = True  # 압축 시 보존 표시

    return {
        'hookSpecificOutput': {
            'updatedMessages': messages
        }
    }

register_hook('PreCompact', preserve_important_messages)
```

---

## 🧪 테스트

### 기본 테스트

```bash
# v2.2 실행 (Hook System 없이)
uv run python -m custom_claude_code.v2_2_langgraph_hooks.main

# Validation Agent 테스트
uv run python test_v2.2_validation.py

# File Extraction Agent 테스트
uv run python test_v2.2_file_extraction.py

# 전체 Hook System 테스트
uv run python test_v2.2_hooks.py
```

### 수동 테스트

```python
import asyncio
from custom_claude_code.v2_2_langgraph_hooks.hooks import *
from custom_claude_code.v2_2_langgraph_hooks.validation_agent import *
from custom_claude_code.v2_2_langgraph_hooks.file_extraction_agent import *

async def test():
    # Validation Agent 테스트
    print("=== Validation Agent Test ===")
    prefix = await call_validation_agent("npm run build")
    print(f"Prefix: {prefix}")  # "none"

    prefix = await call_validation_agent("git status$(id)")
    print(f"Prefix: {prefix}")  # "command_injection_detected"

    # File Extraction Agent 테스트
    print("\n=== File Extraction Agent Test ===")
    result = await call_file_extraction_agent(
        "cat foo.txt",
        "file contents here..."
    )
    print(f"Is displaying: {result['is_displaying_contents']}")  # True
    print(f"Files: {result['filepaths']}")  # ['foo.txt']

asyncio.run(test())
```

---

## 📊 v2.1과의 차이

| 항목 | v2.1 | v2.2 |
|------|------|------|
| **기본 기능** | LangGraph + 13개 도구 | 동일 |
| **Hook System** | ❌ | ✅ 6가지 Hook Event |
| **Validation Agent** | ❌ | ✅ PreToolUse Hook |
| **File Extraction** | ❌ | ✅ PostToolUse Hook |
| **Permission API** | ❌ | ✅ can_use_tool |
| **CLAUDE.md 로드** | ❌ | ✅ Setting Sources |
| **확장성** | 제한적 | 매우 높음 |
| **코드량** | ~585줄 | ~1,200줄 (+Hook System) |

---

## 🎯 사용 권장 사항

### Hook System을 사용해야 하는 경우

1. **보안이 중요한 경우**: Validation Agent로 Bash 명령어 검증
2. **파일 추적이 필요한 경우**: File Extraction Agent로 자동 파일 경로 추출
3. **권한 제어가 필요한 경우**: can_use_tool로 세밀한 도구 권한 관리
4. **프로젝트 컨텍스트가 중요한 경우**: CLAUDE.md 자동 로드
5. **커스텀 확장이 필요한 경우**: 자신만의 Hook 작성

### Hook System을 사용하지 않아도 되는 경우

1. **간단한 테스트**: v2.1과 동일하게 사용 가능
2. **신뢰할 수 있는 환경**: Validation이 필요 없는 경우
3. **빠른 프로토타이핑**: Hook 설정 없이 바로 사용

---

## 🔧 고급 사용법

### 여러 Hook 동시 등록

```python
# Validation + File Extraction + Custom Logger
from custom_claude_code.v2_2_langgraph_hooks.hooks import get_hook_system
from custom_claude_code.v2_2_langgraph_hooks.validation_agent import create_bash_validation_hook
from custom_claude_code.v2_2_langgraph_hooks.file_extraction_agent import create_file_extraction_hook

hook_system = get_hook_system()

# 1. Validation
validation_hook = create_bash_validation_hook()
hook_system.register_callback('PreToolUse', validation_hook, matcher='Bash')

# 2. File Extraction
extraction_hook = create_file_extraction_hook()
hook_system.register_callback('PostToolUse', extraction_hook, matcher='Bash')

# 3. Custom Logger
async def logger(input_data, tool_use_id, context):
    print(f"[{context.turn_count}] Tool: {input_data.get('tool_name')}")
    return {}

hook_system.register_callback('PreToolUse', logger)  # 모든 도구
hook_system.register_callback('PostToolUse', logger)
```

### Hook 결과 처리

```python
result = await trigger_hook('PreToolUse', {...})

# decision 확인
if result.get('decision') == 'block':
    print("Tool execution blocked!")
    print(f"Reason: {result.get('systemMessage')}")
elif result.get('decision') == 'ask':
    print("User approval required")
    # 사용자에게 승인 요청
else:
    print("Tool execution allowed")

# 수정된 입력 확인
if 'updatedInput' in result:
    print(f"Input modified: {result['updatedInput']}")

# Hook별 특수 출력 확인
if '_hook_outputs' in input_data:
    print(f"Hook outputs: {input_data['_hook_outputs']}")
```

---

## 💡 배운 점

v2.2 구현을 통해 배운 Claude Code의 핵심 설계 패턴:

1. **Hook System = 확장의 핵심**
   - 코드 수정 없이 동작 변경 가능
   - 사용자와 내부 구현이 동일한 인터페이스 사용

2. **Stateless Agent = 병렬 처리 가능**
   - Validation/File Extraction Agent는 상태 없음
   - 별도 LLM 호출로 독립적 실행

3. **Prompt Engineering의 중요성**
   - VALIDATION_POLICY, FILE_EXTRACTION_PROMPT
   - 명확한 프롬프트 = 정확한 결과

4. **고수준 API의 가치**
   - can_use_tool = Hook System의 추상화
   - 사용자 친화적이면서도 강력함

---

## 📖 참고 문서

- [CLAUDE_CODE_ARCHITECTURE_ANALYSIS.md](../../../docs/CLAUDE_CODE_ARCHITECTURE_ANALYSIS.md) - 전체 아키텍처 분석
- [HOOK_SYSTEM_ANALYSIS.md](../../../docs/HOOK_SYSTEM_ANALYSIS.md) - Hook System 상세 분석
- [ARCHITECTURE_VISUAL_SUMMARY.md](../../../docs/ARCHITECTURE_VISUAL_SUMMARY.md) - 시각화 요약

---

## 라이선스

교육 및 연구 목적. v2.1을 기반으로 Hook System을 추가했습니다.
