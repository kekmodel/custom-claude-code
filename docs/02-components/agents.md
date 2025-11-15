# Claude Code Subagent 상세 분석

각 subagent의 **발동 조건**, **시스템 프롬프트**, **사용 가능 도구**를 완전히 분석합니다.

## 📋 목차

1. [Subagent 개요](#subagent-개요)
2. [general-purpose Agent](#1-general-purpose-agent)
3. [Explore Agent](#2-explore-agent)
4. [Plan Agent](#3-plan-agent)
5. [statusline-setup Agent](#4-statusline-setup-agent)
6. [비교표](#비교표)
7. [실제 예시](#실제-예시)

---

## Subagent 개요

### 공통 특징

모든 subagent는:
1. ✅ **같은 기본 시스템 프롬프트** (50,000+ 토큰)를 받음
2. ✅ **독립적인 대화 컨텍스트**를 가짐
3. ✅ **Task tool의 prompt가 첫 user 메시지**가 됨
4. ⚠️ **사용 가능한 도구가 다를 수 있음**

### Subagent 실행 메커니즘

```
Main Agent Request:
{
  "tool_use": {
    "name": "Task",
    "input": {
      "subagent_type": "Explore",           ← 어떤 agent인지
      "description": "Find API endpoints",   ← 짧은 설명 (3-5 단어)
      "prompt": "Search for all API...",     ← 실제 지시사항
      "model": "sonnet"                      ← 선택사항
    }
  }
}

↓ Claude Code CLI가 새 subprocess 시작

Subagent Context:
{
  "system": [
    {
      "type": "text",
      "text": "[Same 50,000+ tokens base prompt]",
      "cache_control": {"type": "ephemeral"}
    },
    {
      "type": "text",
      "text": "<env>...</env>",
      "cache_control": {"type": "ephemeral"}
    }
  ],
  "tools": [
    // Subagent 타입에 따라 다를 수 있음
  ],
  "messages": [
    {
      "role": "user",
      "content": "Search for all API..."  ← Task의 prompt가 여기 들어감!
    }
  ]
}
```

---

## 1. general-purpose Agent

### 발동 조건

#### ✅ 사용하는 경우:

```
시스템 프롬프트에서 추출한 실제 지침:
───────────────────────────────────────────────────
general-purpose: General-purpose agent for researching
complex questions, searching for code, and executing
multi-step tasks.

When you are searching for a keyword or file and are not
confident that you will find the right match in the first
few tries, use this agent to perform the search for you.

Available tools: * (all tools)
```

**구체적인 발동 조건**:

1. **복잡한 연구 작업**
   ```
   예: "이 라이브러리가 어떻게 동작하는지 완전히 이해하고 설명해줘"
   이유: 여러 파일을 읽고 분석해야 함
   ```

2. **불확실한 검색**
   ```
   예: "authentication 관련 코드를 모두 찾아줘"
   이유: 여러 번 시도가 필요할 수 있음
   ```

3. **멀티스텝 자동화**
   ```
   예: "모든 deprecated API를 찾아서 새 버전으로 업데이트해줘"
   이유: 검색 → 분석 → 수정이 반복됨
   ```

4. **실험적 탐색**
   ```
   예: "성능 병목을 찾아서 최적화 방법을 제안해줘"
   이유: 여러 접근 방법을 시도해야 함
   ```

#### ❌ 사용하지 않는 경우:

```
시스템 프롬프트에서 추출:
───────────────────────────────────────────────────
When NOT to use the Task tool:

- If you want to read a specific file path, use the Read
  tool instead of the Task tool, to find the match more
  quickly

- If you are searching for a specific class definition
  like "class Foo", use the Glob tool instead, to find
  the match more quickly

- If you are searching for code within a specific file or
  set of 2-3 files, use the Read tool instead

- Other tasks that are not related to complex multi-step work
```

**구체적인 예**:

1. ❌ "package.json 읽어줘" → Read 직접 사용
2. ❌ "Router 클래스 찾아줘" → Glob 직접 사용
3. ❌ "이 파일에서 버그 찾아줘" → Read 직접 사용

### 시스템 프롬프트

```typescript
{
  // 기본 시스템 프롬프트 (50,000+ 토큰)
  system: [
    {
      type: "text",
      text: `
You are Claude Code, Anthropic's official CLI for Claude.
...

# Task tool
Launch a new agent to handle complex, multi-step tasks autonomously.

Available agent types:
- general-purpose: General-purpose agent for researching complex
  questions, searching for code, and executing multi-step tasks.
  When you are searching for a keyword or file and are not confident
  that you will find the right match in the first few tries, use
  this agent to perform the search for you.

  Tools available: * (ALL TOOLS)

  This agent has access to ALL tools and can autonomously decide
  which tools to use and in what order.

...

# Read tool
[2,000 tokens of detailed instructions]

# Write tool
[1,500 tokens of detailed instructions]

# Bash tool
[2,500 tokens of detailed instructions]

... [all 16 tools]

# Task Management
[3,000 tokens about TodoWrite]

# Git Protocol
[2,000 tokens]

# Output Style: Explanatory
[현재 활성화된 스타일 지침]
      `,
      cache_control: {type: "ephemeral"}
    },
    {
      type: "text",
      text: `
<env>
Working directory: /path/to/project
Platform: darwin
...
</env>

Model: Sonnet 4.5
      `,
      cache_control: {type: "ephemeral"}
    }
  ],

  // 모든 16개 도구
  tools: [
    {name: "Task", ...},
    {name: "Read", ...},
    {name: "Write", ...},
    {name: "Edit", ...},
    {name: "Bash", ...},
    {name: "Glob", ...},
    {name: "Grep", ...},
    {name: "TodoWrite", ...},
    {name: "AskUserQuestion", ...},
    {name: "WebSearch", ...},
    {name: "WebFetch", ...},
    {name: "NotebookEdit", ...},
    {name: "ExitPlanMode", ...},
    {name: "SlashCommand", ...},
    {name: "Skill", ...},
    {name: "BashOutput", ...},
    {name: "KillShell", ...}
  ],

  // 첫 메시지는 Task의 prompt
  messages: [
    {
      role: "user",
      content: "[Task tool의 prompt 내용]"
    }
  ]
}
```

### 도구 접근

- ✅ **ALL 16 tools** - 제한 없음
- ✅ 다른 Task agent도 실행 가능 (중첩)

---

## 2. Explore Agent

### 발동 조건

#### ✅ 사용하는 경우:

```
시스템 프롬프트에서 추출:
───────────────────────────────────────────────────
Explore: Fast agent specialized for exploring codebases.

Use this when you need to:
- Quickly find files by patterns (e.g., "src/components/**/*.tsx")
- Search code for keywords (e.g., "API endpoints")
- Answer questions about the codebase (e.g., "how do API endpoints work?")

When calling this agent, specify the desired thoroughness level:
- "quick" for basic searches
- "medium" for moderate exploration
- "very thorough" for comprehensive analysis across multiple
  locations and naming conventions

Available tools: All tools
```

**구체적인 발동 조건**:

1. **코드베이스 탐색**
   ```
   ✅ "이 프로젝트에서 API 엔드포인트를 모두 찾아줘"
   이유: 패턴 기반 검색 + 분석 필요
   ```

2. **아키텍처 이해**
   ```
   ✅ "인증 시스템이 어떻게 구현되어 있는지 설명해줘"
   이유: 관련 파일들을 찾고 분석해야 함
   ```

3. **코드 품질 분석**
   ```
   ✅ "중복 코드 패턴을 찾아줘"
   이유: 전체 코드베이스를 스캔해야 함
   ```

4. **의존성 추적**
   ```
   ✅ "이 함수가 어디서 사용되는지 모두 찾아줘"
   이유: Grep으로 참조를 찾고 각 위치를 분석
   ```

5. **구조 파악**
   ```
   ✅ "컴포넌트 구조를 분석해줘"
   이유: 파일 패턴 매칭 + 계층 분석
   ```

#### ❌ 사용하지 않는 경우:

```
When NOT to use Explore agent:

- When you know the exact file path → use Read directly
- When you need to modify code → use Edit/Write directly
- When the task is about planning → use Plan agent instead
- When the task requires user approval → handle in main agent
```

**Thoroughness 레벨**:

```typescript
interface ThorouphnessLevel {
  quick: {
    scope: "단일 패턴 검색",
    tools: "Glob 또는 Grep 1-2번",
    time: "~5초",
    example: "*.ts 파일만 찾기"
  },

  medium: {
    scope: "여러 패턴 + 기본 분석",
    tools: "Glob + Grep + Read 3-5번",
    time: "~15초",
    example: "API 엔드포인트 찾고 각 파일의 구조 확인"
  },

  "very thorough": {
    scope: "포괄적 분석 + 다양한 네이밍",
    tools: "Glob + Grep (여러 패턴) + Read (많은 파일)",
    time: "~30초+",
    example: "모든 가능한 인증 관련 코드 찾기 (auth, login, session, token, jwt 등)"
  }
}
```

### 시스템 프롬프트

Explore Agent는 **general-purpose와 동일한 시스템 프롬프트**를 받습니다!

차이점:
1. ✅ Task tool의 **prompt가 다름** (탐색 지시사항)
2. ✅ **thoroughness 레벨**이 prompt에 명시됨
3. ✅ Main Agent의 기대가 "탐색 결과"임

```typescript
{
  system: "[Same 50,000+ tokens]",
  tools: "[Same 16 tools]",
  messages: [
    {
      role: "user",
      content: `
Search the codebase for API endpoint implementations.

Look for:
1. Route definitions (Express, Fastify, etc.)
2. Controller functions
3. API documentation

Focus on:
- src/**/*.ts files
- Look for patterns like: app.get, app.post, router.get, etc.

Thoroughness: medium

Return a structured report with:
- File locations
- Endpoint paths
- HTTP methods
- Brief description of each endpoint
      `
    }
  ]
}
```

### 도구 접근

- ✅ **ALL 16 tools**
- 🎯 **자주 사용**: Glob, Grep, Read
- 🎯 **가끔 사용**: Task (중첩 탐색), Bash
- ❌ **거의 안 씀**: Write, Edit (탐색만 하므로)

---

## 3. Plan Agent

### 발동 조건

#### ✅ 사용하는 경우:

```
시스템 프롬프트에서 추출:
───────────────────────────────────────────────────
Plan: Fast agent specialized for planning implementation steps.

Use this when you need to:
- Break down complex tasks into steps
- Create implementation plans
- Analyze architecture before coding

This agent should analyze the codebase, understand requirements,
and EXIT with a detailed plan using the ExitPlanMode tool.

DO NOT implement the plan - only create it.

Available tools: All tools
```

**구체적인 발동 조건**:

1. **복잡한 기능 구현 전**
   ```
   ✅ "사용자 인증 시스템을 추가해줘"
   이유: 여러 단계 필요 → Plan으로 계획 수립 → 승인 → 실행
   ```

2. **대규모 리팩토링**
   ```
   ✅ "전체 프로젝트를 TypeScript로 마이그레이션해줘"
   이유: 단계별 계획 필요
   ```

3. **아키텍처 변경**
   ```
   ✅ "모놀리스를 마이크로서비스로 분리해줘"
   이유: 신중한 계획 필요
   ```

4. **불명확한 요구사항**
   ```
   ✅ "성능을 개선해줘"
   이유: 먼저 병목을 찾고 → 계획 수립 → 승인 → 실행
   ```

#### ❌ 사용하지 않는 경우:

```
When NOT to use Plan agent:

- Simple, straightforward tasks → do it directly
- User already provided a detailed plan → just execute
- Exploratory work without a goal → use Explore instead
- Small changes (< 3 steps) → do directly
```

**Plan 모드 플로우**:

```
User: "복잡한 작업해줘"
    ↓
Main Agent: "복잡하네... Plan Agent 실행"
    ↓
Plan Agent:
    ├─ Explore (optional, 코드베이스 이해)
    ├─ Read (관련 파일들)
    ├─ Analysis (계획 수립)
    └─ ExitPlanMode (계획 제시)
    ↓
Main Agent: User에게 계획 보여줌
    ↓
User: "승인" or "수정 요청"
    ↓
Main Agent:
    ├─ 승인 → 실행 시작
    └─ 수정 → Plan Agent 다시 실행
```

### 시스템 프롬프트

Plan Agent도 **같은 기본 시스템 프롬프트**를 받지만, 중요한 차이가 있습니다:

```typescript
{
  system: "[Same 50,000+ tokens]",
  tools: "[Same 16 tools]",
  messages: [
    {
      role: "user",
      content: `
Based on the user's request and codebase analysis, create a
detailed implementation plan for adding user authentication.

Requirements:
- JWT-based authentication
- Email/password login
- Protected routes
- Session management

Current codebase context:
[Explore Agent의 결과가 여기 포함될 수 있음]

Create a step-by-step plan with:
1. Phase breakdown
2. Specific files to create/modify
3. Code examples
4. Testing strategy

IMPORTANT: Use ExitPlanMode tool to present the plan.
DO NOT implement anything - only plan.
      `
    }
  ]
}
```

**ExitPlanMode 도구**:

```typescript
{
  name: "ExitPlanMode",
  description: "Use this tool when you are in plan mode and have finished presenting your plan and are ready to code. This will prompt the user to exit plan mode.

IMPORTANT: Only use this tool when the task requires planning the implementation steps of a task that requires writing code. For research tasks where you're gathering information, searching files, reading files or in general trying to understand the codebase - do NOT use this tool.",
  input_schema: {
    type: "object",
    properties: {
      plan: {
        type: "string",
        description: "The plan you came up with, that you want to run by the user for approval. Supports markdown. The plan should be pretty concise."
      }
    },
    required: ["plan"]
  }
}
```

### 도구 접근

- ✅ **ALL 16 tools**
- 🎯 **자주 사용**: Read, Task(Explore), ExitPlanMode
- 🎯 **가끔 사용**: Glob, Grep
- ❌ **절대 안 씀**: Write, Edit (계획만 하므로!)

---

## 4. statusline-setup Agent

### 발동 조건

#### ✅ 사용하는 경우:

```
시스템 프롬프트에서 추출:
───────────────────────────────────────────────────
statusline-setup: Use this agent to configure the user's
Claude Code status line setting.

Available tools: Read, Edit (LIMITED!)

This is a specialized agent for a very specific task.
```

**구체적인 발동 조건**:

1. **사용자가 명시적으로 상태표시줄 설정 요청**
   ```
   ✅ "상태표시줄을 설정해줘"
   ✅ "statusline 설정해줘"
   ✅ "/statusline setup"
   ```

2. **자동 발동 (거의 없음)**
   ```
   일반적으로 Main Agent가 직접 처리 가능
   이 Agent는 특수한 경우에만 사용
   ```

#### ❌ 사용하지 않는 경우:

```
모든 다른 경우!

statusline-setup은 매우 특화된 Agent이므로
대부분의 작업에는 사용하지 않습니다.
```

### 시스템 프롬프트

```typescript
{
  system: "[Same 50,000+ tokens base]",

  // ⚠️ 중요: 도구가 제한됨!
  tools: [
    {name: "Read", ...},
    {name: "Edit", ...}
    // 나머지 14개 도구는 없음!
  ],

  messages: [
    {
      role: "user",
      content: "Configure Claude Code statusline for the user's shell environment..."
    }
  ]
}
```

### 도구 접근

- ✅ **ONLY 2 tools**: Read, Edit
- ❌ **NO**: Bash, Write, Task, Glob, Grep 등
- 이유: 상태표시줄 설정은 기존 파일을 읽고 수정하는 것만 필요

---

## 비교표

| 특성 | general-purpose | Explore | Plan | statusline-setup |
|------|----------------|---------|------|------------------|
| **주요 용도** | 복잡한 멀티스텝 작업 | 코드베이스 탐색 | 구현 계획 수립 | 상태표시줄 설정 |
| **도구 접근** | ALL 16 tools | ALL 16 tools | ALL 16 tools | Read, Edit만 |
| **자주 쓰는 도구** | 모두 | Glob, Grep, Read | Read, Task, ExitPlanMode | Read, Edit |
| **절대 안 쓰는 도구** | 없음 | Write, Edit | Write, Edit | 나머지 14개 |
| **시스템 프롬프트** | 기본 50k+ | 기본 50k+ | 기본 50k+ | 기본 50k+ |
| **독립 컨텍스트** | ✅ | ✅ | ✅ | ✅ |
| **Task 중첩 가능** | ✅ | ✅ | ✅ | ❌ (도구 없음) |
| **thoroughness** | N/A | quick/medium/very thorough | N/A | N/A |
| **특수 도구** | 없음 | 없음 | ExitPlanMode | 없음 |
| **발동 빈도** | 🟢 자주 | 🟢 자주 | 🟡 가끔 | 🔴 거의 없음 |

### 발동 조건 비교

```
사용자: "API 엔드포인트를 찾아줘"
├─ general-purpose? ❌ (직접 Grep으로 가능)
├─ Explore? ✅ (코드베이스 탐색!)
├─ Plan? ❌ (탐색만 필요)
└─ statusline-setup? ❌ (무관)

사용자: "인증 시스템을 추가해줘"
├─ general-purpose? ⚠️ (가능하지만 Plan이 더 적합)
├─ Explore? ❌ (구현이 필요함)
├─ Plan? ✅ (복잡한 기능 → 계획 먼저!)
└─ statusline-setup? ❌ (무관)

사용자: "deprecated API를 모두 업데이트해줘"
├─ general-purpose? ✅ (검색 + 수정 반복)
├─ Explore? ⚠️ (찾기만 하면 Explore, 수정까지는 general-purpose)
├─ Plan? ⚠️ (단순하면 직접, 복잡하면 Plan)
└─ statusline-setup? ❌ (무관)

사용자: "상태표시줄 설정해줘"
├─ general-purpose? ❌ (특수 Agent 있음)
├─ Explore? ❌ (설정 작업)
├─ Plan? ❌ (간단한 작업)
└─ statusline-setup? ✅ (정확히 이 용도!)
```

---

## 실제 예시

### 예시 1: Explore Agent

**Main Agent 요청**:
```json
{
  "tool_use": {
    "name": "Task",
    "input": {
      "subagent_type": "Explore",
      "description": "Find all API endpoints",
      "prompt": "Search the codebase for all API endpoint definitions.\n\nLook for:\n- Express/Fastify route definitions\n- HTTP methods (GET, POST, PUT, DELETE)\n- Route paths\n\nFocus on src/**/*.ts files.\n\nThoroughness: medium\n\nReturn a structured list with:\n- File path\n- Line number\n- HTTP method\n- Route path\n- Brief description"
    }
  }
}
```

**Explore Agent 내부 동작**:
```
Turn 1: Glob "src/**/*.ts"
  → 찾음: 45개 파일

Turn 2: Grep "app\.(get|post|put|delete)" in ts files
  → 찾음: 12개 위치

Turn 3: Read src/server.ts:20-50
  → 분석: app.get('/api/config', ...)

Turn 4: Read src/server.ts:50-80
  → 분석: app.post('/api/config', ...)

Turn 5: Read src/index.ts:130-160
  → 분석: server.app.post('/v1/messages', ...)

Turn 6: 최종 리포트 생성
  → 12개 엔드포인트 정리

Return to Main Agent:
{
  "endpoints": [
    {
      "file": "src/server.ts",
      "line": 20,
      "method": "GET",
      "path": "/api/config",
      "description": "Get current config"
    },
    ...
  ]
}
```

### 예시 2: Plan Agent

**Main Agent 요청**:
```json
{
  "tool_use": {
    "name": "Task",
    "input": {
      "subagent_type": "Plan",
      "description": "Plan auth system implementation",
      "prompt": "Create a detailed implementation plan for adding JWT-based user authentication.\n\nRequirements:\n- Email/password login\n- JWT tokens\n- Protected routes\n- Session management\n\nCurrent codebase uses:\n- Fastify for server\n- TypeScript\n- No existing auth\n\nAnalyze the codebase and create a phase-by-phase plan with specific file paths and code examples."
    }
  }
}
```

**Plan Agent 내부 동작**:
```
Turn 1: Task(Explore) - 현재 구조 파악
  → Explore Agent 실행
  → 결과: Fastify setup, routes structure

Turn 2: Read src/server.ts
  → 이해: 서버 초기화 방식

Turn 3: Read src/middleware/auth.ts
  → 발견: 파일 없음 (생성 필요)

Turn 4: 계획 수립 (내부 분석)

Turn 5: ExitPlanMode
  → 상세 계획 제시

Return to Main Agent:
{
  "plan": "## Authentication Implementation Plan\n\n### Phase 1: User Model\n1. Create src/models/User.ts\n   - Properties: id, email, passwordHash\n   - Methods: validatePassword()\n...\n\n### Phase 2: JWT Utils\n...\n\nWould you like to proceed?"
}
```

### 예시 3: general-purpose Agent

**Main Agent 요청**:
```json
{
  "tool_use": {
    "name": "Task",
    "input": {
      "subagent_type": "general-purpose",
      "description": "Update all deprecated APIs",
      "prompt": "Find all usages of the deprecated `oldFunction()` and replace them with `newFunction()`.\n\nSteps:\n1. Search for all occurrences\n2. For each occurrence:\n   - Read the file to understand context\n   - Replace oldFunction() with newFunction()\n   - Verify syntax is correct\n3. Run build to verify\n\nReport any issues encountered."
    }
  }
}
```

**general-purpose Agent 내부 동작**:
```
Turn 1: Grep "oldFunction" in all files
  → 찾음: 8개 파일, 15개 위치

Turn 2-9: 각 파일마다
  ├─ Read (컨텍스트 확인)
  ├─ Edit (oldFunction → newFunction)
  └─ 진행

Turn 10: Bash "npm run build"
  → 성공!

Turn 11: 최종 리포트

Return to Main Agent:
{
  "result": "Successfully updated 15 occurrences across 8 files.\nBuild passed.\nFiles modified:\n- src/utils/helper.ts (3 occurrences)\n- src/services/api.ts (5 occurrences)\n..."
}
```

---

## 핵심 정리

### 1. 모든 Subagent는 같은 기본 시스템 프롬프트

```
✅ 50,000+ 토큰 시스템 프롬프트 (동일)
✅ 16개 도구 정의 (대부분 동일, statusline-setup만 제한)
✅ 환경 정보 (동일)
```

### 2. 차이는 "용도"와 "prompt"

```
Explore: "코드베이스를 탐색해서 X를 찾아라"
Plan: "X를 구현하는 계획을 세워라, ExitPlanMode로 제시해라"
general-purpose: "X를 해라, 어떤 도구든 사용해도 된다"
statusline-setup: "상태표시줄을 설정해라 (Read, Edit만 사용)"
```

### 3. Main Agent의 판단

```typescript
function selectSubagent(userRequest: string): SubagentType | null {
  // Main Agent의 시스템 프롬프트에 있는 지침:

  if (isCodebaseExploration(userRequest)) {
    return "Explore";
    // 예: "API 엔드포인트 찾아줘", "인증 어떻게 구현됐어?"
  }

  if (isComplexImplementation(userRequest) && needsPlan(userRequest)) {
    return "Plan";
    // 예: "인증 시스템 추가해줘", "마이크로서비스로 분리해줘"
  }

  if (isUncertainSearch(userRequest) || isMultiStepAutomation(userRequest)) {
    return "general-purpose";
    // 예: "deprecated API 모두 업데이트", "성능 병목 찾아서 최적화"
  }

  if (isStatuslineSetup(userRequest)) {
    return "statusline-setup";
    // 예: "statusline 설정해줘"
  }

  return null; // Main Agent가 직접 처리
}
```

### 4. 발동 순서 우선도

```
1순위: statusline-setup (명확한 키워드)
2순위: Plan (복잡하고 계획이 필요한 경우)
3순위: Explore (탐색만 필요한 경우)
4순위: general-purpose (불확실하거나 반복적인 경우)
5순위: Main Agent 직접 처리 (간단한 경우)
```

---

**생성 날짜**: 2025-11-14
**기반**: Claude Code의 실제 시스템 프롬프트 분석
