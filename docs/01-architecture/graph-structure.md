# Claude Code 시스템 구조 분석: 그래프인가?

## 결론부터: **DAG (Directed Acyclic Graph)** 구조입니다

Claude Code 시스템은 **순환 없는 방향 그래프(DAG)**이며, **트리 구조**의 특수한 형태입니다.

---

## 1. 레벨별 구조 분석

### Level 1: 메인 대화 흐름 - **선형 리스트**

```
User Message
    ↓
Assistant Response
    ↓
User Message (tool_result)
    ↓
Assistant Response
    ↓
...

구조: 단방향 연결 리스트
순환: ❌ 없음
분기: ❌ 없음
병합: ❌ 없음
```

**messages 배열**:
```json
[
  {"role": "user", "content": "파일 읽어줘"},
  {"role": "assistant", "content": [...]},
  {"role": "user", "content": [{"type": "tool_result", ...}]},
  {"role": "assistant", "content": "파일 내용은..."}
]
```

이는 **선형 구조** - 시간순 일차원 배열입니다.

---

### Level 2: 도구 사용 흐름 - **트리 구조**

```
Main Conversation
    ├─→ Tool Call 1 (Read)
    │       └─→ Result
    │           └─→ 다시 Main으로
    │
    ├─→ Tool Call 2 (Edit)
    │       └─→ Result
    │           └─→ 다시 Main으로
    │
    └─→ Tool Call 3 (Bash)
            └─→ Result
                └─→ 다시 Main으로

구조: 트리 (하지만 항상 Main으로 복귀)
순환: ❌ 없음
분기: ✅ 있음 (병렬 도구 호출 가능)
병합: ✅ 있음 (모두 Main으로 복귀)
```

**병렬 도구 호출 예시**:
```json
{
  "role": "assistant",
  "content": [
    {"type": "tool_use", "name": "Bash", "id": "1"},
    {"type": "tool_use", "name": "Bash", "id": "2"},
    {"type": "tool_use", "name": "Bash", "id": "3"}
  ]
}

↓ 3개 도구 동시 실행

{
  "role": "user",
  "content": [
    {"type": "tool_result", "tool_use_id": "1", "content": "..."},
    {"type": "tool_result", "tool_use_id": "2", "content": "..."},
    {"type": "tool_result", "tool_use_id": "3", "content": "..."}
  ]
}
```

이는 **분기 후 병합**하는 구조 - 하지만 순환은 없습니다.

---

### Level 3: Multi-Agent 시스템 - **트리 구조** (무한 깊이)

```
Main Agent
    ├─→ Task(Explore)
    │       ├─→ Glob → result
    │       ├─→ Grep → result
    │       ├─→ Read → result
    │       └─→ Task(general-purpose)    ← 중첩!
    │               ├─→ Read → result
    │               ├─→ Edit → result
    │               └─→ Final Report
    │           └─→ Report to Explore
    │       └─→ Report to Main
    │
    ├─→ Task(Plan)
    │       ├─→ Read → result
    │       ├─→ Task(Explore)            ← 또 중첩!
    │       │       └─→ ...
    │       └─→ ExitPlanMode
    │           └─→ Plan to Main
    │
    └─→ Continue Main Conversation

구조: 무한 중첩 가능한 트리
순환: ❌ 없음 (Explore가 Main을 호출할 수 없음)
분기: ✅ 있음 (여러 subagent 동시 실행 가능)
병합: ✅ 있음 (모두 parent agent로 복귀)
깊이: ∞ (이론적으로 무한 중첩)
```

**중요한 제약**:
- Subagent는 **절대 parent를 호출할 수 없음**
- Subagent는 **sibling을 호출할 수 없음**
- 오직 **자식 subagent만 생성 가능** (Task tool 사용)

따라서 이는 **순환 없는 트리**입니다.

---

## 2. 그래프 이론 관점 분석

### 그래프 특성

```
노드(Vertex):
├─ Main Conversation
├─ Each Tool Call
├─ Each Subagent
└─ Each Tool Result

엣지(Edge):
├─ User Message → Assistant Response
├─ Assistant Tool Call → Tool Execution
├─ Tool Result → Assistant Response
└─ Task Call → Subagent Execution → Result
```

### DAG (Directed Acyclic Graph) 증명

**1. Directed (방향성)**: ✅
```
Main → Tool (O)
Tool → Main (X) - 도구가 Main을 호출할 수 없음

Main → Subagent (O)
Subagent → Main (X) - Subagent가 Main을 호출할 수 없음
Subagent → Sibling (X) - 형제 간 호출 불가
```

**2. Acyclic (순환 없음)**: ✅
```
순환이 생기려면:
Main → Subagent A → Subagent B → Main

하지만 불가능한 이유:
- Subagent는 Task tool을 사용해 자식만 생성 가능
- Parent나 Root를 호출할 방법이 없음
- 각 Subagent는 독립적인 subprocess
- 결과를 parent에게 "리턴"만 할 수 있음 (호출 아님)
```

**3. 병렬 분기**: ✅
```json
{
  "role": "assistant",
  "content": [
    {"type": "tool_use", "name": "Task", "input": {"subagent_type": "Explore"}},
    {"type": "tool_use", "name": "Task", "input": {"subagent_type": "Plan"}}
  ]
}
```

이는 **동일 depth에서 여러 subagent 동시 실행** 가능.

**4. 병합**: ✅
```
Explore Agent → Report → Main
Plan Agent → Report → Main

두 결과가 Main의 다음 turn에서 병합됨
```

---

## 3. 정확한 구조 정의

### Claude Code는 **"DAG with Tree Execution"**

```
특징:
✅ Directed: 모든 호출은 단방향
✅ Acyclic: 순환 없음
✅ Tree Structure: 부모-자식 관계
✅ Parallel Branches: 같은 depth에서 분기 가능
✅ Merge Points: 모든 분기는 parent로 병합
❌ Cycle: 불가능
❌ Cross-links: sibling 간 연결 불가
❌ Backward edges: 자식이 조상 호출 불가
```

### 시각화

```
┌─────────────────────────────────────────────────┐
│                 Main Agent                       │
│              (Root of DAG)                       │
└───────────┬─────────────────┬───────────────────┘
            │                 │
    ┌───────▼────────┐   ┌───▼────────────┐
    │ Task(Explore)  │   │  Task(Plan)    │  ← Parallel (같은 depth)
    └───────┬────────┘   └───┬────────────┘
            │                │
    ┌───────▼────┐      ┌───▼─────────┐
    │   Glob     │      │ Task(Explore)│  ← 중첩 가능
    └───────┬────┘      └───┬─────────┘
            │                │
    ┌───────▼────┐      ┌───▼────┐
    │   Grep     │      │  Glob  │
    └───────┬────┘      └───┬────┘
            │                │
    ┌───────▼────┐      ┌───▼────┐
    │   Read     │      │  Read  │
    └───────┬────┘      └───┬────┘
            │                │
            │                │
    ┌───────▼────┐      ┌───▼────────┐
    │  Report    │      │  Report    │
    └───────┬────┘      └───┬────────┘
            │                │
            └────────┬───────┘
                     │
            ┌────────▼─────────┐
            │   Main Agent     │  ← Merge point
            │  (continues...)  │
            └──────────────────┘
```

---

## 4. 왜 순환이 불가능한가?

### 기술적 제약

**1. Subprocess 격리**
```javascript
// Main Agent
const subprocess = fork('./agent-runner.js');
subprocess.send({
  system: systemPrompt,
  tools: tools,
  messages: [{role: "user", content: taskPrompt}]
});

subprocess.on('message', (result) => {
  // Parent는 result만 받음
  // Subprocess는 이미 종료됨
});
```

Subagent는 **별도 프로세스**로 실행되고, 완료 후 **종료**됩니다.
종료된 프로세스는 다시 parent를 호출할 수 없습니다.

**2. 독립적인 컨텍스트**
```
Main Context:
{
  messages: [
    {role: "user", content: "리팩토링해줘"},
    {role: "assistant", content: [..., tool_use(Task)]},
    {role: "user", content: [tool_result(Explore report)]}
  ]
}

Explore Context (독립!):
{
  messages: [
    {role: "user", content: "Search for duplicates..."}
  ]
}
```

Explore는 **Main의 messages를 볼 수 없습니다**.
따라서 Main으로 "돌아갈" 방법이 없습니다.

**3. Tool 제한**
```
Main Agent:
- ✅ Task tool 있음 → Subagent 생성 가능
- ✅ "ParentAgent" tool은 없음 → Parent 호출 불가

Subagent:
- ✅ Task tool 있음 → 자식 Subagent 생성 가능
- ❌ "CallParent" tool 없음 → Parent 호출 불가
- ❌ "CallSibling" tool 없음 → 형제 호출 불가
```

**오직 "리턴"만 가능** - 마지막 응답이 자동으로 parent에게 전달됨.

---

## 5. 그래프 vs 트리 비교

| 특성 | 트리 | DAG | Claude Code |
|------|------|-----|-------------|
| **단일 루트** | ✅ | ⚠️ | ✅ (Main Agent) |
| **방향성** | ✅ (parent→child) | ✅ | ✅ (caller→callee) |
| **순환** | ❌ | ❌ | ❌ |
| **자식→부모 엣지** | ❌ | ⚠️ (가능) | ❌ |
| **병렬 분기** | ⚠️ (다중 자식) | ✅ | ✅ (병렬 도구 호출) |
| **크로스 링크** | ❌ | ✅ | ❌ |
| **깊이 제한** | ❌ | ❌ | ❌ (무한 중첩) |

Claude Code는 **트리의 모든 제약을 가진 DAG** = **트리 구조**

---

## 6. 실제 예시로 확인

### 예시 1: 선형 흐름 (리스트)

```
User: "README 읽어줘"
    ↓
Main: Read tool
    ↓
CLI: Execute Read
    ↓
Main: "내용은..."
```

**구조**: 연결 리스트

### 예시 2: 병렬 도구 (DAG)

```
User: "git 상태 확인해줘"
    ↓
Main: ┬→ Bash(git status)
      ├→ Bash(git diff)
      └→ Bash(git log)
    ↓
CLI: 3개 동시 실행
    ↓
Main: 결과 통합 분석
```

**구조**: 분기 후 병합 = DAG

### 예시 3: 중첩 에이전트 (트리)

```
User: "중복 코드 제거"
    ↓
Main → Task(Explore)
           ↓
       Explore → Glob
                 Grep
                 Read
                 Task(general-purpose)
                     ↓
                 general → Read
                           Edit
                           Final Report
                     ↓
                 Explore (report받음)
           ↓
       Main (report받음)
    ↓
Main → Task(Plan)
           ↓
       Plan → Read
              ExitPlanMode
           ↓
       Main (plan받음)
    ↓
Main → 실행 (Write, Edit × 6, Bash)
```

**구조**: 깊이 무한 트리

---

## 7. 그래프 알고리즘 적용 가능성

### 적용 가능한 알고리즘

✅ **DFS (Depth-First Search)**
```
Main → Task(Explore) → Task(general-purpose) → ...
각 subagent를 끝까지 실행 후 다음으로
```

✅ **BFS (Breadth-First Search)** (병렬 실행 시)
```
Main → [Task(Explore), Task(Plan)] 동시 실행
    → 모두 완료 후 다음 단계
```

✅ **Topological Sort**
```
실행 순서:
1. Main (depth 0)
2. Explore, Plan (depth 1) - 병렬
3. Explore의 자식 (depth 2)
4. Plan의 자식 (depth 2)
...
```

✅ **Post-order Traversal**
```
자식 먼저 완료 → 부모 계속
general-purpose 완료 → Explore 계속 → Main 계속
```

❌ **Cycle Detection** (필요 없음 - 순환 불가능)
❌ **Shortest Path** (경로가 하나뿐)
❌ **Strongly Connected Components** (순환 없음)

---

## 8. 요약

| 관점 | 구조 | 설명 |
|------|------|------|
| **messages 배열** | 연결 리스트 | 시간순 선형 구조 |
| **도구 호출** | DAG | 분기 가능, 순환 없음 |
| **Multi-agent** | 트리 | 부모-자식만, 순환/크로스링크 없음 |
| **전체 시스템** | **DAG (트리의 형태)** | 방향성, 비순환, 병렬 분기 가능 |

---

## 9. 핵심 결론

### Claude Code는:
```
1. 메시지 레벨: 연결 리스트
2. 도구 레벨: DAG (분기 후 병합)
3. 에이전트 레벨: 트리 (무한 깊이)
4. 전체: DAG (트리 구조를 가진 방향성 비순환 그래프)
```

### 순환이 불가능한 이유:
```
1. Subprocess 격리 → 종료 후 재호출 불가
2. 독립 컨텍스트 → 상위 context 접근 불가
3. Tool 제한 → "CallParent" 도구 없음
4. 단방향 리턴 → 결과만 전달, 호출 불가
```

### 그래프 특성:
```
✅ Directed (방향성)
✅ Acyclic (비순환)
✅ Tree-like (트리 구조)
✅ Parallel Branches (병렬 분기)
✅ Single Root (단일 루트: Main Agent)
❌ Cycles (순환 없음)
❌ Cross-links (크로스 링크 없음)
```

**최종 답변**: Claude Code는 **DAG (Directed Acyclic Graph) 구조**이며, 더 정확하게는 **무한 깊이의 트리 구조**입니다.
