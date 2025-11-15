# 커스텀 Claude Code 구현 시작하기

> Claude Code를 참고하여 자체 AI 코딩 어시스턴트 구축하기

---

## 전제 조건

### 필수 이해

이 가이드를 시작하기 전에 다음을 이해해야 합니다:

- ✅ [시스템 개요](../01-architecture/system-overview.md)
- ✅ [그래프 구조](../01-architecture/graph-structure.md)
- ✅ [기본 플로우](../03-interactions/basic-flow.md)

### 필수 기술

- LLM API 사용 경험 (Anthropic, OpenAI, 등)
- TypeScript/JavaScript (Node.js)
- 기본 프롬프트 엔지니어링

---

## 최소 구현 체크리스트

### Phase 1: 기본 루프 (1-2일)

```
[✓] 1. LLM API 연결
    - Anthropic API 또는 다른 LLM 선택
    - 환경 변수 설정

[✓] 2. 기본 대화 루프
    - 사용자 입력 → LLM 요청 → 응답 표시
    - messages 배열 관리 (append-only)

[✓] 3. stop_reason 처리
    - "end_turn": 사용자에게 표시
    - "tool_use": 도구 실행 루프
```

### Phase 2: 도구 시스템 (2-3일)

```
[✓] 4. 핵심 도구 구현 (최소 4개)
    - Read: 파일 읽기
    - Write: 파일 쓰기
    - Edit: 문자열 교체
    - Bash: 명령 실행

[✓] 5. 도구 실행 엔진
    - tool_use 파싱
    - 도구 함수 호출
    - tool_result 생성
    - messages에 추가

[✓] 6. 에러 처리
    - 도구 실행 실패 시 에러 메시지
    - 안전성 검증 (경로, 명령어)
```

### Phase 3: 시스템 프롬프트 (3-5일)

```
[✓] 7. 기본 시스템 프롬프트 작성 (최소 10k+ 토큰)
    - 정체성 정의
    - 각 도구 사용 지침
    - 예시 및 안티패턴

[✓] 8. Prompt Caching 적용
    - Anthropic: cache_control
    - 다른 LLM: 자체 캐싱 구현

[✓] 9. 환경 정보 추가
    - Working directory
    - Platform, OS
    - Git repo 정보
```

### Phase 4: 고급 기능 (1주+)

```
[✓] 10. Subagent 시스템 (Task tool)
    - Subprocess 생성
    - 독립 컨텍스트
    - 결과 리턴

[✓] 11. TodoWrite 시스템
    - 작업 추적 UI
    - pending/in_progress/completed

[✓] 12. 에러 복구
    - Verify → Fix → Re-verify
    - 최대 재시도 횟수
```

---

## 빠른 시작 코드

### 1. 기본 구조

```typescript
// main.ts
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const SYSTEM_PROMPT = `
You are an AI coding assistant.

You have access to the following tools:
- Read: Read files
- Write: Write files
- Edit: Edit files
- Bash: Execute commands

Always use tools to complete tasks.
`;

const TOOLS = [
  {
    name: "Read",
    description: "Read a file from the filesystem",
    input_schema: {
      type: "object",
      properties: {
        file_path: { type: "string", description: "Absolute path to file" },
      },
      required: ["file_path"],
    },
  },
  // ... 다른 도구들
];

async function main() {
  const messages: Array<any> = [];

  while (true) {
    // 사용자 입력
    const userInput = await getUserInput();
    if (userInput === "quit") break;

    messages.push({ role: "user", content: userInput });

    // 도구 사용 루프
    while (true) {
      const response = await client.messages.create({
        model: "claude-sonnet-4",
        max_tokens: 8192,
        system: SYSTEM_PROMPT,
        tools: TOOLS,
        messages,
      });

      if (response.stop_reason === "end_turn") {
        // 사용자에게 표시
        console.log(response.content);
        messages.push({ role: "assistant", content: response.content });
        break; // 사용자 입력 대기로
      }

      if (response.stop_reason === "tool_use") {
        // 도구 실행
        messages.push({ role: "assistant", content: response.content });

        const toolResults = await executeTools(response.content);
        messages.push({ role: "user", content: toolResults });

        // 다시 요청
        continue;
      }
    }
  }
}
```

### 2. 도구 실행

```typescript
async function executeTools(content: Array<any>): Promise<Array<any>> {
  const results = [];

  for (const block of content) {
    if (block.type !== "tool_use") continue;

    try {
      let result;

      switch (block.name) {
        case "Read":
          result = await readFile(block.input.file_path);
          break;

        case "Write":
          result = await writeFile(block.input.file_path, block.input.content);
          break;

        case "Edit":
          result = await editFile(
            block.input.file_path,
            block.input.old_string,
            block.input.new_string
          );
          break;

        case "Bash":
          result = await executeBash(block.input.command);
          break;

        default:
          throw new Error(`Unknown tool: ${block.name}`);
      }

      results.push({
        type: "tool_result",
        tool_use_id: block.id,
        content: result,
      });
    } catch (error) {
      results.push({
        type: "tool_result",
        tool_use_id: block.id,
        content: `Error: ${error.message}`,
        is_error: true,
      });
    }
  }

  return results;
}
```

### 3. 도구 구현

```typescript
import fs from "fs/promises";
import { execSync } from "child_process";

async function readFile(path: string): Promise<string> {
  // 안전성 검증
  if (!path.startsWith("/")) {
    throw new Error("File path must be absolute");
  }

  const content = await fs.readFile(path, "utf-8");
  return content;
}

async function writeFile(path: string, content: string): Promise<string> {
  await fs.writeFile(path, content, "utf-8");
  return `File written successfully: ${path}`;
}

async function editFile(
  path: string,
  oldString: string,
  newString: string
): Promise<string> {
  const content = await fs.readFile(path, "utf-8");

  if (!content.includes(oldString)) {
    throw new Error("old_string not found in file");
  }

  const newContent = content.replace(oldString, newString);
  await fs.writeFile(path, newContent, "utf-8");

  return `File edited successfully`;
}

async function executeBash(command: string): Promise<string> {
  // 안전성 검증
  const dangerousCommands = ["rm -rf /", "sudo", "su"];
  if (dangerousCommands.some((cmd) => command.includes(cmd))) {
    throw new Error("Dangerous command blocked");
  }

  try {
    const output = execSync(command, {
      encoding: "utf-8",
      timeout: 30000, // 30초
    });
    return output;
  } catch (error) {
    return `Error: ${error.message}\n${error.stderr}`;
  }
}
```

---

## Prompt Caching 적용

### Anthropic API

```typescript
const response = await client.messages.create({
  model: "claude-sonnet-4",
  max_tokens: 8192,
  system: [
    {
      type: "text",
      text: SYSTEM_PROMPT, // 50k+ tokens
      cache_control: { type: "ephemeral" }, // ← 캐싱!
    },
  ],
  tools: TOOLS,
  messages,
});

// 비용 확인
console.log({
  input_tokens: response.usage.input_tokens,
  cache_creation_tokens: response.usage.cache_creation_tokens, // 첫 요청만
  cache_read_tokens: response.usage.cache_read_tokens, // 두 번째부터
  output_tokens: response.usage.output_tokens,
});
```

**효과**:
```
첫 요청: cache_creation_tokens: 50000 ($0.15)
다음 요청: cache_read_tokens: 50000 ($0.015, 90% 절감!)
```

---

## 시스템 프롬프트 작성

### 최소 구조

```markdown
# You are [정체성]

You are an AI coding assistant that helps users with programming tasks.

## Tools

You have access to the following tools:

### Read Tool

**Description**: Read a file from the filesystem.

**Usage**:
- file_path must be an absolute path
- By default, reads entire file
- For large files, use offset and limit

**When to use**:
- User asks to read a file
- You need to understand code before editing
- Analyzing file contents

**When NOT to use**:
- Don't use `cat` command, use Read tool instead

**Examples**:
\```json
{
  "tool_use": {
    "name": "Read",
    "input": {
      "file_path": "/path/to/file.ts"
    }
  }
}
\```

### [다른 도구들...]

## Workflow

When user asks to fix a bug:
1. Read the file
2. Analyze the code
3. Edit to fix
4. Run build to verify
5. If build fails, read error and fix again

## Safety

- NEVER run destructive commands without confirmation
- Always use absolute paths
- Verify file existence before editing
```

---

## 다음 단계

### 추천 학습 순서

1. ✅ **기본 구현 완성** (이 문서)
2. 📖 [커스텀 Agent 구현](custom-agents.md)
3. 📖 [베스트 프랙티스](best-practices.md)
4. 🔍 [실제 예시](../../examples/) 분석

### 고급 기능 추가

- [ ] Subagent 시스템 (Task tool)
- [ ] TodoWrite로 작업 추적
- [ ] AskUserQuestion으로 확인
- [ ] WebSearch 통합
- [ ] Git 작업 자동화
- [ ] PR 생성 기능

---

**생성 날짜**: 2025-11-15
**목적**: 최소 기능 AI 코딩 어시스턴트 빠르게 구축하기
