# Claude Agent SDK Design Philosophy
## 종합 코드 리뷰 및 디자인 패턴 분석

> 출처: https://github.com/anthropics/claude-agent-sdk-python
> 분석일: 2025-11-20
> 목적: Claude Code의 공식 SDK 설계 철학을 학습하여 v2.2 Hook System 구현에 반영

---

## Executive Summary

Claude Agent SDK는 **명시성(Explicitness)**, **조합성(Composability)**, **타입 안전성(Type Safety)**을 핵심 가치로 하는 Python SDK입니다. 코드베이스를 정밀 분석한 결과, 다음과 같은 핵심 설계 원칙을 발견했습니다:

1. **Explicitness over Convention** - 자동화된 기본값보다 명시적 설정 우선
2. **Composition over Inheritance** - 상속보다 조합을 통한 확장성
3. **Async-First Architecture** - 모든 I/O는 비동기 처리
4. **Discriminated Unions for Type Safety** - Literal 타입으로 완벽한 타입 안전성
5. **Bidirectional Control Protocol** - 양방향 제어 프로토콜로 Hook 구현
6. **In-Process MCP Integration** - 서브프로세스 대신 In-Process 도구 통합

---

## 1. 전체 아키텍처

### 1.1 계층 구조

```
┌─────────────────────────────────────────────────────────┐
│  Public API Layer                                        │
│  ├─ query() - 단발성 쿼리 (async function)              │
│  ├─ ClaudeSDKClient - 대화형 클라이언트 (context mgr)   │
│  ├─ @tool decorator - MCP 도구 정의                     │
│  └─ create_sdk_mcp_server() - In-Process MCP 서버       │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Type System Layer (types.py)                            │
│  ├─ Message Types (User/Assistant/System/Result)        │
│  ├─ Content Blocks (Text/Thinking/ToolUse/ToolResult)   │
│  ├─ Hook Types (PreToolUse/PostToolUse/etc)             │
│  ├─ Permission Types (CanUseTool callbacks)             │
│  └─ Configuration Types (ClaudeAgentOptions)            │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Internal Protocol Layer (_internal/)                    │
│  ├─ Query - 양방향 제어 프로토콜 관리                   │
│  ├─ MessageParser - JSON → Python 객체 변환             │
│  ├─ Transport Abstraction - 추상 통신 인터페이스        │
│  └─ SubprocessCLITransport - CLI 서브프로세스 통신      │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Infrastructure Layer                                    │
│  ├─ Bundled Claude Code CLI (platform-specific binary)  │
│  ├─ Subprocess Management (anyio)                       │
│  ├─ Stream Management (stdin/stdout/stderr)             │
│  └─ JSON Buffering & Parsing                            │
└─────────────────────────────────────────────────────────┘
```

### 1.2 핵심 설계 결정

**왜 Subprocess 방식인가?**
- Claude Code CLI를 번들링하여 별도 설치 불필요
- CLI의 안정성과 기능을 그대로 활용
- Python SDK는 "얇은 래퍼" 역할 (thin wrapper)

**왜 In-Process MCP인가?**
> "No subprocess management, better performance"

- 외부 서브프로세스 MCP 서버의 오버헤드 제거
- 단일 프로세스 아키텍처 지원
- Python 함수를 직접 도구로 등록 가능

---

## 2. 핵심 설계 원칙

### 2.1 Explicitness over Convention

**Before (v0.0.x)**:
```python
# 자동으로 ~/.claude/settings.json 로드
# 자동으로 .claude/commands/ 로드
# 암묵적 기본값 적용
client = ClaudeCodeSDKClient()
```

**After (v0.1.0+)**:
```python
# 명시적 설정 필요
options = ClaudeAgentOptions(
    setting_sources=["user", "project"],  # 명시적 지정
    plugins=[my_plugin],                   # 명시적 등록
)
client = ClaudeSDKClient(options=options)
```

**철학**:
- "Settings files and slash commands are no longer loaded automatically"
- 예측 가능한 동작 (predictable behavior)
- 환경에 따라 다른 동작 방지

### 2.2 Composition over Inheritance

**패턴**: Configuration as Data
```python
# 상속이 아닌 조합
options = ClaudeAgentOptions(
    mcp_servers={                    # MCP 서버 조합
        "my-tools": server_config,
    },
    hooks={                           # Hook 조합
        "PreToolUse": [hook1, hook2],
    },
    agents=[                          # Agent 조합
        agent_definition1,
        agent_definition2,
    ],
)
```

**장점**:
- 런타임 구성 변경 가능
- 테스트 용이 (mocking)
- 재사용성 향상

### 2.3 Async-First Architecture

**모든 I/O는 비동기**:
```python
# query function
async def query(prompt: str, ...) -> AsyncIterator[Message]:
    ...

# ClaudeSDKClient
async with ClaudeSDKClient(options) as client:
    await client.query("...")
    async for msg in client.receive_response():
        ...

# Tool handler
@tool("name", "desc", schema)
async def my_tool(args):  # async def 필수
    return {"content": [...]}

# Hook callback
async def my_hook(input_data, tool_use_id, context):  # async def 필수
    ...
```

**이유**:
- I/O 대기 시간 최소화
- 동시성 지원 (여러 Hook 병렬 실행)
- Python 생태계 표준 (anyio/asyncio)

### 2.4 Type Safety Through Discriminated Unions

**핵심 패턴**: Literal discriminators
```python
# Message 타입 (4가지)
class UserMessage(TypedDict):
    type: Literal["user"]
    content: str | list[ContentBlock]

class AssistantMessage(TypedDict):
    type: Literal["assistant"]
    content: list[ContentBlock]
    model: str

# Union으로 조합
Message = UserMessage | AssistantMessage | SystemMessage | ResultMessage

# 타입 가드로 안전한 접근
if msg["type"] == "assistant":
    model = msg["model"]  # OK - type narrowing
```

**ContentBlock도 동일 패턴**:
```python
class TextBlock(TypedDict):
    type: Literal["text"]
    text: str

class ToolUseBlock(TypedDict):
    type: Literal["tool_use"]
    id: str
    name: str
    input: dict[str, Any]

ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock | ToolResultBlock
```

**Hook Input도 동일 패턴**:
```python
class PreToolUseHookInput(TypedDict):
    hookEventName: Literal["PreToolUse"]
    tool_name: str
    tool_input: dict[str, Any]

class PostToolUseHookInput(TypedDict):
    hookEventName: Literal["PostToolUse"]
    tool_name: str
    tool_result: dict[str, Any]

HookInput = PreToolUseHookInput | PostToolUseHookInput | ...
```

**장점**:
- mypy/pyright에서 완벽한 타입 검사
- IDE 자동완성 지원
- 런타임 에러 사전 방지

---

## 3. 핵심 추상화

### 3.1 Transport Abstraction

**목적**: 통신 방식 추상화

```python
class Transport(Protocol):
    async def send(self, data: str) -> None: ...
    async def receive(self) -> AsyncIterator[str]: ...
    async def close(self) -> None: ...
```

**구현체**:
- `SubprocessCLITransport`: Claude Code CLI와 subprocess 통신
- (향후) `HTTPTransport`: HTTP API 통신
- (향후) `WebSocketTransport`: WebSocket 통신

**설계 의도**:
- 통신 방식 교체 가능
- 테스트 시 Mock Transport 사용 가능
- 확장성 확보

### 3.2 Query Control Protocol

**핵심**: 양방향 제어 메시지

```python
# SDK → CLI
{
    "type": "control_request",
    "request_id": "req_1_abc123",
    "control": {
        "type": "initialize",
        "hooks": {...},
        "mcp_servers": {...}
    }
}

# CLI → SDK
{
    "type": "control_request",
    "request_id": "req_2_def456",
    "control": {
        "type": "can_use_tool",
        "tool_name": "Bash",
        "tool_input": {"command": "ls"}
    }
}

# SDK → CLI (응답)
{
    "type": "control_response",
    "request_id": "req_2_def456",
    "response": {
        "allow": true,
        "updated_input": {...}
    }
}
```

**프로토콜 종류**:
1. **Initialize**: Hook 등록, MCP 서버 설정
2. **can_use_tool**: 도구 사용 권한 확인 (PreToolUse Hook)
3. **hook_callback**: Hook 콜백 실행
4. **mcp_jsonrpc**: In-Process MCP 서버로 JSONRPC 라우팅
5. **set_permission_mode**: 권한 모드 변경
6. **interrupt**: 실행 중단

**핵심 설계**:
- Request-Response 패턴 (request_id로 매칭)
- 60초 타임아웃
- Pending requests 큐 관리

### 3.3 Message Streaming Architecture

**3가지 메시지 카테고리**:

```python
async def _read_messages(self):
    async for line in self._transport.receive():
        msg = json.loads(line)

        # 1. Control Response (응답)
        if msg["type"] == "control_response":
            request_id = msg["request_id"]
            self.pending_control_results[request_id] = msg["response"]

        # 2. Control Request (요청 - SDK가 처리)
        elif msg["type"] == "control_request":
            await self._handle_control_request(msg)

        # 3. SDK Message (사용자에게 전달)
        else:
            await self._message_receive.send(msg)
```

**설계 의도**:
- Control 메시지와 일반 메시지 분리
- 양방향 통신 (SDK ↔ CLI)
- Non-blocking 처리

### 3.4 Hook System Architecture

**Hook 등록 → 실행 플로우**:

```
1. SDK: Hook 등록
   ┌──────────────────────────────────────────┐
   │ options = ClaudeAgentOptions(           │
   │     hooks={                               │
   │         "PreToolUse": [                   │
   │             HookMatcher(                  │
   │                 matcher="Bash",           │
   │                 hooks=[check_bash_cmd]    │
   │             )                             │
   │         ]                                 │
   │     }                                     │
   │ )                                         │
   └──────────────────────────────────────────┘
                    ↓
2. Initialize 프로토콜
   ┌──────────────────────────────────────────┐
   │ SDK → CLI                                 │
   │ {                                         │
   │   "type": "initialize",                   │
   │   "hooks": {                              │
   │     "PreToolUse": [{                      │
   │       "matcher": "Bash",                  │
   │       "callbacks": ["callback_1"]         │
   │     }]                                    │
   │   }                                       │
   │ }                                         │
   └──────────────────────────────────────────┘
                    ↓
3. CLI: 이벤트 발생 감지
   ┌──────────────────────────────────────────┐
   │ CLI detects: Tool "Bash" 실행 직전       │
   │ → Matcher "Bash" 일치 확인               │
   │ → Hook callback 실행 요청                │
   └──────────────────────────────────────────┘
                    ↓
4. Hook Callback 요청
   ┌──────────────────────────────────────────┐
   │ CLI → SDK                                 │
   │ {                                         │
   │   "type": "control_request",              │
   │   "request_id": "req_X",                  │
   │   "control": {                            │
   │     "type": "hook_callback",              │
   │     "callback_id": "callback_1",          │
   │     "input": {                            │
   │       "hookEventName": "PreToolUse",      │
   │       "tool_name": "Bash",                │
   │       "tool_input": {"command": "ls"}     │
   │     },                                    │
   │     "tool_use_id": "toolu_123"            │
   │   }                                       │
   │ }                                         │
   └──────────────────────────────────────────┘
                    ↓
5. SDK: Hook 실행
   ┌──────────────────────────────────────────┐
   │ callback = self.hooks["callback_1"]      │
   │ result = await callback(                 │
   │     input_data=input,                     │
   │     tool_use_id="toolu_123",              │
   │     context=HookContext(...)              │
   │ )                                         │
   └──────────────────────────────────────────┘
                    ↓
6. Hook 결과 반환
   ┌──────────────────────────────────────────┐
   │ SDK → CLI                                 │
   │ {                                         │
   │   "type": "control_response",             │
   │   "request_id": "req_X",                  │
   │   "response": {                           │
   │     "hookSpecificOutput": {               │
   │       "permissionDecision": "deny"        │
   │     }                                     │
   │   }                                       │
   │ }                                         │
   └──────────────────────────────────────────┘
                    ↓
7. CLI: 결과 처리
   ┌──────────────────────────────────────────┐
   │ if permissionDecision == "deny":         │
   │     도구 실행 차단                        │
   │ elif permissionDecision == "ask":        │
   │     사용자 승인 요청                      │
   │ else:                                     │
   │     도구 실행 계속                        │
   └──────────────────────────────────────────┘
```

**핵심 특징**:
- **Decoupled Execution**: Hook 정의와 실행이 분리됨
- **CLI-Driven**: CLI가 Hook 실행 시점 결정
- **Bidirectional**: SDK ↔ CLI 양방향 통신
- **Timeout Support**: Hook 실행 타임아웃 설정 가능

---

## 4. 디자인 패턴 카탈로그

### 4.1 Async Context Manager Pattern

**사용처**: `ClaudeSDKClient`

```python
class ClaudeSDKClient:
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# 사용
async with ClaudeSDKClient(options) as client:
    await client.query("...")
    # 자동으로 연결 종료
```

**장점**:
- 자원 누수 방지
- 명시적 생명주기 관리
- Exception 발생 시에도 안전하게 정리

### 4.2 Lazy Initialization Pattern

**사용처**: `_query` 객체

```python
class ClaudeSDKClient:
    def __init__(self, options):
        self._transport: Transport | None = None
        self._query: Query | None = None  # Lazy
        self.options = options

    async def connect(self):
        self._transport = SubprocessCLITransport(...)
        self._query = Query(self._transport, ...)  # 연결 시 생성
```

**장점**:
- 초기화 비용 지연
- 실제 사용 시점까지 자원 미점유
- 재연결 시나리오 지원

### 4.3 Builder/Configuration Pattern

**사용처**: `ClaudeAgentOptions`

```python
# 복잡한 생성자 대신 설정 객체
options = ClaudeAgentOptions(
    model="claude-sonnet-4",
    working_directory="/path/to/dir",
    mcp_servers={"my-tools": server_config},
    hooks={"PreToolUse": [hook1, hook2]},
    agents=[agent1, agent2],
    permission_mode="ask",
    max_budget_usd=10.0,
)

client = ClaudeSDKClient(options=options)
```

**장점**:
- 매개변수 폭발 방지
- 가독성 향상
- 선택적 설정 명확화

### 4.4 Discriminated Union Pattern

**사용처**: 모든 타입 정의

```python
# Message
class UserMessage(TypedDict):
    type: Literal["user"]
    content: str | list[ContentBlock]

class AssistantMessage(TypedDict):
    type: Literal["assistant"]
    content: list[ContentBlock]

Message = UserMessage | AssistantMessage | SystemMessage | ResultMessage

# 타입 가드 패턴
def process_message(msg: Message):
    if msg["type"] == "user":
        # mypy는 UserMessage로 narrowing
        content = msg["content"]
    elif msg["type"] == "assistant":
        # mypy는 AssistantMessage로 narrowing
        model = msg["model"]
```

**장점**:
- 타입 안전성
- Exhaustive checking
- IDE 자동완성

### 4.5 Decorator Pattern for Tool Definition

**사용처**: `@tool`

```python
@tool("greet", "Greet a user", {"name": str})
async def greet_user(args):
    return {"content": [{"type": "text", "text": f"Hello, {args['name']}!"}]}

# 데코레이터가 SdkMcpTool 객체 생성
# → MCP 서버에 등록
# → JSON Schema 자동 생성
```

**장점**:
- 선언적 도구 정의
- 메타데이터 자동 추출
- 코드 간결성

### 4.6 Request-Response Pattern with Pending Queue

**사용처**: Control Protocol

```python
class Query:
    def __init__(self):
        self.pending_control_results: dict[str, Any] = {}
        self.request_counter = 0

    async def send_control_request(self, control_data):
        request_id = f"req_{self.request_counter}_{random_id()}"
        self.request_counter += 1

        # 요청 전송
        await self._send({
            "type": "control_request",
            "request_id": request_id,
            "control": control_data
        })

        # 응답 대기 (60초 타임아웃)
        for _ in range(600):  # 100ms * 600 = 60s
            if request_id in self.pending_control_results:
                result = self.pending_control_results.pop(request_id)
                return result
            await anyio.sleep(0.1)

        raise TimeoutError(...)
```

**장점**:
- 비동기 요청-응답 매칭
- 다중 동시 요청 지원
- 타임아웃 관리

### 4.7 Stream Multiplexing Pattern

**사용처**: Message Router

```python
async def _read_messages(self):
    async for line in self._transport.receive():
        msg = json.loads(line)

        # 메시지 타입별 라우팅
        if msg["type"] == "control_response":
            # Pending queue에 저장
            self.pending_control_results[msg["request_id"]] = msg["response"]

        elif msg["type"] == "control_request":
            # Control 핸들러로 라우팅
            await self._handle_control_request(msg)

        else:
            # 사용자 메시지 스트림으로 라우팅
            await self._message_receive.send(msg)
```

**장점**:
- 단일 스트림에서 다중 메시지 타입 처리
- Control과 Data 분리
- 확장 가능한 라우팅

### 4.8 Error Hierarchy Pattern

**사용처**: Exception 설계

```python
class ClaudeSDKError(Exception):
    """Base exception"""
    pass

class CLIConnectionError(ClaudeSDKError):
    """Connection failures"""
    pass

class CLINotFoundError(CLIConnectionError):
    """CLI binary not found"""
    pass

class ProcessError(ClaudeSDKError):
    """Process execution failures"""
    def __init__(self, exit_code: int, stderr: str):
        self.exit_code = exit_code
        self.stderr = stderr

class CLIJSONDecodeError(ClaudeSDKError):
    """JSON parsing failures"""
    def __init__(self, line: str, original_error: Exception):
        self.line = line
        self.original_error = original_error
```

**장점**:
- 세밀한 에러 처리
- Rich context 제공
- Progressive specificity (광범위 또는 정밀한 catch)

---

## 5. 타입 시스템 설계

### 5.1 Message Type Hierarchy

```python
# 4가지 메시지 타입
UserMessage = TypedDict(
    "UserMessage",
    {
        "type": Literal["user"],
        "content": str | list[ContentBlock],
        "parent_tool_use_id": NotRequired[str],  # Optional
    }
)

AssistantMessage = TypedDict(
    "AssistantMessage",
    {
        "type": Literal["assistant"],
        "content": list[ContentBlock],
        "model": str,
        "stop_reason": NotRequired[str],
        "usage": NotRequired[dict],
    }
)

SystemMessage = TypedDict(
    "SystemMessage",
    {
        "type": Literal["system"],
        "subtype": str,  # "message", "settings_loaded", etc.
        "metadata": NotRequired[dict],
    }
)

ResultMessage = TypedDict(
    "ResultMessage",
    {
        "type": Literal["result"],
        "result": str,  # "success", "interrupted", "error"
        "cost_usd": NotRequired[float],
        "duration_ms": NotRequired[int],
        "usage": NotRequired[dict],
    }
)

Message = UserMessage | AssistantMessage | SystemMessage | ResultMessage
```

### 5.2 Content Block Hierarchy

```python
TextBlock = TypedDict("TextBlock", {"type": Literal["text"], "text": str})

ThinkingBlock = TypedDict("ThinkingBlock", {"type": Literal["thinking"], "thinking": str})

ToolUseBlock = TypedDict(
    "ToolUseBlock",
    {
        "type": Literal["tool_use"],
        "id": str,
        "name": str,
        "input": dict[str, Any],
    }
)

ToolResultBlock = TypedDict(
    "ToolResultBlock",
    {
        "type": Literal["tool_result"],
        "tool_use_id": str,
        "content": str | list[dict],
        "is_error": NotRequired[bool],
    }
)

ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock | ToolResultBlock
```

### 5.3 Hook Type System

```python
# Hook Input (6가지 이벤트)
PreToolUseHookInput = TypedDict(
    "PreToolUseHookInput",
    {
        "hookEventName": Literal["PreToolUse"],
        "tool_name": str,
        "tool_input": dict[str, Any],
    }
)

PostToolUseHookInput = TypedDict(
    "PostToolUseHookInput",
    {
        "hookEventName": Literal["PostToolUse"],
        "tool_name": str,
        "tool_input": dict[str, Any],
        "tool_result": dict[str, Any],
    }
)

# ... UserPromptSubmit, PreCompact, Stop, SubagentStop

HookInput = (
    PreToolUseHookInput
    | PostToolUseHookInput
    | UserPromptSubmitHookInput
    | PreCompactHookInput
    | StopHookInput
    | SubagentStopHookInput
)

# Hook Callback Type
HookCallback = Callable[
    [dict[str, Any], str | None, HookContext],
    Awaitable[dict[str, Any]]
]

# Hook Output
HookJSONOutput = TypedDict(
    "HookJSONOutput",
    {
        "async": NotRequired[bool],  # Python keyword → async_
        "decision": NotRequired[Literal["block", "ask"]],
        "systemMessage": NotRequired[str],
        "updatedInput": NotRequired[dict[str, Any]],
        "hookSpecificOutput": NotRequired[dict[str, Any]],
    }
)
```

### 5.4 Permission Type System

```python
# Permission Decision Callback
CanUseTool = Callable[
    [str, dict[str, Any], ToolPermissionContext],
    Awaitable[PermissionResult]
]

# Permission Context
ToolPermissionContext = TypedDict(
    "ToolPermissionContext",
    {
        "session_id": str,
        "turn_count": int,
        "tool_use_id": str | None,
        "permission_suggestion": NotRequired[Literal["allow", "deny"]],
    }
)

# Permission Result (Discriminated Union)
PermissionResultAllow = TypedDict(
    "PermissionResultAllow",
    {
        "behavior": Literal["allow"],
        "updated_input": NotRequired[dict[str, Any]],
    }
)

PermissionResultDeny = TypedDict(
    "PermissionResultDeny",
    {
        "behavior": Literal["deny"],
        "message": NotRequired[str],
    }
)

PermissionResultAsk = TypedDict(
    "PermissionResultAsk",
    {
        "behavior": Literal["ask"],
        "message": NotRequired[str],
    }
)

PermissionResult = PermissionResultAllow | PermissionResultDeny | PermissionResultAsk
```

### 5.5 타입 시스템 설계 원칙

**원칙 1: Literal Discriminators**
- 모든 Union 타입은 `type` 또는 `hookEventName` 같은 Literal 필드로 구분
- mypy/pyright의 Type Narrowing 지원

**원칙 2: NotRequired for Optional Fields**
- Python 3.11+의 `NotRequired` 사용
- 선택적 필드와 필수 필드 명확히 구분

**원칙 3: Reserved Keyword Handling**
- Python 키워드 충돌 시 `_` suffix 사용 (`async_`, `continue_`)
- CLI로 전송 시 자동 변환 (`async_` → `async`)

**원칙 4: Structural Typing**
- TypedDict 사용 (클래스 상속 대신)
- Duck typing 지원
- JSON 직렬화 용이

---

## 6. 확장 메커니즘

### 6.1 MCP Server Integration

**In-Process MCP 서버 생성**:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("calculate", "Calculate expression", {"expr": str})
async def calculate(args):
    try:
        result = eval(args["expr"])  # 실제로는 안전한 파서 사용
        return {
            "content": [{"type": "text", "text": str(result)}]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}],
            "is_error": True
        }

# MCP 서버 생성
server = create_sdk_mcp_server(
    name="calculator",
    version="1.0.0",
    tools=[calculate]
)

# SDK에 등록
options = ClaudeAgentOptions(
    mcp_sdk_servers={"calculator": server}
)
```

**동작 원리**:
1. `@tool` 데코레이터가 `SdkMcpTool` 객체 생성
2. `create_sdk_mcp_server()`가 MCP Server 인스턴스 생성
3. SDK가 `initialize` 프로토콜로 CLI에 등록 정보 전송
4. CLI가 도구 호출 시 SDK로 JSONRPC 메시지 전송
5. SDK가 도구 핸들러 실행 후 결과 반환

**장점**:
- **No subprocess**: 서브프로세스 오버헤드 없음
- **Better performance**: In-process 호출
- **Simple deployment**: 단일 프로세스
- **Python native**: Python 함수를 직접 도구로 사용

### 6.2 Hook System

**6가지 Hook 이벤트**:

```python
options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [                # 도구 실행 전
            HookMatcher(
                matcher="Bash",         # 정규식 또는 도구 이름
                hooks=[validate_bash],
                timeout_ms=5000
            )
        ],
        "PostToolUse": [               # 도구 실행 후
            HookMatcher(
                matcher=".*",           # 모든 도구
                hooks=[log_tool_result]
            )
        ],
        "UserPromptSubmit": [          # 사용자 입력 전
            HookMatcher(hooks=[filter_input])
        ],
        "PreCompact": [                # 메시지 압축 전
            HookMatcher(hooks=[save_history])
        ],
        "Stop": [                      # 대화 종료 시
            HookMatcher(hooks=[cleanup])
        ],
        "SubagentStop": [              # Subagent 종료 시
            HookMatcher(hooks=[log_subagent])
        ],
    }
)
```

**Hook Matcher 패턴**:
- `matcher=None`: 모든 도구
- `matcher="Bash"`: 정확히 "Bash"만
- `matcher="^Web.*"`: 정규식 (WebSearch, WebFetch 등)

**Hook Output 형식**:
```python
async def my_hook(input_data, tool_use_id, context):
    # Decision 1: Block
    return {
        "decision": "block",
        "systemMessage": "Dangerous command blocked",
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Contains rm -rf"
        }
    }

    # Decision 2: Ask
    return {
        "decision": "ask",
        "systemMessage": "Do you want to run this?",
    }

    # Decision 3: Allow (default)
    return {}

    # Decision 4: Modify Input
    return {
        "updatedInput": {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"}  # 수정된 입력
        }
    }

    # Decision 5: Async (나중에 처리)
    return {
        "async": True,  # CLI는 Hook 결과 대기하지 않고 계속
    }
```

### 6.3 Agent Definition System

**Agent를 코드로 정의**:

```python
from claude_agent_sdk import AgentDefinition

explore_agent = AgentDefinition(
    name="explore",
    system_prompt="You are a codebase exploration expert...",
    tools=["Glob", "Grep", "Read"],  # 사용 가능한 도구
)

plan_agent = AgentDefinition(
    name="plan",
    system_prompt="You are a planning expert...",
    tools=["Read", "ExitPlanMode"],
)

options = ClaudeAgentOptions(
    agents=[explore_agent, plan_agent]
)
```

**장점**:
- 파일시스템 의존성 제거
- 런타임 Agent 생성 가능
- 프로그래밍 방식 제어

### 6.4 Permission System

**3가지 Permission Mode**:

```python
# Mode 1: Always allow
options = ClaudeAgentOptions(permission_mode="allow")

# Mode 2: Always ask
options = ClaudeAgentOptions(permission_mode="ask")

# Mode 3: Custom callback
async def can_use_tool(tool_name, tool_input, context):
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if "rm -rf" in command:
            return {"behavior": "deny", "message": "Dangerous command"}
        elif "git push" in command:
            return {"behavior": "ask", "message": "Confirm push?"}

    return {"behavior": "allow"}

options = ClaudeAgentOptions(
    permission_mode="ask",  # Default
    can_use_tool=can_use_tool
)
```

**Permission Update (런타임 변경)**:

```python
# 특정 도구 자동 허용
await client.update_permission({
    "type": "add_auto_accept_for_tool_name",
    "tool_name": "Read"
})

# 디렉토리 제한
await client.update_permission({
    "type": "add_allowed_directory",
    "directory": "/safe/path"
})

# 모드 변경
await client.set_permission_mode("allow")
```

---

## 7. 에러 처리 철학

### 7.1 Exception Hierarchy

```python
ClaudeSDKError                          # 최상위
├─ CLIConnectionError                   # 연결 실패
│  └─ CLINotFoundError                  # CLI 바이너리 없음
├─ ProcessError                         # 프로세스 실행 실패
│  (exit_code, stderr 포함)
├─ CLIJSONDecodeError                   # JSON 파싱 실패
│  (line, original_error 포함)
└─ MessageParseError                    # 메시지 파싱 실패
   (parsed_data 포함)
```

### 7.2 Rich Error Context

**ProcessError 예시**:
```python
class ProcessError(ClaudeSDKError):
    def __init__(self, exit_code: int, stderr: str):
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"Process exited with code {exit_code}: {stderr}")

# 사용
try:
    await client.connect()
except ProcessError as e:
    print(f"Exit code: {e.exit_code}")
    print(f"Stderr: {e.stderr}")
```

**CLIJSONDecodeError 예시**:
```python
class CLIJSONDecodeError(ClaudeSDKError):
    def __init__(self, line: str, original_error: Exception):
        self.line = line
        self.original_error = original_error
        super().__init__(f"Failed to decode JSON: {line[:100]}...")

# 사용
try:
    msg = json.loads(line)
except json.JSONDecodeError as e:
    raise CLIJSONDecodeError(line, e)
```

### 7.3 Graceful Degradation

**버퍼 크기 제한**:
```python
class SubprocessCLITransport:
    def __init__(self):
        self._max_buffer_size = 1_000_000  # 1MB
        self.json_buffer = []

    async def receive(self):
        async for line in self._stdout_stream:
            self.json_buffer.append(line)

            # 버퍼 크기 체크
            total_size = sum(len(s) for s in self.json_buffer)
            if total_size > self._max_buffer_size:
                # 오래된 메시지 제거
                self.json_buffer = self.json_buffer[-100:]
```

**Timeout 관리**:
```python
async def send_control_request(self, control_data):
    request_id = f"req_{self.counter}_{random_id()}"
    await self._send({"type": "control_request", ...})

    # 60초 타임아웃
    for _ in range(600):
        if request_id in self.pending_control_results:
            return self.pending_control_results.pop(request_id)
        await anyio.sleep(0.1)

    raise TimeoutError(f"Control request {request_id} timed out")
```

**Cleanup 시 Exception 억제**:
```python
async def close(self):
    try:
        if self._stdin_stream:
            await self._stdin_stream.aclose()
    except Exception:
        pass  # Suppress cleanup exceptions

    try:
        if self._process:
            self._process.terminate()
    except Exception:
        pass
```

---

## 8. 성능 최적화

### 8.1 Buffered JSON Parsing

**문제**: TextReceiveStream이 긴 줄을 잘라낼 수 있음

**해결**:
```python
class SubprocessCLITransport:
    def __init__(self):
        self.json_buffer = []

    async def receive(self):
        async for line in self._stdout_stream:
            self.json_buffer.append(line)

            # 완전한 JSON 객체 파싱 시도
            combined = "".join(self.json_buffer)
            try:
                obj = json.loads(combined)
                self.json_buffer.clear()
                yield obj
            except json.JSONDecodeError:
                # 아직 불완전 - 계속 버퍼링
                continue
```

### 8.2 Platform-Specific Optimizations

**Windows 명령줄 길이 제한 처리**:
```python
def _get_process_args(self):
    args = ["claude-code", "--json"]

    # Agents 설정이 긴 경우
    agents_json = json.dumps(self.options.agents)

    # Windows: 8000자 제한
    if sys.platform == "win32" and len(agents_json) > 8000:
        # 임시 파일로 우회
        temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
        temp_file.write(agents_json)
        temp_file.close()
        args.extend(["--agents-file", temp_file.name])
    else:
        args.extend(["--agents", agents_json])

    return args
```

### 8.3 Stream Multiplexing

**단일 스트림에서 다중 메시지 타입 처리**:
```python
async def _read_messages(self):
    async for line in self._transport.receive():
        msg = json.loads(line)

        # Fast path: 타입별 라우팅
        msg_type = msg["type"]

        if msg_type == "control_response":
            # Pending queue에 직접 저장 (async 불필요)
            self.pending_control_results[msg["request_id"]] = msg["response"]

        elif msg_type == "control_request":
            # Control handler로 라우팅 (async 필요)
            await self._handle_control_request(msg)

        else:
            # Message stream으로 라우팅 (async 필요)
            await self._message_receive.send(msg)
```

### 8.4 Lazy Initialization

**필요할 때만 생성**:
```python
class ClaudeSDKClient:
    def __init__(self, options):
        self.options = options
        self._transport = None      # 아직 생성 안 함
        self._query = None           # 아직 생성 안 함

    async def connect(self):
        # 연결 시점에 생성
        self._transport = SubprocessCLITransport(self.options)
        await self._transport.connect()

        self._query = Query(self._transport, self.options)
        await self._query.initialize()
```

---

## 9. 진화 과정 및 교훈

### 9.1 v0.0.x → v0.1.0: 명시성으로의 전환

**Before**:
```python
# 암묵적 로딩
client = ClaudeCodeSDKClient()
# → ~/.claude/settings.json 자동 로드
# → .claude/commands/ 자동 로드
# → preset="claude_code" 자동 적용
```

**After**:
```python
# 명시적 설정
options = ClaudeAgentOptions(
    setting_sources=["user", "project"],  # 명시
    plugins=[...],                         # 명시
)
client = ClaudeSDKClient(options)
```

**교훈**: "Convention over Configuration"은 예측 불가능성을 초래할 수 있음. 명시적 설정이 더 안전.

### 9.2 v0.1.1: 비용 관리의 중요성

**추가된 기능**:
```python
options = ClaudeAgentOptions(
    max_budget_usd=10.0  # 비용 상한 설정
)
```

**교훈**: AI 에이전트는 비용 폭발 위험이 있음. 안전장치 필수.

### 9.3 v0.1.3: Python Idioms vs CLI Contracts

**문제**: CLI는 `{"async": true}`를 기대하지만 Python에서 `async`는 예약어

**해결**:
```python
# Python 코드
return {"async_": True}  # Python-friendly

# SDK 내부에서 자동 변환
def to_dict(obj):
    result = {}
    for key, value in obj.items():
        # async_ → async
        cli_key = key.rstrip("_") if key.endswith("_") else key
        result[cli_key] = value
    return result
```

**교훈**: 언어별 제약사항을 SDK 계층에서 흡수해야 함.

### 9.4 v0.1.5: Filesystem vs Programmatic Configuration

**Before**: 플러그인을 `~/.claude/plugins/` 디렉토리에서 자동 로드

**After**: 프로그래밍 방식으로 플러그인 등록
```python
options = ClaudeAgentOptions(
    plugins=[
        SdkPluginConfig(
            name="my-plugin",
            mcp_server=server
        )
    ]
)
```

**교훈**: 파일시스템 의존성은 테스트와 배포를 어렵게 함. 프로그래밍 방식이 더 유연.

### 9.5 v0.1.7: Reliability through Fallback

**추가된 기능**: 자동 fallback 모델 처리

**교훈**: AI 서비스는 불안정할 수 있음. Fallback 메커니즘 필수.

---

## 10. v2.2 적용 가이드

### 10.1 우리가 배운 핵심 원칙

**원칙 1: Explicitness over Magic**
- ❌ 자동으로 설정 파일 로드
- ✅ 명시적으로 `SettingsLoader(sources=["project"])` 호출

**원칙 2: Discriminated Unions for Type Safety**
- ✅ `HookEvent = Literal["PreToolUse", "PostToolUse", ...]` 사용
- ✅ 모든 Hook Input에 `hookEventName` discriminator 추가
- ✅ mypy strict mode 활성화

**원칙 3: Async-First**
- ✅ 모든 Hook callback은 `async def`
- ✅ 모든 I/O (파일, LLM 호출)는 비동기

**원칙 4: Request-Response Protocol**
- ✅ Control protocol 구현 (request_id 매칭)
- ✅ Timeout 관리 (60초 기본값)

**원칙 5: Composition over Inheritance**
- ✅ `HookSystem`에 Hook을 등록하는 방식
- ❌ Hook을 상속받아 구현하는 방식

### 10.2 v2.2 코드 개선 제안

#### 개선 1: HookInput에 Discriminator 추가

**현재**:
```python
# v2.2 hooks.py
async def trigger(self, event: HookEvent, input_data: dict[str, Any], ...):
    ...
```

**개선안**:
```python
# Discriminated Union으로 타입 안전성 강화
PreToolUseHookInput = TypedDict(
    "PreToolUseHookInput",
    {
        "hookEventName": Literal["PreToolUse"],
        "tool_name": str,
        "tool_input": dict[str, Any],
    }
)

PostToolUseHookInput = TypedDict(
    "PostToolUseHookInput",
    {
        "hookEventName": Literal["PostToolUse"],
        "tool_name": str,
        "tool_input": dict[str, Any],
        "tool_result": dict[str, Any],
    }
)

HookInput = PreToolUseHookInput | PostToolUseHookInput | ...

async def trigger(
    self,
    event: HookEvent,
    input_data: HookInput,  # 타입 안전성 강화
    tool_use_id: str | None,
    context: HookContext
) -> dict[str, Any]:
    ...
```

#### 개선 2: HookOutput에 Discriminated Union 적용

**현재**:
```python
# 반환값이 dict[str, Any]로 자유로움
return {
    "decision": "block",
    "systemMessage": "Blocked",
    "hookSpecificOutput": {...}
}
```

**개선안**:
```python
# Discriminated Union으로 명확한 결과 타입
HookOutputBlock = TypedDict(
    "HookOutputBlock",
    {
        "decision": Literal["block"],
        "systemMessage": str,
        "hookSpecificOutput": NotRequired[dict[str, Any]],
    }
)

HookOutputAsk = TypedDict(
    "HookOutputAsk",
    {
        "decision": Literal["ask"],
        "systemMessage": str,
    }
)

HookOutputAllow = TypedDict(
    "HookOutputAllow",
    {
        "decision": NotRequired[Literal["allow"]],
        "updatedInput": NotRequired[dict[str, Any]],
    }
)

HookOutput = HookOutputBlock | HookOutputAsk | HookOutputAllow

HookCallback = Callable[
    [HookInput, str | None, HookContext],
    Awaitable[HookOutput]  # 타입 안전성 강화
]
```

#### 개선 3: Permission System을 Hook으로 통합

**현재**: `permission.py`가 별도로 존재

**개선안**: Permission을 PreToolUse Hook의 특수 케이스로 처리
```python
# permission.py를 hooks.py와 통합
def create_permission_hook(can_use_tool_callback: CanUseTool) -> HookCallback:
    """
    can_use_tool 콜백을 PreToolUse Hook으로 변환

    이는 Claude SDK의 패턴을 따름:
    - can_use_tool = PreToolUse Hook의 고수준 API
    - 내부적으로는 동일한 Hook System 사용
    """
    async def hook_wrapper(
        input_data: PreToolUseHookInput,
        tool_use_id: str | None,
        context: HookContext
    ) -> HookOutput:
        tool_name = input_data["tool_name"]
        tool_input = input_data["tool_input"]

        # can_use_tool 콜백 실행
        result = await can_use_tool_callback(tool_name, tool_input, context)

        # PermissionResult → HookOutput 변환
        if result["behavior"] == "deny":
            return {
                "decision": "block",
                "systemMessage": result.get("message", "Permission denied")
            }
        elif result["behavior"] == "ask":
            return {
                "decision": "ask",
                "systemMessage": result.get("message", "Approval required")
            }
        else:  # allow
            hook_result: HookOutput = {}
            if "updated_input" in result:
                hook_result["updatedInput"] = result["updated_input"]
            return hook_result

    return hook_wrapper
```

#### 개선 4: Settings Loader를 Hook System과 통합

**현재**: `settings.py`가 별도로 존재

**개선안**: CLAUDE.md 로딩을 초기화 시점에 처리
```python
# main.py 또는 graph.py에서
def create_agent_graph(cwd: Path | None = None):
    # CLAUDE.md 로드
    loader = SettingsLoader(cwd=cwd)
    settings_data = loader.load_settings(sources=["project"])
    claude_md = settings_data.get("claude_md")

    # System prompt에 주입
    system_prompt = get_system_prompt()
    if claude_md:
        system_prompt += inject_claude_md_context(claude_md, cwd or Path.cwd())

    # Graph 생성
    graph = StateGraph(...)
    ...
```

#### 개선 5: Validation Agent를 Stateless로 유지

**현재**: 올바르게 구현됨 ✅
```python
async def call_validation_agent(command: str) -> str:
    """별도 LLM 호출 - Stateless"""
    llm = get_chat_model()
    messages = [
        SystemMessage(content=VALIDATION_POLICY),
        HumanMessage(content=f"Command: {command}")
    ]
    response = await llm.ainvoke(messages)
    return response.content.strip()
```

**Claude SDK 패턴과 일치**: Validation은 대화 상태가 없는 독립 LLM 호출

#### 개선 6: mypy Strict Mode 활성화

**추가**: `pyproject.toml`에 strict typing 설정
```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true        # 모든 함수에 타입 힌트 필수
disallow_untyped_decorators = true  # 데코레이터에도 타입 힌트
strict = true
```

### 10.3 적용 우선순위

**Priority 1 (High Impact, Low Effort)**:
1. ✅ HookInput에 `hookEventName` discriminator 추가
2. ✅ HookOutput에 Discriminated Union 적용
3. ✅ mypy strict mode 활성화

**Priority 2 (High Impact, Medium Effort)**:
4. ✅ Permission System을 Hook으로 통합
5. ✅ Settings Loader를 초기화 시점으로 이동

**Priority 3 (Nice to Have)**:
6. ⚠️ Request-Response Protocol 구현 (현재는 불필요 - LangGraph 내부에서 자동 처리)
7. ⚠️ Transport Abstraction (현재는 불필요 - subprocess 없음)

---

## 11. 결론

### 11.1 핵심 교훈

Claude Agent SDK의 설계에서 배운 가장 중요한 교훈들:

1. **명시성이 편의성을 이긴다**
   - 자동화된 기본값은 예측 불가능성을 초래
   - 명시적 설정이 더 안전하고 디버깅 용이

2. **타입 시스템을 최대한 활용하라**
   - Discriminated Union은 런타임 에러를 컴파일 타임으로 이동
   - mypy strict mode는 투자 대비 효과가 큼

3. **비동기가 기본이어야 한다**
   - AI 에이전트는 I/O bound 작업이 많음
   - async/await로 성능과 동시성 확보

4. **Hook은 확장의 핵심**
   - 코드 수정 없이 동작 변경 가능
   - 보안, 로깅, 검증 등 횡단 관심사 처리

5. **In-Process가 Subprocess보다 낫다**
   - 성능 향상 (IPC 오버헤드 제거)
   - 배포 단순화 (단일 프로세스)
   - 디버깅 용이 (단일 프로세스)

6. **에러는 Rich Context를 가져야 한다**
   - Exception에 관련 데이터 포함
   - 디버깅 시간 단축

7. **조합이 상속을 이긴다**
   - Configuration as Data
   - 런타임 변경 가능
   - 테스트 용이

### 11.2 v2.2 적용 로드맵

**Phase 1: 타입 안전성 강화** (1-2시간)
- [ ] HookInput에 Discriminated Union 적용
- [ ] HookOutput에 Discriminated Union 적용
- [ ] mypy strict mode 활성화 및 에러 수정

**Phase 2: 아키텍처 정리** (2-3시간)
- [ ] Permission System을 Hook으로 통합
- [ ] Settings Loader를 초기화 시점으로 이동
- [ ] 불필요한 추상화 제거

**Phase 3: 문서화** (1시간)
- [ ] 타입 시스템 문서화
- [ ] Hook 사용 예제 추가
- [ ] 디자인 결정 문서화

### 11.3 최종 권장사항

**DO**:
- ✅ Discriminated Union 사용
- ✅ async/await 사용
- ✅ 명시적 설정
- ✅ Rich error context
- ✅ Composition over inheritance
- ✅ In-process integration

**DON'T**:
- ❌ 암묵적 기본값
- ❌ Untyped dict[str, Any] (가능하면 TypedDict)
- ❌ 동기 I/O
- ❌ 상속 기반 확장
- ❌ Silent failures

---

**작성자**: Claude (Sonnet 4.5)
**분석 대상**: https://github.com/anthropics/claude-agent-sdk-python
**분석 일자**: 2025-11-20
**문서 버전**: 1.0
