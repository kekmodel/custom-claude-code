# Claude Code의 실제 구조 분석

이 문서는 Claude Code Router가 받는 실제 요청을 기반으로 Claude Code의 내부 구조를 역공학한 것입니다.

## 1. 시스템 프롬프트 구조

Claude Code는 매 요청마다 다음과 같은 시스템 프롬프트를 보냅니다:

### Block 1: 핵심 정체성 및 역할

```
You are Claude Code, Anthropic's official CLI for Claude.
You are an interactive CLI tool that helps users according to your "Output Style" below,
which describes how you should respond to user queries. Use the instructions below and
the tools available to you to assist the user.

IMPORTANT: Assist with authorized security testing, defensive security, CTF challenges,
and educational contexts. Refuse requests for destructive techniques, DoS attacks,
mass targeting, supply chain compromise, or detection evasion for malicious purposes.

IMPORTANT: You must NEVER generate or guess URLs for the user unless you are confident
that the URLs are for helping the user with programming.
```

**프롬프트 길이**: 약 50,000+ 토큰 (매우 상세한 지침 포함)

### Block 2: 환경 정보 (동적)

```xml
<env>
Working directory: /Users/jd/Documents/workspace/claude-code-router
Is directory a git repo: Yes
Platform: darwin
OS Version: Darwin 25.1.0
Today's date: 2025-11-15
</env>

You are powered by the model named Sonnet 4.5.
The exact model ID is claude-sonnet-4-5-20250929.
Assistant knowledge cutoff is January 2025.
```

### Block 3: 도구 사용 지침 (각 도구별 상세 설명)

```
# Task tool
Launch a new agent to handle complex, multi-step tasks autonomously.
Available agent types:
- general-purpose: General-purpose agent (Tools: *)
- Explore: Fast agent for exploring codebases (thoroughness: quick/medium/very thorough)
- Plan: Planning agent for implementation steps
- statusline-setup: Configure status line (Tools: Read, Edit)

When NOT to use the Task tool:
- If you want to read a specific file path, use the Read tool instead
- If searching for a specific class definition, use Glob tool
- If searching within specific files, use Read tool
...

# Read tool
Reads a file from the local filesystem.
Usage:
- file_path must be absolute path
- By default, reads up to 2000 lines
- Can specify offset and limit for long files
- Supports images (PNG, JPG), PDFs, Jupyter notebooks
...

# Write tool
Writes a file to the local filesystem.
Usage:
- ALWAYS prefer editing existing files in the codebase
- NEVER write new files unless explicitly required
- NEVER proactively create documentation files
...

[각 도구별로 매우 상세한 사용 지침이 계속됨]
```

### Block 4: 작업 관리 시스템

```
# Task Management
You have access to the TodoWrite tool to help you manage and plan tasks.
Use these tools VERY frequently to ensure tracking your tasks.

Task States:
- pending: Task not yet started
- in_progress: Currently working on (limit to ONE task at a time)
- completed: Task finished successfully

IMPORTANT: Task descriptions must have two forms:
- content: Imperative form (e.g., "Run tests")
- activeForm: Present continuous form (e.g., "Running tests")

Examples:
[상세한 예시들...]
```

### Block 5: 출력 스타일 (현재 활성화된 스타일)

```
# Output Style: Explanatory
You are an interactive CLI tool that helps users with software engineering tasks.
In addition to software engineering tasks, you should provide educational insights
about the codebase along the way.

## Insights
Before and after writing code, always provide brief educational explanations using:
"`★ Insight ─────────────────────────────────────`
[2-3 key educational points]
`─────────────────────────────────────────────────`"
```

### Block 6: Git 작업 프로토콜

```
# Committing changes with git
Only create commits when requested by the user. If unclear, ask first.

Git Safety Protocol:
- NEVER update the git config
- NEVER run destructive/irreversible git commands unless explicitly requested
- NEVER skip hooks (--no-verify, --no-gpg-sign, etc.)
- NEVER run force push to main/master
- Avoid git commit --amend unless explicitly requested

When creating a commit:
1. Run git status, git diff, git log in parallel
2. Analyze all staged changes and draft commit message
3. Add relevant files and create commit with footer:
   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   Co-Authored-By: Claude <noreply@anthropic.com>
...
```

### Block 7: Pull Request 프로토콜

```
# Creating pull requests
Use the gh command via the Bash tool for ALL GitHub-related tasks.

When creating a pull request:
1. Run git status, git diff, git log in parallel
2. Analyze all changes from branch divergence point
3. Draft PR summary with format:
   ## Summary
   - Bullet points

   ## Test plan
   - Checklist

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
...
```

### Block 8: 프로젝트별 지침 (CLAUDE.md가 있으면 주입됨)

```
<system-reminder>
As you answer the user's questions, you can use the following context:
# claudeMd
Codebase and user instructions are shown below.
IMPORTANT: These instructions OVERRIDE any default behavior.

Contents of /Users/jd/Documents/workspace/claude-code-router/CLAUDE.md:
[CLAUDE.md 파일의 전체 내용]
</system-reminder>
```

## 2. 도구(Tools) 목록 및 스키마

Claude Code가 제공하는 도구들:

```json
[
  {
    "name": "Task",
    "description": "Launch a new agent to handle complex, multi-step tasks autonomously...",
    "input_schema": {
      "type": "object",
      "properties": {
        "description": {
          "type": "string",
          "description": "A short (3-5 word) description of the task"
        },
        "prompt": {
          "type": "string",
          "description": "The task for the agent to perform"
        },
        "subagent_type": {
          "type": "string",
          "description": "The type of specialized agent to use"
        },
        "model": {
          "type": "string",
          "enum": ["sonnet", "opus", "haiku"],
          "description": "Optional model to use for this agent"
        },
        "resume": {
          "type": "string",
          "description": "Optional agent ID to resume from"
        }
      },
      "required": ["description", "prompt", "subagent_type"]
    }
  },
  {
    "name": "Bash",
    "description": "Executes a bash command in a persistent shell session...",
    "input_schema": {
      "type": "object",
      "properties": {
        "command": {
          "type": "string",
          "description": "The command to execute"
        },
        "description": {
          "type": "string",
          "description": "Clear, concise description of what this command does in 5-10 words"
        },
        "timeout": {
          "type": "number",
          "description": "Optional timeout in milliseconds (max 600000)"
        },
        "run_in_background": {
          "type": "boolean",
          "description": "Set to true to run this command in the background"
        },
        "dangerouslyDisableSandbox": {
          "type": "boolean",
          "description": "Set to true to run without sandboxing"
        }
      },
      "required": ["command"]
    }
  },
  {
    "name": "Read",
    "description": "Reads a file from the local filesystem...",
    "input_schema": {
      "type": "object",
      "properties": {
        "file_path": {
          "type": "string",
          "description": "The absolute path to the file to read"
        },
        "offset": {
          "type": "number",
          "description": "The line number to start reading from"
        },
        "limit": {
          "type": "number",
          "description": "The number of lines to read"
        }
      },
      "required": ["file_path"]
    }
  },
  {
    "name": "Write",
    "description": "Writes a file to the local filesystem...",
    "input_schema": {
      "type": "object",
      "properties": {
        "file_path": {
          "type": "string",
          "description": "The absolute path to the file to write (must be absolute, not relative)"
        },
        "content": {
          "type": "string",
          "description": "The content to write to the file"
        }
      },
      "required": ["file_path", "content"]
    }
  },
  {
    "name": "Edit",
    "description": "Performs exact string replacements in files...",
    "input_schema": {
      "type": "object",
      "properties": {
        "file_path": {
          "type": "string",
          "description": "The absolute path to the file to modify"
        },
        "old_string": {
          "type": "string",
          "description": "The text to replace"
        },
        "new_string": {
          "type": "string",
          "description": "The text to replace it with"
        },
        "replace_all": {
          "type": "boolean",
          "default": false,
          "description": "Replace all occurences"
        }
      },
      "required": ["file_path", "old_string", "new_string"]
    }
  },
  {
    "name": "Glob",
    "description": "Fast file pattern matching tool...",
    "input_schema": {
      "type": "object",
      "properties": {
        "pattern": {
          "type": "string",
          "description": "The glob pattern to match files against"
        },
        "path": {
          "type": "string",
          "description": "The directory to search in"
        }
      },
      "required": ["pattern"]
    }
  },
  {
    "name": "Grep",
    "description": "A powerful search tool built on ripgrep...",
    "input_schema": {
      "type": "object",
      "properties": {
        "pattern": {
          "type": "string",
          "description": "The regular expression pattern to search for"
        },
        "path": {
          "type": "string",
          "description": "File or directory to search in"
        },
        "output_mode": {
          "type": "string",
          "enum": ["content", "files_with_matches", "count"],
          "description": "Output mode"
        },
        "glob": {
          "type": "string",
          "description": "Glob pattern to filter files"
        },
        "type": {
          "type": "string",
          "description": "File type to search (js, py, rust, go, etc.)"
        },
        "-i": {
          "type": "boolean",
          "description": "Case insensitive search"
        },
        "-A": {
          "type": "number",
          "description": "Lines to show after match"
        },
        "-B": {
          "type": "number",
          "description": "Lines to show before match"
        },
        "-C": {
          "type": "number",
          "description": "Lines to show before and after match"
        },
        "multiline": {
          "type": "boolean",
          "description": "Enable multiline mode"
        },
        "head_limit": {
          "type": "number",
          "description": "Limit output to first N entries"
        },
        "offset": {
          "type": "number",
          "description": "Skip first N entries"
        }
      },
      "required": ["pattern"]
    }
  },
  {
    "name": "TodoWrite",
    "description": "Create and manage a structured task list...",
    "input_schema": {
      "type": "object",
      "properties": {
        "todos": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "content": {
                "type": "string",
                "minLength": 1
              },
              "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed"]
              },
              "activeForm": {
                "type": "string",
                "minLength": 1
              }
            },
            "required": ["content", "status", "activeForm"]
          }
        }
      },
      "required": ["todos"]
    }
  },
  {
    "name": "AskUserQuestion",
    "description": "Ask the user questions during execution...",
    "input_schema": {
      "type": "object",
      "properties": {
        "questions": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "question": {
                "type": "string"
              },
              "header": {
                "type": "string",
                "description": "Short label (max 12 chars)"
              },
              "options": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "label": {
                      "type": "string"
                    },
                    "description": {
                      "type": "string"
                    }
                  },
                  "required": ["label", "description"]
                },
                "minItems": 2,
                "maxItems": 4
              },
              "multiSelect": {
                "type": "boolean"
              }
            },
            "required": ["question", "header", "options", "multiSelect"]
          },
          "minItems": 1,
          "maxItems": 4
        }
      },
      "required": ["questions"]
    }
  },
  {
    "name": "WebFetch",
    "description": "Fetches content from a specified URL...",
    "input_schema": {
      "type": "object",
      "properties": {
        "url": {
          "type": "string",
          "format": "uri"
        },
        "prompt": {
          "type": "string",
          "description": "The prompt to run on the fetched content"
        }
      },
      "required": ["url", "prompt"]
    }
  },
  {
    "name": "WebSearch",
    "description": "Search the web and use the results...",
    "input_schema": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "minLength": 2
        },
        "allowed_domains": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "blocked_domains": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      },
      "required": ["query"]
    }
  },
  {
    "name": "NotebookEdit",
    "description": "Edit Jupyter notebook cells...",
    "input_schema": {
      "type": "object",
      "properties": {
        "notebook_path": {
          "type": "string"
        },
        "new_source": {
          "type": "string"
        },
        "cell_id": {
          "type": "string"
        },
        "cell_type": {
          "type": "string",
          "enum": ["code", "markdown"]
        },
        "edit_mode": {
          "type": "string",
          "enum": ["replace", "insert", "delete"]
        }
      },
      "required": ["notebook_path", "new_source"]
    }
  },
  {
    "name": "ExitPlanMode",
    "description": "Exit plan mode after presenting your plan...",
    "input_schema": {
      "type": "object",
      "properties": {
        "plan": {
          "type": "string",
          "description": "The plan you came up with (supports markdown)"
        }
      },
      "required": ["plan"]
    }
  },
  {
    "name": "SlashCommand",
    "description": "Execute a slash command within the main conversation...",
    "input_schema": {
      "type": "object",
      "properties": {
        "command": {
          "type": "string",
          "description": "The slash command to execute with arguments"
        }
      },
      "required": ["command"]
    }
  },
  {
    "name": "Skill",
    "description": "Execute a skill within the main conversation...",
    "input_schema": {
      "type": "object",
      "properties": {
        "skill": {
          "type": "string",
          "description": "The skill name (no arguments)"
        }
      },
      "required": ["skill"]
    }
  },
  {
    "name": "BashOutput",
    "description": "Retrieves output from a running background shell...",
    "input_schema": {
      "type": "object",
      "properties": {
        "bash_id": {
          "type": "string"
        },
        "filter": {
          "type": "string",
          "description": "Optional regex to filter output lines"
        }
      },
      "required": ["bash_id"]
    }
  },
  {
    "name": "KillShell",
    "description": "Kills a running background bash shell...",
    "input_schema": {
      "type": "object",
      "properties": {
        "shell_id": {
          "type": "string"
        }
      },
      "required": ["shell_id"]
    }
  }
]
```

**총 도구 개수**: 16개

## 3. 대화 흐름 패턴

### 패턴 1: 단순 질문-응답

```json
{
  "messages": [
    {
      "role": "user",
      "content": "package.json 파일을 읽어줘"
    }
  ]
}
```

Claude의 응답:
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "package.json 파일을 읽어보겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_01A23B45C67D89E",
      "name": "Read",
      "input": {
        "file_path": "/Users/jd/Documents/workspace/claude-code-router/package.json"
      }
    }
  ]
}
```

사용자 (도구 결과):
```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01A23B45C67D89E",
      "content": "{\"name\": \"@musistudio/claude-code-router\", ...}"
    }
  ]
}
```

### 패턴 2: 복잡한 작업 (Plan 모드)

```json
{
  "messages": [
    {
      "role": "user",
      "content": "새로운 인증 시스템을 구현해줘"
    }
  ]
}
```

Claude의 응답:
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "인증 시스템 구현을 계획하겠습니다. 먼저 코드베이스를 분석해야 합니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_plan_001",
      "name": "Task",
      "input": {
        "subagent_type": "Explore",
        "description": "Analyze authentication structure",
        "prompt": "Find existing authentication code, database models, and API endpoints..."
      }
    }
  ]
}
```

Plan 에이전트 결과 후:
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_exit_plan",
      "name": "ExitPlanMode",
      "input": {
        "plan": "## Authentication System Implementation\n\n1. Create user model\n2. Add JWT middleware\n3. ..."
      }
    }
  ]
}
```

### 패턴 3: 멀티 도구 사용

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "먼저 관련 파일들을 찾아보겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_glob",
      "name": "Glob",
      "input": {
        "pattern": "**/*.ts"
      }
    }
  ]
}
```

도구 결과 후:
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "이제 특정 패턴을 검색하겠습니다."
    },
    {
      "type": "tool_use",
      "id": "toolu_grep",
      "name": "Grep",
      "input": {
        "pattern": "export.*router",
        "type": "ts"
      }
    }
  ]
}
```

## 4. 특수 기능

### Thinking Mode

```json
{
  "thinking": {
    "type": "enabled",
    "budget_tokens": 10000
  }
}
```

응답에 `thinking` 블록 포함:
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "thinking",
      "thinking": "이 문제를 해결하려면..."
    },
    {
      "type": "text",
      "text": "실제 응답..."
    }
  ]
}
```

### Prompt Caching

```json
{
  "system": [
    {
      "type": "text",
      "text": "긴 시스템 프롬프트...",
      "cache_control": {
        "type": "ephemeral"
      }
    }
  ]
}
```

- 캐시되는 것: 시스템 프롬프트, 최근 대화
- 효과: 비용 절감 (75-90% 할인)

### Session Tracking

```json
{
  "metadata": {
    "user_id": "user_abc123_session_xyz789"
  }
}
```

- `user_abc123`: 사용자 ID
- `session_xyz789`: 세션 ID
- 세션별 컨텍스트 유지

## 5. 에이전트 시스템

### Explore Agent

```json
{
  "name": "Task",
  "input": {
    "subagent_type": "Explore",
    "description": "Find API endpoints",
    "prompt": "Search for all API endpoints in the codebase. Thoroughness: medium"
  }
}
```

- 모든 도구 사용 가능
- 자율적으로 탐색
- thoroughness 레벨에 따라 탐색 깊이 조절

### Plan Agent

```json
{
  "name": "Task",
  "input": {
    "subagent_type": "Plan",
    "description": "Plan feature implementation",
    "prompt": "Create implementation plan for user authentication system"
  }
}
```

- 코드 작성 없이 계획만 수립
- `ExitPlanMode`로 사용자에게 승인 요청

### General-Purpose Agent

```json
{
  "name": "Task",
  "input": {
    "subagent_type": "general-purpose",
    "description": "Complex refactoring task",
    "prompt": "Refactor all React components to use TypeScript",
    "model": "sonnet"
  }
}
```

- 모든 도구 접근
- 복잡한 멀티 스텝 작업

## 6. 실제 요청 예시 (완전한 형태)

```json
{
  "model": "claude-sonnet-4",
  "max_tokens": 8192,
  "temperature": 1.0,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 10000
  },
  "messages": [
    {
      "role": "user",
      "content": "이 프로젝트에 대해 설명해줘"
    }
  ],
  "system": [
    {
      "type": "text",
      "text": "[50,000+ 토큰의 시스템 프롬프트]",
      "cache_control": {"type": "ephemeral"}
    },
    {
      "type": "text",
      "text": "<env>Working directory: /path/to/project\nPlatform: darwin\n...</env>",
      "cache_control": {"type": "ephemeral"}
    }
  ],
  "tools": [
    /* 16개 도구의 전체 스키마 */
  ],
  "metadata": {
    "user_id": "user_abc123_session_xyz789"
  }
}
```

**토큰 분석**:
- 시스템 프롬프트: ~50,000 토큰 (캐시됨)
- 도구 정의: ~15,000 토큰 (캐시됨)
- 사용자 메시지: 가변
- 총 입력: ~65,000+ 토큰 (캐시 없이는 매우 비쌈!)

## 7. 주요 특징 요약

1. **매우 긴 시스템 프롬프트**: 50,000+ 토큰
2. **Prompt Caching 적극 활용**: 비용 최적화
3. **풍부한 도구 세트**: 16개 도구, 각각 상세한 지침
4. **에이전트 시스템**: Task tool로 서브에이전트 실행
5. **Thinking Mode**: 추론 과정 노출
6. **작업 관리**: TodoWrite로 진행 상황 추적
7. **출력 스타일**: Explanatory/Concise/Detailed 선택 가능
8. **Git 통합**: 안전한 커밋/PR 생성
9. **프로젝트 커스터마이징**: CLAUDE.md로 지침 오버라이드
10. **세션 관리**: 프로젝트별 대화 컨텍스트 유지
