# Claude Code의 검증(Verification) 시스템

## 결론: ❌ 검증 전용 Agent는 없습니다

Claude Code에는 **검증만을 위한 별도 subagent가 없습니다**.

현재 존재하는 subagent는 **4개뿐**:
1. general-purpose
2. Explore
3. Plan
4. statusline-setup

---

## 검증은 어떻게 이루어지는가?

### 패턴 1: Main Agent가 직접 검증

**가장 일반적인 패턴**

```json
User: "버그 수정해줘"
    ↓
Main: Read (파일 읽기)
    ↓
Main: Edit (버그 수정)
    ↓
Main: Bash ("npm run build") ← 검증!
    ↓
Main: Bash ("npm test") ← 추가 검증!
    ↓
Main: "✅ 빌드 성공, 테스트 통과!"
```

**실제 도구 사용 예시**:
```json
{
  "role": "assistant",
  "content": [
    {"type": "text", "text": "수정을 완료했습니다. 이제 빌드해서 검증하겠습니다."},
    {
      "type": "tool_use",
      "name": "Bash",
      "input": {
        "command": "npm run build",
        "description": "Build project to verify fix"
      }
    }
  ]
}
```

**특징**:
- ✅ 단순하고 빠름
- ✅ 대부분의 검증에 충분
- ✅ 빌드 실패 시 즉시 수정 가능

---

### 패턴 2: general-purpose Agent가 검증 포함

**복잡한 멀티스텝 작업**

```json
User: "deprecated API를 모두 업데이트해줘"
    ↓
Main: Task(general-purpose)
    ↓
general-purpose Agent:
    ├→ Grep (모든 사용처 찾기)
    ├→ Read (각 파일 컨텍스트 이해)
    ├→ Edit (첫 번째 수정)
    ├→ Bash ("npm run build") ← 검증!
    │   ├→ 실패? → Read (에러 로그) → Edit (수정) → Bash (재검증)
    │   └→ 성공? → 계속
    ├→ Edit (두 번째 수정)
    ├→ Bash ("npm run build") ← 다시 검증!
    └→ Final Report
    ↓
Main: "모든 업데이트 완료!"
```

**실제 prompt 예시**:
```json
{
  "tool_use": {
    "name": "Task",
    "input": {
      "subagent_type": "general-purpose",
      "description": "Update all deprecated APIs",
      "prompt": "Find all usages of `oldFunction()` and replace with `newFunction()`.\n\nFor each replacement:\n1. Read file context\n2. Replace function call\n3. Run build to verify\n4. If build fails, fix and retry\n\nReport total replacements and any issues."
    }
  }
}
```

**특징**:
- ✅ 자동으로 검증 포함
- ✅ 실패 시 자동 수정 및 재시도
- ✅ 여러 파일 수정 시 각각 검증 가능

---

### 패턴 3: Plan Agent의 검증 단계

**복잡한 기능 구현**

```json
User: "인증 시스템 추가해줘"
    ↓
Main: Task(Plan)
    ↓
Plan Agent: ExitPlanMode with plan:
{
  "Phase 1": "Create auth utilities",
  "Phase 2": "Implement login endpoint",
  "Phase 3": "Add middleware",
  "Phase 4": "Testing & Verification",  ← 검증 단계!
  "steps": [
    {"step": "4.1", "action": "Run unit tests"},
    {"step": "4.2", "action": "Run integration tests"},
    {"step": "4.3", "action": "Manual verification checklist"}
  ]
}
    ↓
User: "진행해"
    ↓
Main: 구현...
    ↓
Main: Bash("npm test")  ← Phase 4 실행
    ↓
Main: "✅ 모든 테스트 통과!"
```

**특징**:
- ✅ 검증이 계획의 일부
- ✅ 단계별로 명확한 검증 포인트
- ✅ 수동 검증 체크리스트도 포함 가능

---

### 패턴 4: 병렬 검증

**여러 독립적인 검증 동시 실행**

```json
Main: [코드 변경 완료]
    ↓
Main: 병렬 검증 시작
    ├→ Bash("npm run build")    ← 빌드 검증
    ├→ Bash("npm test")          ← 유닛 테스트
    ├→ Bash("npm run lint")      ← 린트 검증
    └→ Bash("npm run type-check") ← 타입 검증
    ↓
Main: 모든 결과 분석
    ├→ 모두 성공? → "✅ 완료!"
    └→ 실패 있음? → 수정 → 재검증
```

**실제 도구 사용 예시**:
```json
{
  "role": "assistant",
  "content": [
    {"type": "text", "text": "이제 여러 검증을 병렬로 실행하겠습니다."},
    {
      "type": "tool_use",
      "id": "build",
      "name": "Bash",
      "input": {"command": "npm run build", "description": "Build verification"}
    },
    {
      "type": "tool_use",
      "id": "test",
      "name": "Bash",
      "input": {"command": "npm test", "description": "Run tests"}
    },
    {
      "type": "tool_use",
      "id": "lint",
      "name": "Bash",
      "input": {"command": "npm run lint", "description": "Lint check"}
    }
  ]
}
```

**특징**:
- ✅ 빠름 (병렬 실행)
- ✅ 포괄적 검증
- ✅ 실패 원인 즉시 파악

---

## 검증 도구들

Claude Code가 검증에 사용하는 주요 도구:

### 1. Bash (가장 중요!)

```bash
# 빌드 검증
npm run build
npm run compile
tsc --noEmit

# 테스트 검증
npm test
npm run test:unit
npm run test:integration
pytest
cargo test

# 린트 검증
npm run lint
eslint .
flake8

# 타입 검증
npm run type-check
mypy .
```

### 2. Read (로그 분석)

```json
{
  "name": "Read",
  "input": {
    "file_path": "/path/to/build.log",
    "offset": 900,
    "limit": 50
  }
}
```

빌드 실패 시 로그 읽고 원인 분석.

### 3. Grep (에러 패턴 찾기)

```json
{
  "name": "Grep",
  "input": {
    "pattern": "TypeError|ReferenceError|SyntaxError",
    "output_mode": "content"
  }
}
```

코드베이스에서 잠재적 에러 패턴 검색.

---

## 왜 검증 전용 Agent가 없는가?

### 이유 1: 검증은 작업의 일부

검증은 독립적인 작업이 아니라 **구현 워크플로의 마지막 단계**:

```
Read → Analyze → Edit → Verify
                         ↑
                     검증은 여기!
```

별도 agent로 분리할 필요가 없음.

### 이유 2: 검증은 단순함

검증은 대부분:
```bash
npm run build && npm test
```

이것만으로 충분. 복잡한 agent가 필요 없음.

### 이유 3: 즉각적인 피드백 필요

```
Edit → Bash(build) → 실패! → Read(error) → Edit(fix) → Bash(build) → 성공!
↑                                                                      ↑
수정                                                                재검증
```

검증과 수정이 **긴밀하게 연결**되어 있어서, 같은 agent에서 처리하는 게 효율적.

### 이유 4: general-purpose로 충분

복잡한 검증이 필요하면:
```json
{
  "subagent_type": "general-purpose",
  "prompt": "Implement feature X with comprehensive testing:\n1. Write code\n2. Write tests\n3. Run tests\n4. Fix failures\n5. Verify 100% pass"
}
```

general-purpose agent가 검증을 포함한 전체 작업 수행 가능.

---

## 시스템 프롬프트에서의 검증 지침

시스템 프롬프트에는 검증에 대한 **패턴 지침**이 포함되어 있음:

```
Task tool usage example:
<example>
user: "Please write a function that checks if a number is prime"
assistant: [writes function]
assistant: [Uses Task tool to launch code-reviewer agent]  ← 예시일 뿐!
</example>
```

**주의**: 이것은 **예시**일 뿐, 실제로 "code-reviewer" agent는 존재하지 않음!

실제로는:
```json
user: "Please write a function that checks if a number is prime"
assistant: Write (코드 작성)
assistant: Bash ("npm test") ← 직접 검증!
assistant: "✅ 테스트 통과!"
```

---

## 실제 검증 플로우 예시

### 예시 1: 간단한 버그 수정

```
User: "TypeError in utils/router.ts 수정해줘"
    ↓
Main:
  Turn 1: Read(utils/router.ts)
      → "182줄에 'modle' 오타 발견"

  Turn 2: Edit(utils/router.ts, "modle" → "model")
      → "수정 완료"

  Turn 3: Bash("npm run build")
      → "✅ Build successful in 2.3s"

  Turn 4: 최종 응답
      → "버그를 수정했습니다. 빌드 성공적으로 완료했습니다."
```

**총 4 turns, 검증 1회 (Bash)**

---

### 예시 2: 복잡한 리팩토링 (general-purpose)

```
User: "모든 API 엔드포인트를 async/await로 변환해줘"
    ↓
Main: Task(general-purpose, prompt="Convert all API endpoints...")
    ↓
general-purpose Agent:
  Turn 1: Grep("app\\.(get|post|put)", output_mode="files")
      → "12개 파일 발견"

  Turn 2-13: [각 파일마다]
      → Read(파일)
      → Edit(변환)
      → Bash("npm run build")  ← 검증!
      → 실패하면 → Read(에러) → Edit(수정) → 재검증

  Turn 14: Bash("npm test")  ← 최종 검증!
      → "✅ All tests passed"

  Turn 15: Final Report
      → "12개 파일, 45개 엔드포인트 변환 완료"
    ↓
Main: "리팩토링 완료! 모든 테스트 통과했습니다."
```

**검증 13회 (각 파일마다) + 최종 검증 1회 = 총 14회**

---

### 예시 3: 계획된 검증 (Plan Agent)

```
User: "새로운 인증 시스템 추가해줘"
    ↓
Main: Task(Plan)
    ↓
Plan Agent:
  Turn 1: Task(Explore, "Find existing auth code")
      → "인증 코드 없음"

  Turn 2: Read(src/server.ts)
      → "Fastify 사용 중"

  Turn 3: ExitPlanMode(plan={
      Phase 1: "Create JWT utilities",
      Phase 2: "Implement /login endpoint",
      Phase 3: "Add auth middleware",
      Phase 4: "Testing & Verification",
      steps: [
        "4.1: Write unit tests for JWT utils",
        "4.2: Test /login endpoint",
        "4.3: Test protected routes",
        "4.4: Run full test suite",
        "4.5: Manual verification checklist"
      ]
  })
    ↓
Main: [사용자에게 계획 제시]
    ↓
User: "좋아, 진행해"
    ↓
Main: [Phase 1-3 구현...]
    ↓
Main: Phase 4 시작 (검증!)
  Turn 20: Write(src/__tests__/jwt.test.ts)  ← 테스트 작성
  Turn 21: Bash("npm test jwt.test.ts")  ← 검증 1
      → "✅ 5/5 passed"

  Turn 22: Bash("npm test login.test.ts")  ← 검증 2
      → "✅ 8/8 passed"

  Turn 23: Bash("npm test")  ← 검증 3 (전체)
      → "✅ All 47 tests passed"

  Turn 24: 최종 응답
      → "인증 시스템 구현 완료! 모든 테스트 통과했습니다.

          수동 검증 체크리스트:
          □ /login으로 로그인 테스트
          □ JWT 토큰으로 보호된 라우트 접근
          □ 만료된 토큰으로 접근 시 거부 확인"
```

**검증 3회 + 수동 검증 체크리스트**

---

## 비교: 검증 전용 Agent가 있다면?

### 현재 (검증 Agent 없음):

```
Main → Edit → Bash(build) → 성공!
```

**3 turns, 빠름, 간단**

---

### 만약 검증 Agent가 있다면:

```
Main → Edit → Task(Verifier)
            ↓
       Verifier Agent:
         → Bash(build)
         → Bash(test)
         → Bash(lint)
         → Report
            ↓
       Main ← Report 받음
       Main → 사용자 응답
```

**7+ turns, 느림, 복잡**

---

## 요약

| 질문 | 답변 |
|------|------|
| **검증 전용 Agent 있나?** | ❌ 없음 |
| **검증은 어떻게?** | Main 또는 general-purpose agent가 Bash로 수행 |
| **검증 도구는?** | Bash (빌드, 테스트, 린트), Read (로그), Grep (에러 패턴) |
| **검증 패턴은?** | 1) Main 직접, 2) general-purpose 포함, 3) Plan의 단계, 4) 병렬 검증 |
| **왜 없나?** | 검증은 작업의 일부라 별도 agent 불필요, 즉각적 피드백 필요 |

---

## 핵심 인사이트

### 1. 검증은 "후처리"가 아닌 "통합 프로세스"

Claude Code의 철학:
```
Write → Verify → Fix → Verify → Success
        ↑         ↑        ↑
    즉각적 피드백 루프!
```

검증을 별도 agent로 분리하면 이 루프가 깨짐.

### 2. Bash tool의 강력함

```bash
npm run build  # 컴파일 검증
npm test       # 로직 검증
npm run lint   # 스타일 검증
npm audit      # 보안 검증
```

**하나의 도구로 모든 검증 가능**

### 3. TodoWrite로 검증 추적

```json
{
  "todos": [
    {"content": "Implement feature", "status": "completed"},
    {"content": "Write tests", "status": "completed"},
    {"content": "Run tests", "status": "in_progress"},  ← 검증 단계!
    {"content": "Fix failures", "status": "pending"},
    {"content": "Verify all pass", "status": "pending"}
  ]
}
```

검증은 **todo의 일부로 추적됨**.

---

**생성 날짜**: 2025-11-15
**목적**: Claude Code의 검증 시스템 이해
**결론**: 검증 전용 agent는 없으며, Main/general-purpose agent가 Bash 도구로 검증 수행
