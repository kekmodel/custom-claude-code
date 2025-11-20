# Hook System 동작 흐름 시각화

> **Hook이 어떻게 제어하는지 그림으로 이해하기**

---

## 🎯 전체 Hook System 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                      User Request                            │
│                  "Bash로 파일 삭제해줘"                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              UserPromptSubmit Hook 🎣                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. CLAUDE.md 컨텍스트 주입                          │   │
│  │ 2. 타임스탬프 추가                                  │   │
│  │ 3. 프롬프트 전처리                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│  Result: updatedInput (수정된 프롬프트)                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Main Agent (LLM)                           │
│  "사용자가 파일 삭제를 원하네. Bash 도구를 사용해야겠다."   │
│  Decision: Bash("rm important_file.txt")                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               PreToolUse Hook 🎣 🔒                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Hook 1: can_use_tool (Permission Check)            │   │
│  │   → "Write 도구는 /system/ 경로 금지"               │   │
│  │   → Result: allow                                    │   │
│  │                                                      │   │
│  │ Hook 2: Validation Agent (보안 검증)               │   │
│  │   ┌──────────────────────────────────────┐         │   │
│  │   │ 🤖 별도 LLM 호출 (Stateless)         │         │   │
│  │   │ Input: "rm important_file.txt"       │         │   │
│  │   │ System: VALIDATION_POLICY            │         │   │
│  │   │ Output: "rm"                         │         │   │
│  │   └──────────────────────────────────────┘         │   │
│  │   → Allowlist 확인: "rm" in allowlist?             │   │
│  │   → Result: ask (승인 필요)                         │   │
│  │                                                      │   │
│  │ Hook 3: Custom Logger                              │   │
│  │   → 로그 기록                                       │   │
│  │   → Result: allow                                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  Final Result: decision="ask"                               │
│               systemMessage="Command 'rm' requires approval"│
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ├─── decision="block" ────┐
                       │                          │
                       ├─── decision="ask" ───────┼──→ 사용자 승인 요청
                       │                          │
                       └─── decision="allow" ─────┘
                                │
                                ▼
                      ┌──────────────────┐
                      │  Tool Execution  │
                      │  Bash("rm ...")  │
                      └────────┬─────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               PostToolUse Hook 🎣 📁                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Hook 1: File Extraction Agent                       │   │
│  │   ┌──────────────────────────────────────┐         │   │
│  │   │ 🤖 별도 LLM 호출 (Stateless)         │         │   │
│  │   │ Input: Command + Output              │         │   │
│  │   │ System: FILE_EXTRACTION_PROMPT       │         │   │
│  │   │ Output:                              │         │   │
│  │   │   <is_displaying_contents>          │         │   │
│  │   │   false                              │         │   │
│  │   │   </is_displaying_contents>          │         │   │
│  │   │   <filepaths>                        │         │   │
│  │   │   important_file.txt                 │         │   │
│  │   │   </filepaths>                       │         │   │
│  │   └──────────────────────────────────────┘         │   │
│  │   → Result: filepaths=["important_file.txt"]       │   │
│  │                                                      │   │
│  │ Hook 2: Custom Logger                              │   │
│  │   → "Bash 완료, 파일: important_file.txt"          │   │
│  │   → Result: allow                                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  Final Result: hookSpecificOutput={                         │
│                  filepaths=["important_file.txt"]           │
│                }                                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│            Main Agent (결과 처리)                            │
│  "파일이 삭제되었습니다. 관련 파일: important_file.txt"      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
                  User Response
```

---

## 🔒 PreToolUse Hook 상세 흐름 (Validation Agent)

### 1. Hook 트리거

```
Main Agent가 도구 사용 결정
        ↓
┌─────────────────────────────────┐
│  trigger_hook('PreToolUse', {   │
│    tool_name: 'Bash',            │
│    tool_input: {                 │
│      command: 'rm file.txt'      │
│    }                             │
│  })                              │
└─────────────────────────────────┘
```

### 2. Hook System 처리

```
┌────────────────────────────────────────────────────────────┐
│                    Hook System                             │
│                                                            │
│  hooks['PreToolUse'] = [                                   │
│    HookMatcher(matcher='Bash', hooks=[                     │
│      can_use_tool_callback,      ← Hook 1                 │
│      validation_callback,         ← Hook 2                 │
│      logger_callback              ← Hook 3                 │
│    ])                                                       │
│  ]                                                          │
│                                                            │
│  실행 순서:                                                 │
│  1. tool_name='Bash'가 matcher='Bash'와 매치? ✅          │
│  2. 순차적으로 각 callback 실행                            │
│  3. decision='block'이면 즉시 중단                         │
│  4. updatedInput이 있으면 다음 hook에 전달                 │
└────────────────────────────────────────────────────────────┘
```

### 3. Validation Agent Hook 실행

```
┌────────────────────────────────────────────────────────────┐
│            Validation Agent Hook Callback                   │
│                                                            │
│  Step 1: Command 추출                                       │
│    command = input_data['tool_input']['command']           │
│    → "rm file.txt"                                         │
│                                                            │
│  Step 2: 🤖 별도 LLM 호출 (Stateless)                     │
│    ┌──────────────────────────────────────────┐           │
│    │  call_validation_agent(command)          │           │
│    │                                          │           │
│    │  LLM 호출:                               │           │
│    │    model: claude-sonnet-4-5              │           │
│    │    system: VALIDATION_POLICY             │           │
│    │    messages: [{                          │           │
│    │      role: "user",                       │           │
│    │      content: "Command: rm file.txt"     │           │
│    │    }]                                    │           │
│    │    tools: []  ← 도구 없음 (순수 분석)    │           │
│    │                                          │           │
│    │  LLM 응답:                               │           │
│    │    "rm"  ← prefix 추출                   │           │
│    └──────────────────────────────────────────┘           │
│    prefix = "rm"                                           │
│                                                            │
│  Step 3: Allowlist 확인                                    │
│    allowlist = ["ls", "cat", "git status", ...]            │
│    "rm" in allowlist? ❌                                   │
│                                                            │
│  Step 4: 결정 반환                                          │
│    return {                                                │
│      'decision': 'ask',                                    │
│      'systemMessage': 'Command "rm" requires approval',    │
│      'hookSpecificOutput': {                               │
│        'permissionDecision': 'ask',                        │
│        'command': 'rm file.txt',                           │
│        'prefix': 'rm'                                      │
│      }                                                      │
│    }                                                        │
└────────────────────────────────────────────────────────────┘
```

### 4. Hook System 최종 결정

```
┌────────────────────────────────────────────────────────────┐
│                  Hook System Decision                       │
│                                                            │
│  Hook 1 Result: allow                                      │
│  Hook 2 Result: ask  ← 이 시점에서 중단!                   │
│  Hook 3 Result: (실행 안됨)                                │
│                                                            │
│  Final Result:                                              │
│    {                                                        │
│      decision: 'ask',                                      │
│      systemMessage: 'Command "rm" requires approval'       │
│    }                                                        │
│                                                            │
│  → Main Agent로 반환                                        │
│  → 사용자에게 승인 요청                                     │
└────────────────────────────────────────────────────────────┘
```

---

## 📁 PostToolUse Hook 상세 흐름 (File Extraction Agent)

### 1. Tool 실행 완료

```
Bash("cat foo.txt") 실행
        ↓
Result: {
  output: "Hello world\nThis is foo.txt content",
  exitCode: 0
}
        ↓
┌─────────────────────────────────┐
│  trigger_hook('PostToolUse', {  │
│    tool_name: 'Bash',            │
│    tool_input: {                 │
│      command: 'cat foo.txt'      │
│    },                            │
│    tool_result: {                │
│      output: '...'               │
│    }                             │
│  })                              │
└─────────────────────────────────┘
```

### 2. File Extraction Agent Hook 실행

```
┌────────────────────────────────────────────────────────────┐
│         File Extraction Agent Hook Callback                 │
│                                                            │
│  Step 1: Command & Output 추출                             │
│    command = "cat foo.txt"                                 │
│    output = "Hello world\nThis is foo.txt content"         │
│                                                            │
│  Step 2: 🤖 별도 LLM 호출 (Stateless)                     │
│    ┌──────────────────────────────────────────┐           │
│    │  call_file_extraction_agent(cmd, output) │           │
│    │                                          │           │
│    │  LLM 호출:                               │           │
│    │    model: claude-sonnet-4-5              │           │
│    │    system: FILE_EXTRACTION_PROMPT        │           │
│    │    messages: [{                          │           │
│    │      role: "user",                       │           │
│    │      content:                            │           │
│    │        "Command: cat foo.txt\n          │           │
│    │         Output: Hello world..."          │           │
│    │    }]                                    │           │
│    │    tools: []  ← 도구 없음                │           │
│    │    temperature: 1.0  ← 창의적 추출       │           │
│    │                                          │           │
│    │  LLM 응답:                               │           │
│    │    <is_displaying_contents>             │           │
│    │    true                                  │           │
│    │    </is_displaying_contents>             │           │
│    │    <filepaths>                           │           │
│    │    foo.txt                               │           │
│    │    </filepaths>                          │           │
│    └──────────────────────────────────────────┘           │
│                                                            │
│  Step 3: XML 파싱                                          │
│    is_displaying = True                                    │
│    filepaths = ["foo.txt"]                                 │
│                                                            │
│  Step 4: 결과 반환                                          │
│    return {                                                │
│      'hookSpecificOutput': {                               │
│        'is_displaying_contents': True,                     │
│        'filepaths': ['foo.txt'],                           │
│        'suggestion': 'Files mentioned: foo.txt'            │
│      }                                                      │
│    }                                                        │
└────────────────────────────────────────────────────────────┘
```

### 3. 추출된 파일 정보 활용

```
┌────────────────────────────────────────────────────────────┐
│                   Main Agent                                │
│                                                            │
│  PostToolUse Hook Result:                                   │
│    filepaths = ["foo.txt"]                                 │
│    is_displaying_contents = True                           │
│                                                            │
│  → "foo.txt 파일의 내용을 확인했습니다."                    │
│  → (선택적) 자동으로 Read("foo.txt") 호출하여 컨텍스트 추가│
└────────────────────────────────────────────────────────────┘
```

---

## 🔄 여러 Hook이 연쇄되는 과정

### 시나리오: Bash 명령어 실행 시 3개 Hook 동작

```
User: "git status 실행해줘"
        ↓
┌─────────────────────────────────────────────────────────────┐
│  PreToolUse Hook 연쇄 실행                                   │
│                                                             │
│  Hook 1: can_use_tool                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Input: {tool_name: 'Bash', tool_input: {...}}     │    │
│  │ Logic: "git" 명령어는 허용                         │    │
│  │ Output: {decision: undefined} → 다음 hook으로      │    │
│  └────────────────────────────────────────────────────┘    │
│          ↓                                                  │
│  Hook 2: validation_agent                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Input: {tool_name: 'Bash', tool_input: {...}}     │    │
│  │ 🤖 LLM 호출: prefix = "git status"                │    │
│  │ Allowlist 확인: "git status" in allowlist? ✅     │    │
│  │ Output: {decision: 'allow'} → 다음 hook으로        │    │
│  └────────────────────────────────────────────────────┘    │
│          ↓                                                  │
│  Hook 3: custom_logger                                      │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Input: {tool_name: 'Bash', tool_input: {...}}     │    │
│  │ Logic: 로그 기록 "[Turn 5] Bash: git status"       │    │
│  │ Output: {} → 통과                                   │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  Final Result: 모든 hook 통과 → Tool 실행 허용              │
└─────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────┐
│  Tool Execution: Bash("git status")                         │
│  Result: "On branch main\nYour branch is up to date..."     │
└─────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────┐
│  PostToolUse Hook 연쇄 실행                                  │
│                                                             │
│  Hook 1: file_extraction_agent                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Input: {tool_name: 'Bash', tool_result: {...}}    │    │
│  │ 🤖 LLM 호출: filepaths = [], displaying = false   │    │
│  │ Output: {filepaths: []} → 다음 hook으로            │    │
│  └────────────────────────────────────────────────────┘    │
│          ↓                                                  │
│  Hook 2: custom_logger                                      │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Input: {tool_name: 'Bash', tool_result: {...}}    │    │
│  │ Logic: 로그 기록 "Bash completed, no files"        │    │
│  │ Output: {} → 통과                                   │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  Final Result: 모든 hook 통과 → Main Agent로 반환           │
└─────────────────────────────────────────────────────────────┘
        ↓
    User Response
```

---

## ⚖️ Hook의 Decision 처리 흐름

### Decision 타입

```
Hook 반환값의 'decision' 필드:
┌─────────────────────────────────────────┐
│  undefined (없음)  → 통과, 다음 hook으로 │
│  'allow'          → 명시적 허용          │
│  'ask'            → 사용자 승인 요청      │
│  'block'          → 즉시 차단            │
└─────────────────────────────────────────┘
```

### Decision 우선순위

```
┌────────────────────────────────────────────────────────────┐
│              Hook Decision Priority                         │
│                                                            │
│  Hook 1: return {}                    → 계속               │
│  Hook 2: return {decision: 'allow'}   → 계속               │
│  Hook 3: return {decision: 'ask'}     → ⚠️ 여기서 중단!   │
│  Hook 4: (실행 안됨)                                       │
│  Hook 5: (실행 안됨)                                       │
│                                                            │
│  Rule:                                                      │
│    1. 'block' 발견 즉시 중단 및 차단                        │
│    2. 'ask' 발견 즉시 중단 및 승인 요청                     │
│    3. 모든 hook이 undefined/'allow' → 최종 허용            │
└────────────────────────────────────────────────────────────┘
```

### 실제 처리 예시

```python
# Hook System 내부 처리 로직
for hook_callback in hooks:
    result = await hook_callback(input_data, tool_use_id, context)

    if result.get('decision') == 'block':
        return result  # 즉시 차단!

    if result.get('decision') == 'ask':
        return result  # 즉시 승인 요청!

    # 'allow' 또는 undefined → 계속
    if 'updatedInput' in result:
        input_data.update(result['updatedInput'])  # 다음 hook으로 전달

# 모든 hook 통과
return {}  # 허용
```

---

## 🎭 can_use_tool과 Hook의 관계

### can_use_tool = Hook의 고수준 추상화

```
┌─────────────────────────────────────────────────────────────┐
│                  can_use_tool API                            │
│                 (사용자 친화적)                               │
│                                                             │
│  async def my_permission(tool_name, input_data, context):   │
│      if tool_name == "Write":                               │
│          return {"behavior": "deny"}                        │
│      return {"behavior": "allow"}                           │
│                                                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ create_permission_hook()
                       │ (자동 변환)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               PreToolUse Hook Callback                       │
│              (내부 Hook System 형식)                         │
│                                                             │
│  async def hook_wrapper(input_data, tool_use_id, context):  │
│      # can_use_tool 호출                                    │
│      result = await my_permission(...)                      │
│                                                             │
│      # behavior → decision 변환                             │
│      if result['behavior'] == 'deny':                       │
│          return {'decision': 'block'}                       │
│      elif result['behavior'] == 'ask':                      │
│          return {'decision': 'ask'}                         │
│      else:                                                   │
│          return {}  # allow                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 Hook Matcher 동작 원리

### Matcher 패턴 매칭

```
┌────────────────────────────────────────────────────────────┐
│                  Hook Matcher Logic                         │
│                                                            │
│  HookMatcher(matcher='Bash', hooks=[...])                   │
│                                                            │
│  Tool: 'Bash'                                              │
│    → matcher='Bash'.match('Bash') ✅ → Hook 실행          │
│                                                            │
│  Tool: 'Write'                                             │
│    → matcher='Bash'.match('Write') ❌ → Hook 스킵         │
│                                                            │
│  ─────────────────────────────────────────────────────     │
│                                                            │
│  HookMatcher(matcher='Write|Edit', hooks=[...])            │
│  (정규식 패턴)                                              │
│                                                            │
│  Tool: 'Write'                                             │
│    → pattern.match('Write') ✅ → Hook 실행                │
│                                                            │
│  Tool: 'Edit'                                              │
│    → pattern.match('Edit') ✅ → Hook 실행                 │
│                                                            │
│  Tool: 'Bash'                                              │
│    → pattern.match('Bash') ❌ → Hook 스킵                 │
│                                                            │
│  ─────────────────────────────────────────────────────────     │
│                                                            │
│  HookMatcher(matcher=None, hooks=[...])                    │
│  (모든 도구에 적용)                                          │
│                                                            │
│  Tool: Any                                                 │
│    → matcher=None ✅ → Hook 실행 (모든 도구)              │
└────────────────────────────────────────────────────────────┘
```

### 여러 Matcher 조합

```
hooks['PreToolUse'] = [
    HookMatcher(matcher='Bash', hooks=[validation_hook]),      # Bash만
    HookMatcher(matcher='Write|Edit', hooks=[file_check_hook]), # Write/Edit만
    HookMatcher(matcher=None, hooks=[logger_hook])             # 모든 도구
]

실행:
  Tool='Bash'
    → validation_hook 실행 ✅
    → file_check_hook 스킵 ❌
    → logger_hook 실행 ✅

  Tool='Write'
    → validation_hook 스킵 ❌
    → file_check_hook 실행 ✅
    → logger_hook 실행 ✅

  Tool='Read'
    → validation_hook 스킵 ❌
    → file_check_hook 스킵 ❌
    → logger_hook 실행 ✅
```

---

## 🧩 실제 사용 예시: 복잡한 Hook 체인

### 시나리오: 파일 쓰기 작업

```
User: "/system/config.json 파일에 설정 저장해줘"
        ↓
Main Agent: Write("/system/config.json", "...")
        ↓
┌─────────────────────────────────────────────────────────────┐
│  PreToolUse Hook 체인                                        │
│                                                             │
│  Hook 1: permission_check                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ if tool_name == "Write":                           │    │
│  │   if path.startswith("/system/"):                  │    │
│  │     return {decision: 'block'} → ⛔ 여기서 중단!   │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  Hook 2: (실행 안됨)                                        │
│  Hook 3: (실행 안됨)                                        │
│                                                             │
│  Final Result:                                              │
│    decision: 'block'                                        │
│    systemMessage: 'System directory write not allowed'      │
└─────────────────────────────────────────────────────────────┘
        ↓
    User에게 오류 메시지 표시

───────────────────────────────────────────────────────────────

User: "./config.json 파일에 설정 저장해줘"
        ↓
Main Agent: Write("./config.json", "...")
        ↓
┌─────────────────────────────────────────────────────────────┐
│  PreToolUse Hook 체인                                        │
│                                                             │
│  Hook 1: permission_check                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ if tool_name == "Write":                           │    │
│  │   if "config" in path:                             │    │
│  │     # 경로 리다이렉션                               │    │
│  │     return {                                       │    │
│  │       updatedInput: {                              │    │
│  │         file_path: "./sandbox/config.json"         │    │
│  │       }                                            │    │
│  │     }                                              │    │
│  └────────────────────────────────────────────────────┘    │
│          ↓                                                  │
│  Hook 2: file_size_check                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │ file_path = "./sandbox/config.json" (수정됨)       │    │
│  │ content_size = len(content)                        │    │
│  │ if content_size > MAX_SIZE:                        │    │
│  │   return {decision: 'ask'}                         │    │
│  │ else:                                              │    │
│  │   return {}  # 통과                                │    │
│  └────────────────────────────────────────────────────┘    │
│          ↓                                                  │
│  Hook 3: audit_logger                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │ log(f"Write: {file_path}")                         │    │
│  │ return {}  # 통과                                   │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  Final Result:                                              │
│    모든 hook 통과                                           │
│    updatedInput: {file_path: "./sandbox/config.json"}      │
└─────────────────────────────────────────────────────────────┘
        ↓
Write("./sandbox/config.json", "...")  ← 수정된 경로로 실행!
        ↓
    Success
```

---

## 💡 핵심 포인트

### 1. Hook = 제어의 역전 (Inversion of Control)

```
기존:
  Tool 실행 → 결과 반환

Hook System:
  Tool 실행 요청
    → PreToolUse Hook 🎣 (검증, 수정, 로깅)
      → Tool 실행 (또는 차단)
        → PostToolUse Hook 🎣 (결과 처리, 추가 작업)
          → 최종 결과
```

### 2. Stateless Agent = 병렬 처리 가능

```
Validation Agent:
  ┌─────────────────┐
  │ LLM Call (독립) │  ← 상태 없음
  └─────────────────┘

File Extraction Agent:
  ┌─────────────────┐
  │ LLM Call (독립) │  ← 상태 없음
  └─────────────────┘

→ 두 Agent를 병렬로 실행 가능!
→ 캐싱, 재시도, 로드밸런싱 용이
```

### 3. 여러 Hook의 조합 = 강력한 제어

```
PreToolUse Hook:
  1. can_use_tool (권한)
  2. Validation Agent (보안)
  3. Cost Estimator (비용)
  4. Rate Limiter (제한)
  5. Audit Logger (감사)

→ 각각 독립적으로 개발/테스트
→ 조합하여 복잡한 정책 구현
```

---

## 📚 요약

**Hook System의 제어 방식**:

1. **PreToolUse**: 도구 실행 **전** 제어
   - 검증, 차단, 수정, 로깅
   - Validation Agent = PreToolUse Hook의 구현체

2. **PostToolUse**: 도구 실행 **후** 제어
   - 결과 분석, 추가 작업, 로깅
   - File Extraction Agent = PostToolUse Hook의 구현체

3. **Decision Chain**: 여러 Hook의 연쇄 실행
   - `block` → 즉시 중단
   - `ask` → 사용자 승인 요청
   - `allow` / `undefined` → 계속 진행

4. **Input Modification**: 다음 Hook으로 전달
   - `updatedInput` → 도구 입력 수정
   - 경로 리다이렉션, 파라미터 변경 등

5. **Matcher Pattern**: 선택적 Hook 실행
   - 도구 이름 패턴 매칭
   - 정규식 지원
   - `None` = 모든 도구

이제 Hook이 어떻게 제어하는지 완전히 이해했습니다! 🎉
