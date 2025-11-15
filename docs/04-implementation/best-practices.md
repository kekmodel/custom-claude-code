# 베스트 프랙티스

> Claude Code 구현 시 알아야 할 핵심 패턴과 안티패턴

---

## 시스템 프롬프트 작성

### ✅ DO: 구체적이고 상세하게

```markdown
# Read Tool

**When to use**:
- User asks to read a file: "Show me config.ts"
- Before editing a file to understand context
- Analyzing error messages in log files

**When NOT to use**:
- Don't use `cat` command via Bash
- Don't guess file contents
- Don't read files without explicit need

**Parameters**:
- file_path: MUST be absolute path (e.g., "/Users/x/project/file.ts")
- offset: Optional, for large files (start from line N)
- limit: Optional, read N lines only

**Examples**:

Good:
\```json
{"name": "Read", "input": {"file_path": "/absolute/path/file.ts"}}
\```

Bad:
\```json
{"name": "Read", "input": {"file_path": "./relative/path"}}  // ← 상대 경로!
\```
```

### ❌ DON'T: 너무 간단하게

```markdown
# Read Tool
Reads files.
```

**문제**: LLM이 언제 사용할지, 어떻게 사용할지 모름.

---

## 도구 설계

### ✅ DO: 안전성 우선

```typescript
async function executeBash(command: string): Promise<string> {
  // 1. 위험한 명령어 차단
  const dangerous = [
    "rm -rf /",
    "sudo",
    "su",
    "> /dev/sda", // 디스크 덮어쓰기
    ":(){ :|:& };:", // fork bomb
  ];

  if (dangerous.some((cmd) => command.includes(cmd))) {
    throw new Error(`Dangerous command blocked: ${command}`);
  }

  // 2. 타임아웃 설정
  try {
    const output = execSync(command, {
      encoding: "utf-8",
      timeout: 30000, // 30초
      maxBuffer: 10 * 1024 * 1024, // 10MB
    });
    return output;
  } catch (error) {
    // 에러 정보 포함
    return `Command failed: ${error.message}\nStderr: ${error.stderr}`;
  }
}
```

### ✅ DO: 명확한 에러 메시지

```typescript
async function readFile(path: string): Promise<string> {
  // 검증
  if (!path.startsWith("/")) {
    throw new Error(
      `File path must be absolute. Got: ${path}\nExample: /Users/user/project/file.ts`
    );
  }

  if (!existsSync(path)) {
    throw new Error(
      `File not found: ${path}\n\nDid you mean:\n- Check if path is correct\n- Use Glob to find the file first`
    );
  }

  // 실행
  const content = await fs.readFile(path, "utf-8");
  return content;
}
```

### ❌ DON'T: 모호한 에러

```typescript
async function readFile(path: string): Promise<string> {
  try {
    return await fs.readFile(path, "utf-8");
  } catch {
    return "Error"; // ← 무슨 에러인지 모름!
  }
}
```

---

## Prompt Caching

### ✅ DO: 반드시 적용

```typescript
const response = await client.messages.create({
  model: "claude-sonnet-4",
  max_tokens: 8192,
  system: [
    {
      type: "text",
      text: SYSTEM_PROMPT, // 50k+ tokens
      cache_control: { type: "ephemeral" }, // ← 필수!
    },
  ],
  tools: TOOLS,
  messages,
});
```

**효과**:
```
Caching 없이: $1.95 (10 requests)
Caching 있으면: $0.60 (10 requests)
절감: 69%
```

### ❌ DON'T: 캐싱 없이 50k+ 토큰

```typescript
// 이렇게 하면 파산함!
const response = await client.messages.create({
  system: HUGE_SYSTEM_PROMPT, // 매번 $0.15!
  // ...
});
```

---

## 도구 사용 루프

### ✅ DO: stop_reason 명확히 처리

```typescript
while (true) {
  const response = await claude.create({...});

  if (response.stop_reason === "end_turn") {
    // 완료 - 사용자에게 표시
    displayToUser(response.content);
    break;
  }

  else if (response.stop_reason === "tool_use") {
    // 도구 실행 - 루프 계속
    const results = await executeTools(response.content);
    messages.push({role: "assistant", content: response.content});
    messages.push({role: "user", content: results});
    continue;
  }

  else if (response.stop_reason === "max_tokens") {
    // 토큰 부족 - 에러
    throw new Error("Response truncated - increase max_tokens");
  }

  else {
    // 예상 못한 stop_reason
    throw new Error(`Unknown stop_reason: ${response.stop_reason}`);
  }
}
```

### ❌ DON'T: stop_reason 무시

```typescript
// 이렇게 하면 도구가 실행 안 됨!
const response = await claude.create({...});
console.log(response.content); // ← tool_use일 수도 있는데 그냥 표시?
```

---

## Subagent 설계

### ✅ DO: 독립적인 컨텍스트

```typescript
async function executeTask(taskInput: TaskInput): Promise<string> {
  // 새로운 messages (독립!)
  const subagentMessages = [
    {
      role: "user",
      content: taskInput.prompt, // ← Task의 prompt만
    },
  ];

  // Subagent 실행
  while (true) {
    const response = await claude.create({
      system: SYSTEM_PROMPT, // 같은 프롬프트
      tools: TOOLS, // 같은 도구
      messages: subagentMessages, // ← 독립된 messages!
    });

    // ...
  }
}
```

### ❌ DON'T: Main messages 공유

```typescript
async function executeTask(taskInput: TaskInput): Promise<string> {
  // Main의 messages 사용 (잘못됨!)
  mainMessages.push({role: "user", content: taskInput.prompt});

  const response = await claude.create({
    messages: mainMessages, // ← Main context 오염!
  });
}
```

**문제**: Subagent가 Main의 대화 내용을 보게 됨 → 혼란

---

## 에러 복구

### ✅ DO: 자동 재시도 (최대 N번)

```typescript
async function verifyAndFix(maxRetries = 3): Promise<boolean> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    // 빌드 실행
    const buildResult = await bash("npm run build");

    if (buildResult.success) {
      return true; // 성공!
    }

    // 실패 - 에러 분석
    const errorLog = await read(buildResult.logPath);
    const fix = analyzeMistake(errorLog);

    // 수정
    await edit(fix.file, fix.oldCode, fix.newCode);

    console.log(`Attempt ${attempt}/${maxRetries} failed, retrying...`);
  }

  // 최종 실패
  throw new Error(
    `Build failed after ${maxRetries} attempts. Manual intervention needed.`
  );
}
```

### ❌ DON'T: 무한 루프

```typescript
async function verifyAndFix(): Promise<void> {
  while (true) {
    // 무한 루프! 멈출 수 없음!
    const result = await bash("npm run build");
    if (result.success) break;

    await autoFix(); // 계속 시도...
  }
}
```

---

## 대화 관리

### ✅ DO: messages append-only

```typescript
const messages: Array<Message> = [];

// 사용자 입력 추가
messages.push({ role: "user", content: userInput });

// Assistant 응답 추가
messages.push({ role: "assistant", content: response.content });

// 도구 결과 추가
messages.push({ role: "user", content: toolResults });

// 절대 삭제하지 않음!
```

### ❌ DON'T: messages 수정/삭제

```typescript
// 잘못된 예
messages.pop(); // ← 삭제하지 마세요!
messages[0] = newMessage; // ← 수정하지 마세요!
messages.splice(2, 1); // ← 중간 삭제도 안 됩니다!
```

**이유**: DAG 구조 유지, 대화 히스토리 보존

---

## 비용 최적화

### ✅ DO: 토큰 사용량 추적

```typescript
let totalInputTokens = 0;
let totalOutputTokens = 0;
let totalCachedTokens = 0;

const response = await claude.create({...});

totalInputTokens += response.usage.input_tokens;
totalOutputTokens += response.usage.output_tokens;
totalCachedTokens += response.usage.cache_read_tokens || 0;

const cost =
  (totalInputTokens / 1000) * 0.003 +
  (totalOutputTokens / 1000) * 0.015 +
  (totalCachedTokens / 1000) * 0.0003;

console.log(`Total cost: $${cost.toFixed(4)}`);
```

### ✅ DO: 긴 대화 시 요약

```typescript
if (messages.length > 100) {
  // 오래된 대화 요약
  const summary = await summarizeConversation(messages.slice(0, 50));

  messages = [
    { role: "user", content: `[Conversation summary: ${summary}]` },
    ...messages.slice(50), // 최근 대화만 유지
  ];
}
```

---

## 보안

### ✅ DO: 사용자 확인

```typescript
async function deleteFiles(paths: string[]): Promise<void> {
  // 위험한 작업 - 사용자 확인 필수!
  const confirmation = await askUser({
    question: `Delete ${paths.length} files?`,
    options: [
      { label: "Yes", description: "Permanently delete files" },
      { label: "No", description: "Cancel operation" },
    ],
  });

  if (confirmation !== "Yes") {
    throw new Error("Operation cancelled by user");
  }

  // 실행...
}
```

### ❌ DON'T: 위험한 작업 자동 실행

```typescript
async function cleanup(): Promise<void> {
  // 위험! 사용자 확인 없이 삭제!
  await bash("rm -rf node_modules");
  await bash("rm -rf .git");
}
```

---

## 테스트

### ✅ DO: 도구 단위 테스트

```typescript
describe("Read tool", () => {
  it("should read existing file", async () => {
    const result = await readFile("/path/to/test.txt");
    expect(result).toContain("expected content");
  });

  it("should reject relative paths", async () => {
    await expect(readFile("./relative/path")).rejects.toThrow(
      "must be absolute"
    );
  });

  it("should throw on missing file", async () => {
    await expect(readFile("/nonexistent")).rejects.toThrow("not found");
  });
});
```

### ✅ DO: 전체 플로우 테스트

```typescript
describe("Bug fix workflow", () => {
  it("should read, edit, verify", async () => {
    const messages = [
      { role: "user", content: "Fix typo in file.ts" },
    ];

    // Turn 1: Read
    let response = await runAgent({ messages });
    expect(response.content).toContainToolUse("Read");

    // Turn 2: Edit
    messages.push({ role: "assistant", content: response.content });
    messages.push({ role: "user", content: executeTools(response.content) });

    response = await runAgent({ messages });
    expect(response.content).toContainToolUse("Edit");

    // Turn 3: Verify
    // ...
  });
});
```

---

## 패턴 요약

### 좋은 패턴 (✅)

1. **도구 중심**: 모든 작업을 도구 조합으로
2. **안전 우선**: 위험한 작업은 확인 필수
3. **명확한 에러**: 무엇이 잘못되었는지 정확히
4. **Prompt Caching**: 50k+ 토큰은 반드시 캐싱
5. **stop_reason 처리**: end_turn vs tool_use 명확히
6. **독립 Subagent**: 각자의 messages
7. **제한된 재시도**: 무한 루프 방지
8. **append-only messages**: 삭제/수정 금지
9. **비용 추적**: 토큰 사용량 모니터링
10. **단위 테스트**: 각 도구 개별 테스트

### 나쁜 패턴 (❌)

1. **모호한 프롬프트**: "Do something"
2. **안전성 무시**: 확인 없이 삭제
3. **캐싱 없이 대용량**: 비용 폭탄
4. **stop_reason 무시**: 도구 미실행
5. **Context 공유**: Subagent가 Main 봄
6. **무한 재시도**: 멈출 수 없음
7. **messages 수정**: DAG 깨짐
8. **비용 미추적**: 예상 못한 청구서
9. **테스트 없음**: 버그 발견 못 함
10. **에러 숨김**: "Error" (무슨 에러?)

---

## 체크리스트

### 배포 전 확인

- [ ] 모든 도구에 상세한 지침 (시스템 프롬프트)
- [ ] Prompt Caching 적용 확인
- [ ] 위험한 명령어 차단 (rm, sudo 등)
- [ ] 사용자 확인 플로우 (삭제, 덮어쓰기)
- [ ] 최대 재시도 횟수 설정
- [ ] 토큰 사용량 추적
- [ ] 에러 로깅
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 작성
- [ ] 비용 예산 설정

---

**생성 날짜**: 2025-11-15
**목적**: 안전하고 효율적인 AI 코딩 어시스턴트 구축
