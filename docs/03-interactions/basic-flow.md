# Claude Code의 전체 상호작용 흐름

이 문서는 **실제 Claude Code가 어떻게 동작하는지** 완전한 흐름을 보여줍니다.

## 📋 목차

1. [초기화: 시스템 프롬프트와 도구](#1-초기화-시스템-프롬프트와-도구)
2. [간단한 상호작용](#2-간단한-상호작용-파일-읽기)
3. [도구 사용 루프](#3-도구-사용-루프)
4. [멀티 에이전트 시스템](#4-멀티-에이전트-시스템)
5. [Plan 모드](#5-plan-모드)
6. [전체 시스템 아키텍처](#6-전체-시스템-아키텍처)

---

## 1. 초기화: 시스템 프롬프트와 도구

### 시스템 프롬프트 구조 (약 50,000+ 토큰)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLAUDE CODE SYSTEM PROMPT                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Block 1: 핵심 정체성 및 정책 (~5,000 토큰)                      │
│ ├─ "You are Claude Code, Anthropic's official CLI"            │
│ ├─ 보안 정책 (authorized testing only)                        │
│ ├─ URL 생성 금지 정책                                          │
│ └─ 피드백 안내                                                 │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Block 2: 도구 사용 지침 (~35,000 토큰) ⚠️ 가장 큼!             │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ Task Tool (~3,000 토큰)                                 │   │
│ │ ├─ 언제 사용: 복잡한 멀티스텝 작업                      │   │
│ │ ├─ 언제 사용 안 함: 단순 파일 읽기, 특정 검색          │   │
│ │ ├─ Subagent Types:                                     │   │
│ │ │   ├─ general-purpose (tools: *)                     │   │
│ │ │   ├─ Explore (quick/medium/very thorough)          │   │
│ │ │   ├─ Plan (tools: all)                             │   │
│ │ │   └─ statusline-setup (tools: Read, Edit)          │   │
│ │ ├─ 예시 5개 이상                                        │   │
│ │ ├─ 안티패턴 예시                                        │   │
│ │ └─ 병렬 실행 지침                                       │   │
│ └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ Read Tool (~2,000 토큰)                                 │   │
│ │ ├─ file_path는 절대 경로                                │   │
│ │ ├─ 기본 2000줄 읽기                                     │   │
│ │ ├─ offset/limit 사용법                                  │   │
│ │ ├─ 이미지/PDF/Jupyter 지원                              │   │
│ │ ├─ 병렬 읽기 권장                                        │   │
│ │ └─ 예시 + 안티패턴                                       │   │
│ └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ Write Tool (~1,500 토큰)                                │   │
│ │ ├─ ALWAYS prefer Edit for existing files               │   │
│ │ ├─ NEVER write unless required                         │   │
│ │ ├─ NEVER proactively create docs                       │   │
│ │ ├─ Must Read before Write                              │   │
│ │ └─ 예시 + 안티패턴                                       │   │
│ └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│ [Edit, Bash, Glob, Grep, TodoWrite, AskUserQuestion...         │
│  각 도구마다 1,000~3,000 토큰의 상세 지침]                       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Block 3: 작업 관리 시스템 (~3,000 토큰)                         │
│ ├─ TodoWrite 사용 지침                                          │
│ ├─ States: pending/in_progress/completed                       │
│ ├─ ONE task in_progress at a time (중요!)                      │
│ ├─ content (imperative) vs activeForm (continuous)             │
│ ├─ 언제 사용: 3+ steps, non-trivial tasks                      │
│ ├─ 언제 사용 안 함: single task, trivial                       │
│ └─ 예시 10개 이상                                               │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Block 4: 출력 스타일 (~2,000 토큰)                              │
│ ├─ Explanatory: Educational insights with ★ Insight blocks    │
│ ├─ Concise: Brief, focused responses                           │
│ └─ Detailed: Comprehensive explanations                        │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Block 5: Git 작업 프로토콜 (~2,000 토큰)                        │
│ ├─ Safety: NEVER skip hooks, NEVER force push                  │
│ ├─ Workflow: status → diff → log → commit → status            │
│ ├─ Commit message format with footer                           │
│ └─ Pre-commit hook 처리                                         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Block 6: PR 생성 프로토콜 (~1,500 토큰)                         │
│ ├─ gh command 사용                                              │
│ ├─ 브랜치 divergence point부터 분석                             │
│ └─ PR 템플릿                                                    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Block 7: 환경 정보 (동적, ~500 토큰)                            │
│ ├─ Working directory                                            │
│ ├─ Git repo status                                              │
│ ├─ Platform & OS                                                │
│ ├─ Today's date                                                 │
│ └─ Model info                                                   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Block 8: 프로젝트별 지침 (CLAUDE.md, 가변)                      │
│ └─ 프로젝트 커스텀 지침 (있으면 주입)                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

총 토큰: ~50,000+ 토큰
Cache Control: ephemeral (75-90% 비용 절감)
```

### 16개 도구와 스키마 (~15,000 토큰)

```json
[
  {
    "name": "Task",
    "description": "Launch a new agent to handle complex, multi-step tasks...",
    "input_schema": {
      "type": "object",
      "properties": {
        "subagent_type": {
          "type": "string",
          "enum": ["general-purpose", "Explore", "Plan", "statusline-setup"]
        },
        "description": {"type": "string"},
        "prompt": {"type": "string"},
        "model": {"type": "string", "enum": ["sonnet", "opus", "haiku"]},
        "resume": {"type": "string"}
      },
      "required": ["description", "prompt", "subagent_type"]
    }
  },
  {
    "name": "Read",
    "description": "Reads a file from the local filesystem...",
    "input_schema": {
      "properties": {
        "file_path": {"type": "string"},
        "offset": {"type": "number"},
        "limit": {"type": "number"}
      },
      "required": ["file_path"]
    }
  },
  {
    "name": "Write",
    "input_schema": {
      "properties": {
        "file_path": {"type": "string"},
        "content": {"type": "string"}
      },
      "required": ["file_path", "content"]
    }
  },
  {
    "name": "Edit",
    "input_schema": {
      "properties": {
        "file_path": {"type": "string"},
        "old_string": {"type": "string"},
        "new_string": {"type": "string"},
        "replace_all": {"type": "boolean"}
      },
      "required": ["file_path", "old_string", "new_string"]
    }
  },
  {
    "name": "Bash",
    "input_schema": {
      "properties": {
        "command": {"type": "string"},
        "description": {"type": "string"},
        "timeout": {"type": "number"},
        "run_in_background": {"type": "boolean"}
      },
      "required": ["command"]
    }
  },
  {
    "name": "Glob",
    "input_schema": {
      "properties": {
        "pattern": {"type": "string"},
        "path": {"type": "string"}
      },
      "required": ["pattern"]
    }
  },
  {
    "name": "Grep",
    "input_schema": {
      "properties": {
        "pattern": {"type": "string"},
        "path": {"type": "string"},
        "output_mode": {"enum": ["content", "files_with_matches", "count"]},
        "glob": {"type": "string"},
        "type": {"type": "string"},
        "-i": {"type": "boolean"},
        "-A/-B/-C": {"type": "number"},
        "multiline": {"type": "boolean"}
      },
      "required": ["pattern"]
    }
  },
  {
    "name": "TodoWrite",
    "input_schema": {
      "properties": {
        "todos": {
          "type": "array",
          "items": {
            "properties": {
              "content": {"type": "string"},
              "status": {"enum": ["pending", "in_progress", "completed"]},
              "activeForm": {"type": "string"}
            }
          }
        }
      }
    }
  },
  {
    "name": "AskUserQuestion",
    "input_schema": {
      "properties": {
        "questions": {
          "type": "array",
          "items": {
            "properties": {
              "question": {"type": "string"},
              "header": {"type": "string"},
              "options": {"type": "array"},
              "multiSelect": {"type": "boolean"}
            }
          }
        }
      }
    }
  },
  {
    "name": "WebSearch",
    "input_schema": {
      "properties": {
        "query": {"type": "string"},
        "allowed_domains": {"type": "array"},
        "blocked_domains": {"type": "array"}
      }
    }
  },
  {
    "name": "WebFetch",
    "input_schema": {
      "properties": {
        "url": {"type": "string", "format": "uri"},
        "prompt": {"type": "string"}
      }
    }
  },
  {
    "name": "NotebookEdit",
    "input_schema": {
      "properties": {
        "notebook_path": {"type": "string"},
        "new_source": {"type": "string"},
        "cell_id": {"type": "string"},
        "cell_type": {"enum": ["code", "markdown"]},
        "edit_mode": {"enum": ["replace", "insert", "delete"]}
      }
    }
  },
  {
    "name": "ExitPlanMode",
    "input_schema": {
      "properties": {
        "plan": {"type": "string"}
      }
    }
  },
  {
    "name": "SlashCommand",
    "input_schema": {
      "properties": {
        "command": {"type": "string"}
      }
    }
  },
  {
    "name": "Skill",
    "input_schema": {
      "properties": {
        "skill": {"type": "string"}
      }
    }
  },
  {
    "name": "BashOutput",
    "input_schema": {
      "properties": {
        "bash_id": {"type": "string"},
        "filter": {"type": "string"}
      }
    }
  },
  {
    "name": "KillShell",
    "input_schema": {
      "properties": {
        "shell_id": {"type": "string"}
      }
    }
  }
]
```

총 토큰: ~15,000 토큰
Cache Control: ephemeral

---

## 2. 간단한 상호작용: 파일 읽기

### Request #1: 사용자 입력

```json
{
  "model": "claude-sonnet-4",
  "max_tokens": 8192,
  "messages": [
    {
      "role": "user",
      "content": "package.json 파일을 읽어줘"
    }
  ],
  "system": [/* 50,000+ 토큰 */],
  "tools": [/* 16개 도구, 15,000 토큰 */],
  "metadata": {
    "user_id": "user_abc123_session_xyz789"
  }
}
```

### Response #1: Claude의 응답

```json
{
  "id": "msg_01ABC123",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "package.json 파일을 읽어보겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_01XYZ789",
      "name": "Read",
      "input": {
        "file_path": "/Users/jd/Documents/workspace/claude-code-router/package.json"
      }
    }
  ],
  "stop_reason": "tool_use",
  "usage": {
    "input_tokens": 65234,  // 시스템 프롬프트 + 도구 + 메시지
    "output_tokens": 87,
    "cache_creation_input_tokens": 65000,  // 첫 요청
    "cache_read_input_tokens": 0
  }
}
```

### Request #2: 도구 결과 전달

```json
{
  "model": "claude-sonnet-4",
  "max_tokens": 8192,
  "messages": [
    {
      "role": "user",
      "content": "package.json 파일을 읽어줘"
    },
    {
      "role": "assistant",
      "content": [
        {"type": "text", "text": "package.json 파일을 읽어보겠습니다."},
        {
          "type": "tool_use",
          "id": "toolu_01XYZ789",
          "name": "Read",
          "input": {
            "file_path": "/Users/jd/Documents/workspace/claude-code-router/package.json"
          }
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "tool_result",
          "tool_use_id": "toolu_01XYZ789",
          "content": "{\n  \"name\": \"@musistudio/claude-code-router\",\n  \"version\": \"1.0.66\",\n  \"description\": \"Use Claude Code without an Anthropics account\",\n  ...\n}"
        }
      ]
    }
  ],
  "system": [/* 50,000+ 토큰 (캐시됨!) */],
  "tools": [/* 16개 도구 (캐시됨!) */]
}
```

### Response #2: 최종 응답

```json
{
  "id": "msg_02DEF456",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "package.json 파일의 내용을 확인했습니다.\n\n이 프로젝트는 `@musistudio/claude-code-router`로, 버전 1.0.66입니다..."
    }
  ],
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 520,      // 메시지만! (캐시 덕분)
    "output_tokens": 234,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 65000  // 캐시에서 읽음 (75-90% 할인!)
  }
}
```

**캐시 효과**:
- 첫 요청: 65,234 토큰 (전체 비용)
- 두 번째 요청: 520 + 65,000 (캐시) = 75-90% 할인!

---

## 3. 도구 사용 루프

### 복잡한 작업: "버그를 찾아서 수정해줘"

#### Turn 1: 사용자 요청
```
User: "src/utils/router.ts에 버그가 있는 것 같아. 찾아서 수정해줘"
```

#### Turn 2: Claude - 탐색 단계
```json
{
  "role": "assistant",
  "content": [
    {"type": "text", "text": "먼저 파일을 읽어보겠습니다."},
    {
      "type": "tool_use",
      "id": "toolu_001",
      "name": "Read",
      "input": {"file_path": "/path/to/src/utils/router.ts"}
    }
  ]
}
```

#### Turn 3: 도구 결과
```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_001",
      "content": "[파일 내용 200줄...]"
    }
  ]
}
```

#### Turn 4: Claude - 분석 및 수정
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "버그를 발견했습니다. 182번 줄에서 변수명이 잘못되었네요. 수정하겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_002",
      "name": "Edit",
      "input": {
        "file_path": "/path/to/src/utils/router.ts",
        "old_string": "const modle = await getUseModel(...)",
        "new_string": "const model = await getUseModel(...)"
      }
    }
  ]
}
```

#### Turn 5: 수정 결과
```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_002",
      "content": "File successfully edited"
    }
  ]
}
```

#### Turn 6: Claude - 확인
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "버그를 수정했습니다. 변경 사항을 확인하겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_003",
      "name": "Bash",
      "input": {
        "command": "npm run build",
        "description": "Build project to verify fix"
      }
    }
  ]
}
```

**루프 구조**:
```
User Input
    ↓
Claude Response (tool_use)
    ↓
Tool Execution (by Claude Code CLI)
    ↓
Tool Result (user message)
    ↓
Claude Response (tool_use or final)
    ↓
... 반복 ...
    ↓
Final Response (end_turn)
```

---

## 4. 멀티 에이전트 시스템

### 시나리오: "코드베이스 분석 후 리팩토링"

#### Main Agent: 사용자 요청

```json
{
  "role": "user",
  "content": "코드베이스를 분석해서 중복 코드를 찾고 리팩토링해줘"
}
```

#### Main Agent: Task tool로 Explore Agent 실행

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "먼저 코드베이스를 탐색하겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_task_001",
      "name": "Task",
      "input": {
        "subagent_type": "Explore",
        "description": "Find duplicate code patterns",
        "prompt": "Search the codebase for duplicate code patterns. Look for:\n1. Similar function implementations\n2. Repeated logic blocks\n3. Copy-pasted code\n\nThoroughness: very thorough"
      }
    }
  ]
}
```

#### Explore Agent 내부 동작 (독립 대화)

Explore Agent는 **완전히 새로운 대화 컨텍스트**를 가집니다:

```
┌─────────────────────────────────────────────┐
│         Explore Agent (Subprocess)          │
├─────────────────────────────────────────────┤
│ System Prompt: [Same 50,000+ tokens]       │
│ Tools: [All 16 tools]                       │
│ Messages: [Starts fresh!]                   │
├─────────────────────────────────────────────┤
│                                             │
│ Agent's internal loop:                      │
│                                             │
│ 1. Glob: "**/*.ts"                          │
│    → 찾음: 50개 파일                         │
│                                             │
│ 2. Grep: "function.*\{" (모든 함수 찾기)     │
│    → 찾음: 200개 함수                        │
│                                             │
│ 3. Read: src/utils/router.ts               │
│    → 분석 중...                              │
│                                             │
│ 4. Read: src/utils/status.ts               │
│    → 분석 중...                              │
│                                             │
│ 5. Grep: "JSON\.parse" (중복 패턴 찾기)     │
│    → 찾음: 12개 위치                         │
│                                             │
│ 6. 분석 완료 → 결과 보고                     │
│                                             │
└─────────────────────────────────────────────┘
```

Explore Agent의 최종 보고:

```json
{
  "agent_id": "agent_explore_abc123",
  "result": {
    "findings": [
      {
        "pattern": "JSON.parse with error handling",
        "locations": [
          "src/utils/router.ts:70-77",
          "src/utils/status.ts:45-52",
          "src/server.ts:21-28"
        ],
        "suggestion": "Create a shared parseJSON() utility function"
      },
      {
        "pattern": "fs.existsSync + fs.mkdirSync",
        "locations": [
          "src/utils/router.ts:192",
          "src/utils/logCleanup.ts:23",
          "src/index.ts:31"
        ],
        "suggestion": "Create ensureDir() utility"
      }
    ]
  }
}
```

#### Main Agent: Explore 결과 받고 다음 단계

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_task_001",
      "content": "[Explore Agent의 결과...]"
    }
  ]
}
```

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "중복 코드를 발견했습니다. 이제 계획을 세우겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_task_002",
      "name": "Task",
      "input": {
        "subagent_type": "Plan",
        "description": "Create refactoring plan",
        "prompt": "Based on the duplicate code findings, create a detailed refactoring plan:\n\n[Explore Agent 결과 포함]\n\nCreate a step-by-step plan to:\n1. Create utility functions\n2. Replace duplicates\n3. Test changes"
      }
    }
  ]
}
```

#### Plan Agent 내부 동작

```
┌─────────────────────────────────────────────┐
│          Plan Agent (Subprocess)            │
├─────────────────────────────────────────────┤
│                                             │
│ 1. Read: src/utils/router.ts:70-77         │
│ 2. Read: src/utils/status.ts:45-52         │
│ 3. Read: src/server.ts:21-28               │
│                                             │
│ 4. 분석 및 계획 수립                         │
│                                             │
│ 5. ExitPlanMode로 사용자 승인 요청           │
│                                             │
└─────────────────────────────────────────────┘
```

Plan Agent의 보고:

```markdown
## Refactoring Plan

### Phase 1: Create Utilities
1. Create `src/utils/json.ts`
   - Add `parseJSON()` function with error handling
   - Add `stringifyJSON()` function

2. Create `src/utils/fs.ts`
   - Add `ensureDir()` function

### Phase 2: Replace Duplicates
1. router.ts:70-77 → use parseJSON()
2. status.ts:45-52 → use parseJSON()
3. server.ts:21-28 → use parseJSON()
4. router.ts:192 → use ensureDir()
5. logCleanup.ts:23 → use ensureDir()
6. index.ts:31 → use ensureDir()

### Phase 3: Test
1. Run build: `npm run build`
2. Run tests (if exist)
3. Manual verification

Would you like me to proceed?
```

#### Main Agent: 사용자 승인 후 실행

사용자: "좋아, 진행해"

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_write_001",
      "name": "Write",
      "input": {
        "file_path": "/path/to/src/utils/json.ts",
        "content": "export function parseJSON(str: string): any {\n  try {\n    return JSON.parse(str);\n  } catch (e) {\n    return null;\n  }\n}"
      }
    }
  ]
}
```

... 각 단계 실행 ...

**멀티 에이전트 구조**:

```
Main Agent
    │
    ├─→ Task(Explore Agent)
    │       │
    │       ├─ Glob
    │       ├─ Grep
    │       ├─ Read
    │       └─ [Result] → Main Agent
    │
    ├─→ Task(Plan Agent)
    │       │
    │       ├─ Read
    │       ├─ Analysis
    │       └─ [Plan] → Main Agent → User
    │
    └─→ [User Approval]
        │
        ├─ Write (create utilities)
        ├─ Edit (replace duplicates)
        ├─ Edit (replace duplicates)
        ├─ Edit (replace duplicates)
        └─ Bash (test)
```

**핵심**: 각 Agent는 **독립적인 대화 컨텍스트**를 가지지만, **같은 시스템 프롬프트와 도구**를 사용합니다!

---

## 5. Plan 모드

### 언제 활성화?

1. 사용자가 구체적인 명령 없이 질문할 때
2. 복잡한 작업이 예상될 때
3. 여러 단계가 필요한 작업일 때

### 예시: "인증 시스템을 추가해줘"

#### Request #1
```json
{
  "role": "user",
  "content": "사용자 인증 시스템을 추가해줘"
}
```

#### Response #1: Plan 모드 진입
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "인증 시스템 구현을 계획하겠습니다. 먼저 현재 코드베이스를 분석하겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_plan_explore",
      "name": "Task",
      "input": {
        "subagent_type": "Explore",
        "description": "Analyze authentication setup",
        "prompt": "Find:\n1. Existing auth code\n2. User models\n3. API routes\n4. Database setup\n\nThoroughness: medium"
      }
    }
  ]
}
```

#### Explore Agent 분석 후...

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "코드베이스 분석을 완료했습니다. 이제 구현 계획을 세우겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_exit_plan",
      "name": "ExitPlanMode",
      "input": {
        "plan": "## Authentication System Implementation\n\n### Phase 1: User Model & Database\n1. Create `src/models/User.ts`\n   - Properties: id, email, passwordHash, createdAt\n   - Methods: validatePassword(), hashPassword()\n\n2. Setup database migration\n   - Add users table\n   - Add indexes on email\n\n### Phase 2: Authentication Middleware\n1. Create `src/middleware/auth.ts`\n   - JWT token verification\n   - User session management\n\n2. Create `src/utils/jwt.ts`\n   - generateToken()\n   - verifyToken()\n\n### Phase 3: API Endpoints\n1. POST /api/auth/register\n   - Email validation\n   - Password hashing\n   - User creation\n\n2. POST /api/auth/login\n   - Credential verification\n   - JWT generation\n\n3. GET /api/auth/me\n   - Current user info\n   - Protected route\n\n### Phase 4: Protected Routes\n1. Add auth middleware to existing routes\n2. Update route handlers\n\n### Phase 5: Testing\n1. Unit tests for auth utilities\n2. Integration tests for auth flow\n3. Manual testing\n\nWould you like me to proceed with this plan?"
        }
      }
    }
  ]
}
```

#### 사용자 승인
```
User: "좋아, 진행해"
```

#### Implementation Starts
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "구현을 시작하겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_todo_001",
      "name": "TodoWrite",
      "input": {
        "todos": [
          {"content": "Create User model", "status": "in_progress", "activeForm": "Creating User model"},
          {"content": "Setup database migration", "status": "pending", "activeForm": "Setting up database migration"},
          {"content": "Create auth middleware", "status": "pending", "activeForm": "Creating auth middleware"},
          {"content": "Create JWT utilities", "status": "pending", "activeForm": "Creating JWT utilities"},
          {"content": "Implement register endpoint", "status": "pending", "activeForm": "Implementing register endpoint"},
          {"content": "Implement login endpoint", "status": "pending", "activeForm": "Implementing login endpoint"},
          {"content": "Implement me endpoint", "status": "pending", "activeForm": "Implementing me endpoint"},
          {"content": "Protect existing routes", "status": "pending", "activeForm": "Protecting existing routes"},
          {"content": "Write tests", "status": "pending", "activeForm": "Writing tests"},
          {"content": "Manual testing", "status": "pending", "activeForm": "Performing manual testing"}
        ]
      }
    }
  ]
}
```

... 각 단계 실행하면서 TodoWrite로 상태 업데이트 ...

**Plan 모드 흐름**:

```
User Request
    ↓
Ambiguous/Complex? → Yes → Plan Mode
    ↓
Task(Explore) - 코드베이스 분석
    ↓
분석 결과 수집
    ↓
ExitPlanMode - 계획 제시
    ↓
User Approval?
    ├─ Yes → Implementation
    │           ↓
    │      TodoWrite (진행 상황 추적)
    │           ↓
    │      각 단계 실행
    │           ↓
    │      TodoWrite 업데이트
    │           ↓
    │      완료
    │
    └─ No → 계획 수정
              ↓
          다시 제시
```

---

## 6. 전체 시스템 아키텍처

### 레이어 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                        User (Terminal)                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ User Input
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Claude Code CLI Process                      │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  1. Parse user input                                        │ │
│ │  2. Build request with:                                     │ │
│ │     - System prompt (50,000+ tokens)                        │ │
│ │     - Tools (16 tools, 15,000 tokens)                       │ │
│ │     - Messages history                                      │ │
│ │  3. Send to Anthropic API (or Router!)                      │ │
│ └─────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP POST /v1/messages
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│               Claude Code Router (localhost:3456)               │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  src/index.ts: preHandler Hook                              │ │
│ │  ├─ Built-in agents (image processing etc)                  │ │
│ │  └─ src/utils/router.ts: Model selection                    │ │
│ │      ├─ Token count check                                   │ │
│ │      ├─ Thinking mode check                                 │ │
│ │      ├─ WebSearch check                                     │ │
│ │      ├─ Background/Haiku check                              │ │
│ │      └─ Custom router script                                │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ req.body.model = "deepseek,deepseek-chat"  ← 변경!              │
│ req.body.messages, system, tools  ← 그대로!                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Forward to @musistudio/llms
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    @musistudio/llms Package                     │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  1. Find Provider (deepseek)                                │ │
│ │  2. Get Transformer (deepseek transformer)                  │ │
│ │  3. Transform Request:                                      │ │
│ │     Anthropic format → DeepSeek format                      │ │
│ │     - messages: merge system into messages                  │ │
│ │     - tools: convert to DeepSeek tool format                │ │
│ └─────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP POST to Provider API
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                 LLM Provider (DeepSeek/Gemini/etc)              │
│                                                                 │
│  - Receives: Provider-specific format                           │
│  - Processes: Generates response                                │
│  - Returns: Provider-specific format                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Response
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    @musistudio/llms Package                     │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  4. Transform Response:                                     │ │
│ │     DeepSeek format → Anthropic format                      │ │
│ │     - role: assistant                                       │ │
│ │     - content: [text blocks, tool_use blocks]               │ │
│ │     - usage: input/output tokens                            │ │
│ └─────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Anthropic format response
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│               Claude Code Router (localhost:3456)               │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  src/index.ts: onSend Hook                                  │ │
│ │  ├─ Built-in agent tool calls processing                    │ │
│ │  ├─ Session usage tracking                                  │ │
│ │  └─ Return to Claude Code CLI                               │ │
│ └─────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Anthropic format response
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Claude Code CLI Process                      │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  1. Receive response                                        │ │
│ │  2. Check stop_reason:                                      │ │
│ │     - "tool_use" → Execute tools → Send results back        │ │
│ │     - "end_turn" → Display to user                          │ │
│ │  3. Update conversation history                             │ │
│ └─────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ If tool_use
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Tool Execution                             │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  Read → fs.readFileSync()                                   │ │
│ │  Write → fs.writeFileSync()                                 │ │
│ │  Bash → child_process.spawn()                               │ │
│ │  Task → NEW SUBPROCESS with full context!                   │ │
│ └─────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Tool Result
                             ↓
                        [Loop back to Request]
```

### 전체 흐름 요약

```
1. User Input
     ↓
2. Claude Code CLI
   ├─ Build request (system + tools + messages)
   └─ Send to Router
     ↓
3. Router
   ├─ Select model (routing logic)
   └─ Forward to @musistudio/llms
     ↓
4. @musistudio/llms
   ├─ Transform to Provider format
   └─ Call Provider API
     ↓
5. LLM Provider (DeepSeek/Gemini)
   ├─ Generate response
   └─ Return
     ↓
6. @musistudio/llms
   ├─ Transform to Anthropic format
   └─ Return
     ↓
7. Router
   ├─ Process (if needed)
   └─ Return
     ↓
8. Claude Code CLI
   ├─ If tool_use:
   │   ├─ Execute tool
   │   └─ Go to step 2 (with tool result)
   ├─ If Task tool:
   │   ├─ Start subprocess (new agent)
   │   ├─ Agent runs independently
   │   └─ Return result
   └─ If end_turn:
       └─ Display to user
```

### 멀티 에이전트 트리 구조

```
Main Conversation
│
├─ Message 1: User "복잡한 작업"
│
├─ Message 2: Assistant (Task tool)
│   │
│   └─→ [Explore Agent Subprocess]
│       ├─ System: [Same 50k tokens]
│       ├─ Tools: [Same 16 tools]
│       ├─ Messages: [Independent]
│       │   ├─ Message 1: (from Task prompt)
│       │   ├─ Message 2: Glob result
│       │   ├─ Message 3: Grep result
│       │   └─ Final: Report
│       └─→ [Return to Main]
│
├─ Message 3: Tool result (Explore report)
│
├─ Message 4: Assistant (Task tool)
│   │
│   └─→ [Plan Agent Subprocess]
│       ├─ System: [Same 50k tokens]
│       ├─ Tools: [Same 16 tools]
│       ├─ Messages: [Independent]
│       │   ├─ Message 1: (from Task prompt + Explore results)
│       │   ├─ Message 2: Read files
│       │   ├─ Message 3: Analysis
│       │   └─ Final: ExitPlanMode
│       └─→ [Return to Main]
│
├─ Message 5: Tool result (Plan)
│
├─ Message 6: User "승인"
│
├─ Message 7: Assistant (TodoWrite + implementations)
│   ├─ Write file 1
│   ├─ Edit file 2
│   ├─ Edit file 3
│   └─ Bash test
│
└─ Message 8: Final response
```

**핵심 포인트**:
1. 각 Agent는 **독립적인 대화**
2. 하지만 **같은 시스템 프롬프트와 도구**
3. Parent Agent는 결과만 받음
4. 무한 중첩 가능 (Agent 안에 Agent 안에 Agent...)

---

## 7. 캐싱 전략

### Prompt Caching 효과

```
Request #1 (Cold Start):
┌────────────────────────────────────┐
│ Input Tokens:                      │
├────────────────────────────────────┤
│ System Prompt: 50,000 (NEW)       │
│ Tools: 15,000 (NEW)                │
│ Messages: 100                      │
├────────────────────────────────────┤
│ Total: 65,100 tokens               │
│ Cost: $0.195 (full price)          │
└────────────────────────────────────┘

Request #2 (Cached):
┌────────────────────────────────────┐
│ Input Tokens:                      │
├────────────────────────────────────┤
│ System Prompt: 50,000 (CACHED!)   │
│ Tools: 15,000 (CACHED!)            │
│ Messages: 200 (NEW)                │
├────────────────────────────────────┤
│ Total: 200 + 65,000 (cached)       │
│ Cost: $0.020 + $0.020 (90% off)    │
│     = $0.040 (79% savings!)        │
└────────────────────────────────────┘
```

### Cache TTL

- **5분**: 캐시 유지 시간
- 5분 이내 다음 요청: 캐시 히트
- 5분 이후: 캐시 미스 (다시 생성)

---

## 결론

Claude Code는:

1. **50,000+ 토큰의 초상세 시스템 프롬프트**로 LLM을 정교하게 제어
2. **16개 도구**로 파일 시스템, Git, 웹, 에이전트를 통합
3. **계층적 에이전트 시스템**으로 복잡한 작업을 분해
4. **Prompt Caching**으로 경제적으로 운영
5. **도구 사용 루프**로 사용자와 인터렉티브하게 상호작용

라우터는 이 모든 구조를 **투명하게 유지**하면서 다른 LLM으로 전환하는 **프록시** 역할을 합니다!
