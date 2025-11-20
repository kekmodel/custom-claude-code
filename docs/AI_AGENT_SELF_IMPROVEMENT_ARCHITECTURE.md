# AI Agent Self-Improvement Architecture
## Claude Code의 지속적 목표 달성 메커니즘 - Ultra Deep Dive

> **분석 범위**: Claude Code CLI + Claude Agent SDK Python
> **분석 방법**: 코드 구현 + 프롬프트 설계 + 실제 대화 패턴 종합
> **핵심 질문**: 어떻게 Agent가 interactive하고, 정확도 높고, 스스로 개선하며, 목표를 달성하는가?

---

## Executive Summary

Claude Code는 **반복적 자기 수정(Iterative Self-Correction)** 아키텍처를 통해 목표를 달성합니다. 핵심은:

1. **무한 루프가 아닌 목표 지향적 반복** - finish_reason과 TodoWrite로 제어
2. **도구 실행 결과를 즉시 분석** - LLM이 성공/실패를 판단하고 다음 행동 결정
3. **명시적 프롬프트 엔지니어링** - "If you notice insecure code, immediately fix it"
4. **계층적 작업 분해** - Main Agent → Task Subagent → 독립 실행
5. **상태 기반 메모리** - messages는 append-only, 모든 컨텍스트 유지

**결론**: Claude Code는 "단순 LLM 호출"이 아니라 **Self-Supervising Agent Loop**입니다.

---

## 1. 핵심 아키텍처: The Agent Loop

### 1.1 기본 루프 구조

```python
# v1_openai/main.py:276-331
async def process_turn_loop(messages, system_prompt, max_turns=50):
    """Claude Code의 핵심: finish_reason이 'stop'일 때까지 반복"""
    turn_count = 0

    while turn_count < max_turns:
        turn_count += 1

        # Step 1: LLM 호출
        assistant_message = await stream_assistant_response(messages, system_prompt)
        finish_reason = assistant_message.pop("_finish_reason", "stop")
        messages.append(assistant_message)

        # Step 2: finish_reason 분기
        if finish_reason == "stop":
            break  # LLM이 "완료"라고 판단

        elif finish_reason == "tool_calls":
            # Step 3: 도구 실행
            tool_calls = assistant_message.get("tool_calls", [])
            tool_results = [await execute_single_tool_call(tc, system_prompt) for tc in tool_calls]

            # Step 4: 결과를 messages에 추가
            messages.extend(tool_results)

            # Step 5: 루프 계속 (LLM이 tool_result 분석)
            continue

        elif finish_reason == "length":
            break  # 토큰 한계

        else:
            break  # 에러 등

    if turn_count >= max_turns:
        print("Max turns exceeded")  # 무한 루프 방지
```

### 1.2 루프의 핵심 특징

**특징 1: LLM이 루프를 제어**
- `finish_reason == "stop"` → LLM이 "이제 완료했다"고 판단
- `finish_reason == "tool_calls"` → LLM이 "더 작업이 필요하다"고 판단
- **코드가 루프를 제어하는 것이 아니라 LLM이 제어**

**특징 2: 상태는 messages에만 저장**
```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": "Fix the bug"},
    {"role": "assistant", "content": "Let me read the file", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "File content: ..."},  # ← LLM이 이걸 본다!
    {"role": "assistant", "content": "I found the bug", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "File edited"},  # ← LLM이 이걸 본다!
    {"role": "assistant", "content": "Let me verify", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "Build success"},  # ← LLM이 이걸 본다!
    {"role": "assistant", "content": "Done!"}  # finish_reason == "stop"
]
```

**특징 3: 무한 루프 방지**
- `max_turns=50` (하드 리미트)
- LLM이 스스로 `finish_reason="stop"` 반환해야 함
- TodoWrite로 진행 상황 추적

---

## 2. Self-Correction 메커니즘

### 2.1 에러 감지 및 복구 패턴

**코드 구현**:
```python
# v1_openai/main.py:262-273
async def execute_single_tool_call(tool_call, system_prompt):
    tool_name = tool_call["function"]["name"]
    tool_input = json.loads(tool_call["function"]["arguments"])

    try:
        tool_result = await execute_tool(tool_name, tool_input)
        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": tool_result.result  # ← 성공 시 결과
        }
    except Exception as e:
        error_msg = f"Error: {type(e).__name__}: {str(e)}"
        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": error_msg  # ← 실패 시 에러 메시지
        }
```

**핵심**: 에러를 던지지 않고 **tool_result로 반환**
- LLM이 다음 턴에 `tool_result`를 보고 판단
- 성공이면 다음 단계 진행
- 실패면 다른 방법 시도

### 2.2 실제 Self-Correction 예시

**시나리오**: 빌드 실패 → 에러 분석 → 수정 → 재빌드

```
Turn 1:
  User: "Run the build and fix any errors"

Turn 2:
  LLM: "I'll run the build"
  Tool: Bash("npm run build")

Turn 3:
  Tool Result: "Error: Type error in src/index.ts:42"  # ← 실패!

Turn 4:
  LLM: "I found a type error. Let me read the file"  # ← 스스로 판단!
  Tool: Read("src/index.ts")

Turn 5:
  Tool Result: "[file content with error at line 42]"

Turn 6:
  LLM: "I'll fix the type error"
  Tool: Edit("src/index.ts", old="const x: number = 'hello'", new="const x: string = 'hello'")

Turn 7:
  Tool Result: "File edited successfully"

Turn 8:
  LLM: "Let me rebuild to verify"  # ← 스스로 검증!
  Tool: Bash("npm run build")

Turn 9:
  Tool Result: "Build successful"  # ← 성공!

Turn 10:
  LLM: "Build completed successfully!"
  finish_reason: "stop"  # ← 완료 판단
```

**패턴 분석**:
1. **실패 감지**: Tool Result의 에러 메시지
2. **원인 분석**: Read 도구로 파일 읽기
3. **수정 실행**: Edit 도구로 코드 수정
4. **검증**: 다시 Bash로 빌드
5. **완료 판단**: 성공 확인 후 `finish_reason="stop"`

### 2.3 프롬프트 레벨 Self-Correction 지시

**시스템 프롬프트의 명시적 지시**:
```
# Doing tasks
- Be careful not to introduce security vulnerabilities such as command injection,
  XSS, SQL injection, and other OWASP top 10 vulnerabilities.
  If you notice that you wrote insecure code, immediately fix it.
```

**핵심**: "If you notice... immediately fix it"
- LLM에게 **자기 검증 의무** 부여
- 도구 실행 결과를 보고 스스로 판단
- 문제 발견 시 즉시 수정 행동

---

## 3. 목표 추적 시스템: TodoWrite

### 3.1 TodoWrite의 역할

**프롬프트 지시**:
```
# Task Management
You have access to the TodoWrite tools to help you manage and plan tasks.
Use these tools VERY frequently to ensure that you are tracking your tasks
and giving the user visibility into your progress.

These tools are also EXTREMELY helpful for planning tasks, and for breaking
down larger complex tasks into smaller steps. If you do not use this tool
when planning, you may forget to do important tasks - and that is unacceptable.

It is critical that you mark todos as completed as soon as you are done with a task.
Do not batch up multiple tasks before marking them as completed.
```

**핵심 원칙**:
1. **"VERY frequently"** - 자주 사용해야 함
2. **"unacceptable"** - 사용하지 않으면 안 됨 (강력한 명령)
3. **즉시 완료 표시** - 배치 처리 금지

### 3.2 TodoWrite 사용 패턴

**예시 1: 복잡한 작업 분해**
```
User: "Help me write a new feature that allows users to track their usage metrics"

LLM: I'll help you implement a usage metrics tracking feature.
     Let me first use the TodoWrite tool to plan this task.

Tool: TodoWrite([
    {content: "Research existing metrics tracking in the codebase", status: "pending"},
    {content: "Design the metrics collection system", status: "pending"},
    {content: "Implement core metrics tracking functionality", status: "pending"},
    {content: "Create export functionality for different formats", status: "pending"}
])

LLM: Let me start by researching the existing codebase...

Tool: task_tool(subagent_type="Explore", description="Find existing metrics code")
...
Tool Result: "[Subagent report: Found telemetry.ts with basic tracking]"

LLM: I've found existing telemetry code. Let me mark the first todo as completed.

Tool: TodoWrite([
    {content: "Research existing metrics tracking in the codebase", status: "completed"},  # ← 완료!
    {content: "Design the metrics collection system", status: "in_progress"},  # ← 다음 시작
    ...
])
```

**패턴**:
- **계획**: 전체 작업을 작은 단계로 분해
- **실행**: 한 단계씩 진행
- **추적**: 각 단계 완료 즉시 표시
- **가시성**: 사용자가 진행 상황 확인 가능

### 3.3 TodoWrite와 Self-Correction의 결합

```
User: "Run the build and fix any type errors"

LLM: I'm going to use the TodoWrite tool to write the following items:
Tool: TodoWrite([
    {content: "Run the build", status: "pending"},
    {content: "Fix any type errors", status: "pending"}
])

LLM: I'm now going to run the build using Bash.
Tool: Bash("npm run build")
Tool Result: "10 type errors found"

LLM: I found 10 type errors. I'm going to update the todo list.
Tool: TodoWrite([
    {content: "Run the build", status: "completed"},
    {content: "Fix type error in src/index.ts:42", status: "pending"},
    {content: "Fix type error in src/utils.ts:15", status: "pending"},
    # ... 10 items total
])

LLM: Marking the first todo as in_progress...
Tool: TodoWrite([
    {content: "Run the build", status: "completed"},
    {content: "Fix type error in src/index.ts:42", status: "in_progress"},  # ← 현재 작업
    ...
])

[Fix the error]

LLM: The first item has been fixed, let me mark it as completed and move on...
Tool: TodoWrite([
    {content: "Run the build", status: "completed"},
    {content: "Fix type error in src/index.ts:42", status: "completed"},  # ← 완료!
    {content: "Fix type error in src/utils.ts:15", status: "in_progress"},  # ← 다음
    ...
])

[Continue until all 10 errors are fixed]
```

**핵심**:
- **동적 계획**: 빌드 결과를 보고 Todo 리스트 확장
- **순차 처리**: 한 번에 하나씩 (in_progress는 1개만)
- **완료 보장**: 모든 에러를 수정할 때까지 반복
- **무한 루프 방지**: Todo 개수가 유한하므로 종료 보장

---

## 4. 계층적 작업 분해: Subagent System

### 4.1 Subagent의 목적

**프롬프트 지시**:
```
# Tool usage policy
- When exploring the codebase to gather context or to answer a question that
  is not a needle query for a specific file/class/function, it is CRITICAL
  that you use the Task tool with subagent_type=Explore instead of running
  search commands directly.

Example:
user: Where are errors from the client handled?
assistant: [Uses the Task tool with subagent_type=Explore to find the files
           that handle client errors instead of using Glob or Grep directly]
```

**핵심**: **"CRITICAL"** - 탐색 작업은 반드시 Subagent 사용

### 4.2 Subagent 독립 실행 구조

```python
# v2_1_langgraph_improved/nodes.py:63-156
async def execute_subagent(
    subagent_type: str,
    prompt: str,
    system_prompt: str,
    current_depth: int = 0,
    max_depth: int = 5
):
    """독립 StateGraph로 Subagent 실행"""

    if current_depth >= max_depth:
        return "[ERROR] Max subagent depth exceeded"  # 재귀 방지

    # 도구 제한 (역할별)
    if subagent_type == "Explore":
        # 읽기 전용: 파일 수정/실행 금지
        allowed_tools = {"read_file", "grep_code", "glob_files", "web_search", "web_fetch"}
    elif subagent_type == "Plan":
        # 계획만: 실행 금지
        allowed_tools = {"read_file", "grep_code", "glob_files", "web_search", "web_fetch"}
    else:  # general-purpose
        # 모든 도구 (task_tool, todo_write 제외)
        allowed_tools = ALL_TOOLS - {"task_tool", "todo_write"}

    # 독립 StateGraph 생성
    subagent_graph = StateGraph(AgentState)
    subagent_graph.add_node("agent", subagent_call_agent)
    subagent_graph.add_node("tools", ToolNode(allowed_tools))
    # ... 그래프 구성

    # 독립 실행 (callbacks=[] 로 이벤트 격리)
    final_state = await subagent_graph.ainvoke(
        initial_state,
        config=RunnableConfig(callbacks=[])  # ← Main과 분리!
    )

    # 최종 AIMessage만 반환
    return last_message.content
```

### 4.3 Subagent의 핵심 특징

**특징 1: 독립된 대화 컨텍스트**
```
Main Agent Context:
  - messages: [user: "Find the bug", assistant: "I'll use Explore agent"]

Explore Subagent Context (독립):
  - messages: [user: "Where are errors from the client handled?"]
  - system_prompt: "You are a file search specialist..."
  - tools: ["read_file", "grep_code", "glob_files"]  # 읽기 전용
  - 자체 Agent Loop 실행

Main Agent receives:
  - Subagent의 최종 보고서만 받음 (문자열)
  - Subagent의 중간 메시지는 Main에 영향 없음
```

**특징 2: 역할 기반 도구 제한**
```python
Explore Agent:
  ✅ read_file, grep_code, glob_files, web_search
  ❌ write_file, edit_file, run_bash
  → "READ-ONLY exploration task. You MUST NOT create, write, or modify any files"

Plan Agent:
  ✅ read_file, grep_code, glob_files, web_search
  ❌ write_file, edit_file, run_bash
  → "Plan only, no execution"

General-purpose Agent:
  ✅ 모든 도구
  ❌ task_tool (재귀 방지), todo_write (Main 전용)
  → "Complex multi-step tasks"
```

**특징 3: 재귀 깊이 제한**
```python
max_depth = 5  # Subagent가 또 다른 Subagent를 호출 가능
current_depth = 0

# Main → Subagent1 (depth=1) → Subagent2 (depth=2) → ... → Subagent5 (depth=5) → STOP
```

### 4.4 Subagent 사용 패턴

**시나리오**: 복잡한 버그 수정

```
User: "There's a bug in the authentication system. Find and fix it."

Main Agent:
  Turn 1: I'll use the Explore agent to locate authentication code.
  Tool: task_tool(
    subagent_type="Explore",
    description="Find authentication-related files",
    prompt="Locate all files related to user authentication"
  )

  [Explore Subagent 독립 실행]
  Explore Subagent Turn 1:
    Tool: glob_files("**/auth*")
    Tool Result: ["src/auth/login.ts", "src/auth/session.ts", ...]

  Explore Subagent Turn 2:
    Tool: grep_code("authentication", type="ts")
    Tool Result: ["src/middleware/auth.ts:42", ...]

  Explore Subagent Turn 3:
    Tool: read_file("src/middleware/auth.ts")
    Tool Result: "[file content]"

  Explore Subagent Turn 4:
    LLM: "Found the authentication logic in 3 files..."
    finish_reason: "stop"

  [Explore Subagent 보고서 반환]
  Tool Result: "Authentication system found in:\n1. src/auth/login.ts - login logic\n..."

Main Agent:
  Turn 2: I found the auth files. Let me read the main file.
  Tool: read_file("src/auth/login.ts")
  Tool Result: "[file content with bug at line 78]"

Main Agent:
  Turn 3: I found the bug at line 78. Let me fix it.
  Tool: edit_file("src/auth/login.ts", old="if (user = null)", new="if (user === null)")
  Tool Result: "File edited"

Main Agent:
  Turn 4: Let me verify with a build.
  Tool: run_bash("npm run build")
  Tool Result: "Build success"

Main Agent:
  Turn 5: Bug fixed successfully!
  finish_reason: "stop"
```

**패턴 분석**:
1. **탐색 위임**: Explore Subagent가 파일 찾기 전담
2. **독립 실행**: Subagent는 자체 루프로 탐색 완료
3. **보고서 반환**: Main Agent는 요약만 받음
4. **직접 수정**: Main Agent가 실제 수정 수행
5. **검증**: Main Agent가 빌드로 확인

---

## 5. Context 관리 및 메모리

### 5.1 Append-Only Messages 패턴

**코드 구현**:
```python
# v1_openai/main.py:336-374
async def run_conversation_loop():
    messages: List[Dict[str, Any]] = []  # ← 절대 삭제 금지!
    system_prompt = get_system_prompt(os.getcwd())

    while True:
        user_input = await get_user_input()

        # User message 추가
        messages.append({"role": "user", "content": user_input})

        # Turn loop 실행
        await process_turn_loop(messages, system_prompt)
        # process_turn_loop 내부에서도 messages.append()만 함
```

**핵심**: `messages`는 **절대 삭제/수정하지 않음**
- `messages.append()` ✅
- `messages.pop()` ❌
- `messages[i] = ...` ❌
- `messages.clear()` ❌ (user command 제외)

### 5.2 Messages의 역할

**Messages = Agent의 완전한 메모리**

```python
messages = [
    # Turn 0: 시스템 프롬프트
    {"role": "system", "content": "[17,000 chars system prompt]"},

    # Turn 1: 사용자 요청
    {"role": "user", "content": "Fix the bug in src/index.ts"},

    # Turn 2: Agent 분석
    {"role": "assistant", "content": "I'll read the file first",
     "tool_calls": [{"type": "function", "function": {"name": "Read", ...}}]},

    # Turn 3: 도구 결과
    {"role": "tool", "tool_call_id": "call_abc",
     "content": "[file content... line 42 has syntax error]"},

    # Turn 4: Agent 수정 결정
    {"role": "assistant", "content": "I found the bug at line 42. Fixing it now",
     "tool_calls": [{"type": "function", "function": {"name": "Edit", ...}}]},

    # Turn 5: 수정 결과
    {"role": "tool", "tool_call_id": "call_def",
     "content": "File successfully edited"},

    # Turn 6: Agent 검증
    {"role": "assistant", "content": "Let me build to verify",
     "tool_calls": [{"type": "function", "function": {"name": "Bash", ...}}]},

    # Turn 7: 빌드 결과
    {"role": "tool", "tool_call_id": "call_ghi",
     "content": "Build successful"},

    # Turn 8: Agent 완료
    {"role": "assistant", "content": "Bug fixed successfully! The syntax error at line 42 has been corrected."}
]
```

**LLM이 볼 수 있는 것**:
- Turn 3에서 LLM은 "file content"를 봄
- Turn 5에서 LLM은 "successfully edited"를 봄
- Turn 7에서 LLM은 "Build successful"를 봄
- **모든 컨텍스트가 유지됨** → LLM이 전체 흐름 이해

### 5.3 Context Window 관리

**문제**: Messages가 계속 늘어나면 context window 초과

**해결 방법**:

**v2 (LangGraph)**: Automatic Compression
```python
# v2_langgraph/nodes.py
async def compact_messages(state):
    """100k 토큰 초과 시 자동 압축"""
    messages = state["messages"]

    if count_tokens(messages) > 100_000:
        # Claude Haiku + Extended Thinking으로 압축
        summary = await llm.ainvoke([
            SystemMessage("Summarize the conversation keeping key facts"),
            *messages
        ])

        # 압축된 메시지로 교체
        return {
            "messages": [
                messages[0],  # System prompt 유지
                HumanMessage(f"[Previous conversation summary: {summary}]"),
                *messages[-5:]  # 최근 5개 메시지 유지
            ]
        }

    return {}
```

**v2.1 (LangGraph Improved)**: No Compression
```python
# 압축 제거 (단순함 우선)
# 대신: 긴 컨텍스트 모델 사용 (Gemini 2.5 Pro = 1M tokens)
```

**v2.2 (Hook System)**: No Compression
```python
# Hook System으로 메시지 필터링만 수행
# 컨텍스트 관리는 외부 시스템에 위임
```

---

## 6. 프롬프트 엔지니어링 전략

### 6.1 시스템 프롬프트 구조 분석

**총 175줄, 약 17,000 chars**

```
┌─────────────────────────────────────────────────────┐
│ Section 1: 역할 정의 (Lines 1-10)                   │
│ "You are an interactive CLI tool..."                │
│ → Agent의 정체성 확립                                │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Section 2: 안전 지침 (Lines 4-5, 121-122)           │
│ "Refuse destructive techniques, DoS attacks..."     │
│ → 행동 제약 설정                                     │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Section 3: Task Management (Lines 23-67)            │
│ "Use TodoWrite VERY frequently..."                  │
│ "It is unacceptable to forget tasks"                │
│ → 목표 추적 강제                                     │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Section 4: 작업 수행 가이드 (Lines 74-79)           │
│ "If you notice insecure code, immediately fix it"   │
│ → Self-Correction 명시                              │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Section 5: 도구 사용 정책 (Lines 84-100)            │
│ "Use Task tool with Explore for codebase questions" │
│ "Maximize parallel tool calls"                      │
│ → 효율성 및 정확성 향상                              │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Section 6: Output Style (Lines 135-148)             │
│ "Provide educational insights"                      │
│ "★ Insight ─────────"                               │
│ → 사용자 경험 개선                                   │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Section 7: 환경 정보 (Lines 104-111)                │
│ "Working directory: /path/to/project"               │
│ "Platform: darwin"                                  │
│ → 컨텍스트 제공                                      │
└─────────────────────────────────────────────────────┘
```

### 6.2 핵심 프롬프트 패턴

#### 패턴 1: 명시적 명령어 (Explicit Imperatives)

**일반적 LLM 프롬프트**:
```
"You should try to avoid security vulnerabilities."
```

**Claude Code 프롬프트**:
```
"Be careful not to introduce security vulnerabilities.
If you notice that you wrote insecure code, immediately fix it."
```

**차이점**:
- "should try" → "immediately fix" (강제)
- "avoid" → "notice... fix" (능동적 감지 + 수정)

#### 패턴 2: 불가능 선언 (Impossibility Statements)

**예시**:
```
"If you do not use this tool when planning, you may forget to do
important tasks - and that is unacceptable."
```

**효과**:
- "may forget" - 위험성 경고
- "unacceptable" - 절대 금지
- LLM이 TodoWrite 사용을 **필수로 인식**

#### 패턴 3: 예시 기반 학습 (Example-Driven Learning)

**TodoWrite 섹션**:
```xml
<example>
user: Run the build and fix any type errors
assistant: I'm going to use the TodoWrite tool to write the following items to the todo list:
- Run the build
- Fix any type errors

I'm now going to run the build using Bash.

Looks like I found 10 type errors. I'm going to use the TodoWrite tool to write 10 items to the todo list.

marking the first todo as in_progress

Let me start working on the first item...

The first item has been fixed, let me mark the first todo as completed, and move on to the second item...
..
..
</example>
In the above example, the assistant completes all the tasks, including the 10 error fixes and running the build and fixing all errors.
```

**효과**:
- 구체적인 행동 패턴 제시
- "completes all the tasks" - 완료 보장 강조
- LLM이 이 패턴을 따라함

#### 패턴 4: 계층적 우선순위 (Hierarchical Priorities)

**도구 사용 정책**:
```
1. CRITICAL: Use Task tool with Explore for codebase questions
   (가장 높은 우선순위)

2. VERY IMPORTANT: Use specialized tools instead of bash
   (높은 우선순위)

3. Maximize parallel tool calls
   (일반 우선순위)
```

**효과**:
- "CRITICAL" > "VERY IMPORTANT" > 일반
- LLM이 우선순위 인식

### 6.3 Explore Agent의 특수 프롬프트

```
You are a file search specialist for Claude Code, Anthropic's official CLI for Claude.
You excel at thoroughly navigating and exploring codebases.

CRITICAL: This is a READ-ONLY exploration task. You MUST NOT create, write, or
modify any files under any circumstances. Your role is strictly to search and analyze
existing code.

Your strengths:
- Rapidly finding files using glob patterns
- Searching code and text with powerful regex patterns
- Reading and analyzing file contents

Guidelines:
- Use Glob for broad file pattern matching
- Use Grep for searching file contents with regex
- Use Read when you know the specific file path you need to read
- Use Bash ONLY for read-only operations (ls, git status, git log, git diff, find,
  cat, head, tail). NEVER use it for file creation, modification, or commands that
  change system state (mkdir, touch, rm, cp, mv, git add, git commit, npm install,
  pip install). NEVER use redirect operators (>, >>, |) or heredocs to create files
```

**핵심**:
- **CRITICAL** + **MUST NOT** - 쓰기 금지 강력 명령
- **NEVER** 반복 - 금지 명령 강조
- **역할 명확화** - "file search specialist"
- **도구별 가이드** - Glob vs Grep vs Read vs Bash

---

## 7. 도구 체이닝 패턴

### 7.1 Read → Analyze → Edit → Verify 패턴

**가장 일반적인 패턴**:

```
Step 1: Read (정보 수집)
  Tool: Read("src/index.ts")
  Result: "[file content with potential bug]"

Step 2: Analyze (LLM 분석)
  LLM: "I found a bug at line 42: variable 'modle' should be 'model'"

Step 3: Edit (수정 실행)
  Tool: Edit("src/index.ts", old="const modle =", new="const model =")
  Result: "File successfully edited"

Step 4: Verify (검증)
  Tool: Bash("npm run build")
  Result: "Build successful"

Step 5: Complete (완료)
  LLM: "Bug fixed and verified!"
  finish_reason: "stop"
```

### 7.2 Explore → Plan → Execute 패턴

**복잡한 기능 구현 시**:

```
Step 1: Explore (탐색)
  Tool: task_tool(subagent_type="Explore", prompt="Find all authentication code")
  Result: "[Subagent report: Found in src/auth/, 3 files]"

Step 2: Plan (계획)
  Tool: task_tool(subagent_type="Plan", prompt="Plan how to add OAuth support")
  Result: "[Subagent report: 1) Add OAuth provider config, 2) Implement OAuth flow, ...]"

Step 3: Execute (실행)
  LLM: "Based on the plan, I'll start with step 1"
  Tool: Write("src/config/oauth.ts", content="...")
  Tool: Edit("src/auth/login.ts", ...)
  Tool: Bash("npm run test")
  ...

Step 4: Verify (검증)
  Tool: Bash("npm run build && npm test")
  Result: "All tests passed"

Step 5: Complete
  LLM: "OAuth support successfully added!"
```

### 7.3 병렬 도구 실행

**프롬프트 지시**:
```
- You can call multiple tools in a single response. If you intend to call multiple
  tools and there are no dependencies between them, make all independent tool calls
  in parallel. Maximize use of parallel tool calls where possible to increase efficiency.
```

**코드 구현**:
```python
# v1_openai/main.py:306
tool_results = [await execute_single_tool_call(tc, system_prompt) for tc in tool_calls]
# asyncio.gather로 병렬 실행 (내부적으로)
```

**병렬 실행 예시**:
```
LLM: "I'll read multiple files to understand the structure"

Tool Calls (parallel):
  1. Read("src/index.ts")
  2. Read("src/utils.ts")
  3. Read("src/config.ts")
  4. Read("package.json")

Tool Results (parallel):
  1. "[index.ts content]"
  2. "[utils.ts content]"
  3. "[config.ts content]"
  4. "[package.json content]"

LLM: "Based on all 4 files, I understand the architecture..."
```

**장점**:
- 4개 파일을 순차 읽기: 4 * T
- 4개 파일을 병렬 읽기: T
- **효율성 4배 향상**

---

## 8. 실패 처리 전략

### 8.1 도구 실행 실패

**코드 구현**:
```python
# v1_openai/tools.py
async def execute_tool(tool_name: str, tool_input: dict) -> ToolResult:
    try:
        # 도구 실행
        result_content = await handler(input_obj)
        return ToolResult(
            tool_name=tool_name,
            result=result_content,
            is_error=False
        )
    except Exception as e:
        # 에러를 ToolResult로 변환
        error_msg = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
        return ToolResult(
            tool_name=tool_name,
            result=error_msg,
            is_error=True  # ← 에러 플래그
        )
```

**핵심**: 예외를 던지지 않고 **ToolResult로 변환**
- `is_error=True` 플래그
- 에러 메시지 + 스택 트레이스
- LLM이 다음 턴에 이 정보를 보고 판단

### 8.2 Subagent 실패

```python
# v2_1_langgraph_improved/nodes.py:155-156
except Exception as e:
    return f"[ERROR] Subagent failed: {type(e).__name__}: {str(e)}"
```

**Main Agent는 계속 진행**:
```
Main: I'll use Explore agent to find the code
Tool: task_tool(subagent_type="Explore", ...)
Tool Result: "[ERROR] Subagent failed: TimeoutError: Max depth exceeded"

Main: The Explore agent failed. I'll search manually instead.
Tool: grep_code("authentication")
Tool Result: "Found in src/auth/login.ts:42"

Main: Found it! Let me read the file.
...
```

**패턴**: Subagent 실패 → Main이 대체 방법 시도

### 8.3 LLM 환각 (Hallucination) 방지

**문제**: LLM이 존재하지 않는 파일/함수를 언급

**해결 방법 1: 도구 결과 즉시 확인**
```
LLM: "I'll read the config file at /etc/app/config.json"
Tool: Read("/etc/app/config.json")
Tool Result: "[ERROR] File does not exist"

LLM: "The file doesn't exist. Let me search for it."
Tool: glob_files("**/config.json")
Tool Result: "/home/user/project/config.json"

LLM: "Found it at /home/user/project/config.json. Reading now."
Tool: Read("/home/user/project/config.json")
Tool Result: "[actual file content]"
```

**해결 방법 2: 프롬프트 제약**
```
IMPORTANT: You must NEVER generate or guess URLs for the user unless you are
confident that the URLs are for helping the user with programming.
```

### 8.4 무한 루프 방지

**3단계 방어**:

**Level 1: max_turns 제한**
```python
async def process_turn_loop(messages, system_prompt, max_turns=50):
    turn_count = 0
    while turn_count < max_turns:
        turn_count += 1
        ...

    if turn_count >= max_turns:
        print("⚠ Max turns exceeded")
```

**Level 2: Subagent max_depth 제한**
```python
async def execute_subagent(current_depth=0, max_depth=5):
    if current_depth >= max_depth:
        return "[ERROR] Max subagent depth exceeded"
```

**Level 3: TodoWrite 진행 추적**
```
- TodoWrite로 작업 목록 관리
- 각 Todo가 완료되면 체크
- 모든 Todo 완료 → finish_reason="stop"
- 진행 없음 감지 가능
```

---

## 9. 인터랙티브 대화 유지

### 9.1 스트리밍 응답

**코드 구현**:
```python
# v1_openai/main.py:88-166
async def stream_assistant_response(messages, system_prompt):
    """스트리밍으로 어시스턴트 응답 처리"""
    print("\nAssistant: ", end=" ")

    collected_content = ""
    collected_tool_calls = []

    stream = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, *messages],
        tools=TOOLS,
        stream=True  # ← 스트리밍 활성화
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta

        # Content 실시간 출력
        if delta.content:
            print(delta.content, end="", flush=True)  # ← 즉시 출력
            collected_content += delta.content

        # Tool calls 수집 (실시간 표시 안 함)
        if delta.tool_calls:
            # ... 수집 로직

    print()  # 줄바꿈
    return assistant_message
```

**효과**:
- 사용자가 LLM의 "생각하는 과정" 실시간 확인
- 긴 응답도 지루하지 않음
- 진행 상황 가시성

### 9.2 도구 실행 표시

```python
# v1_openai/main.py:66-73
def display_tool_use(tool_name: str, tool_input: dict):
    """도구 사용을 표시"""
    console.print(f"\n🔧 Using tool: {tool_name}")
    input_str = json.dumps(tool_input, indent=2)
    if len(input_str) > 300:
        input_str = input_str[:300] + "\n  ...\n}"
    console.print(f"[dim]{input_str}[/dim]")
```

**출력 예시**:
```
🔧 Using tool: Read
{
  "file_path": "/Users/jd/project/src/index.ts"
}

✅ Tool completed: Read
import { foo } from './utils';
...

🔧 Using tool: Edit
{
  "file_path": "/Users/jd/project/src/index.ts",
  "old_string": "const modle = await...",
  "new_string": "const model = await..."
}

✅ Tool completed: Edit
File successfully edited
```

**효과**:
- 사용자가 Agent의 행동 이해
- 디버깅 용이
- 신뢰성 향상

### 9.3 Rich UI (v1 구현)

```python
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Assistant 메시지
console.print(Panel(
    Markdown(content),
    title="[bold blue]Assistant[/bold blue]",
    border_style="blue"
))

# Tool 결과
console.print(Panel(
    content,
    title="[bold cyan]Tool Result[/bold cyan]",
    border_style="cyan"
))

# Subagent 보고서
console.print(Panel(
    Markdown(subagent_report),
    border_style="green"
))
```

**출력 예시**:
```
╭─ Assistant ──────────────────────────────────────╮
│ I'll read the file to find the bug.             │
╰──────────────────────────────────────────────────╯

🔧 Using tool: Read

╭─ Tool Result ────────────────────────────────────╮
│ [File content with syntax error at line 42]     │
╰──────────────────────────────────────────────────╯

╭─ Assistant ──────────────────────────────────────╮
│ I found the bug! It's a typo at line 42.        │
│                                                   │
│ ★ Insight ───────────────────────────────────    │
│ This is a common mistake where 'model' was       │
│ misspelled as 'modle', causing a ReferenceError. │
│ ─────────────────────────────────────────────    │
╰──────────────────────────────────────────────────╯
```

---

## 10. 종합 분석: Self-Improvement 메커니즘

### 10.1 핵심 메커니즘 요약

```
┌─────────────────────────────────────────────────────────────┐
│              AI Agent Self-Improvement Loop                 │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
  ┌──────────┐      ┌──────────┐      ┌──────────┐
  │  Goal    │      │ Action   │      │  Result  │
  │ Tracking │      │Execution │      │ Analysis │
  └──────────┘      └──────────┘      └──────────┘
        │                  │                  │
        │                  │                  │
  ┌─────┴─────┐      ┌─────┴─────┐    ┌──────┴──────┐
  │TodoWrite  │      │Tool Calls │    │Tool Results │
  │ - Plan    │      │ - Read    │    │ - Success?  │
  │ - Track   │      │ - Edit    │    │ - Error?    │
  │ - Update  │      │ - Bash    │    │ - Partial?  │
  └───────────┘      └───────────┘    └─────────────┘
        │                  │                  │
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   LLM Decision  │
                  │                 │
                  │ • Continue?     │
                  │ • Fix needed?   │
                  │ • Complete?     │
                  └─────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   [Continue]          [Correct]           [Stop]
  Next Action       Fix & Retry         finish_reason
```

### 10.2 Self-Correction의 5단계

**Stage 1: Goal Definition (목표 정의)**
```
User: "Fix all type errors in the project"
LLM: "I'll create a plan using TodoWrite"
Tool: TodoWrite([
    {content: "Run build to find errors", status: "pending"},
    {content: "Fix all found errors", status: "pending"},
    {content: "Verify build succeeds", status: "pending"}
])
```

**Stage 2: Action Execution (행동 실행)**
```
LLM: "Starting first task"
Tool: TodoWrite([{content: "Run build...", status: "in_progress"}, ...])
Tool: Bash("npm run build")
```

**Stage 3: Result Analysis (결과 분석)**
```
Tool Result: "Found 10 type errors:
  - src/index.ts:42: Type 'string' is not assignable to type 'number'
  - src/utils.ts:15: Property 'foo' does not exist
  - ..."

LLM: [분석]
  - 10개 에러 발견
  - 각각 수정 필요
  - Todo 리스트 확장 필요
```

**Stage 4: Plan Adjustment (계획 조정)**
```
Tool: TodoWrite([
    {content: "Run build...", status: "completed"},  # ← 완료
    {content: "Fix error in src/index.ts:42", status: "pending"},  # ← 새로 추가
    {content: "Fix error in src/utils.ts:15", status: "pending"},
    # ... 10개 에러 각각 Todo로 추가
    {content: "Verify build succeeds", status: "pending"}
])
```

**Stage 5: Iterative Correction (반복 수정)**
```
Loop for each error:
  1. LLM: "Fixing error 1/10"
  2. Tool: Read(file)
  3. LLM: Analyze error
  4. Tool: Edit(fix)
  5. Tool: TodoWrite(mark completed)
  6. Continue to next error

Final:
  Tool: Bash("npm run build")
  Tool Result: "Build successful"
  LLM: "All errors fixed!"
  finish_reason: "stop"
```

### 10.3 정확도 유지 메커니즘

**Mechanism 1: Immediate Feedback Loop**
```
Action → Result → Analysis → Decision (< 1 turn)
```
- 도구 실행 후 즉시 결과 확인
- LLM이 바로 다음 행동 결정
- 에러 발견 시 즉시 수정

**Mechanism 2: Explicit Verification**
```
프롬프트 지시:
"Let me verify..." / "Let me check..." / "Let me build to confirm..."
```
- LLM이 스스로 검증 단계 추가
- 수정 후 재빌드/재테스트
- 성공 확인 후 완료

**Mechanism 3: Layered Validation**
```
Level 1: Tool Execution (도구가 에러 반환)
Level 2: LLM Analysis (LLM이 결과 분석)
Level 3: Build/Test (실제 빌드로 검증)
Level 4: User Feedback (사용자가 최종 확인)
```

### 10.4 목표 달성 보장

**Guarantee 1: TodoWrite Tracking**
- 모든 작업이 Todo로 기록됨
- 완료되지 않은 Todo가 있으면 계속 진행
- 모든 Todo 완료 = 목표 달성

**Guarantee 2: Max Turns Limit**
- 무한 루프 방지 (max_turns=50)
- 50턴 내 완료 강제
- 실패 시 명시적 경고

**Guarantee 3: Finish Reason Control**
- LLM이 `finish_reason="stop"` 반환해야 종료
- 프롬프트가 "완료 시에만 stop" 지시
- 중간 종료 방지

---

## 11. 실제 사례 분석

### 11.1 Case Study: 버그 수정

**시나리오**: "src/utils/router.ts에 버그가 있어. 찾아서 수정해줘"

**Turn-by-Turn 분석**:

```
Turn 1: Goal Understanding
  User: "src/utils/router.ts에 버그가 있어. 찾아서 수정해줘"
  LLM: [내부 추론]
    - 버그를 찾아야 함
    - 찾으면 수정해야 함
    - 수정 후 검증해야 함

  Action: 계획 수립
  Tool: TodoWrite([
    {content: "Read router.ts to find bug", status: "pending"},
    {content: "Fix the bug", status: "pending"},
    {content: "Verify with build", status: "pending"}
  ])

Turn 2: Investigation
  LLM: "먼저 파일을 읽어서 문제를 파악하겠습니다"
  Tool: TodoWrite([
    {content: "Read router.ts to find bug", status: "in_progress"},
    ...
  ])
  Tool: Read("/Users/jd/.../src/utils/router.ts")

Turn 3: Analysis
  Tool Result: "[300 lines of code... line 182: const modle = await getUseModel(...)]"
  LLM: [내부 추론]
    - 182번 줄에서 'modle' 발견
    - 'model'의 오타로 판단
    - Edit 도구로 수정 가능

  Action: Todo 업데이트 + 수정 실행
  Tool: TodoWrite([
    {content: "Read router.ts to find bug", status: "completed"},  # ← 완료!
    {content: "Fix typo at line 182", status: "in_progress"},      # ← 구체화
    {content: "Verify with build", status: "pending"}
  ])
  Tool: Edit(
    file_path="/Users/jd/.../src/utils/router.ts",
    old_string="const modle = await getUseModel(req, tokenCount, config, lastMessageUsage);",
    new_string="const model = await getUseModel(req, tokenCount, config, lastMessageUsage);"
  )

Turn 4: Verification
  Tool Result: "File successfully edited"
  LLM: [내부 추론]
    - 수정 성공
    - 이제 빌드로 검증 필요

  Action: Todo 업데이트 + 빌드 실행
  Tool: TodoWrite([
    {content: "Read router.ts to find bug", status: "completed"},
    {content: "Fix typo at line 182", status: "completed"},  # ← 완료!
    {content: "Verify with build", status: "in_progress"}
  ])
  Tool: Bash("npm run build")

Turn 5: Completion
  Tool Result: "Building... ✓ CLI built successfully ✓ UI built successfully Build completed in 2.3s"
  LLM: [내부 추론]
    - 빌드 성공
    - 모든 Todo 완료
    - 작업 완료

  Action: Todo 완료 + 최종 보고
  Tool: TodoWrite([
    {content: "Read router.ts to find bug", status: "completed"},
    {content: "Fix typo at line 182", status: "completed"},
    {content: "Verify with build", status: "completed"}  # ← 모두 완료!
  ])
  Response: "버그를 성공적으로 수정했습니다!

  수정 내용:
  - 위치: src/utils/router.ts:182
  - 문제: 변수명 오타 ('modle' → 'model')
  - 확인: 빌드 성공

  프로젝트가 정상적으로 빌드되었습니다."

  finish_reason: "stop"  # ← 종료!
```

**Self-Improvement 포인트**:
1. **즉시 검증**: 수정 후 바로 빌드로 확인
2. **구체적 Todo**: "Fix the bug" → "Fix typo at line 182"
3. **완료 기준 명확**: 빌드 성공 = 작업 완료
4. **무한 루프 없음**: 5턴만에 완료

### 11.2 Case Study: 복잡한 기능 구현

**시나리오**: "사용자가 메트릭을 추적하고 다양한 형식으로 내보낼 수 있는 기능을 만들어줘"

```
Turn 1-3: Planning Phase
  User: "메트릭 추적 및 내보내기 기능 구현"

  LLM: "복잡한 작업이므로 먼저 계획을 세우겠습니다"
  Tool: TodoWrite([
    {content: "Research existing metrics in codebase", status: "pending"},
    {content: "Design metrics collection system", status: "pending"},
    {content: "Implement core tracking", status: "pending"},
    {content: "Create export functionality", status: "pending"},
    {content: "Write tests", status: "pending"},
    {content: "Verify with build", status: "pending"}
  ])

  LLM: "기존 코드베이스를 먼저 탐색하겠습니다"
  Tool: task_tool(
    subagent_type="Explore",
    description="Find existing metrics/telemetry code",
    prompt="Locate all files related to metrics, telemetry, or tracking"
  )

Turn 4-5: Analysis Phase
  Explore Subagent: [독립 실행]
    - glob_files("**/*metric*", "**/*telemetry*", "**/*track*")
    - grep_code("track|metric|telemetry")
    - read_file("src/utils/telemetry.ts")
    - 보고서: "Found basic telemetry in src/utils/telemetry.ts"

  Tool Result: "현재 시스템에는 기본적인 텔레메트리가 있습니다:
    - src/utils/telemetry.ts: 기본 이벤트 추적
    - 하지만 사용자별 메트릭이나 내보내기 기능은 없음"

  LLM: [분석]
    - 기존 telemetry.ts 확장 가능
    - 새로운 모듈 필요: metrics-collector, exporter

  Tool: TodoWrite([
    {content: "Research existing metrics", status: "completed"},  # ← 완료
    {content: "Design metrics collection system", status: "in_progress"},  # ← 진행
    ...
  ])

Turn 6-15: Implementation Phase
  LLM: "설계를 바탕으로 구현하겠습니다"

  # 파일 1: Metrics Collector
  Tool: Write("src/utils/metrics-collector.ts", content="[new file content]")
  Tool Result: "File created"
  Tool: TodoWrite([..., {content: "Implement core tracking", status: "in_progress"}])

  # 파일 2: Exporter
  Tool: Write("src/utils/metrics-exporter.ts", content="[exporter code]")
  Tool Result: "File created"

  # 기존 파일 수정
  Tool: Edit("src/index.ts", old="...", new="... import MetricsCollector ...")
  Tool Result: "File edited"

Turn 16-20: Testing Phase
  Tool: TodoWrite([
    ...,
    {content: "Implement core tracking", status: "completed"},
    {content: "Create export functionality", status: "completed"},
    {content: "Write tests", status: "in_progress"}
  ])

  Tool: Write("tests/metrics.test.ts", content="[test code]")
  Tool: Bash("npm test -- metrics.test.ts")
  Tool Result: "5 tests passed"

Turn 21-25: Verification & Completion
  Tool: Bash("npm run build")
  Tool Result: "Build successful"

  Tool: Bash("npm run lint")
  Tool Result: "No linting errors"

  Tool: TodoWrite([
    {content: "Research existing metrics", status: "completed"},
    {content: "Design metrics collection system", status: "completed"},
    {content: "Implement core tracking", status: "completed"},
    {content: "Create export functionality", status: "completed"},
    {content: "Write tests", status: "completed"},
    {content: "Verify with build", status: "completed"}  # ← 모두 완료!
  ])

  LLM: "메트릭 추적 및 내보내기 기능을 성공적으로 구현했습니다!

  구현 내용:
  1. src/utils/metrics-collector.ts - 사용자별 메트릭 수집
  2. src/utils/metrics-exporter.ts - JSON, CSV, Excel 형식 지원
  3. src/index.ts - 메인 앱에 통합
  4. tests/metrics.test.ts - 5개 테스트 (모두 통과)

  빌드 및 테스트 모두 성공했습니다!"

  finish_reason: "stop"
```

**Self-Improvement 포인트**:
1. **계층적 분해**: 6단계 Todo로 분해
2. **Explore Subagent 활용**: 기존 코드 탐색 위임
3. **점진적 구현**: 한 파일씩 작성 및 검증
4. **다층 검증**: 테스트 + 빌드 + 린트
5. **완료 기준**: 모든 Todo 완료 + 모든 검증 통과

---

## 12. 결론: AI Agent가 목표를 달성하는 방법

### 12.1 핵심 메커니즘 정리

| 메커니즘 | 구현 방법 | 효과 |
|---------|----------|------|
| **Iterative Loop** | `while` + `finish_reason` | LLM이 완료 시점 결정 |
| **Immediate Feedback** | Tool Result → Next Turn | 에러 즉시 감지 |
| **Explicit Verification** | Bash build/test after edit | 수정 검증 |
| **Goal Tracking** | TodoWrite | 진행 상황 추적 |
| **Task Decomposition** | Subagent | 복잡도 분산 |
| **Context Preservation** | Append-only messages | 전체 흐름 유지 |
| **Prompt Engineering** | "immediately fix", "unacceptable" | 강력한 행동 지시 |
| **Parallel Execution** | Multiple tool calls | 효율성 향상 |
| **Layered Defense** | max_turns, max_depth, TodoWrite | 무한 루프 방지 |

### 12.2 Interactive한 이유

1. **Streaming Responses** - 실시간 출력으로 진행 상황 표시
2. **Tool Execution Display** - 도구 사용 가시화
3. **TodoWrite Visibility** - 작업 목록으로 진행 상황 공유
4. **Rich UI** - Panel, Markdown으로 가독성 향상
5. **Turn-by-Turn** - 각 턴마다 사용자가 개입 가능

### 12.3 정확도가 높은 이유

1. **Read → Analyze → Edit → Verify** - 4단계 검증
2. **Immediate Result Analysis** - 도구 결과 즉시 분석
3. **Explicit Verification Steps** - LLM이 스스로 검증 추가
4. **Subagent Specialization** - 역할별 도구 제한
5. **Prompt Constraints** - "MUST NOT", "NEVER" 등 강력한 제약

### 12.4 스스로 개선하는 이유

1. **Tool Result as Feedback** - 에러를 예외가 아닌 피드백으로 처리
2. **Self-Correction Prompts** - "If you notice..., immediately fix it"
3. **Verification Loop** - 수정 후 재실행으로 확인
4. **Dynamic Planning** - 실행 중 Todo 리스트 확장
5. **Context Accumulation** - Messages로 과거 실수 기억

### 12.5 목표를 달성하는 이유

1. **TodoWrite Tracking** - 모든 작업 명시적 추적
2. **Finish Reason Control** - LLM이 완료 판단
3. **Max Turns Limit** - 무한 루프 강제 종료
4. **Completion Criteria** - "모든 Todo 완료" = 목표 달성
5. **User Feedback** - 사용자가 최종 검증

### 12.6 최종 인사이트

Claude Code는 **단순한 LLM API 호출**이 아닙니다.

**Self-Supervising Agent Loop**입니다:

```
Goal Definition (TodoWrite)
     ↓
Action Execution (Tool Calls)
     ↓
Result Analysis (LLM 분석)
     ↓
Decision Making (Continue/Correct/Complete)
     ↓
[Loop until all Todos completed]
     ↓
Verification (Build/Test)
     ↓
Goal Achieved
```

**핵심은 "LLM이 자신의 행동을 스스로 감독(Self-Supervise)"한다는 것**:
- Tool Result를 보고 스스로 판단
- 에러 발견 시 스스로 수정
- 검증 필요 시 스스로 테스트
- 완료 판단도 스스로

이것이 Claude Code가 interactive하고, 정확하고, 스스로 개선하며, 목표를 달성하는 **AI Agent Self-Improvement Architecture**입니다.

---

**작성자**: Claude (Sonnet 4.5)
**분석 대상**: Claude Code CLI + Claude Agent SDK Python
**분석 방법**: Code + Prompt + Interaction Pattern 종합
**문서 버전**: 1.0 (2025-11-20)
