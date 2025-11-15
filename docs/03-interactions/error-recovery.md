# Claude Code: 사이클 vs DAG

## 예상 구조 vs 실제 구조

### 💭 사용자의 예상: "PDCA-like 사이클"

```
      ┌─────────────────────────────────┐
      │                                 │
      ↓                                 │
┌──────────┐                            │
│   Plan   │ (계획 수립)                 │
└────┬─────┘                            │
     │                                  │
     ↓                                  │
┌──────────┐                            │
│ Research │ (조사/탐색)                 │
└────┬─────┘                            │
     │                                  │
     ↓                                  │
┌──────────┐                            │
│  Action  │ (실행/구현)                 │
└────┬─────┘                            │
     │                                  │
     ↓                                  │
┌──────────┐                            │
│ Verify   │ (검증)                      │
└────┬─────┘                            │
     │                                  │
     ↓                                  │
┌──────────┐                            │
│ Improve  │ (개선) ─────────────────────┘
└──────────┘     (다시 Plan으로!)

= 순환(Cycle) 구조
```

**이것은 PDCA (Plan-Do-Check-Act) 사이클**입니다.

---

### ✅ 실제 Claude Code: "DAG + 조건부 재시도"

```
Main Agent
    │
    ├→ Task(Explore) ← Research
    │      │
    │      └→ Report
    │          ↓
    ├→ Task(Plan) ← Plan
    │      │
    │      └→ Plan Report
    │          ↓
    ├→ Write/Edit × N ← Action
    │      ↓
    ├→ Bash(build) ← Verify
    │      ↓
    │   실패? ──Yes─→ Read(error) → Edit(fix) → Bash(build) ← Improve (조건부!)
    │      │
    │      No
    │      ↓
    └→ 완료! (end_turn)

= DAG + 조건부 분기 (진정한 사이클 아님!)
```

**차이점**:
- ❌ 순환 없음 (DAG)
- ✅ 조건부 재시도 (실패 시에만)
- ✅ 한 방향 흐름 (앞으로만)

---

## 상세 비교

### 1️⃣ Plan (계획)

#### 예상: 항상 계획부터 시작
```
모든 작업 → Plan Agent → 계획 생성 → 실행
```

#### 실제: 선택적으로만 사용
```
간단한 작업: Main → 바로 실행 (Plan 건너뜀!)

복잡한 작업: Main → Task(Plan) → 계획 생성 → 사용자 승인 → 실행
```

**예시**:
```json
// 간단 - Plan 없음
User: "README 읽어줘"
Main: Read → 응답  (Plan 건너뜀!)

// 복잡 - Plan 있음
User: "인증 시스템 추가해줘"
Main: Task(Plan) → 계획 제시 → 사용자 승인 → 실행
```

---

### 2️⃣ Research (조사)

#### 예상: 별도 단계로 항상 수행
```
Plan 완료 → Research Agent 실행 → 조사 완료 → Action
```

#### 실제: 필요시에만, 다양한 방식으로
```
패턴 1: 탐색 필요
Main → Task(Explore) → 조사 완료 → 실행

패턴 2: Plan 내부에서
Main → Task(Plan)
         └→ Task(Explore) ← Plan이 Research 요청!
              └→ Report
           └→ 계획 생성

패턴 3: Main이 직접
Main → Grep → Read → Edit  (Explore 건너뜀!)
```

**예시**:
```json
// Main이 직접 조사
User: "utils/router.ts에서 getModel 함수 찾아줘"
Main: Grep("getModel", "utils/router.ts") → Read → 응답
  (Explore 건너뜀!)

// Explore Agent 사용
User: "이 프로젝트의 모든 API 엔드포인트 찾아줘"
Main: Task(Explore, "Find all API endpoints", thoroughness="very thorough")
```

---

### 3️⃣ Action (실행)

#### 예상: 별도 Action Agent
```
Research 완료 → Action Agent → 구현
```

#### 실제: Main 또는 general-purpose가 수행
```
Main → Write/Edit/Bash (직접 실행)

또는

Main → Task(general-purpose)
         └→ Write/Edit × N
            └→ Report
       ← Report
Main → 응답
```

**Action 전용 Agent는 없음!**

---

### 4️⃣ Verification (검증)

#### 예상: 별도 Verification Agent
```
Action 완료 → Verification Agent → 검증 결과 → Improve or Complete
```

#### 실제: Bash 도구로 즉시 검증
```
Main → Edit (구현)
Main → Bash("npm run build") ← 검증 (agent 아님!)
    ↓
실패? → Read(error) → Edit(fix) → Bash(build) ← 재검증
    ↓
성공 → 완료!
```

**Verification Agent 없음!**

---

### 5️⃣ Improve (개선)

#### 예상: 개선 단계 후 다시 Plan으로
```
Verification 결과 → Improve Agent → 개선 → 다시 Plan
                                            ↑
                                         순환!
```

#### 실제: 조건부 재시도 (순환 아님!)
```
Bash(build) → 실패
    ↓
Read(error) → Edit(fix) → Bash(build) → 성공 → 완료!
                               ↓
                            실패하면 다시 반복 (최대 N회)
```

**진정한 사이클이 아니라 조건부 루프!**

```python
# 유사 코드
while True:
    build_result = bash("npm run build")
    if build_result.success:
        break  # 순환하지 않고 종료!
    else:
        error = read(build_result.log)
        edit(file, fix_based_on_error)
        # 다시 build (루프)
```

**Plan으로 돌아가지 않음!** 같은 단계를 재시도할 뿐.

---

## 완전한 플로우 비교

### 예상: PDCA 사이클

```
Iteration 1:
  Plan → Research → Action → Verify → Fail
                                       ↓
Iteration 2:                           ↓
  Plan (개선된) ← ← ← ← ← ← ← ← ← ← Improve
     ↓
  Research (다시!) → Action (다시!) → Verify → Success
```

**특징**:
- ✅ 전체 사이클 반복
- ✅ Plan도 다시 수립
- ✅ Research도 다시 수행
- ✅ 지속적 개선

---

### 실제: DAG + 조건부 재시도

```
Main
 ├→ [필요시] Task(Explore) → Report
 ├→ [필요시] Task(Plan) → Plan → 사용자 승인
 │
 ├→ Action (Write/Edit)
 │
 ├→ Verify (Bash)
 │    ↓
 │  실패? → Fix Loop (Read → Edit → Bash) × N
 │    │                                    ↑
 │    │                                    │
 │    └─→ 성공 또는 Max Retry ─────────────┘
 │                ↓
 └→ 완료 (end_turn)

Plan으로 돌아가지 않음! ❌
```

**특징**:
- ❌ 전체 사이클 반복 없음
- ❌ Plan 재수립 없음
- ❌ Research 재수행 없음
- ✅ 실패한 부분만 재시도
- ✅ 한 방향 흐름 (DAG)

---

## 왜 사이클이 아닌가?

### 이유 1: DAG 제약

```python
# 불가능한 시나리오
Main → Task(Plan) → Task(Explore) → Task(Main)  ❌
                                        ↑
                                    순환 불가!
```

**Subagent는 parent를 호출할 수 없음** → 순환 불가능

---

### 이유 2: 단방향 대화 흐름

```
messages = [
  {role: "user", content: "작업 요청"},
  {role: "assistant", content: [Plan]},
  {role: "user", content: [tool_result]},
  {role: "assistant", content: [Action]},
  {role: "user", content: [tool_result]},
  {role: "assistant", content: "완료!"}
]

시간 →→→→→→→
```

**messages는 append-only** → 뒤로 갈 수 없음 → 순환 불가능

---

### 이유 3: stop_reason 메커니즘

```python
while True:
    response = claude.messages.create(...)

    if response.stop_reason == "end_turn":
        break  # 대화 종료!

    elif response.stop_reason == "tool_use":
        result = execute_tools(response.content)
        messages.append(result)
        continue  # 다음 turn
```

**"end_turn"이 나오면 무조건 종료** → Plan으로 돌아갈 수 없음!

---

## 실제 사이클 같은 패턴

### 패턴 1: Verification Loop (가장 유사)

```python
# 실패 시 자동 수정 루프
def verify_and_fix():
    while retry_count < MAX_RETRY:
        result = bash("npm run build")

        if result.success:
            return "✅ Success"

        # Improve 단계
        error = read(result.log)
        edit(file, analyze_and_fix(error))
        retry_count += 1

    return "❌ Failed after N retries"
```

**이것이 가장 사이클에 가까운 구조!**

하지만:
- ✅ 지역적 루프 (Verify ↔ Improve만)
- ❌ 전역적 사이클 아님 (Plan으로 안 돌아감)

---

### 패턴 2: Multi-Step with Verification

```
User: "deprecated API 모두 업데이트"
    ↓
Main: Task(general-purpose)
    ↓
general-purpose:
  for each_file in files:
      Read(file)
      Edit(file)
      Bash(build)  ← Verify
          ↓
      실패? → Read(error) → Edit(fix) → Bash(build)  ← Improve Loop
          ↓
      성공 → 다음 파일로
```

**각 파일마다 "Verify → Improve" 미니 루프**

---

### 패턴 3: Plan → Execute → User Feedback → Re-plan

```
Turn 1:
User: "인증 시스템 추가"
    ↓
Main: Task(Plan) → "Phase 1-3 계획 제시"
    ↓
User: "Phase 2를 다르게 해줘"  ← 사용자 피드백!
    ↓
Main: Task(Plan) → "수정된 계획 제시"  ← 다시 Plan!
    ↓
User: "좋아, 진행해"
    ↓
Main: Execute plan...
```

**이것은 사용자 개입으로 인한 재계획** (자동 사이클 아님!)

---

## 진정한 사이클이 가능하려면?

### 필요한 것:

1. **CallParent Tool**
```json
{
  "name": "CallParent",
  "description": "Call parent agent to re-plan or get new instructions"
}
```

2. **순환 허용**
```
Main → Plan → Action → Verify → Improve → CallParent(Main)
                                              ↓
                                           Main → Plan (다시!)
```

3. **무한 대화**
```python
# stop_reason이 "end_turn"이어도 계속
while not user_satisfied:
    response = claude.messages.create(...)
    # 계속 반복
```

하지만 **모두 현재 Claude Code에는 없음!**

---

## 실제 워크플로우 예시

### 복잡한 작업: "전체 코드베이스 리팩토링"

```
Main Agent (대화 시작)
    │
    ├→ Turn 1: Task(Explore) ← Research
    │      ├→ Glob(src/**/*.ts)
    │      ├→ Grep("duplicate patterns")
    │      ├→ Read × 5
    │      └→ Report: "3개 중복 패턴 발견"
    │
    ├→ Turn 2: Task(Plan) ← Plan
    │      ├→ Read (컨텍스트)
    │      └→ Plan: "Phase 1-3"
    │
    ├→ Turn 3: 사용자 승인 대기
    │      User: "진행해"
    │
    ├→ Turn 4-10: TodoWrite + 구현 ← Action
    │      ├→ Write(utils/common.ts)
    │      ├→ Edit(file1.ts)
    │      ├→ Edit(file2.ts)
    │      ├→ Edit(file3.ts)
    │      ...
    │
    ├→ Turn 11: Bash("npm run build") ← Verify
    │      ↓
    │    실패! (TypeError)
    │
    ├→ Turn 12: Read(build.log) ← Analyze Error
    │      "file2.ts:45 - Cannot find name 'oldFunction'"
    │
    ├→ Turn 13: Edit(file2.ts) ← Improve (Fix)
    │      import 추가
    │
    ├→ Turn 14: Bash("npm run build") ← Re-verify
    │      ↓
    │    성공! ✅
    │
    └→ Turn 15: 최종 응답
         "리팩토링 완료! 3개 파일 수정, 빌드 성공"
         (end_turn)

Plan으로 돌아가지 않음! ❌
새로운 Explore 안 함! ❌
한 방향으로만 진행! ✅
```

**DAG 구조 유지!**

---

## 비교 요약표

| 특성 | 예상 (사이클) | 실제 (DAG) |
|------|--------------|-----------|
| **구조** | 순환 (Cycle) | 방향성 비순환 그래프 (DAG) |
| **Plan** | 항상 첫 단계 | 선택적 (복잡한 작업만) |
| **Research** | 별도 단계 | Task(Explore) 또는 Main이 직접 |
| **Action** | Action Agent | Main 또는 general-purpose |
| **Verify** | Verification Agent | Bash 도구 (Main이 직접) |
| **Improve** | 개선 후 Plan으로 | 조건부 재시도 (같은 단계만) |
| **반복** | 전체 사이클 반복 | 실패한 부분만 재시도 |
| **종료** | 사용자가 만족할 때 | stop_reason="end_turn" |
| **Parent 호출** | 가능 (순환 위해) | 불가능 (DAG 제약) |
| **지속적 개선** | ✅ | ❌ (한 번 완료하면 끝) |

---

## 실전 예시 비교

### 시나리오: "버그 수정 후 테스트 실패"

#### 예상 (사이클):
```
1. Plan: 버그 수정 계획
2. Research: 코드 분석
3. Action: 버그 수정
4. Verify: 테스트 실행 → 실패!
5. Improve: 원인 분석
6. 다시 Plan으로! (재계획)
   ├→ 새로운 접근 방법 계획
   ├→ Research (다시 조사)
   ├→ Action (다시 수정)
   └→ Verify → 성공!
```

**순환 구조, 재계획**

---

#### 실제 (DAG):
```
1. Read(파일) ← Research (Main이 직접)
2. Edit(버그 수정) ← Action (Main이 직접)
3. Bash(npm test) ← Verify (Main이 직접)
    ↓
  실패! "10 tests failed"
    ↓
4. Read(test output) ← Analyze
5. Edit(추가 수정) ← Improve
6. Bash(npm test) ← Re-verify
    ↓
  성공! ✅
7. 완료 (end_turn)
```

**재계획 없음, 즉시 수정 재시도**

---

## 핵심 차이점

### 1. 사이클 (예상)
```
┌─→ Plan ─→ Research ─→ Action ─→ Verify ─┐
│                                          ↓
└──────────── Improve ← ← ← ← ← ← ← ← ← ──┘
(무한 반복 가능)
```

### 2. DAG (실제)
```
Main ─→ [Plan] ─→ [Research] ─→ Action ─→ Verify ─┐
                                              ↓     │
                                           실패? ──Yes─→ Fix ─┐
                                              │            ↓   │
                                              No       Re-verify│
                                              ↓            ↑    │
                                           완료! ← ← ← 성공 ← ─┘
(한 방향, 조건부 루프)
```

---

## 실제 "사이클"이 필요한 경우

### 사용자 개입으로 구현 가능!

```
First Attempt:
User: "API 성능 개선해줘"
Main: Task(Plan) → Plan 제시
User: "진행해"
Main: 구현 → Verify → "30% 개선됨"
    ↓
User: "더 개선할 방법 찾아줘"  ← 사용자가 사이클 시작!
Main: Task(Explore) → 새로운 방법 발견
User: "그걸로 해줘"
Main: 구현 → Verify → "60% 개선됨" ✅
```

**사용자가 "사이클"을 만듦!**

하지만 이것도 messages는 append-only → 진정한 순환 아님.

---

## 왜 DAG인가? (설계 철학)

### 1. 예측 가능성
```
DAG: A → B → C → D (항상 같은 순서)
Cycle: A → B → C → A → B → C → ... (언제 끝날지 모름)
```

### 2. 비용 효율
```
DAG: 한 번 실행 → 완료 → 비용 예측 가능
Cycle: 계속 반복 → 비용 무한대 가능
```

### 3. 사용자 제어
```
DAG: 각 단계마다 사용자가 확인 가능
Cycle: 자동으로 계속 → 사용자 통제력 상실
```

### 4. 디버깅 용이
```
DAG: 실패 지점 명확
Cycle: 어느 반복에서 실패했는지 추적 어려움
```

---

## 결론

| 질문 | 답변 |
|------|------|
| **사이클 구조인가?** | ❌ 아님. DAG 구조. |
| **Plan → Research → Action → Verify → Improve 순서인가?** | ⚠️ 부분적으로만. Plan과 Research는 선택적. |
| **Improve 후 Plan으로 돌아가나?** | ❌ 아님. 같은 단계만 재시도. |
| **검증 실패 시 개선하나?** | ✅ 맞음. 하지만 조건부 루프, 순환 아님. |
| **지속적 개선 가능한가?** | ⚠️ 사용자 개입 시에만. 자동 사이클은 아님. |

---

## 최종 비교 다이어그램

### 예상 (PDCA 사이클)
```
        ┌────────────────┐
        │                │
        ↓                ↑
    ┌──────┐        ┌────────┐
    │ Plan │        │ Improve│
    └───┬──┘        └────↑───┘
        │                │
        ↓                │
  ┌──────────┐      ┌────────┐
  │ Research │      │ Verify │
  └────┬─────┘      └────↑───┘
       │                 │
       ↓                 │
  ┌──────────┐      ┌────┴───┐
  │  Action  │─────→│        │
  └──────────┘      └────────┘

  무한 순환 가능 ✅
```

### 실제 (DAG + 조건부)
```
Main
 │
 ├→ [Optional] Task(Plan)
 │      └→ Plan
 │
 ├→ [Optional] Task(Explore)
 │      └→ Report
 │
 ├→ Action (Write/Edit)
 │
 ├→ Verify (Bash)
 │    │
 │    ├→ Success → 완료
 │    │
 │    └→ Fail → Fix → Re-verify
 │              ↑         │
 │              └─────────┘
 │           (조건부 루프만!)
 │
 └→ end_turn

 Plan으로 돌아가지 않음 ❌
 한 방향 진행 (DAG) ✅
```

---

**생성 날짜**: 2025-11-15
**목적**: 예상 사이클 구조 vs 실제 DAG 구조 비교
**핵심**: Claude Code는 순환 사이클이 아니라 DAG + 조건부 재시도 구조
