# Claude Code 상호작용 시뮬레이션

이 폴더는 **Claude Code의 전체 동작 흐름**을 시뮬레이션한 데이터를 포함합니다.

## 📁 파일 구조

### 1. `1-simple-file-read.json`
가장 기본적인 흐름: 파일 읽기

```
User: "package.json 읽어줘"
  ↓
Claude: Read 도구 사용
  ↓
CLI: 파일 읽기 실행
  ↓
Claude: 결과 분석 및 응답
```

**핵심 포인트**:
- 시스템 프롬프트 50,000+ 토큰 (첫 요청에 캐시 생성)
- 두 번째 요청부터 캐시 히트 (75-90% 비용 절감)
- 단순한 요청-응답-도구-결과 루프

---

### 2. `2-multi-tool-loop.json`
도구 사용 루프: 버그 찾기 → 수정 → 검증

```
User: "버그 찾아서 수정해줘"
  ↓
Claude: Read (파일 읽기)
  ↓
Claude: Edit (버그 수정)
  ↓
Claude: Bash (빌드로 검증)
  ↓
Claude: 완료 보고
```

**핵심 포인트**:
- 여러 도구를 순차적으로 사용
- 각 도구 결과를 다음 도구 사용의 입력으로 활용
- Read → Analyze → Edit → Verify 패턴

**도구 체인**:
```
Read → [파일 내용 분석]
  ↓
Edit → [버그 수정]
  ↓
Bash → [빌드 검증]
  ↓
최종 응답
```

---

### 3. `3-multi-agent-task.json`
멀티 에이전트 시스템: 코드베이스 분석 → 계획 → 실행

```
Main Agent
    │
    ├─→ Task(Explore Agent)
    │       └─ 코드베이스 탐색
    │           ├─ Glob (파일 찾기)
    │           ├─ Grep (패턴 검색)
    │           └─ Read (파일 읽기)
    │       → 결과 리포트
    │
    ├─→ Task(Plan Agent)
    │       └─ 리팩토링 계획 수립
    │           ├─ Read (컨텍스트 이해)
    │           └─ ExitPlanMode (계획 제시)
    │       → 상세 계획
    │
    └─→ 사용자 승인 후 실행
        ├─ TodoWrite (진행 상황 추적)
        ├─ Write (유틸리티 생성)
        ├─ Edit × 6 (중복 제거)
        └─ Bash (빌드)
```

**핵심 포인트**:
- 각 Agent는 **독립적인 subprocess**
- 같은 시스템 프롬프트와 도구 세트 사용
- Agent는 완전히 자율적으로 동작
- Parent Agent는 결과만 받음

**에이전트 독립성**:
```
Main Agent Context:
├─ System: [50k tokens]
├─ Tools: [16 tools]
└─ Messages: [User conversation]

Explore Agent Context (독립!):
├─ System: [Same 50k tokens]
├─ Tools: [Same 16 tools]
└─ Messages: [Fresh, from Task prompt]
    ├─ Glob → result
    ├─ Grep → result
    └─ Read → result

Plan Agent Context (독립!):
├─ System: [Same 50k tokens]
├─ Tools: [Same 16 tools]
└─ Messages: [Fresh, from Task prompt + Explore result]
    ├─ Read → context
    └─ ExitPlanMode → plan
```

---

## 🔄 전체 시스템 루프

### Level 1: 기본 루프 (도구 없음)

```
┌──────────────┐
│ User Input   │
└──────┬───────┘
       │
       ↓
┌──────────────────────────────────┐
│ Claude Code CLI                  │
│ ├─ Build Request                 │
│ │   ├─ System (50k tokens)       │
│ │   ├─ Tools (16 tools)          │
│ │   └─ Messages                  │
│ └─ Send to API                   │
└──────┬───────────────────────────┘
       │
       ↓
┌──────────────────────────────────┐
│ Router (model selection)         │
└──────┬───────────────────────────┘
       │
       ↓
┌──────────────────────────────────┐
│ LLM (DeepSeek/Gemini/etc)        │
│ └─ Generate response             │
└──────┬───────────────────────────┘
       │
       ↓
┌──────────────────────────────────┐
│ Claude Code CLI                  │
│ └─ Display to user               │
└──────┬───────────────────────────┘
       │
       ↓
┌──────────────┐
│ User sees    │
│ response     │
└──────────────┘
```

### Level 2: 도구 사용 루프

```
User: "파일 읽어줘"
    ↓
Claude: [tool_use: Read]
    ↓
CLI: Execute Read tool
    ↓
Claude: [tool_result] → 다시 요청
    ↓
Claude: "파일 내용은..." [end_turn]
```

**stop_reason 분기**:
```
Response.stop_reason:
├─ "tool_use"
│   ├─ CLI가 도구 실행
│   ├─ 결과를 user 메시지로 추가
│   └─ 다시 Claude에게 요청 (루프!)
│
└─ "end_turn"
    └─ 사용자에게 응답 표시 (종료)
```

### Level 3: 멀티 에이전트 루프

```
Main Agent
    │
    ├─ [tool_use: Task]
    │       ↓
    │   ┌─────────────────────────┐
    │   │ Subprocess 생성         │
    │   │ (독립 대화 컨텍스트)     │
    │   ├─────────────────────────┤
    │   │ Subagent 실행           │
    │   │ ├─ 도구 사용 루프       │
    │   │ └─ 최종 결과 생성       │
    │   └─────────────────────────┘
    │       ↓
    ├─ [tool_result] 받음
    │
    └─ 다음 작업 또는 응답
```

**무한 중첩 가능**:
```
Main Agent
    └─→ Task(Explore)
        └─→ Task(general-purpose)
            └─→ Task(Explore)
                └─→ ... 계속 가능
```

---

## 🎯 시스템 프롬프트와 도구의 관계

### 시스템 프롬프트 = "사용 설명서"

```
System Prompt (50,000+ tokens):
├─ Block 1: 정체성
│   └─ "You are Claude Code..."
│
├─ Block 2-7: 16개 도구 사용법
│   ├─ Task Tool (3,000 tokens)
│   │   ├─ 언제 사용하는가?
│   │   ├─ 언제 사용하지 않는가?
│   │   ├─ 에이전트 타입 4가지
│   │   ├─ 예시 10개
│   │   └─ 안티패턴 5개
│   │
│   ├─ Read Tool (2,000 tokens)
│   │   ├─ file_path는 절대경로
│   │   ├─ offset/limit 사용법
│   │   ├─ 이미지/PDF 지원
│   │   └─ 예시 + 안티패턴
│   │
│   └─ [각 도구마다 상세 지침...]
│
├─ Block 8: TodoWrite 시스템
│   ├─ 3+ steps일 때 사용
│   ├─ ONE task in_progress
│   └─ 즉시 완료 표시
│
├─ Block 9: Git 프로토콜
├─ Block 10: PR 프로토콜
└─ Block 11: 환경 정보
```

### 도구 = "실행 가능한 함수"

```json
{
  "name": "Read",
  "description": "Reads a file...",
  "input_schema": {
    "type": "object",
    "properties": {
      "file_path": {"type": "string"}
    },
    "required": ["file_path"]
  }
}
```

**시스템 프롬프트 + 도구 = 완벽한 통합**:

1. **시스템 프롬프트**가 "언제, 어떻게" 사용하는지 가르침
2. **도구 스키마**가 "무엇을" 실행하는지 정의
3. **Claude**가 적절한 도구를 선택하고 올바른 파라미터 생성
4. **CLI**가 실제로 도구를 실행

---

## 💡 인터렉티브 상호작용 패턴

### 패턴 1: 순차 실행

```
User: "버그 수정해줘"
  → Read (분석)
  → Edit (수정)
  → Bash (검증)
  → 응답
```

### 패턴 2: 병렬 정보 수집

```
User: "코드 리뷰해줘"
  → Bash(git status) + Bash(git diff) + Bash(git log)  // 병렬!
  → 결과 통합 분석
  → 응답
```

### 패턴 3: 조건부 분기

```
User: "테스트 실행해줘"
  → Bash(npm test)
  → 실패?
      ├─ Yes → Read (로그)
      │         → Edit (수정)
      │         → Bash (재시도)
      │
      └─ No → 성공 보고
```

### 패턴 4: 사용자 확인

```
User: "데이터베이스 초기화해줘"
  → AskUserQuestion ("정말 초기화할까요?")
  → 사용자 응답 대기
  → Yes?
      └─ Bash (초기화)
```

### 패턴 5: 에이전트 위임

```
User: "코드베이스 분석해줘"
  → 복잡함 감지
  → Task(Explore, thoroughness: "very thorough")
      └─ Explore Agent가 자율적으로 탐색
  → 결과 받아서 요약
```

---

## 🔧 라우터의 투명성

라우터는 이 모든 구조를 **변경하지 않고 유지**합니다:

```
Claude Code Request:
┌────────────────────────────────┐
│ model: "claude-sonnet-4"       │  ← 라우터가 변경!
│ system: [50k tokens]           │  ← 그대로!
│ tools: [16 tools]              │  ← 그대로!
│ messages: [...]                │  ← 그대로!
│ thinking: {...}                │  ← 그대로!
│ metadata: {...}                │  ← 그대로!
└────────────────────────────────┘
         ↓
Router: model = "deepseek,deepseek-chat"
         ↓
@musistudio/llms:
  Transform to DeepSeek format
         ↓
DeepSeek API
         ↓
@musistudio/llms:
  Transform back to Anthropic format
         ↓
Claude Code CLI
  (구조가 동일해서 정상 동작!)
```

---

## 📊 토큰 효율성

### 요청마다 보내는 데이터

```
첫 요청:
├─ System: 50,000 tokens (NEW - 캐시 생성)
├─ Tools: 15,000 tokens (NEW - 캐시 생성)
├─ Messages: 100 tokens
└─ Total: 65,100 tokens ($0.195)

두 번째 요청:
├─ System: 50,000 tokens (CACHED - 90% 할인)
├─ Tools: 15,000 tokens (CACHED - 90% 할인)
├─ Messages: 200 tokens (NEW)
└─ Total: 200 + 65,000 (cached) ($0.040)

세 번째 요청:
├─ System: 50,000 tokens (CACHED)
├─ Tools: 15,000 tokens (CACHED)
├─ Messages: 300 tokens (NEW)
└─ Total: 300 + 65,000 (cached) ($0.045)
```

**Prompt Caching 없이는 불가능!**
- 매 요청마다 65,000 토큰 = $0.195
- 10번 요청 = $1.95
- Caching으로 = $0.60 (69% 절감!)

---

## 🎓 핵심 학습 포인트

### 1. 초상세 시스템 프롬프트
- 50,000+ 토큰의 지침
- 각 도구마다 1,000-3,000 토큰
- 예시, 안티패턴, 주의사항 모두 포함

### 2. 도구 중심 아키텍처
- 16개 도구로 모든 작업 수행
- 각 도구는 명확한 책임
- 시스템 프롬프트가 사용법 가르침

### 3. 계층적 에이전트
- Task tool로 서브프로세스 생성
- 독립적인 대화 컨텍스트
- 무한 중첩 가능

### 4. 경제적 설계
- Prompt Caching으로 비용 최적화
- 캐시 없이는 실행 불가능
- 5분 TTL로 세션 유지

### 5. 인터렉티브 루프
- tool_use / end_turn 분기
- 도구 결과를 다시 입력으로
- 사용자 확인 요청 가능

---

## 🚀 실제 사용 예시

### 간단한 작업
```bash
$ claude "README를 읽어줘"
→ 1 turn, 1 tool (Read)
```

### 중간 복잡도
```bash
$ claude "버그 찾아서 수정해줘"
→ 3 turns, 3 tools (Read, Edit, Bash)
```

### 복잡한 작업
```bash
$ claude "코드베이스 분석 후 리팩토링해줘"
→ 20+ turns
→ 2 subagents (Explore, Plan)
→ 10+ tools
→ User approval checkpoint
```

---

**생성 날짜**: 2025-11-14
**목적**: Claude Code의 전체 동작 흐름 이해
**데이터 유형**: 시뮬레이션 (실제 동작 기반)
