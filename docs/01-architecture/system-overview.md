# Claude Code 시스템 개요

> Claude Code의 전체 아키텍처와 핵심 컴포넌트 이해

---

## 목차

1. [시스템 구조](#시스템-구조)
2. [핵심 컴포넌트](#핵심-컴포넌트)
3. [데이터 흐름](#데이터-흐름)
4. [작동 원리](#작동-원리)

---

## 시스템 구조

### 고수준 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                    User Input                        │
└───────────────────┬─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│              Claude Code CLI                         │
│  ┌────────────────────────────────────────────────┐ │
│  │  Request Builder                                │ │
│  │  ├─ System Prompt (50k+ tokens, cached)       │ │
│  │  ├─ Tools Definition (16 tools)               │ │
│  │  ├─ Messages History                          │ │
│  │  └─ Metadata                                  │ │
│  └────────────────────────────────────────────────┘ │
└───────────────────┬─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│              Anthropic API                           │
│         (또는 Router로 다른 LLM)                      │
└───────────────────┬─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│              LLM Response                            │
│  stop_reason:                                       │
│    - "tool_use" → CLI가 도구 실행 → 다시 요청       │
│    - "end_turn" → 사용자에게 응답 표시              │
└─────────────────────────────────────────────────────┘
```

---

## 핵심 컴포넌트

### 1. 시스템 프롬프트 (50,000+ 토큰)

**역할**: AI에게 "사용 설명서" 제공

```
┌──────────────────────────────────────────────┐
│ Block 1: 정체성                               │
│   "You are Claude Code..."                  │
│   (1,000 tokens)                            │
├──────────────────────────────────────────────┤
│ Block 2: 환경 정보                            │
│   <env>Working directory, Platform...</env> │
│   (500 tokens)                              │
├──────────────────────────────────────────────┤
│ Block 3-18: 16개 도구 사용 지침               │
│   각 도구마다:                                │
│   - 언제 사용하는가                           │
│   - 언제 사용하지 않는가                       │
│   - 예시 10개                                │
│   - 안티패턴 5개                             │
│   (각 1,000-3,000 tokens)                   │
├──────────────────────────────────────────────┤
│ Block 19: Task Management (TodoWrite)       │
│   (2,000 tokens)                            │
├──────────────────────────────────────────────┤
│ Block 20-21: Git & PR 프로토콜               │
│   (3,000 tokens)                            │
├──────────────────────────────────────────────┤
│ Block 22-25: 기타 지침                       │
│   (5,000 tokens)                            │
└──────────────────────────────────────────────┘

총 50,000+ 토큰
```

**최적화**: Prompt Caching (ephemeral)
```
첫 요청: 50k tokens × $0.003/1k = $0.15 (캐시 생성)
다음 요청: 50k tokens × $0.0003/1k = $0.015 (90% 절감!)
```

---

### 2. 16개 도구

#### 파일 작업 (4개)
- **Read**: 파일 읽기 (이미지, PDF, Jupyter 지원)
- **Write**: 파일 쓰기 (덮어쓰기)
- **Edit**: 문자열 교체로 파일 수정
- **NotebookEdit**: Jupyter 노트북 셀 편집

#### 코드 탐색 (2개)
- **Glob**: 파일 패턴 찾기 (`**/*.ts`)
- **Grep**: 코드 내용 검색 (정규식 지원)

#### 실행 (3개)
- **Bash**: 쉘 명령 실행
- **BashOutput**: 백그라운드 쉘 출력 확인
- **KillShell**: 백그라운드 쉘 종료

#### 에이전트 (1개)
- **Task**: Subagent 생성 (독립 subprocess)

#### 관리 (2개)
- **TodoWrite**: 작업 추적 (pending/in_progress/completed)
- **AskUserQuestion**: 사용자에게 질문 (선택지 제공)

#### 외부 (2개)
- **WebSearch**: 웹 검색
- **WebFetch**: URL 내용 가져오기

#### 기타 (2개)
- **ExitPlanMode**: Plan Agent의 계획 제시 완료
- **SlashCommand**: 커스텀 명령 실행

---

### 3. 4개 Subagent

| Agent | 목적 | 도구 접근 | 발동 조건 |
|-------|------|-----------|----------|
| **general-purpose** | 복잡한 멀티스텝 작업 | ALL 16 tools | 불확실한 검색, 자동화 워크플로우 |
| **Explore** | 코드베이스 탐색 | ALL 16 tools | 파일 찾기, 패턴 검색, 아키텍처 이해 |
| **Plan** | 구현 계획 수립 | ALL 16 tools | 복잡한 기능 구현 전 계획 필요 |
| **statusline-setup** | 상태표시줄 설정 | Read, Edit만 | 상태표시줄 설정 명시적 요청 시 |

**공통점**:
- ✅ 모두 같은 50k+ 토큰 시스템 프롬프트
- ✅ 독립적인 대화 컨텍스트 (subprocess)
- ✅ Task tool의 prompt가 첫 user 메시지

**차이점**:
- ⚠️ statusline-setup만 도구 제한 (Read, Edit만)
- ⚠️ Explore는 thoroughness 파라미터 (quick/medium/very thorough)
- ⚠️ Plan은 ExitPlanMode 필수 사용

---

### 4. DAG 구조 (Directed Acyclic Graph)

```
Main Agent (Root)
    │
    ├→ [Optional] Task(Explore) ← Research
    │      ├→ Glob
    │      ├→ Grep
    │      ├→ Read × N
    │      └→ Report
    │
    ├→ [Optional] Task(Plan) ← Planning
    │      ├→ Read
    │      ├→ Task(Explore) (중첩!)
    │      └→ ExitPlanMode(plan)
    │
    ├→ Action ← Implementation
    │      ├→ Write
    │      ├→ Edit × N
    │      └→ TodoWrite
    │
    └→ Verify ← Validation
           ├→ Bash(build)
           │    ↓
           │  실패? ──Yes─→ Fix (Read + Edit) → Re-verify
           │    │                                  ↑
           │    └─ No                              │
           │                                       │
           └→ 성공 → 완료 ← ← ← ← ← ← ← ← ← ← ← ─┘
```

**특징**:
- ✅ 한 방향 (뒤로 못 감)
- ✅ 순환 없음 (Acyclic)
- ✅ 조건부 재시도 (Verify ↔ Fix만)
- ❌ 자동 Re-plan 없음

---

## 데이터 흐름

### 요청 구조

```json
{
  "model": "claude-sonnet-4",
  "max_tokens": 8192,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 10000
  },
  "system": [
    {
      "type": "text",
      "text": "[50,000+ tokens]",
      "cache_control": {"type": "ephemeral"}
    },
    {
      "type": "text",
      "text": "<env>...</env>",
      "cache_control": {"type": "ephemeral"}
    }
  ],
  "tools": [
    {"name": "Read", "description": "...", "input_schema": {...}},
    {"name": "Write", ...},
    // ... 16개 도구
  ],
  "messages": [
    {"role": "user", "content": "사용자 요청"},
    {"role": "assistant", "content": [...]},
    {"role": "user", "content": [{"type": "tool_result", ...}]},
    // ...
  ],
  "metadata": {
    "user_id": "user_xxx_session_yyy"
  }
}
```

---

### 응답 구조

```json
{
  "id": "msg_xxx",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "파일을 읽어보겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_01ABC",
      "name": "Read",
      "input": {
        "file_path": "/path/to/file.ts"
      }
    }
  ],
  "stop_reason": "tool_use",  // ← 중요!
  "usage": {
    "input_tokens": 850,
    "cache_creation_tokens": 0,
    "cache_read_tokens": 65000,
    "output_tokens": 87
  }
}
```

**stop_reason**:
- `"tool_use"`: CLI가 도구 실행 → 결과를 messages에 추가 → 다시 요청
- `"end_turn"`: 사용자에게 응답 표시 → 대화 종료

---

## 작동 원리

### 기본 루프

```python
messages = []

while True:
    # 1. 사용자 입력 대기
    user_input = wait_for_user()
    if user_input == "quit":
        break

    messages.append({"role": "user", "content": user_input})

    # 2. Claude 요청
    while True:
        response = claude.create(
            model="claude-sonnet-4",
            system=SYSTEM_PROMPT,  # 50k+ tokens, cached
            tools=TOOLS,           # 16 tools
            messages=messages
        )

        # 3. stop_reason 처리
        if response.stop_reason == "end_turn":
            # 사용자에게 표시
            print(response.content)
            messages.append({"role": "assistant", "content": response.content})
            break  # 사용자 입력 대기로

        elif response.stop_reason == "tool_use":
            # 도구 실행
            tool_results = execute_tools(response.content)

            # messages에 추가
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            # 다시 요청 (루프!)
            continue
```

---

### 도구 실행 루프

```
User: "README 읽어줘"
    ↓
┌─────────────────────────────────┐
│ Turn 1: Claude Request          │
│  messages: [                    │
│    {role: "user", content: "..."}│
│  ]                              │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Turn 1: Claude Response         │
│  stop_reason: "tool_use"        │
│  content: [                     │
│    {type: "tool_use",           │
│     name: "Read"}               │
│  ]                              │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ CLI: Execute Read               │
│  result = read_file("README")   │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Turn 2: Claude Request          │
│  messages: [                    │
│    {role: "user", ...},         │
│    {role: "assistant", ...},    │
│    {role: "user",               │
│     content: [                  │
│       {type: "tool_result",     │
│        content: "file..."}      │
│     ]}                          │
│  ]                              │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Turn 2: Claude Response         │
│  stop_reason: "end_turn"        │
│  content: "README 내용은..."    │
└─────────────────────────────────┘
    ↓
User: "완료!"
```

---

### Multi-Agent 플로우

```
User: "코드베이스 리팩토링"
    ↓
Main: Task(Explore)
    ↓
┌────────────────────────────────────┐
│ Explore Agent (subprocess)         │
│  system: [Same 50k+ tokens]       │
│  tools: [Same 16 tools]           │
│  messages: [                      │
│    {role: "user",                 │
│     content: "Search for..."}     │ ← Task의 prompt
│  ]                                │
│                                   │
│  Turn 1: Glob → files             │
│  Turn 2: Grep → patterns          │
│  Turn 3: Read → analysis          │
│  Turn 4: Final report             │
└────────────────────────────────────┘
    ↓
Main: [Explore report 받음]
Main: Task(Plan)
    ↓
┌────────────────────────────────────┐
│ Plan Agent (subprocess)            │
│  messages: [                       │
│    {role: "user",                  │
│     content: "Based on...         │
│               [Explore report]"}   │
│  ]                                 │
│                                    │
│  Turn 1: Read → context            │
│  Turn 2: ExitPlanMode(plan)        │
└────────────────────────────────────┘
    ↓
Main: [Plan 받음]
Main: 사용자에게 계획 제시
    ↓
User: "진행해"
    ↓
Main: [구현 시작]
    ├→ TodoWrite
    ├→ Write
    ├→ Edit × 6
    └→ Bash(build) → 완료!
```

---

## 토큰 효율성

### Prompt Caching의 중요성

```
첫 요청:
├─ System: 50,000 tokens (NEW → 캐시 생성)
├─ Tools: 15,000 tokens (NEW → 캐시 생성)
├─ Messages: 100 tokens
└─ Total: 65,100 tokens
   비용: $0.195

두 번째 요청:
├─ System: 50,000 tokens (CACHED → 90% 할인)
├─ Tools: 15,000 tokens (CACHED → 90% 할인)
├─ Messages: 200 tokens (NEW)
└─ Total: 200 + 65,000 (cached)
   비용: $0.040

10번 요청:
  Caching 없이: $1.95
  Caching 있으면: $0.60
  절감: 69%
```

**Caching 없이는 Claude Code 불가능!**

---

## 핵심 설계 원칙

### 1. 도구 중심 아키텍처

```
모든 작업 = 도구 조합

"버그 수정" = Read + Edit + Bash
"리팩토링" = Task(Explore) + Task(Plan) + Write + Edit × N + Bash
"PR 생성" = Bash(git) × 3 + Bash(gh pr create)
```

### 2. 선언적 지침

```
시스템 프롬프트 = "무엇을 할까"가 아닌 "어떻게 할까"

예시:
"Read tool을 사용할 때:
 - file_path는 절대 경로여야 함
 - 긴 파일은 offset/limit 사용
 - 이미지/PDF도 읽을 수 있음
 - 읽기 전에 반드시 Read 사용 (cat 안 됨)"
```

### 3. 사용자 제어

```
자동 루프 없음!

Claude: "완료했습니다" (end_turn)
    ↓
[대기...]
    ↓
User: "이제 이것도 해줘"
    ↓
Claude: [새 작업 시작]
```

### 4. 예측 가능성

```
DAG 구조 = 순환 없음 = 무한 루프 없음

사용자가 항상 제어:
- 언제든 중단 가능
- 비용 예측 가능
- 진행 상황 투명
```

---

## 요약

### Claude Code는:

1. **50k+ 토큰 시스템 프롬프트** → Prompt Caching 필수
2. **16개 도구** → 모든 작업은 도구 조합
3. **4개 Subagent** → 복잡한 작업 분해
4. **DAG 구조** → 순환 없음, 예측 가능
5. **도구 사용 루프** → stop_reason 기반
6. **사용자 제어** → 자동 반복 없음

### 다음 단계:

- [그래프 구조 상세](graph-structure.md)
- [데이터 흐름 분석](data-flow.md)
- [시스템 프롬프트](../02-components/system-prompt.md)

---

**생성 날짜**: 2025-11-15
**목적**: Claude Code 전체 시스템 이해
