# 사용자 피드백으로 목표 확장 시 루프 구조

## 핵심 질문:
**"사용자가 피드백 주면서 목표를 확장시킬 때, 어떻게 루프가 도는가?"**

---

## 답변:
**루프가 돌지 않습니다! 대화가 "계속 확장"됩니다.**

---

## 실제 예시: 점진적 목표 확장

### 시나리오:

```
User [Turn 1]: "README 읽어줘"
    ↓
Claude: Read(README.md) → "README 내용은..."
    ↓
User [Turn 2]: "좋아, 이제 package.json도 읽어줘"  ← 목표 확장!
    ↓
Claude: Read(package.json) → "package.json 내용은..."
    ↓
User [Turn 3]: "두 파일을 비교 분석해줘"  ← 또 확장!
    ↓
Claude: [비교 분석] → "차이점은..."
    ↓
User [Turn 4]: "의존성을 최신 버전으로 업데이트해줘"  ← 더 확장!
    ↓
Claude: Edit(package.json) → Bash(npm install) → "업데이트 완료!"
```

---

## messages 배열로 보면:

```json
{
  "messages": [
    // Turn 1
    {"role": "user", "content": "README 읽어줘"},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Read", ...}]},
    {"role": "user", "content": [{"type": "tool_result", ...}]},
    {"role": "assistant", "content": "README 내용은..."},

    // Turn 2 - 목표 확장!
    {"role": "user", "content": "좋아, 이제 package.json도 읽어줘"},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Read", ...}]},
    {"role": "user", "content": [{"type": "tool_result", ...}]},
    {"role": "assistant", "content": "package.json 내용은..."},

    // Turn 3 - 또 확장!
    {"role": "user", "content": "두 파일을 비교 분석해줘"},
    {"role": "assistant", "content": "차이점은..."},

    // Turn 4 - 더 확장!
    {"role": "user", "content": "의존성을 최신 버전으로 업데이트해줘"},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Edit", ...}]},
    // ...
  ]
}
```

**계속 append만 됨!** (뒤로 돌아가지 않음)

---

## 시각화: 루프처럼 보이지만 실제로는 선형

### 사용자 관점 (루프처럼 느껴짐):

```
┌─────────────────────────────────────┐
│                                     │
│  User: 요청 1                        │
│    ↓                                │
│  Claude: 응답 1                      │
│    ↓                                │
│  User: 피드백 → 요청 2  ← 루프?      │
│    ↓                                │
│  Claude: 응답 2                      │
│    ↓                                │
│  User: 피드백 → 요청 3  ← 또 루프?   │
│    ↓                                │
│  Claude: 응답 3                      │
│    ↓                                │
│  ...                                │
│                                     │
└─────────────────────────────────────┘
```

**마치 "Plan → Do → Feedback → Re-plan" 사이클처럼 보임!**

---

### 실제 시스템 관점 (선형!):

```
시간 →→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→

t1: User "요청 1"
t2: Claude [응답 1]
t3: User "피드백 + 요청 2"  ← 새로운 입력 (루프 아님!)
t4: Claude [응답 2]
t5: User "피드백 + 요청 3"  ← 또 새로운 입력
t6: Claude [응답 3]
...

messages 길이: 1 → 2 → 3 → 4 → 5 → 6 → ...
```

**뒤로 돌아가지 않음! 계속 앞으로!**

---

## 핵심 차이점

### ❌ 진짜 루프 (Claude Code 아님):

```python
while not user_satisfied:
    plan = create_plan()
    result = execute(plan)

    if not user_satisfied:
        # 처음으로 돌아가서 다시 계획 수립
        continue  # ← 루프!
```

**특징**:
- Plan 단계로 자동 복귀
- 사용자 입력 없이 자동 반복
- 무한 루프 위험

---

### ✅ Claude Code 방식 (대화 확장):

```python
messages = []

while True:
    # 사용자 입력 대기
    user_input = wait_for_user()  # ← 블로킹!
    if user_input == "quit":
        break

    messages.append({"role": "user", "content": user_input})

    # Claude 응답
    response = claude.create(messages=messages)
    messages.append({"role": "assistant", "content": response})

    if response.stop_reason == "end_turn":
        # 다시 사용자 입력 대기로...
        continue  # ← 사용자 입력 기다림!
```

**특징**:
- 항상 사용자 입력 대기
- 사용자가 "루프"를 제어
- 무한 루프 없음 (사용자가 언제든 멈출 수 있음)

---

## 복잡한 예시: 점진적 리팩토링

### 시나리오:

```
User [Turn 1]: "코드베이스에서 중복 코드 찾아줘"
    ↓
Claude: Task(Explore) → "3개 중복 패턴 발견"
    ↓
User [Turn 2]: "좋아, 첫 번째 패턴만 먼저 리팩토링해줘"  ← 목표 축소!
    ↓
Claude: Edit × 3 → Bash(build) → "완료!"
    ↓
User [Turn 3]: "잘됐네! 두 번째 패턴도 해줘"  ← 목표 확장!
    ↓
Claude: Edit × 2 → Bash(build) → "완료!"
    ↓
User [Turn 4]: "마지막 패턴은 좀 다르게... 유틸 함수 말고 클래스로 만들어줘"  ← 요구사항 변경!
    ↓
Claude: Write(class) → Edit × 3 → Bash(build) → "완료!"
    ↓
User [Turn 5]: "완벽해! 이제 테스트 작성해줘"  ← 완전히 새로운 목표!
    ↓
Claude: Write(test) → Bash(npm test) → "✅ All pass!"
```

---

### messages 배열:

```json
{
  "messages": [
    // Turn 1: 초기 목표
    {"role": "user", "content": "코드베이스에서 중복 코드 찾아줘"},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Task", "input": {"subagent_type": "Explore"}}]},
    {"role": "user", "content": [{"type": "tool_result", "content": "3개 중복 패턴 발견..."}]},
    {"role": "assistant", "content": "3개 중복 패턴을 발견했습니다..."},

    // Turn 2: 목표 축소
    {"role": "user", "content": "좋아, 첫 번째 패턴만 먼저 리팩토링해줘"},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Edit", ...}]},
    // ... (Edit × 3, Bash)
    {"role": "assistant", "content": "첫 번째 패턴 리팩토링 완료!"},

    // Turn 3: 목표 확장
    {"role": "user", "content": "잘됐네! 두 번째 패턴도 해줘"},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Edit", ...}]},
    // ... (Edit × 2, Bash)
    {"role": "assistant", "content": "두 번째 패턴 리팩토링 완료!"},

    // Turn 4: 요구사항 변경
    {"role": "user", "content": "마지막 패턴은 좀 다르게... 클래스로 만들어줘"},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Write", ...}]},
    // ... (Write, Edit × 3, Bash)
    {"role": "assistant", "content": "클래스 방식으로 완료!"},

    // Turn 5: 새로운 목표
    {"role": "user", "content": "완벽해! 이제 테스트 작성해줘"},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Write", ...}]},
    // ...
  ]
}
```

**messages 길이: 4 → 8 → 12 → 16 → 20...**

**계속 증가만! 뒤로 안 감!**

---

## 왜 이게 "루프"처럼 느껴지는가?

### 사용자 경험:

```
1. 요청
2. 결과 확인
3. 피드백
4. 다시 1번으로?  ← 루프처럼 느껴짐!
```

**하지만 실제로는:**

```
1. 요청 A
2. 결과 A 확인
3. 새로운 요청 B (A에 대한 피드백 포함)
4. 결과 B 확인
5. 새로운 요청 C (B에 대한 피드백 포함)
...
```

**각 요청이 독립적!** (루프 아님)

---

## 대화 컨텍스트의 역할

### Claude는 전체 대화를 기억:

```python
# Turn 5에서 Claude가 보는 것:
context = {
    "Turn 1": "중복 코드 찾기",
    "Turn 2": "첫 번째 패턴 리팩토링",
    "Turn 3": "두 번째 패턴 리팩토링",
    "Turn 4": "세 번째 패턴 클래스로",
    "Turn 5": "테스트 작성"  ← 현재
}

# Claude의 이해:
"사용자가 점진적으로 리팩토링을 진행 중이고,
이제 테스트를 원하는구나."
```

**컨텍스트 덕분에 연속성 유지!**

---

## 진짜 "Re-plan" 예시

### 목표가 완전히 바뀔 때:

```
User [Turn 1]: "인증 시스템 추가해줘"
    ↓
Claude: Task(Plan)
    ↓
Plan Agent:
    Phase 1: JWT 유틸 생성
    Phase 2: /login 엔드포인트
    Phase 3: 인증 미들웨어
    ↓
Claude: "이렇게 진행할까요?"
    ↓
User [Turn 2]: "아니야, JWT 말고 OAuth2로 해줘"  ← 계획 변경!
    ↓
Claude: Task(Plan)  ← 다시 계획!
    ↓
Plan Agent:
    Phase 1: OAuth2 클라이언트 설정
    Phase 2: /auth/google 엔드포인트
    Phase 3: 토큰 검증 미들웨어
    ↓
Claude: "OAuth2 기반으로 다시 계획했습니다"
    ↓
User [Turn 3]: "좋아, 진행해"
    ↓
Claude: [구현 시작]
```

---

### messages 배열:

```json
{
  "messages": [
    // Turn 1: 초기 계획
    {"role": "user", "content": "인증 시스템 추가해줘"},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Task", "input": {"subagent_type": "Plan"}}]},
    {"role": "user", "content": [{"type": "tool_result", "content": "JWT 기반 계획..."}]},
    {"role": "assistant", "content": "JWT 방식으로 계획했습니다. 진행할까요?"},

    // Turn 2: 계획 변경 (Re-plan!)
    {"role": "user", "content": "아니야, JWT 말고 OAuth2로 해줘"},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Task", "input": {"subagent_type": "Plan"}}]},
    {"role": "user", "content": [{"type": "tool_result", "content": "OAuth2 기반 계획..."}]},
    {"role": "assistant", "content": "OAuth2 방식으로 다시 계획했습니다."},

    // Turn 3: 진행
    {"role": "user", "content": "좋아, 진행해"},
    // ...
  ]
}
```

**Task(Plan)을 두 번 호출했지만:**
- ❌ Plan Agent가 자동으로 재실행된 게 아님
- ✅ 사용자 요청으로 새로운 Plan Agent 실행

---

## 자동 Re-plan vs 수동 Re-plan

### ❌ 자동 Re-plan (Claude Code 아님):

```python
while True:
    plan = create_plan()
    result = execute(plan)

    if verify(result) == False:
        # 자동으로 다시 계획
        continue  # ← 사용자 개입 없이!
```

---

### ✅ 수동 Re-plan (Claude Code):

```python
# Turn 1
plan = create_plan()
show_to_user(plan)
user_input = wait_for_user()  # ← 블로킹!

# Turn 2 (사용자가 변경 요청)
if "다르게" in user_input:
    plan = create_plan()  # ← 사용자 요청으로!
    show_to_user(plan)
    user_input = wait_for_user()

# Turn 3 (사용자가 승인)
if "진행" in user_input:
    execute(plan)
```

**항상 사용자가 제어!**

---

## 토큰 비용 관점

### 목표 확장 시:

```
Turn 1:
  Input: 50k (system) + 0.1k (user) = 50.1k tokens
  Output: 0.5k tokens

Turn 2 (목표 확장):
  Input: 50k (cached!) + 1.5k (history) + 0.1k (user) = 51.6k tokens
                          ↑
                     Turn 1 대화 포함!
  Output: 0.5k tokens

Turn 3 (또 확장):
  Input: 50k (cached!) + 3k (history) + 0.1k (user) = 53.1k tokens
                        ↑
                   Turn 1-2 대화 포함!
  Output: 0.5k tokens
```

**대화가 길어질수록 history가 증가!**

하지만 **system은 캐시됨** (50k를 매번 새로 안 보냄)

---

## 실전 패턴들

### 패턴 1: 점진적 구현

```
User: "로그인 기능 추가해줘"
Claude: [로그인 구현]

User: "좋아, 이제 로그아웃도 추가해줘"  ← 확장
Claude: [로그아웃 구현]

User: "완벽해! 세션 타임아웃도 넣어줘"  ← 또 확장
Claude: [타임아웃 구현]
```

**각 turn은 독립적이지만, 컨텍스트는 누적!**

---

### 패턴 2: 반복적 개선

```
User: "API 성능 개선해줘"
Claude: [캐싱 추가] → "30% 개선됨"

User: "더 개선할 방법은?"  ← 피드백 + 확장
Claude: Task(Explore) → "인덱스 추가 제안"

User: "그거 해줘"  ← 새 목표
Claude: [인덱스 추가] → "60% 개선됨"

User: "완벽해! 이제 문서 업데이트해줘"  ← 완전히 새 목표
Claude: [문서 작성]
```

**마치 "Plan → Do → Check → Act" 사이클처럼 보이지만,
실제로는 사용자가 각 단계를 명시적으로 요청!**

---

### 패턴 3: 실패 후 전략 변경

```
User: "모든 API를 GraphQL로 마이그레이션해줘"
Claude: Task(Plan) → "Phase 1-5 계획"

User: "진행해"
Claude: [구현 시작] → Write, Edit × 10

Claude: Bash(npm test) → "❌ 27 tests failed"
Claude: "마이그레이션 중 많은 테스트가 실패했습니다."

User: "일단 중단! 하나씩 마이그레이션하자"  ← 전략 변경!
Claude: "알겠습니다. 어떤 API부터 시작할까요?"

User: "/users API만 먼저 해줘"  ← 새 목표
Claude: [/users만 마이그레이션]
```

**Claude가 자동으로 전략 변경 안 함!**
**사용자가 명시적으로 지시!**

---

## 비교 요약

| 특성 | 자동 루프 | Claude Code (사용자 제어) |
|------|----------|------------------------|
| **구조** | while True: ... | user_input → response → wait |
| **반복** | 자동 | 사용자 요청 시 |
| **종료** | 조건 만족 시 | 사용자가 언제든 |
| **목표 변경** | 자동 재계획 | 사용자가 명시적 요청 |
| **비용** | 예측 불가 | 예측 가능 |
| **제어권** | 시스템 | 사용자 |
| **messages** | 초기화 가능 | append-only |
| **컨텍스트** | 매번 새로 | 누적 |

---

## 핵심 인사이트

### 1. "루프"는 사용자가 만든다

```
Claude는 루프를 돌지 않음.
사용자가 계속 요청하는 것!

Claude: "완료했습니다" (end_turn) → 대기
User: "이제 이것도 해줘" → 새 요청
Claude: "알겠습니다" → 실행
Claude: "완료했습니다" (end_turn) → 대기
User: "또 이것도..." → 또 새 요청
...

무한처럼 보이지만, 각 turn은 독립적!
```

---

### 2. 컨텍스트가 연속성을 제공

```
Turn 1: "A 해줘" → "A 완료"
Turn 2: "B도 해줘"

Claude가 보는 것:
  Context: [Turn 1에서 A를 했음]
  Current: "B도 해줘"
  Understanding: "A에 이어서 B를 원하는구나"

사용자는 "루프"처럼 느끼지만,
시스템은 선형 대화로 처리!
```

---

### 3. 비용 효율성

```
자동 루프:
  Plan(1) → Execute(1) → Fail
  Plan(2) → Execute(2) → Fail
  Plan(3) → Execute(3) → Success
  비용: Plan × 3, Execute × 3

사용자 제어:
  Plan(1) → Show to user
  User: "수정해줘"
  Plan(2) → Show to user
  User: "진행해"
  Execute(2) → Success
  비용: Plan × 2, Execute × 1 (사용자가 실패 방지!)
```

---

## 최종 정리

### 질문: "사용자 피드백으로 목표 확장 시 루프는?"

### 답변:

**"루프가 돌지 않습니다. 대화가 확장됩니다."**

```
사용자 관점:
  요청 → 결과 → 피드백 → 요청 → 결과 → ...
  (루프처럼 느껴짐!)

시스템 관점:
  messages[0] → messages[1] → messages[2] → ...
  (계속 추가만 됨!)

핵심:
  ✅ 사용자가 "루프"를 제어
  ✅ 각 turn은 독립적
  ✅ 컨텍스트가 연속성 제공
  ❌ 자동 반복 없음
  ❌ 진짜 순환 구조 아님
```

---

**생성 날짜**: 2025-11-15
**목적**: 사용자 피드백 시 "루프"의 정체 이해
**핵심**: 루프가 아니라 사용자 제어 하의 대화 확장!
