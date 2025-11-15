# 커스텀 Agent 구현 가이드

> Subagent 시스템을 구현하여 복잡한 작업을 분해하기

---

## Subagent 시스템 개요

### 핵심 개념

```
Main Agent
    │
    ├→ Task("Explore", "Find API endpoints")
    │      ↓
    │   [Subagent 실행 - 독립 프로세스]
    │      ├─ Glob, Grep, Read
    │      └─ Report 생성
    │      ↓
    ├─ [Report 받음]
    │
    └→ 계속 작업...
```

**특징**:
- ✅ 독립적인 대화 컨텍스트
- ✅ 같은 시스템 프롬프트 + 도구
- ✅ Task의 prompt가 첫 user 메시지
- ✅ 무한 중첩 가능 (DAG 제약)

---

## Task Tool 구현

### 1. 도구 정의

```typescript
const TOOLS = [
  {
    name: "Task",
    description: "Launch a subagent to handle complex tasks autonomously",
    input_schema: {
      type: "object",
      properties: {
        subagent_type: {
          type: "string",
          enum: ["general-purpose", "Explore", "Plan"],
          description: "Type of agent to launch",
        },
        description: {
          type: "string",
          description: "Short 3-5 word description of the task",
        },
        prompt: {
          type: "string",
          description: "Detailed instructions for the subagent",
        },
        model: {
          type: "string",
          enum: ["sonnet", "opus", "haiku"],
          description: "Optional model to use",
        },
      },
      required: ["subagent_type", "description", "prompt"],
    },
  },
  // ... 다른 도구들
];
```

---

### 2. Subagent 실행 엔진

```typescript
async function executeTask(input: {
  subagent_type: string;
  description: string;
  prompt: string;
  model?: string;
}): Promise<string> {
  // 1. 새로운 messages 생성
  const subagentMessages = [
    {
      role: "user",
      content: input.prompt, // ← Task의 prompt가 첫 메시지!
    },
  ];

  // 2. Subagent 대화 루프
  while (true) {
    const response = await client.messages.create({
      model: input.model || "claude-sonnet-4",
      max_tokens: 8192,
      system: SYSTEM_PROMPT, // ← 같은 시스템 프롬프트!
      tools: TOOLS, // ← 같은 도구!
      messages: subagentMessages,
    });

    if (response.stop_reason === "end_turn") {
      // Subagent 완료!
      const report = extractText(response.content);
      return report; // Parent에게 리턴
    }

    if (response.stop_reason === "tool_use") {
      // Subagent도 도구 사용 가능!
      subagentMessages.push({ role: "assistant", content: response.content });

      const toolResults = await executeTools(response.content);
      subagentMessages.push({ role: "user", content: toolResults });

      // 계속 반복
      continue;
    }
  }
}
```

---

### 3. Main Agent 통합

```typescript
async function executeTools(content: Array<any>): Promise<Array<any>> {
  const results = [];

  for (const block of content) {
    if (block.type !== "tool_use") continue;

    try {
      let result;

      switch (block.name) {
        case "Task":
          // Subagent 실행!
          result = await executeTask(block.input);
          break;

        case "Read":
          result = await readFile(block.input.file_path);
          break;

        // ... 다른 도구들

        default:
          throw new Error(`Unknown tool: ${block.name}`);
      }

      results.push({
        type: "tool_result",
        tool_use_id: block.id,
        content: result,
      });
    } catch (error) {
      // 에러 처리...
    }
  }

  return results;
}
```

---

## Agent 타입별 구현

### 1. general-purpose Agent

**용도**: 복잡한 멀티스텝 작업, 불확실한 검색

**시스템 프롬프트 추가**:
```markdown
## general-purpose Agent

Use this agent for:
- Complex multi-step tasks
- Uncertain searches (may need multiple tries)
- Automated workflows

The agent has access to ALL tools and can work autonomously.

Example:
\```json
{
  "name": "Task",
  "input": {
    "subagent_type": "general-purpose",
    "description": "Update deprecated APIs",
    "prompt": "Find all usages of oldFunction() and replace with newFunction().\n\n1. Search all files\n2. For each file:\n   - Read context\n   - Replace\n   - Verify with build\n3. Report results"
  }
}
\```
```

---

### 2. Explore Agent

**용도**: 코드베이스 탐색

**시스템 프롬프트 추가**:
```markdown
## Explore Agent

Use this agent for:
- Finding files by patterns
- Searching code for keywords
- Understanding codebase architecture

Thoroughness levels:
- "quick": Basic search
- "medium": Moderate exploration
- "very thorough": Comprehensive analysis

Example:
\```json
{
  "name": "Task",
  "input": {
    "subagent_type": "Explore",
    "description": "Find API endpoints",
    "prompt": "Search for all API endpoints.\n\nLook for:\n- Express/Fastify routes\n- HTTP methods\n- Route paths\n\nFocus on src/**/*.ts\n\nThoroughness: medium\n\nReturn structured list with file, line, method, path."
  }
}
\```
```

**구현 팁**:
```typescript
// Explore Agent는 일반 agent와 동일하지만,
// 시스템 프롬프트에서 thoroughness 파라미터 언급
// 실제 구현은 LLM이 프롬프트를 해석하여 처리
```

---

### 3. Plan Agent

**용도**: 구현 계획 수립

**ExitPlanMode 도구 추가**:
```typescript
{
  name: "ExitPlanMode",
  description: "Exit plan mode with a finalized plan",
  input_schema: {
    type: "object",
    properties: {
      plan: {
        type: "string",
        description: "The finalized implementation plan (supports markdown)"
      }
    },
    required: ["plan"]
  }
}
```

**시스템 프롬프트 추가**:
```markdown
## Plan Agent

Use this agent for:
- Creating implementation plans for complex features
- Breaking down large tasks into phases

The Plan Agent MUST:
1. Analyze requirements
2. Research existing code (can use Task(Explore))
3. Create detailed phase-by-phase plan
4. Use ExitPlanMode to present the plan
5. NEVER implement - only plan!

Example:
\```json
{
  "name": "Task",
  "input": {
    "subagent_type": "Plan",
    "description": "Plan auth implementation",
    "prompt": "Create implementation plan for JWT authentication.\n\nRequirements:\n- Email/password login\n- JWT tokens\n- Protected routes\n\nAnalyze codebase and create phase-by-phase plan."
  }
}
\```

Plan Agent 내부:
\```json
{
  "name": "ExitPlanMode",
  "input": {
    "plan": "## Phase 1: JWT Utils\n...\n## Phase 2: Login Endpoint\n..."
  }
}
\```
```

**구현**:
```typescript
case "ExitPlanMode":
  // Plan Agent만 사용 가능
  if (currentAgent !== "Plan") {
    throw new Error("ExitPlanMode only available in Plan agent");
  }

  // 계획을 리턴하고 종료
  return block.input.plan;
```

---

## 중첩 Agent 예시

```typescript
// Main Agent
User: "코드베이스 리팩토링"
    ↓
Main: Task(Explore, "Find duplicates")
    ↓
// Explore Agent (subprocess 1)
Explore:
  Turn 1: Glob("src/**/*.ts")
  Turn 2: Grep("duplicate patterns")
  Turn 3: Read × 5
  Turn 4: Report: "3 patterns found"
    ↓
// Main Agent
Main: [Report 받음]
Main: Task(Plan, "Create refactoring plan")
    ↓
// Plan Agent (subprocess 2)
Plan:
  Turn 1: Read(context)
  Turn 2: Task(Explore, "Find utility usage") ← 중첩!
      ↓
  // Explore Agent (subprocess 2-1)
  Explore:
    Turn 1: Grep("import.*utils")
    Turn 2: Report
      ↓
  // Plan Agent
  Plan: [Explore report 받음]
  Plan: ExitPlanMode(detailed plan)
    ↓
// Main Agent
Main: [Plan 받음]
Main: 사용자에게 계획 제시
    ↓
User: "진행해"
    ↓
Main: [구현...]
```

---

## 도구 제한 (statusline-setup 예시)

```typescript
async function executeTask(input: TaskInput): Promise<string> {
  // Agent 타입별 도구 필터링
  let allowedTools = TOOLS;

  if (input.subagent_type === "statusline-setup") {
    // Read와 Edit만 허용
    allowedTools = TOOLS.filter((t) =>
      ["Read", "Edit"].includes(t.name)
    );
  }

  // Subagent 실행
  while (true) {
    const response = await client.messages.create({
      model: input.model || "claude-sonnet-4",
      max_tokens: 8192,
      system: SYSTEM_PROMPT,
      tools: allowedTools, // ← 제한된 도구!
      messages: subagentMessages,
    });

    // ...
  }
}
```

---

## 비용 최적화

### Subagent도 Prompt Caching 활용

```typescript
// Main Agent와 Subagent 모두 같은 시스템 프롬프트 사용
// → 캐시 공유!

First request (Main):
  - cache_creation: 50k tokens ($0.15)

Subagent request:
  - cache_read: 50k tokens ($0.015, 90% 절감!)

Second Subagent:
  - cache_read: 50k tokens ($0.015)
```

**핵심**: 모든 Agent가 같은 시스템 프롬프트 → 캐시 효율 극대화

---

## 베스트 프랙티스

### 1. Agent 선택 로직

```typescript
// 시스템 프롬프트에 명확한 기준 제공

When to use each agent:

Explore:
  - "Find all X in the codebase"
  - "Search for Y pattern"
  - "Understand architecture"

Plan:
  - "Add authentication system"
  - "Implement new feature X"
  - "Refactor entire Y"

general-purpose:
  - "Update all deprecated APIs"
  - "Fix all linting errors"
  - "Migrate X to Y"
```

### 2. Prompt 작성

```typescript
// 좋은 Task prompt
{
  "prompt": `Find all API endpoints in the codebase.

Look for:
- Express/Fastify route definitions
- HTTP methods (GET, POST, PUT, DELETE)
- Route paths

Focus on src/**/*.ts files.

Thoroughness: medium

Return a structured list with:
- File path
- Line number
- HTTP method
- Route path
- Brief description`
}

// 나쁜 Task prompt
{
  "prompt": "Find endpoints" // ← 너무 모호!
}
```

### 3. 에러 처리

```typescript
async function executeTask(input: TaskInput): Promise<string> {
  try {
    // Subagent 실행...
  } catch (error) {
    // Subagent 실패 시 에러 리포트
    return `Subagent failed: ${error.message}\n\nYou may need to handle this manually.`;
  }
}
```

---

## 고급: Agent 재시도

```typescript
async function executeTask(
  input: TaskInput,
  maxRetries = 3
): Promise<string> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const result = await runSubagent(input);

      // 결과 검증
      if (isValidReport(result)) {
        return result;
      }

      // 재시도
      console.log(`Attempt ${attempt} produced invalid result, retrying...`);
    } catch (error) {
      if (attempt === maxRetries) {
        throw error; // 최종 실패
      }
    }
  }

  throw new Error("Subagent failed after 3 attempts");
}
```

---

## 다음 단계

- [베스트 프랙티스](best-practices.md)
- [실제 예시](../../examples/interaction-simulations/3-multi-agent-task.json)

---

**생성 날짜**: 2025-11-15
**목적**: Subagent 시스템 구현하여 복잡한 작업 분해하기
